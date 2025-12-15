from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, TypedDict

from sqlalchemy import func, select

from ..core.db import TargetSessionLocal
from ..core.logging import get_logger
from ..models.faq_review import KnowledgeItem, PendingFAQ


logger = get_logger(__name__)
MAX_BULK_OPERATION_SIZE = 100


class BulkAcceptData(TypedDict):
    pending_faq_id: int
    scenario_id: int
    question: str
    answer: str


class NotFoundError(Exception):
    pass


class ReviewService:
    @staticmethod
    def _validate_bulk_size(count: int) -> None:
        if count < 1:
            raise ValueError("至少需要选择一条数据进行操作")
        if count > MAX_BULK_OPERATION_SIZE:
            raise ValueError(f"单次最多只能处理 {MAX_BULK_OPERATION_SIZE} 条数据")

    def list_pending_faqs(
        self,
        page: int,
        page_size: int,
        keyword: Optional[str] = None,
        source_group_code: Optional[str] = None,
    ) -> Tuple[List[PendingFAQ], int]:
        """Return pending FAQs with pagination."""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 1

        offset = (page - 1) * page_size
        filters = [PendingFAQ.status == "pending"]
        if keyword:
            like_pattern = f"%{keyword}%"
            filters.append(PendingFAQ.question.like(like_pattern))
        if source_group_code:
            filters.append(PendingFAQ.source_group_code == source_group_code)

        with TargetSessionLocal() as session:
            total = session.execute(
                select(func.count()).select_from(PendingFAQ).where(*filters)
            ).scalar_one()

            items = (
                session.execute(
                    select(PendingFAQ)
                    .where(*filters)
                    .order_by(PendingFAQ.created_at.desc())
                    .offset(offset)
                    .limit(page_size)
                )
                .scalars()
                .all()
            )

        return items, total

    def accept_pending_faq(
        self,
        pending_faq_id: int,
        scenario_id: int,
        question: str,
        answer: str,
        allowed_group_code: Optional[str] = None,
    ) -> KnowledgeItem:
        """Create a knowledge item from a pending FAQ and mark it processed."""
        with TargetSessionLocal() as session:
            pending = session.get(PendingFAQ, pending_faq_id)
            if pending is None:
                raise NotFoundError(f"Pending FAQ {pending_faq_id} not found")
            if pending.status != "pending":
                raise ValueError(f"Pending FAQ {pending_faq_id} is already {pending.status}")
            if allowed_group_code and pending.source_group_code != allowed_group_code:
                raise PermissionError(
                    f"Pending FAQ {pending_faq_id} does not belong to the allowed group {allowed_group_code}"
                )

            item = KnowledgeItem(
                scenario_id=scenario_id,
                question=question,
                answer=answer,
                status="active",
            )
            session.add(item)

            pending.status = "processed"

            session.commit()
            session.refresh(item)

        logger.info("Accepted pending FAQ %s as knowledge item %s", pending_faq_id, item.id)
        return item

    def discard_pending_faq(self, pending_faq_id: int, allowed_group_code: Optional[str] = None) -> None:
        """Mark a pending FAQ as discarded."""
        with TargetSessionLocal() as session:
            pending = session.get(PendingFAQ, pending_faq_id)
            if pending is None:
                raise NotFoundError(f"Pending FAQ {pending_faq_id} not found")
            if allowed_group_code and pending.source_group_code != allowed_group_code:
                raise PermissionError(
                    f"Pending FAQ {pending_faq_id} does not belong to the allowed group {allowed_group_code}"
                )

            pending.status = "discarded"
            session.commit()

        logger.info("Discarded pending FAQ %s", pending_faq_id)

    def bulk_accept_pending_faqs(
        self,
        *,
        payloads: Sequence[BulkAcceptData],
        scenario_id: int,
        allowed_group_code: Optional[str] = None,
    ) -> int:
        self._validate_bulk_size(len(payloads))

        pending_ids = [payload["pending_faq_id"] for payload in payloads]
        if len(set(pending_ids)) != len(pending_ids):
            raise ValueError("包含重复的待审核 FAQ 编号")

        with TargetSessionLocal() as session:
            with session.begin():
                pending_rows = (
                    session.execute(
                        select(PendingFAQ)
                        .where(PendingFAQ.id.in_(pending_ids))
                        .with_for_update()
                    )
                    .scalars()
                    .all()
                )
                pending_map = {row.id: row for row in pending_rows}
                missing = [pid for pid in pending_ids if pid not in pending_map]
                if missing:
                    raise NotFoundError(f"Pending FAQ {missing[0]} not found")

                for payload in payloads:
                    pending = pending_map[payload["pending_faq_id"]]
                    if pending.status != "pending":
                        raise ValueError(f"Pending FAQ {pending.id} is already {pending.status}")
                    if allowed_group_code and pending.source_group_code != allowed_group_code:
                        raise PermissionError(
                            f"Pending FAQ {pending.id} does not belong to the allowed group {allowed_group_code}"
                        )
                    if payload["scenario_id"] != scenario_id:
                        raise PermissionError(
                            f"Pending FAQ {pending.id} does not belong to scenario {scenario_id}"
                        )

                    item = KnowledgeItem(
                        scenario_id=scenario_id,
                        question=payload["question"],
                        answer=payload["answer"],
                        status="active",
                    )
                    session.add(item)
                    pending.status = "processed"

        logger.info("Bulk accepted %s pending FAQs", len(payloads))
        return len(payloads)

    def bulk_discard_pending_faqs(
        self,
        *,
        pending_faq_ids: Sequence[int],
        allowed_group_code: Optional[str] = None,
    ) -> int:
        self._validate_bulk_size(len(pending_faq_ids))

        if len(set(pending_faq_ids)) != len(pending_faq_ids):
            raise ValueError("包含重复的待审核 FAQ 编号")

        with TargetSessionLocal() as session:
            with session.begin():
                pending_rows = (
                    session.execute(
                        select(PendingFAQ)
                        .where(PendingFAQ.id.in_(pending_faq_ids))
                        .with_for_update()
                    )
                    .scalars()
                    .all()
                )
                pending_map = {row.id: row for row in pending_rows}
                missing = [pid for pid in pending_faq_ids if pid not in pending_map]
                if missing:
                    raise NotFoundError(f"Pending FAQ {missing[0]} not found")

                for pending_id in pending_faq_ids:
                    pending = pending_map[pending_id]
                    if pending.status != "pending":
                        raise ValueError(f"Pending FAQ {pending.id} is already {pending.status}")
                    if allowed_group_code and pending.source_group_code != allowed_group_code:
                        raise PermissionError(
                            f"Pending FAQ {pending.id} does not belong to the allowed group {allowed_group_code}"
                        )

                    pending.status = "discarded"

        logger.info("Bulk discarded %s pending FAQs", len(pending_faq_ids))
        return len(pending_faq_ids)
