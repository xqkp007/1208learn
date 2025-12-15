from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select

from ..core.db import TargetSessionLocal
from ..core.logging import get_logger
from ..models.faq_review import KnowledgeItem
from .review import NotFoundError


logger = get_logger(__name__)


class KnowledgeService:
    def list_items(
        self,
        *,
        scenario_id: int,
        status: str,
        page: int,
        page_size: int,
        keyword: Optional[str] = None,
    ) -> Tuple[List[KnowledgeItem], int]:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 1

        filters = [KnowledgeItem.scenario_id == scenario_id]
        if status:
            filters.append(KnowledgeItem.status == status)
        if keyword:
            like_pattern = f"%{keyword}%"
            filters.append(
                or_(
                    KnowledgeItem.question.like(like_pattern),
                    KnowledgeItem.answer.like(like_pattern),
                )
            )

        with TargetSessionLocal() as session:
            total = (
                session.execute(
                    select(func.count()).select_from(KnowledgeItem).where(*filters)
                ).scalar_one()
            )

            rows = (
                session.execute(
                    select(KnowledgeItem)
                        .where(*filters)
                        .order_by(KnowledgeItem.updated_at.desc())
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                )
                .scalars()
                .all()
            )

        return rows, total

    def get_item(self, *, item_id: int, scenario_id: int) -> KnowledgeItem:
        with TargetSessionLocal() as session:
            item = session.get(KnowledgeItem, item_id)
            if item is None or item.scenario_id != scenario_id:
                raise NotFoundError(f"Knowledge item {item_id} not found")
            session.expunge(item)
        return item

    def update_item(
        self,
        *,
        item_id: int,
        scenario_id: int,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        status: Optional[str] = None,
    ) -> KnowledgeItem:
        allowed_status = {"active", "disabled"}
        if status and status not in allowed_status:
            raise ValueError("Invalid status")

        with TargetSessionLocal() as session:
            item = session.get(KnowledgeItem, item_id)
            if item is None or item.scenario_id != scenario_id:
                raise NotFoundError(f"Knowledge item {item_id} not found")

            if question is not None:
                item.question = question
            if answer is not None:
                item.answer = answer
            if status is not None:
                item.status = status

            session.commit()
            session.refresh(item)
            session.expunge(item)

        logger.info("Updated knowledge item %s", item_id)
        return item

