from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from ..core.db import SourceSessionLocal, TargetSessionLocal
from ..core.logging import get_logger
from ..core.settings import get_settings
from ..models.dialog import ConversationStatus, PeopleCustomerDialog, PreparedConversation


logger = get_logger(__name__)
settings = get_settings()


@dataclass
class GroupProcessingResult:
    group_code: str
    conversations_total: int
    inserted: int
    skipped_existing: int


@dataclass
class ETLRunResult:
    target_date: date
    groups_processed: int
    conversations_total: int
    inserted: int
    skipped_existing: int


class DialogETLService:
    def __init__(self, max_workers: Optional[int] = None, timezone: Optional[str] = None) -> None:
        self.max_workers = max_workers or settings.scheduler.max_workers
        self.timezone = timezone or settings.scheduler.timezone

    def run_for_date(self, target_date: date) -> ETLRunResult:
        start_dt, end_dt = self._compute_date_range(target_date)
        group_codes = self._fetch_group_codes(start_dt, end_dt)
        if not group_codes:
            logger.info("No dialogs found for %s", target_date.isoformat())
            return ETLRunResult(target_date, 0, 0, 0, 0)

        results: List[GroupProcessingResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(self._process_group_code, code, start_dt, end_dt): code for code in group_codes
            }
            for future in as_completed(future_map):
                code = future_map[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(
                        "Group %s processed - total:%d inserted:%d skipped:%d",
                        code,
                        result.conversations_total,
                        result.inserted,
                        result.skipped_existing,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    logger.exception("ETL failed for group %s: %s", code, exc)
                    raise

        total = sum(r.conversations_total for r in results)
        inserted = sum(r.inserted for r in results)
        skipped = sum(r.skipped_existing for r in results)
        logger.info(
            "ETL complete for %s - groups:%d total:%d inserted:%d skipped:%d",
            target_date.isoformat(),
            len(results),
            total,
            inserted,
            skipped,
        )
        return ETLRunResult(target_date, len(results), total, inserted, skipped)

    def default_target_date(self) -> date:
        try:
            tz = ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")
        now = datetime.now(tz)
        return (now - timedelta(days=1)).date()

    @staticmethod
    def _compute_date_range(target_date: date) -> Tuple[datetime, datetime]:
        start = datetime.combine(target_date, time.min)
        end = start + timedelta(days=1)
        return start, end

    def _fetch_group_codes(self, start: datetime, end: datetime) -> List[str]:
        stmt = (
            select(PeopleCustomerDialog.group_code)
            .where(
                and_(
                    PeopleCustomerDialog.create_time >= start,
                    PeopleCustomerDialog.create_time < end,
                )
            )
            .distinct()
        )
        with SourceSessionLocal() as session:
            result = session.execute(stmt)
            return [row[0] for row in result]

    def _process_group_code(self, group_code: str, start: datetime, end: datetime) -> GroupProcessingResult:
        stmt = (
            select(PeopleCustomerDialog)
            .where(
                and_(
                    PeopleCustomerDialog.group_code == group_code,
                    PeopleCustomerDialog.create_time >= start,
                    PeopleCustomerDialog.create_time < end,
                )
            )
            .order_by(
                PeopleCustomerDialog.call_id,
                PeopleCustomerDialog.create_time,
                PeopleCustomerDialog.seq,
            )
        )
        with SourceSessionLocal() as source_session:
            dialogs: Sequence[PeopleCustomerDialog] = source_session.execute(stmt).scalars().all()

        inserted = 0
        skipped = 0
        conversations_total = 0

        with TargetSessionLocal() as target_session:
            buffer: list[PeopleCustomerDialog] = []
            current_call_id: Optional[str] = None

            def flush_buffer(records: Sequence[PeopleCustomerDialog]) -> None:
                nonlocal inserted, skipped, conversations_total
                if not records:
                    return
                call_id = records[0].call_id
                conversations_total += 1
                full_text, conversation_time = self._build_conversation_text(records)
                exists_stmt = select(PreparedConversation.id).where(PreparedConversation.call_id == call_id)
                exists = target_session.execute(exists_stmt).scalar_one_or_none()
                if exists:
                    skipped += 1
                    return
                conversation = PreparedConversation(
                    group_code=group_code,
                    call_id=call_id,
                    full_text=full_text,
                    status=ConversationStatus.UNPROCESSED.value,
                    conversation_time=conversation_time,
                )
                target_session.add(conversation)
                inserted += 1

            for dialog in dialogs:
                if current_call_id != dialog.call_id:
                    flush_buffer(buffer)
                    buffer = []
                    current_call_id = dialog.call_id
                buffer.append(dialog)
            flush_buffer(buffer)

            try:
                target_session.commit()
            except IntegrityError:
                logger.exception("Integrity error while committing prepared conversations for group %s", group_code)
                target_session.rollback()
                raise

        return GroupProcessingResult(group_code, conversations_total, inserted, skipped)

    @staticmethod
    def _build_conversation_text(records: Sequence[PeopleCustomerDialog]) -> Tuple[str, datetime]:
        lines: List[str] = []
        conversation_time: Optional[datetime] = None
        for record in records:
            prefix = "市民" if record.source == 1 else "客服"
            text = (record.text or "").strip()
            lines.append(f"{prefix}：{text}")
            if conversation_time is None and record.create_time:
                conversation_time = record.create_time

        return "\n".join(lines), conversation_time or datetime.utcnow()
