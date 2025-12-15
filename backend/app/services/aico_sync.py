from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import select

from ..core.db import TargetSessionLocal
from ..core.logging import get_logger
from ..core.settings import get_settings
from ..models.faq_review import KnowledgeItem
from ..models.scenario import Scenario


logger = get_logger(__name__)
settings = get_settings()


class AicoSyncError(Exception):
    pass


@dataclass
class SyncRunResult:
    scenario_id: int
    items: int
    status: str
    message: str


class AicoSyncOrchestrator:
    def __init__(self) -> None:
        self.aico_settings = settings.aico

    def run_for_scenario(self, scenario_id: int) -> SyncRunResult:
        with TargetSessionLocal() as session:
            scenario = session.get(Scenario, scenario_id)
            if scenario is None:
                raise AicoSyncError(f"Scenario {scenario_id} not found")
            if not scenario.is_active:
                raise AicoSyncError(f"Scenario {scenario_id} is inactive")

            items = (
                session.execute(
                    select(KnowledgeItem).where(
                        KnowledgeItem.scenario_id == scenario_id,
                        KnowledgeItem.status == "active",
                    )
                )
                .scalars()
                .all()
            )

        if not items:
            return SyncRunResult(
                scenario_id=scenario_id,
                items=0,
                status="skipped",
                message="No active knowledge items to sync.",
            )

        token, scenario = self._ensure_token_and_cache(scenario)
        pid, scenario = self._ensure_pid_and_cache(scenario, token)
        kb_id, scenario = self._ensure_kb_id_and_cache(scenario, token, pid)

        file_name, file_bytes = self._build_csv_file(scenario, items)

        file_id = self._upload_file(token, pid, kb_id, file_name, file_bytes)
        self._trigger_split(token, pid, kb_id, file_id)
        self._wait_for_split_complete(token, pid, kb_id, file_name)
        self._online_all(token, pid, kb_id)

        return SyncRunResult(
            scenario_id=scenario_id,
            items=len(items),
            status="success",
            message=f"Synced {len(items)} knowledge items to AICO.",
        )

    def _build_csv_file(self, scenario: Scenario, items: list[KnowledgeItem]) -> tuple[str, bytes]:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_name = f"{scenario.scenario_code}_knowledge_{timestamp}.csv"

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["question", "answer"])
        for item in items:
            writer.writerow([item.question or "", item.answer or ""])

        content = buffer.getvalue().encode("utf-8")
        return file_name, content

    def _build_client(self) -> httpx.Client:
        timeout = httpx.Timeout(self.aico_settings.timeout_seconds)
        # trust_env=False 避免受本机 HTTP(S)_PROXY / ALL_PROXY 等环境变量影响，
        # 从而不再要求 socksio 依赖。
        return httpx.Client(timeout=timeout, trust_env=False)

    def _ensure_token_and_cache(self, scenario: Scenario) -> tuple[str, Scenario]:
        # 使用“无时区”的 UTC 时间，避免和数据库取出的 naive datetime 相减时报错
        now = datetime.utcnow()
        if scenario.aico_cached_token and scenario.aico_token_expires_at:
            expires_at = scenario.aico_token_expires_at
            if expires_at.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=None)
            # 留一点缓冲时间，避免刚好过期
            if expires_at - now > timedelta(minutes=5):
                return scenario.aico_cached_token, scenario

        url = f"http://{self.aico_settings.host}:{self.aico_settings.user_port}/aicoapi/user/generate_user_token"
        payload = {"username": scenario.aico_username, "user_id": scenario.aico_user_id}

        with self._build_client() as client, TargetSessionLocal() as session:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("code") != 200 or "data" not in data or "token" not in data["data"]:
                raise AicoSyncError(f"Unexpected token response: {data}")

            token = data["data"]["token"]
            # token 有效期在 payload 的 exp 里，这里简单假设 2 小时有效
            expires_at = now + timedelta(hours=2)

            db_scenario = session.get(Scenario, scenario.id)
            if db_scenario is not None:
                db_scenario.aico_cached_token = token
                db_scenario.aico_token_expires_at = expires_at
                session.commit()
                session.refresh(db_scenario)
                scenario = db_scenario

        return token, scenario

    def _ensure_pid_and_cache(self, scenario: Scenario, token: str) -> tuple[int, Scenario]:
        if scenario.aico_cached_pid:
            return scenario.aico_cached_pid, scenario

        url = (
            f"http://{self.aico_settings.host}:{self.aico_settings.project_port}"
            "/api/project_manage/projects/search_project"
        )
        params = {"project_name": scenario.aico_project_name}
        headers = {"Authorization": f"Bearer {token}"}

        with self._build_client() as client, TargetSessionLocal() as session:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            projects = data.get("data") or []
            if not projects:
                raise AicoSyncError(f"No project found for name {scenario.aico_project_name}")
            pid = int(projects[0]["id"])

            db_scenario = session.get(Scenario, scenario.id)
            if db_scenario is not None:
                db_scenario.aico_cached_pid = pid
                session.commit()
                session.refresh(db_scenario)
                scenario = db_scenario

        return pid, scenario

    def _ensure_kb_id_and_cache(self, scenario: Scenario, token: str, pid: int) -> tuple[int, Scenario]:
        if scenario.aico_cached_kb_id:
            return scenario.aico_cached_kb_id, scenario

        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}/aicoapi/kb_manage/kbm/search_kb"
        params = {"pid": pid, "view_type": "personal", "kb_name": scenario.aico_kb_name}
        headers = {"Authorization": f"Bearer {token}"}

        with self._build_client() as client, TargetSessionLocal() as session:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            kbs = data.get("data") or []
            if not kbs:
                raise AicoSyncError(f"No knowledge base found for name {scenario.aico_kb_name}")
            kb_id = int(kbs[0]["id"])

            db_scenario = session.get(Scenario, scenario.id)
            if db_scenario is not None:
                db_scenario.aico_cached_kb_id = kb_id
                session.commit()
                session.refresh(db_scenario)
                scenario = db_scenario

        return kb_id, scenario

    def _upload_file(self, token: str, pid: int, kb_id: int, file_name: str, content: bytes) -> int:
        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}/aicoapi/knowledge_manage/file/upload"
        headers = {"Authorization": f"Bearer {token}"}
        files = {
            "files": (file_name, content, "text/csv"),
        }
        data = {
            "pid": str(pid),
            "kb_id": str(kb_id),
            "source": "2",  # 接口
            "oper": "1",  # 覆盖
            # AICO 新版本要求的标记字段，表示由自动化任务上传
            "is_auto": "1",
        }

        with self._build_client() as client:
            response = client.post(url, data=data, files=files, headers=headers)
            response.raise_for_status()
            payload = response.json()
            if payload.get("err_code") not in (0, None):
                raise AicoSyncError(f"Upload failed: {payload}")

        file_id = self._wait_for_file_appearance(token, pid, kb_id, file_name)
        return file_id

    def _wait_for_file_appearance(self, token: str, pid: int, kb_id: int, title: str) -> int:
        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}/aicoapi/knowledge_manage/file/show"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "title": title,
            "pid": pid,
            "kb_id": str(kb_id),
            "view_type": "personal",
            "type": "1",
        }

        with self._build_client() as client:
            for _ in range(30):
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                files = data.get("data") or []
                if files:
                    return int(files[0]["id"])
                time.sleep(2)

        raise AicoSyncError("Uploaded file did not appear in file list within timeout.")

    def _trigger_split(self, token: str, pid: int, kb_id: int, file_id: int) -> None:
        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}/aicoapi/knowledge_manage/file/split"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        payload = {
            "user_id": 0,
            "pid": pid,
            "file_ids": [file_id],
            "kb_id": str(kb_id),
            "keep_img": True,
            "type": 1,
            "length": 512,
            "overlap": 100,
        }

        with self._build_client() as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()

    def _wait_for_split_complete(self, token: str, pid: int, kb_id: int, title: str) -> None:
        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}/aicoapi/knowledge_manage/file/show"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "title": title,
            "pid": pid,
            "kb_id": str(kb_id),
            "view_type": "personal",
            "type": "1",
        }

        with self._build_client() as client:
            for _ in range(60):
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                files = data.get("data") or []
                if not files:
                    time.sleep(2)
                    continue
                is_slice = files[0].get("is_slice")
                if is_slice == 3:
                    return
                if is_slice == 4:
                    raise AicoSyncError("File split failed in AICO.")
                time.sleep(2)

        raise AicoSyncError("File split did not complete within timeout.")

    def _online_all(self, token: str, pid: int, kb_id: int) -> None:
        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}/aicoapi/knowledge_manage/knowledge/online"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"kb_id": str(kb_id), "pid": pid, "id_list": []}

        with self._build_client() as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get("err_code") not in (0, None):
                raise AicoSyncError(f"Online operation failed: {data}")
