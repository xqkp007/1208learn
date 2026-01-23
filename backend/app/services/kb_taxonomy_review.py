from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import delete, select

from ..core.db import TargetSessionLocal
from ..models.kb_taxonomy import KbTaxonomyCase, KbTaxonomyNode
from ..models.kb_taxonomy_review import KbTaxonomyReviewCase, KbTaxonomyReviewItem


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


class KbTaxonomyReviewService:
    def list_pending(self, scope: str) -> Tuple[List[KbTaxonomyReviewItem], Dict[int, List[KbTaxonomyReviewCase]]]:
        with TargetSessionLocal() as session:
            items = (
                session.execute(
                    select(KbTaxonomyReviewItem)
                    .where(
                        KbTaxonomyReviewItem.scope_code == scope,
                        KbTaxonomyReviewItem.status == "pending",
                    )
                    .order_by(KbTaxonomyReviewItem.created_at.desc())
                )
                .scalars()
                .all()
            )

            if not items:
                return [], {}

            item_ids = [int(item.id) for item in items]
            cases = (
                session.execute(
                    select(KbTaxonomyReviewCase)
                    .where(KbTaxonomyReviewCase.review_item_id.in_(item_ids))
                    .order_by(KbTaxonomyReviewCase.id.asc())
                )
                .scalars()
                .all()
            )

        case_map: Dict[int, List[KbTaxonomyReviewCase]] = {}
        for item in cases:
            case_map.setdefault(int(item.review_item_id), []).append(item)

        return items, case_map

    def accept_review_item(
        self,
        review_item_id: int,
        scope: str,
        l3_name: str,
        definition: str,
        cases: List[str],
    ) -> None:
        clean_l3 = (l3_name or "").strip()
        clean_definition = (definition or "").strip()
        clean_cases = [(c or "").strip() for c in (cases or [])]

        if not clean_l3:
            raise ValidationError("三级分类名称不能为空")
        if not clean_definition:
            raise ValidationError("定义不能为空")
        if not clean_cases:
            raise ValidationError("至少需要一条案例")
        if any(not c for c in clean_cases):
            raise ValidationError("案例内容不能为空")

        with TargetSessionLocal() as session:
            with session.begin():
                item = (
                    session.execute(
                        select(KbTaxonomyReviewItem)
                        .where(KbTaxonomyReviewItem.id == review_item_id)
                        .with_for_update()
                    )
                    .scalars()
                    .one_or_none()
                )
                if item is None:
                    raise NotFoundError(f"Review item {review_item_id} not found")
                if item.scope_code != scope:
                    raise PermissionError("Scope not allowed")
                if item.status != "pending":
                    raise ValidationError("审核项已处理")

                item.l3_name = clean_l3
                item.definition = clean_definition
                session.execute(
                    delete(KbTaxonomyReviewCase).where(KbTaxonomyReviewCase.review_item_id == item.id)
                )
                for content in clean_cases:
                    session.add(KbTaxonomyReviewCase(review_item_id=item.id, content=content))

                l1 = self._get_or_create_node(
                    session=session,
                    scope=scope,
                    level=1,
                    name=item.l1_name,
                    parent_id=None,
                )
                l2 = self._get_or_create_node(
                    session=session,
                    scope=scope,
                    level=2,
                    name=item.l2_name,
                    parent_id=int(l1.id),
                )
                l3 = (
                    session.execute(
                        select(KbTaxonomyNode).where(
                            KbTaxonomyNode.scope_code == scope,
                            KbTaxonomyNode.level == 3,
                            KbTaxonomyNode.parent_id == l2.id,
                            KbTaxonomyNode.name == clean_l3,
                        )
                    )
                    .scalars()
                    .one_or_none()
                )
                if l3 is None:
                    l3 = KbTaxonomyNode(
                        scope_code=scope,
                        level=3,
                        name=clean_l3,
                        parent_id=int(l2.id),
                        definition=clean_definition,
                    )
                    session.add(l3)
                    session.flush()
                else:
                    l3.definition = clean_definition

                session.execute(delete(KbTaxonomyCase).where(KbTaxonomyCase.node_id == l3.id))
                for content in clean_cases:
                    session.add(KbTaxonomyCase(node_id=int(l3.id), content=content))

                item.status = "accepted"

    def discard_review_item(self, review_item_id: int, scope: str) -> None:
        with TargetSessionLocal() as session:
            with session.begin():
                item = (
                    session.execute(
                        select(KbTaxonomyReviewItem)
                        .where(KbTaxonomyReviewItem.id == review_item_id)
                        .with_for_update()
                    )
                    .scalars()
                    .one_or_none()
                )
                if item is None:
                    raise NotFoundError(f"Review item {review_item_id} not found")
                if item.scope_code != scope:
                    raise PermissionError("Scope not allowed")
                if item.status != "pending":
                    raise ValidationError("审核项已处理")
                item.status = "discarded"

    @staticmethod
    def _get_or_create_node(
        *,
        session,
        scope: str,
        level: int,
        name: str,
        parent_id: int | None,
    ) -> KbTaxonomyNode:
        node = (
            session.execute(
                select(KbTaxonomyNode).where(
                    KbTaxonomyNode.scope_code == scope,
                    KbTaxonomyNode.level == level,
                    KbTaxonomyNode.parent_id == parent_id,
                    KbTaxonomyNode.name == name,
                )
            )
            .scalars()
            .one_or_none()
        )
        if node is not None:
            return node

        node = KbTaxonomyNode(
            scope_code=scope,
            level=level,
            name=name,
            parent_id=parent_id,
            definition=None,
        )
        session.add(node)
        session.flush()
        return node
