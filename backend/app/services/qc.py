"""质量控制业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import math
from typing import Any

from app.store import store

MODULE = "qc"
REQUIRED_FIELDS = ["质控编号", "质控类别", "标准值"]
STATUS_ORDER = ["待检测", "检测中", "受控", "失控"]
ACTION_RULES = {"检测质控": "检测中", "确认受控": "受控", "标记失控": "失控"}
NEGATIVE_ACTIONS = []

LIST_FIELDS = ["质控编号", "质控类别", "标准值", "允许偏差", "实测值", "判定结果", "检测日期", "质控状态"]
SORTABLE_FIELDS = ["质控编号", "质控类别", "标准值", "允许偏差", "实测值", "判定结果", "检测日期"]
NUMERIC_FIELDS = {"标准值", "允许偏差", "实测值"}


def _as_number(value: Any) -> float | None:
    """把「±0.5」「10.0」这类写法解析成数值；解析不了返回 None。"""
    text = str(value or "").strip().lstrip("±").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _in_range(value: Any, lower: float | None, upper: float | None) -> bool:
    """设置了区间边界时，非数值的记录直接排除，避免静默混入。"""
    if lower is None and upper is None:
        return True
    number = _as_number(value)
    if number is None:
        return False
    if lower is not None and number < lower:
        return False
    if upper is not None and number > upper:
        return False
    return True


def _sort_key(field: str):
    if field in NUMERIC_FIELDS:
        def key(row: dict[str, Any]) -> tuple[bool, float, str]:
            number = _as_number(row.get(field))
            # 非数值排在最后，保证升降序都稳定可预期
            return (number is None, number if number is not None else 0.0, str(row.get(field) or ""))
        return key

    def text_key(row: dict[str, Any]) -> str:
        return str(row.get(field) or "")

    return text_key


class QcService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        standard_value: str | None = None,
        deviation: str | None = None,
        standard_min: float | None = None,
        standard_max: float | None = None,
        deviation_min: float | None = None,
        deviation_max: float | None = None,
        status: str | None = None,
        sort: str | None = None,
        order: str = "asc",
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        if standard_min is not None and standard_max is not None and standard_min > standard_max:
            raise ValueError("标准值下限大于上限，筛选条件互相矛盾")
        if deviation_min is not None and deviation_max is not None and deviation_min > deviation_max:
            raise ValueError("允许偏差下限大于上限，筛选条件互相矛盾")
        if sort is not None and sort not in SORTABLE_FIELDS:
            raise ValueError(f"不支持按「{sort}」排序，可排序字段：{'、'.join(SORTABLE_FIELDS)}")
        if order not in ("asc", "desc"):
            raise ValueError("排序方向只支持 asc 或 desc")

        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("质控编号", ""))]
        if category:
            rows = [row for row in rows if category in str(row.get("质控类别", ""))]
        if standard_value:
            rows = [row for row in rows if standard_value in str(row.get("标准值", ""))]
        if deviation:
            rows = [row for row in rows if deviation in str(row.get("允许偏差", ""))]
        rows = [row for row in rows if _in_range(row.get("标准值"), standard_min, standard_max)]
        rows = [row for row in rows if _in_range(row.get("允许偏差"), deviation_min, deviation_max)]
        if status:
            rows = [row for row in rows if row.get("status") == status]

        if sort:
            rows = sorted(rows, key=_sort_key(sort), reverse=(order == "desc"))

        total = len(rows)
        # 统计与列表共用同一批过滤结果，数量指标不会和当前列表错位
        stats = {label: sum(1 for row in rows if row.get("status") == label) for label in STATUS_ORDER}

        pages = max(1, math.ceil(total / size))
        page = min(max(page, 1), pages)
        start = (page - 1) * size
        return {
            "items": rows[start:start + size],
            "total": total,
            "page": page,
            "pages": pages,
            "stats": stats,
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"质控样品 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于质量控制可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"质控样品已{action}"
