from __future__ import annotations

import csv
import io
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

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

    def _cache_enabled_for_host(self, scenario: Scenario) -> bool:
        scenario_host = str(getattr(scenario, "aico_host", "") or "").strip()
        current_host = str(self.aico_settings.host or "").strip()
        return bool(scenario_host) and scenario_host == current_host

    @property
    def _file_type(self) -> int:
        # 与 upload 的 split_config.type 对齐（研发提供的示例为 3: 按行）
        return 3

    def run_for_scenario(self, scenario_id: int, run_id: str) -> SyncRunResult:
        started_at = time.monotonic()
        logger.info("[run_id=%s] Sync start (scenario_id=%s)", run_id, scenario_id)
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

            aico_scenario = self._select_aico_scenario(session, scenario)

            # detach from session to avoid accidental lazy-load after close
            session.expunge(scenario)
            if aico_scenario is not scenario:
                session.expunge(aico_scenario)
            for item in items:
                session.expunge(item)

        result = self.run_for_items(
            scenario=scenario,
            aico_scenario=aico_scenario,
            items=items,
            run_id=run_id,
            allow_empty=False,
            source_label="knowledge items",
            skip_message="No active knowledge items to sync.",
        )
        return result

    def run_for_items(
        self,
        *,
        scenario: Scenario,
        aico_scenario: Scenario,
        items: list[object],
        run_id: str,
        allow_empty: bool,
        source_label: str,
        skip_message: str,
    ) -> SyncRunResult:
        started_at = time.monotonic()
        if not items and not allow_empty:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.info("[run_id=%s] Sync skipped: no items (%dms)", run_id, elapsed_ms)
            return SyncRunResult(
                scenario_id=scenario.id,
                items=0,
                status="skipped",
                message=skip_message,
            )

        logger.info(
            "[run_id=%s] Loaded %d %s (scenario_code=%s)",
            run_id,
            len(items),
            source_label,
            scenario.scenario_code,
        )
        if aico_scenario.id != scenario.id:
            logger.info(
                "[run_id=%s] Using AICO config from scenario_id=%s (scenario_code=%s aico_host=%s)",
                run_id,
                aico_scenario.id,
                aico_scenario.scenario_code,
                getattr(aico_scenario, "aico_host", None),
            )
        else:
            logger.info(
                "[run_id=%s] Using AICO config from current scenario_id=%s (scenario_code=%s)",
                run_id,
                scenario.id,
                scenario.scenario_code,
            )

        token, aico_scenario = self._ensure_token_and_cache(aico_scenario, run_id)
        pid, aico_scenario = self._ensure_pid_and_cache(aico_scenario, token, run_id)
        kb_id, aico_scenario = self._ensure_kb_id_and_cache(aico_scenario, token, pid, run_id)
        logger.info("[run_id=%s] Resolved AICO context: pid=%s kb_id=%s", run_id, pid, kb_id)

        # V1.11: 上传前先清理旧文件（先删后增）
        step_started = time.monotonic()
        logger.info("[run_id=%s] Step: cleanup old files ...", run_id)
        self._cleanup_old_files(token, pid, kb_id, scenario.scenario_code, aico_scenario.aico_user_id, run_id)
        logger.info(
            "[run_id=%s] Step: cleanup old files done (%dms)",
            run_id,
            int((time.monotonic() - step_started) * 1000),
        )

        if not items:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.info(
                "[run_id=%s] Sync complete: no items to upload (%dms)",
                run_id,
                elapsed_ms,
            )
            return SyncRunResult(
                scenario_id=scenario.id,
                items=0,
                status="success",
                message=f"{skip_message} Cleared previous sync files.",
            )

        file_name, file_bytes = self._build_csv_file(scenario, items)
        logger.info("[run_id=%s] Built CSV: %s (%d bytes)", run_id, file_name, len(file_bytes))

        step_started = time.monotonic()
        logger.info("[run_id=%s] Step: upload file ...", run_id)
        _file_id = self._upload_file(token, pid, kb_id, file_name, file_bytes, run_id)
        logger.info(
            "[run_id=%s] Step: upload file done (file_id=%s, %dms)",
            run_id,
            _file_id,
            int((time.monotonic() - step_started) * 1000),
        )

        step_started = time.monotonic()
        logger.info("[run_id=%s] Step: wait split complete ...", run_id)
        self._wait_for_split_complete(token, pid, kb_id, file_name, run_id)
        logger.info(
            "[run_id=%s] Step: wait split complete done (%dms)",
            run_id,
            int((time.monotonic() - step_started) * 1000),
        )

        step_started = time.monotonic()
        logger.info("[run_id=%s] Step: online all ...", run_id)
        self._online_all(token, pid, kb_id, run_id)
        logger.info(
            "[run_id=%s] Step: online all done (%dms)",
            run_id,
            int((time.monotonic() - step_started) * 1000),
        )

        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        logger.info("[run_id=%s] Sync success (%d items, %dms)", run_id, len(items), elapsed_ms)
        return SyncRunResult(
            scenario_id=scenario.id,
            items=len(items),
            status="success",
            message=f"Synced {len(items)} items to AICO.",
        )

    def _select_aico_scenario(self, session: Session, scenario: Scenario) -> Scenario:
        # Keep knowledge items bound to the user's scenario_id, but allow AICO config
        # switching based on current AICO_HOST. Since scenario_code is unique, the common
        # pattern is to store test configs as "<scenario_code>_test" rows.
        aico_scenario = scenario
        current_host = str(self.aico_settings.host or "").strip()
        host_test = str(os.getenv("AICO_HOST_TEST", "") or "").strip()
        host_prod = str(os.getenv("AICO_HOST_PROD", "") or "").strip()
        test_suffix = str(os.getenv("AICO_TEST_SCENARIO_SUFFIX", "_test") or "_test").strip() or "_test"

        base_code = scenario.scenario_code
        root_code = base_code[:-len(test_suffix)] if base_code.endswith(test_suffix) else base_code

        preferred_codes: list[str]
        if host_test and current_host == host_test:
            preferred_codes = [f"{root_code}{test_suffix}", root_code]
        elif host_prod and current_host == host_prod:
            preferred_codes = [root_code, f"{root_code}{test_suffix}"]
        else:
            preferred_codes = [base_code, f"{root_code}{test_suffix}", root_code]

        candidates = (
            session.execute(
                select(Scenario).where(
                    Scenario.scenario_code.in_(preferred_codes),
                    Scenario.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )
        if candidates:
            by_code_rank = {code: i for i, code in enumerate(preferred_codes)}

            def _rank(s: Scenario) -> int:
                return by_code_rank.get(s.scenario_code, 9999)

            # Prefer exact host binding when present.
            host_matched = [
                s for s in candidates if str(getattr(s, "aico_host", "") or "").strip() == current_host
            ]
            picked = min(host_matched, key=_rank) if host_matched else min(candidates, key=_rank)
            aico_scenario = picked

        return aico_scenario

    @staticmethod
    def _build_split_config(pid: int, kb_id: int) -> str:
        """
        AICO 新版 upload 接口支持在上传时携带切分配置：
        - seprate=1
        - split_config=<json string>
        该配置字段名为 `split_config`（字符串），内容为 JSON。
        """
        payload = {
            "pid": pid,
            "kb_id": str(kb_id),
            "keep_img": False,
            "type": 3,
            "user_id": 999,
            "user_uuid": "",
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _build_csv_file(self, scenario: Scenario, items: list[object]) -> tuple[str, bytes]:
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

    def _ensure_token_and_cache(self, scenario: Scenario, run_id: str) -> tuple[str, Scenario]:
        # 使用“无时区”的 UTC 时间，避免和数据库取出的 naive datetime 相减时报错
        now = datetime.utcnow()
        cache_enabled = self._cache_enabled_for_host(scenario)
        if cache_enabled and scenario.aico_cached_token and scenario.aico_token_expires_at:
            expires_at = scenario.aico_token_expires_at
            if expires_at.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=None)
            # 留一点缓冲时间，避免刚好过期
            if expires_at - now > timedelta(minutes=5):
                return scenario.aico_cached_token, scenario

        url = f"http://{self.aico_settings.host}:{self.aico_settings.user_port}/aicoapi/user/generate_user_token"
        payload = {"username": scenario.aico_username, "user_id": scenario.aico_user_id}

        with self._build_client() as client:
            logger.info(
                "[run_id=%s] Step: generate token (host=%s port=%s timeout=%ss)",
                run_id,
                self.aico_settings.host,
                self.aico_settings.user_port,
                self.aico_settings.timeout_seconds,
            )
            try:
                response = client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                raise AicoSyncError(
                    f"Connect to AICO token endpoint timed out (host={self.aico_settings.host} port={self.aico_settings.user_port})."
                ) from exc
            response.raise_for_status()
            data = response.json()
            if data.get("code") != 200 or "data" not in data or "token" not in data["data"]:
                raise AicoSyncError(f"Unexpected token response: {data}")

            token = data["data"]["token"]
            # token 有效期在 payload 的 exp 里，这里简单假设 2 小时有效
            expires_at = now + timedelta(hours=2)

        if cache_enabled:
            with TargetSessionLocal() as session:
                db_scenario = session.get(Scenario, scenario.id)
                if db_scenario is not None:
                    db_scenario.aico_cached_token = token
                    db_scenario.aico_token_expires_at = expires_at
                    session.commit()
                    session.refresh(db_scenario)
                    scenario = db_scenario

        return token, scenario

    def _ensure_pid_and_cache(self, scenario: Scenario, token: str, run_id: str) -> tuple[int, Scenario]:
        cache_enabled = self._cache_enabled_for_host(scenario)
        if cache_enabled and scenario.aico_cached_pid:
            return scenario.aico_cached_pid, scenario

        url = (
            f"http://{self.aico_settings.host}:{self.aico_settings.project_port}"
            "/api/project_manage/projects/search_project"
        )
        params = {"project_name": scenario.aico_project_name}
        headers = {"Authorization": f"Bearer {token}"}

        with self._build_client() as client:
            logger.info("[run_id=%s] Step: resolve pid (project_name=%s)", run_id, scenario.aico_project_name)
            try:
                response = client.get(url, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                raise AicoSyncError(
                    f"Connect to AICO project endpoint timed out (host={self.aico_settings.host} port={self.aico_settings.project_port})."
                ) from exc
            response.raise_for_status()
            data = response.json()
            projects = data.get("data") or []
            if not projects:
                raise AicoSyncError(f"No project found for name {scenario.aico_project_name}")
            pid = int(projects[0]["id"])

        if cache_enabled:
            with TargetSessionLocal() as session:
                db_scenario = session.get(Scenario, scenario.id)
                if db_scenario is not None:
                    db_scenario.aico_cached_pid = pid
                    session.commit()
                    session.refresh(db_scenario)
                    scenario = db_scenario

        return pid, scenario

    def _ensure_kb_id_and_cache(self, scenario: Scenario, token: str, pid: int, run_id: str) -> tuple[int, Scenario]:
        cache_enabled = self._cache_enabled_for_host(scenario)
        if cache_enabled and scenario.aico_cached_kb_id:
            return scenario.aico_cached_kb_id, scenario

        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}/aicoapi/kb_manage/kbm/search_kb"
        params = {"pid": pid, "view_type": "personal", "kb_name": scenario.aico_kb_name}
        headers = {"Authorization": f"Bearer {token}"}

        with self._build_client() as client:
            logger.info("[run_id=%s] Step: resolve kb_id (kb_name=%s pid=%s)", run_id, scenario.aico_kb_name, pid)
            try:
                response = client.get(url, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                raise AicoSyncError(
                    f"Connect to AICO kb endpoint timed out (host={self.aico_settings.host} port={self.aico_settings.kb_port})."
                ) from exc
            response.raise_for_status()
            data = response.json()
            kbs = data.get("data") or []
            if not kbs:
                raise AicoSyncError(f"No knowledge base found for name {scenario.aico_kb_name}")
            kb_id = int(kbs[0]["id"])

        if cache_enabled:
            with TargetSessionLocal() as session:
                db_scenario = session.get(Scenario, scenario.id)
                if db_scenario is not None:
                    db_scenario.aico_cached_kb_id = kb_id
                    session.commit()
                    session.refresh(db_scenario)
                    scenario = db_scenario

        return kb_id, scenario

    def _upload_file(self, token: str, pid: int, kb_id: int, file_name: str, content: bytes, run_id: str) -> int:
        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}/aicoapi/knowledge_manage/file/upload"
        headers = {"Authorization": f"Bearer {token}"}
        files = {
            "files": (file_name, content, "text/csv"),
        }
        split_config = self._build_split_config(pid, kb_id)
        data = {
            "pid": str(pid),
            "kb_id": str(kb_id),
            "source": "1",
            "oper": "1",  # 覆盖
            # AICO 新版本：上传时触发切分
            "seprate": "1",
            "split_config": split_config,
            # AICO 新版本要求的标记字段，表示由自动化任务上传
            "is_auto": "true",
        }

        with self._build_client() as client:
            response = client.post(url, data=data, files=files, headers=headers)
            response.raise_for_status()
            payload = response.json()
            if payload.get("err_code") not in (0, None):
                raise AicoSyncError(f"Upload failed: {payload}")

        logger.info("[run_id=%s] Upload accepted by AICO, waiting for file to appear: %s", run_id, file_name)
        file_id = self._wait_for_file_appearance(token, pid, kb_id, file_name, run_id)
        return file_id

    def _list_files(self, token: str, pid: int, kb_id: int, title: str, run_id: str) -> list[dict]:
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
            "type": str(self._file_type),
        }

        with self._build_client() as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get("err_code") not in (0, None):
                raise AicoSyncError(f"File list failed: {data}")
            files = data.get("data") or []
            if not isinstance(files, list):
                raise AicoSyncError(f"Unexpected file list payload: {data}")
            filtered = [f for f in files if isinstance(f, dict)]
            logger.info(
                "[run_id=%s] AICO file/show returned %d files (title=%s)",
                run_id,
                len(filtered),
                title if title else "<empty>",
            )
            return filtered

    def _delete_files(self, token: str, pid: int, kb_id: int, user_id: int, file_ids: list[int], run_id: str) -> None:
        endpoint = (self.aico_settings.file_delete_endpoint or "/aicoapi/knowledge_manage/file/del").strip()
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Login-Type": "NORMAL",
        }
        payload = {
            "user_id": user_id,
            "user_uuid": "",
            "file_ids": file_ids,
            "pid": pid,
            "kb_id": str(kb_id),
        }

        with self._build_client() as client:
            logger.info(
                "[run_id=%s] Deleting files via %s (count=%d, pid=%s, kb_id=%s)",
                run_id,
                endpoint,
                len(file_ids),
                pid,
                kb_id,
            )
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            if response.headers.get("content-type", "").startswith("application/json"):
                data = response.json()
                if isinstance(data, dict) and data.get("err_code") not in (0, None):
                    raise AicoSyncError(f"Delete files failed: {data}")
                logger.info("[run_id=%s] Delete files response: %s", run_id, data if isinstance(data, dict) else "<json>")
            else:
                logger.info("[run_id=%s] Delete files response: %s", run_id, response.status_code)

    def _cleanup_old_files(
        self,
        token: str,
        pid: int,
        kb_id: int,
        scenario_code: str,
        user_id: int,
        run_id: str,
    ) -> None:
        """
        V1.11: 清理历史同步文件，避免依赖 upload 覆盖行为。
        仅删除符合本系统命名规则的文件，避免误删非本系统管理的文件。
        """
        prefix = f"{scenario_code}_knowledge_"

        # AICO 文档里 title 为必填；尝试用空字符串拉全量（若不支持则退化为按前缀查询）。
        try:
            candidates = self._list_files(token, pid, kb_id, title="", run_id=run_id)
        except Exception:
            candidates = self._list_files(token, pid, kb_id, title=prefix, run_id=run_id)

        targets: list[dict] = []
        for f in candidates:
            file_name = str(f.get("file_name") or "")
            if file_name.startswith(prefix):
                targets.append(f)

        if not targets:
            logger.info(
                "[run_id=%s] No previous sync files to delete (scenario=%s, kb_id=%s)",
                run_id,
                scenario_code,
                kb_id,
            )
            return

        logger.info(
            "[run_id=%s] Deleting %d previous sync files (scenario=%s, kb_id=%s)",
            run_id,
            len(targets),
            scenario_code,
            kb_id,
        )
        file_ids: list[int] = []
        for f in targets:
            file_id = f.get("id")
            if not isinstance(file_id, int):
                try:
                    file_id = int(file_id)
                except Exception as exc:
                    raise AicoSyncError(f"Invalid file id in file list: {f}") from exc
            file_ids.append(file_id)

        self._delete_files(token, pid, kb_id, user_id, file_ids, run_id)

    def _wait_for_file_appearance(self, token: str, pid: int, kb_id: int, title: str, run_id: str) -> int:
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
            "type": str(self._file_type),
        }

        with self._build_client() as client:
            started = time.monotonic()
            for i in range(30):
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                files = data.get("data") or []
                if files:
                    file_id = int(files[0]["id"])
                    logger.info("[run_id=%s] File appeared in AICO list (file_id=%s)", run_id, file_id)
                    return file_id
                if i % 10 == 0:
                    logger.info(
                        "[run_id=%s] Waiting for file to appear in list... elapsed=%ds",
                        run_id,
                        int(time.monotonic() - started),
                    )
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

    def _wait_for_split_complete(self, token: str, pid: int, kb_id: int, title: str, run_id: str) -> None:
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
            "type": str(self._file_type),
        }

        with self._build_client() as client:
            started = time.monotonic()
            last_status: object = None
            for i in range(60):
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                files = data.get("data") or []
                if not files:
                    if i % 10 == 0:
                        logger.info(
                            "[run_id=%s] Split status polling: no file yet elapsed=%ds",
                            run_id,
                            int(time.monotonic() - started),
                        )
                    time.sleep(2)
                    continue
                raw_status = (
                    files[0].get("is_slice")
                    if isinstance(files[0], dict)
                    else None
                )
                if raw_status is None and isinstance(files[0], dict):
                    raw_status = files[0].get("slice_status") or files[0].get("sliceStatus")

                status: object = raw_status
                if isinstance(raw_status, str):
                    s = raw_status.strip()
                    if s.isdigit():
                        status = int(s)
                elif isinstance(raw_status, (int, float)):
                    status = int(raw_status)

                if i == 0 or i % 10 == 0 or status != last_status:
                    logger.info(
                        "[run_id=%s] Split status polling: status=%s elapsed=%ds",
                        run_id,
                        status,
                        int(time.monotonic() - started),
                    )
                    last_status = status

                if status == 3:
                    return
                if status == 4:
                    raise AicoSyncError("File split failed in AICO.")
                time.sleep(2)

        raise AicoSyncError("File split did not complete within timeout.")

    def _online_all(self, token: str, pid: int, kb_id: int, run_id: str) -> None:
        url = f"http://{self.aico_settings.host}:{self.aico_settings.kb_port}/aicoapi/knowledge_manage/knowledge/online"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"kb_id": str(kb_id), "pid": pid, "id_list": []}

        with self._build_client() as client:
            logger.info("[run_id=%s] Calling AICO online (kb_id=%s pid=%s)", run_id, kb_id, pid)
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get("err_code") not in (0, None):
                raise AicoSyncError(f"Online operation failed: {data}")
