from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple

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

            faq = PendingFAQ(
                question=question,
                answer=answer,
                status="pending",
                source_group_code=conv.group_code,
                source_call_id=conv.call_id,
                source_conversation_text=conv.full_text,
            )
            session.add(faq)
            conv.status = ConversationStatus.COMPLETED.value
            session.commit()

        logger.info("Created pending FAQ from conversation %s", conv_id)
        return True

    def _call_aico(self, full_text: str) -> str:
        if not settings.aico.chatbot_api_key:
            raise RuntimeError("AICO chatbot API key is not configured.")

        url = settings.aico.chatbot_url
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.aico.chatbot_api_key}",
        }
        payload = {"query": full_text, "stream": False}

        timeout = httpx.Timeout(settings.aico.timeout_seconds)

        # trust_env=False 避免受本机 HTTP(S)_PROXY / ALL_PROXY 等环境变量影响，
        # 从而不再要求 socksio 依赖。
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.post(url, headers=headers, json=payload)
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
