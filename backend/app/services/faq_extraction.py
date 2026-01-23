from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple

import json
import time

from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from sqlalchemy import and_, select

from ..core.db import TargetSessionLocal
from ..core.logging import get_logger
from ..core.settings import get_settings
from ..models.dialog import ConversationStatus, PreparedConversation
from ..models.faq_review import PendingFAQ


logger = get_logger(__name__)
settings = get_settings()


@dataclass
class FAQExtractionResult:
    target_date: Optional[date]
    conversations_total: int
    faqs_created: int


class FAQExtractionService:
    def __init__(self, max_workers: Optional[int] = None) -> None:
        self.max_workers = max_workers or settings.scheduler.faq_max_workers
        self.auto_review_max_retries = 2
        self.auto_review_retry_delay_seconds = 5

    def run(self, target_date: Optional[date] = None, limit: Optional[int] = None) -> FAQExtractionResult:
        ids = self._fetch_unprocessed_ids(target_date)

        if limit is not None:
            ids = ids[:limit]

        if not ids:
            logger.info("No conversations to extract FAQs from.")
            return FAQExtractionResult(target_date=target_date, conversations_total=0, faqs_created=0)

        faqs_created = self._process_batch(ids)
        return FAQExtractionResult(
            target_date=target_date,
            conversations_total=len(ids),
            faqs_created=faqs_created,
        )

    @staticmethod
    def _compute_date_range(target_date: date) -> Tuple[datetime, datetime]:
        start = datetime.combine(target_date, time.min)
        end = start + timedelta(days=1)
        return start, end

    def _fetch_unprocessed_ids(self, target_date: Optional[date]) -> list[int]:
        stmt = select(PreparedConversation.id).where(
            PreparedConversation.status == ConversationStatus.UNPROCESSED.value,
        )
        if target_date is not None:
            start, end = self._compute_date_range(target_date)
            stmt = stmt.where(
                and_(
                    PreparedConversation.conversation_time >= start,
                    PreparedConversation.conversation_time < end,
                )
            )

        with TargetSessionLocal() as session:
            rows = session.execute(stmt.order_by(PreparedConversation.id)).all()
        return [row[0] for row in rows]

    def _process_batch(self, ids: list[int]) -> int:
        created = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {executor.submit(self._process_single, conv_id): conv_id for conv_id in ids}
            for future in as_completed(future_map):
                conv_id = future_map[future]
                try:
                    outcome = future.result()
                except Exception as exc:  # pylint: disable=broad-except
                    logger.exception("FAQ extraction task failed for conversation %s: %s", conv_id, exc)
                    outcome = False
                if outcome:
                    created += 1
        return created

    def _process_single(self, conv_id: int) -> bool:
        with TargetSessionLocal() as session:
            conv = session.get(PreparedConversation, conv_id)
            if conv is None:
                return False
            if conv.status != ConversationStatus.UNPROCESSED.value:
                return False

            conv.status = ConversationStatus.PROCESSING.value
            session.commit()
            session.refresh(conv)

            full_text = (conv.full_text or "").strip()
            if not full_text:
                conv.status = ConversationStatus.PROCESSED_NO_FAQ.value
                session.commit()
                return False

            try:
                reply_text = self._call_aico(full_text)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("AICO call failed for conversation %s: %s", conv.call_id, exc)
                conv.status = ConversationStatus.FAILED.value
                session.commit()
                return False

            parsed = reply_text.strip()
            if parsed == "否":
                conv.status = ConversationStatus.PROCESSED_NO_FAQ.value
                session.commit()
                return False

            question, answer = self._parse_question_answer(parsed)
            if not question or not answer:
                conv.status = ConversationStatus.PROCESSED_NO_FAQ.value
                session.commit()
                return False

            pending_status = self._determine_pending_status(question, answer, conv.call_id)
            faq = PendingFAQ(
                question=question,
                answer=answer,
                status=pending_status,
                source_group_code=conv.group_code,
                source_call_id=conv.call_id,
                source_conversation_text=conv.full_text,
            )
            session.add(faq)
            conv.status = ConversationStatus.COMPLETED.value
            session.commit()

        logger.info("Created pending FAQ from conversation %s", conv_id)
        return True

    def _determine_pending_status(self, question: str, answer: str, call_id: str) -> str:
        try:
            decision = self._run_auto_review(question, answer)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Auto review failed for conversation %s: %s", call_id, exc)
            return "pending"

        if decision != "approved":
            return "auto_rejected"

        try:
            compare_decision = self._run_compare_review(question, answer)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Compare review failed for conversation %s: %s", call_id, exc)
            return "pending"

        if compare_decision == "approved":
            return "pending"
        return "auto_rejected"

    def _run_auto_review(self, question: str, answer: str) -> str:
        query = self._build_auto_review_query(question, answer)
        url = settings.aico.auto_review_url or settings.aico.chatbot_url
        if not url:
            raise RuntimeError("AICO auto review URL is not configured.")

        for attempt in range(self.auto_review_max_retries + 1):
            try:
                reply_text = self._call_aico(query, url=url)
            except Exception as exc:  # pylint: disable=broad-except
                if attempt < self.auto_review_max_retries:
                    logger.warning(
                        "Auto review attempt %s failed, retrying: %s",
                        attempt + 1,
                        exc,
                    )
                    time.sleep(self.auto_review_retry_delay_seconds)
                    continue
                raise

            decision = reply_text.strip()
            normalized = decision.lower()
            if normalized == "approved":
                return "approved"
            if normalized == "rejected":
                return "rejected"

            parsed = self._parse_auto_review_json(decision)
            if parsed:
                return parsed

            logger.warning("Auto review returned unexpected text, treating as rejected: %s", reply_text)
            return "rejected"

        return "rejected"

    def _run_compare_review(self, question: str, answer: str) -> str:
        query = self._build_auto_review_query(question, answer)
        url = (
            settings.aico.compare_review_url
            or settings.aico.auto_review_url
            or settings.aico.chatbot_url
        )
        if not url:
            raise RuntimeError("AICO compare review URL is not configured.")

        for attempt in range(self.auto_review_max_retries + 1):
            try:
                reply_text = self._call_aico(query, url=url)
            except Exception as exc:  # pylint: disable=broad-except
                if attempt < self.auto_review_max_retries:
                    logger.warning(
                        "Compare review attempt %s failed, retrying: %s",
                        attempt + 1,
                        exc,
                    )
                    time.sleep(self.auto_review_retry_delay_seconds)
                    continue
                raise

            decision = reply_text.strip()
            normalized = decision.lower()
            if normalized == "approved":
                return "approved"
            if normalized == "rejected":
                return "rejected"

            parsed = self._parse_auto_review_json(decision)
            if parsed:
                return parsed

            logger.warning("Compare review returned unexpected text, treating as rejected: %s", reply_text)
            return "rejected"

        return "rejected"

    @staticmethod
    def _build_auto_review_query(question: str, answer: str) -> str:
        return f"问题：{question}\n答案：{answer}"

    @staticmethod
    def _parse_auto_review_json(raw: str) -> Optional[str]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None

        def extract(value: object) -> Optional[str]:
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in ("approved", "rejected"):
                    return normalized
            return None

        if isinstance(payload, dict):
            for key in (
                "result",
                "status",
                "decision",
                "auto_review",
                "autoReview",
                "auto_review_result",
                "autoReviewResult",
            ):
                extracted = extract(payload.get(key))
                if extracted:
                    return extracted
            for value in payload.values():
                extracted = extract(value)
                if extracted:
                    return extracted
            return None

        if isinstance(payload, list):
            for item in payload:
                extracted = extract(item)
                if extracted:
                    return extracted
                if isinstance(item, dict):
                    for value in item.values():
                        extracted = extract(value)
                        if extracted:
                            return extracted

        return None
    def _call_aico(self, full_text: str, url: Optional[str] = None) -> str:
        if not settings.aico.chatbot_api_key:
            raise RuntimeError("AICO chatbot API key is not configured.")

        target_url = url or settings.aico.chatbot_url
        if not target_url:
            raise RuntimeError("AICO chatbot URL is not configured.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.aico.chatbot_api_key}",
        }
        payload = {"query": full_text, "stream": False}

        timeout = httpx.Timeout(settings.aico.timeout_seconds)

        # trust_env=False 避免受本机 HTTP(S)_PROXY / ALL_PROXY 等环境变量影响，
        # 从而不再要求 socksio 依赖。
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.post(target_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        outer = (data or {}).get("data") or {}

        # 兼容两种返回格式：
        # 1) data.text[0]  （文档里的格式）
        # 2) data.data.output （你现在环境里的真实格式）
        text_list = outer.get("text") or []
        if isinstance(text_list, list) and text_list:
            return str(text_list[0])

        inner_data = outer.get("data") or {}
        if isinstance(inner_data, dict) and "output" in inner_data:
            return str(inner_data["output"])

        raise RuntimeError(f"AICO response missing expected text/output field: {data}")

    @staticmethod
    def _parse_question_answer(raw: str) -> Tuple[str, str]:
        """
        支持形如：
        "问题：xxx\\n答案：yyy"
        """
        text = raw.strip()
        if "问题：" in text and "答案：" in text:
            try:
                _, rest = text.split("问题：", 1)
                q_part, a_part = rest.split("答案：", 1)
                question = q_part.strip()
                answer = a_part.strip()
                return question, answer
            except ValueError:
                # 回退到整体作为问答
                pass

        return text, text
