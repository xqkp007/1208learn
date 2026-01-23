from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from ..core.db import TargetSessionLocal
from ..models.kb_taxonomy import KbTaxonomyCase, KbTaxonomyNode


class KbTaxonomyError(Exception):
    pass


class ValidationError(KbTaxonomyError):
    pass


class NotFoundError(KbTaxonomyError):
    pass


@dataclass(frozen=True)
class ImportRow:
    domain: str
    l1: str
    l2: str
    l3: str
    definition: str
    cases: List[str]


@dataclass(frozen=True)
class ImportPlan:
    scope: str
    rows: List[ImportRow]
    category_count: int
    case_count: int


SCOPE_TO_DOMAIN_ZH = {
    "water": "水务",
    "bus": "公交",
    "bike": "自行车",
}

REQUIRED_COLUMNS = ["业务域", "一级", "二级", "三级", "定义"]


def _normalize_cell(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _read_csv_bytes(raw: bytes) -> Tuple[List[str], List[Tuple[int, Dict[str, str]]]]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or []) if h is not None]
    rows: List[Tuple[int, Dict[str, str]]] = []
    for row_number, row in enumerate(reader, start=2):  # header=1
        normalized: Dict[str, str] = {}
        for key, value in (row or {}).items():
            if key is None:
                continue
            normalized[key.strip()] = _normalize_cell(value)
        if not any(v for v in normalized.values()):
            continue
        rows.append((row_number, normalized))
    return headers, rows


def _read_xlsx_bytes(raw: bytes) -> Tuple[List[str], List[Tuple[int, Dict[str, str]]]]:
    try:
        import openpyxl
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Missing dependency: openpyxl") from exc

    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if header_row is None:
        return [], []

    headers = [(_normalize_cell(h) if h is not None else "") for h in header_row]
    headers = [h.strip() for h in headers]

    rows: List[Tuple[int, Dict[str, str]]] = []
    for excel_row_number, values in enumerate(rows_iter, start=2):  # header=1
        normalized: Dict[str, str] = {}
        any_value = False
        for idx, header in enumerate(headers):
            if not header:
                continue
            cell = values[idx] if idx < len(values) else None
            val = _normalize_cell(cell)
            if val:
                any_value = True
            normalized[header] = val
        if not any_value:
            continue
        rows.append((excel_row_number, normalized))

    return headers, rows


def _read_tabular_bytes(raw: bytes, filename: str) -> Tuple[List[str], List[Tuple[int, Dict[str, str]]]]:
    lower = (filename or "").lower()
    if lower.endswith(".xlsx"):
        return _read_xlsx_bytes(raw)
    if lower.endswith(".csv") or not lower:
        return _read_csv_bytes(raw)
    raise ValidationError("仅支持CSV或XLSX文件")


def _extract_case_columns(headers: Iterable[str]) -> List[str]:
    return [h for h in headers if h.startswith("案例")]


def build_import_plan(scope: str, raw: bytes, filename: str) -> Tuple[Optional[ImportPlan], List[dict]]:
    try:
        headers, rows = _read_tabular_bytes(raw, filename)
    except ValidationError as exc:
        return None, [{"row": 1, "column": "file", "message": str(exc)}]
    errors: List[dict] = []

    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        for c in missing:
            errors.append(
                {
                    "row": 1,
                    "column": c,
                    "message": "缺少必需表头",
                    "expected": "存在该列",
                    "actual": "缺失",
                }
            )
        return None, errors

    case_cols = _extract_case_columns(headers)
    expected_domain = SCOPE_TO_DOMAIN_ZH.get(scope)
    if expected_domain is None:
        errors.append({"row": 1, "column": "scope", "message": "非法scope", "expected": "water|bus|bike", "actual": scope})
        return None, errors

    path_definition: Dict[Tuple[str, str, str, str], Tuple[str, int]] = {}
    import_rows: List[ImportRow] = []
    for row_number, row in rows:
        domain = _normalize_cell(row.get("业务域"))
        l1 = _normalize_cell(row.get("一级"))
        l2 = _normalize_cell(row.get("二级"))
        l3 = _normalize_cell(row.get("三级"))
        definition = _normalize_cell(row.get("定义"))

        if domain != expected_domain:
            errors.append(
                {
                    "row": row_number,
                    "column": "业务域",
                    "message": "业务域与当前范围不一致",
                    "expected": expected_domain,
                    "actual": domain or "(空)",
                }
            )

        for col_name, value in [("业务域", domain), ("一级", l1), ("二级", l2), ("三级", l3), ("定义", definition)]:
            if not value:
                errors.append(
                    {
                        "row": row_number,
                        "column": col_name,
                        "message": "必填字段不能为空",
                        "expected": "非空",
                        "actual": "(空)",
                    }
                )

        if not (domain and l1 and l2 and l3 and definition) or domain != expected_domain:
            continue

        path_key = (expected_domain, l1, l2, l3)
        prev = path_definition.get(path_key)
        if prev is None:
            path_definition[path_key] = (definition, row_number)
        else:
            prev_def, prev_row = prev
            if prev_def != definition:
                errors.append(
                    {
                        "row": row_number,
                        "column": "定义",
                        "message": "同一分类路径定义不一致",
                        "expected": f"与第{prev_row}行一致",
                        "actual": definition,
                    }
                )
                continue

        case_values: List[str] = []
        for c in case_cols:
            val = _normalize_cell(row.get(c))
            if val:
                case_values.append(val)

        import_rows.append(
            ImportRow(
                domain=expected_domain,
                l1=l1,
                l2=l2,
                l3=l3,
                definition=definition,
                cases=case_values,
            )
        )

    if errors:
        return None, errors

    unique_categories = {(r.l1, r.l2, r.l3, r.definition) for r in import_rows}
    case_count = sum(len(r.cases) for r in import_rows)
    return ImportPlan(scope=scope, rows=import_rows, category_count=len(unique_categories), case_count=case_count), []


class KbTaxonomyService:
    def _assert_unique_sibling_name(
        self,
        *,
        session,
        scope: str,
        parent_id: Optional[int],
        name: str,
        exclude_id: Optional[int] = None,
    ) -> None:
        stmt = select(KbTaxonomyNode.id).where(
            KbTaxonomyNode.scope_code == scope,
            KbTaxonomyNode.name == name,
        )
        if parent_id is None:
            stmt = stmt.where(KbTaxonomyNode.parent_id.is_(None))
        else:
            stmt = stmt.where(KbTaxonomyNode.parent_id == parent_id)
        if exclude_id is not None:
            stmt = stmt.where(KbTaxonomyNode.id != exclude_id)
        exists = session.execute(stmt.limit(1)).first()
        if exists:
            raise ValidationError("同级下已存在同名分类")

    def list_tree(self, scope: str) -> List[KbTaxonomyNode]:
        with TargetSessionLocal() as session:
            stmt = (
                select(KbTaxonomyNode)
                .where(KbTaxonomyNode.scope_code == scope)
                .order_by(KbTaxonomyNode.level.asc(), KbTaxonomyNode.name.asc(), KbTaxonomyNode.id.asc())
            )
            return session.execute(stmt).scalars().all()

    def get_node(self, node_id: int) -> KbTaxonomyNode:
        with TargetSessionLocal() as session:
            node = session.get(KbTaxonomyNode, node_id)
            if node is None:
                raise NotFoundError(f"Node {node_id} not found")
            session.expunge(node)
            return node

    def list_cases(self, node_id: int, keyword: Optional[str]) -> List[KbTaxonomyCase]:
        with TargetSessionLocal() as session:
            stmt = select(KbTaxonomyCase).where(KbTaxonomyCase.node_id == node_id).order_by(KbTaxonomyCase.id.asc())
            if keyword:
                stmt = stmt.where(KbTaxonomyCase.content.like(f"%{keyword}%"))
            return session.execute(stmt).scalars().all()

    def create_node(
        self,
        *,
        scope: str,
        level: int,
        name: str,
        parent_id: Optional[int],
        definition: Optional[str],
    ) -> KbTaxonomyNode:
        name = name.strip()
        if not name:
            raise ValidationError("name is required")
        if level not in (1, 2, 3):
            raise ValidationError("level must be 1|2|3")
        if level == 1 and parent_id is not None:
            raise ValidationError("level 1 node cannot have parent")
        if level in (2, 3) and parent_id is None:
            raise ValidationError("parentId is required for level 2/3")
        if level == 3 and not (definition or "").strip():
            raise ValidationError("definition is required for level 3")

        with TargetSessionLocal() as session:
            if parent_id is not None:
                parent = session.get(KbTaxonomyNode, parent_id)
                if parent is None:
                    raise NotFoundError(f"Parent node {parent_id} not found")
                if parent.scope_code != scope:
                    raise ValidationError("parent scope mismatch")
                if level == 2 and parent.level != 1:
                    raise ValidationError("level 2 parent must be level 1")
                if level == 3 and parent.level != 2:
                    raise ValidationError("level 3 parent must be level 2")

            self._assert_unique_sibling_name(session=session, scope=scope, parent_id=parent_id, name=name)

            node = KbTaxonomyNode(
                scope_code=scope,
                level=level,
                name=name,
                parent_id=parent_id,
                definition=definition.strip() if definition is not None else None,
            )
            session.add(node)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValidationError("同级下已存在同名分类") from exc
            session.refresh(node)
            session.expunge(node)
            return node

    def update_node(self, *, node_id: int, scope: str, name: Optional[str], definition: Optional[str]) -> KbTaxonomyNode:
        with TargetSessionLocal() as session:
            node = session.get(KbTaxonomyNode, node_id)
            if node is None:
                raise NotFoundError(f"Node {node_id} not found")
            if node.scope_code != scope:
                raise NotFoundError(f"Node {node_id} not found")

            if name is not None:
                if not name.strip():
                    raise ValidationError("name cannot be empty")
                next_name = name.strip()
                if next_name != node.name:
                    self._assert_unique_sibling_name(
                        session=session,
                        scope=scope,
                        parent_id=int(node.parent_id) if node.parent_id is not None else None,
                        name=next_name,
                        exclude_id=int(node.id),
                    )
                node.name = next_name

            if definition is not None:
                if node.level != 3:
                    raise ValidationError("only level 3 supports definition")
                if not definition.strip():
                    raise ValidationError("definition cannot be empty")
                node.definition = definition

            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValidationError("同级下已存在同名分类") from exc
            session.refresh(node)
            session.expunge(node)
            return node

    def delete_node(self, *, node_id: int, scope: str) -> None:
        with TargetSessionLocal() as session:
            node = session.get(KbTaxonomyNode, node_id)
            if node is None or node.scope_code != scope:
                raise NotFoundError(f"Node {node_id} not found")

            child_exists = session.execute(
                select(KbTaxonomyNode.id).where(KbTaxonomyNode.parent_id == node_id).limit(1)
            ).first()
            if child_exists:
                raise ValidationError("请先删除/迁移子节点")

            session.delete(node)
            session.commit()

    def create_case(self, *, scope: str, node_id: int, content: str) -> KbTaxonomyCase:
        content = content.strip()
        if not content:
            raise ValidationError("content is required")
        with TargetSessionLocal() as session:
            node = session.get(KbTaxonomyNode, node_id)
            if node is None or node.scope_code != scope:
                raise NotFoundError(f"Node {node_id} not found")
            if node.level != 3:
                raise ValidationError("cases can only attach to level 3")

            case = KbTaxonomyCase(node_id=node_id, content=content)
            session.add(case)
            session.commit()
            session.refresh(case)
            session.expunge(case)
            return case

    def update_case(self, *, scope: str, case_id: int, content: str) -> KbTaxonomyCase:
        content = content.strip()
        if not content:
            raise ValidationError("content is required")
        with TargetSessionLocal() as session:
            case = session.get(KbTaxonomyCase, case_id)
            if case is None:
                raise NotFoundError(f"Case {case_id} not found")
            node = session.get(KbTaxonomyNode, case.node_id)
            if node is None or node.scope_code != scope:
                raise NotFoundError(f"Case {case_id} not found")

            case.content = content
            session.commit()
            session.refresh(case)
            session.expunge(case)
            return case

    def delete_case(self, *, scope: str, case_id: int) -> None:
        with TargetSessionLocal() as session:
            case = session.get(KbTaxonomyCase, case_id)
            if case is None:
                raise NotFoundError(f"Case {case_id} not found")
            node = session.get(KbTaxonomyNode, case.node_id)
            if node is None or node.scope_code != scope:
                raise NotFoundError(f"Case {case_id} not found")
            session.delete(case)
            session.commit()

    def import_validate(self, *, scope: str, raw: bytes, filename: str) -> Tuple[Optional[ImportPlan], List[dict]]:
        return build_import_plan(scope, raw, filename=filename)

    def import_execute(self, *, scope: str, raw: bytes, filename: str) -> ImportPlan:
        plan, errors = build_import_plan(scope, raw, filename=filename)
        if errors or plan is None:
            raise ValidationError("文件校验失败")

        with TargetSessionLocal() as session:
            with session.begin():
                node_ids_subq = select(KbTaxonomyNode.id).where(KbTaxonomyNode.scope_code == scope)
                session.execute(delete(KbTaxonomyCase).where(KbTaxonomyCase.node_id.in_(node_ids_subq)))
                # Delete nodes in leaf-to-root order to satisfy the self-referencing FK on parent_id.
                for level in (3, 2, 1):
                    session.execute(
                        delete(KbTaxonomyNode).where(
                            KbTaxonomyNode.scope_code == scope,
                            KbTaxonomyNode.level == level,
                        )
                    )

                root_cache: Dict[Tuple[Optional[int], str], KbTaxonomyNode] = {}
                for row in plan.rows:
                    l1 = root_cache.get((None, row.l1))
                    if l1 is None:
                        l1 = KbTaxonomyNode(scope_code=scope, level=1, name=row.l1, parent_id=None, definition=None)
                        session.add(l1)
                        session.flush()
                        root_cache[(None, row.l1)] = l1

                    l2 = root_cache.get((l1.id, row.l2))
                    if l2 is None:
                        l2 = KbTaxonomyNode(scope_code=scope, level=2, name=row.l2, parent_id=l1.id, definition=None)
                        session.add(l2)
                        session.flush()
                        root_cache[(l1.id, row.l2)] = l2

                    l3 = root_cache.get((l2.id, row.l3))
                    if l3 is None:
                        l3 = KbTaxonomyNode(
                            scope_code=scope,
                            level=3,
                            name=row.l3,
                            parent_id=l2.id,
                            definition=row.definition,
                        )
                        session.add(l3)
                        session.flush()
                        root_cache[(l2.id, row.l3)] = l3

                    for content in row.cases:
                        session.add(KbTaxonomyCase(node_id=l3.id, content=content))

        return plan
