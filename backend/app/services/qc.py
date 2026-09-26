"""质量控制业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.store import store

MODULE = "qc"
REQUIRED_FIELDS = ["质控编号", "质控类别", "标准值"]
STATUS_ORDER = ["待检测", "检测中", "受控", "失控"]
ACTION_RULES = {"检测质控": "检测中", "确认受控": "受控", "标记失控": "失控"}
NEGATIVE_ACTIONS = ["标记失控"]

SORTABLE_FIELDS = ["质控编号", "质控类别", "标准值", "允许偏差"]
NUMERIC_FIELDS = {"标准值", "允许偏差"}
SORT_DIRECTIONS = ("asc", "desc")


@dataclass
class QcListResult:
    """一次列表查询的完整口径：列表、分页、统计与提示同源返回，避免数量与列表错位。"""

    items: list[dict[str, Any]]
    total: int
    page: int
    size: int
    stats: dict[str, int] = field(default_factory=dict)
    categories: list[str] = field(default_factory=list)
    notice: str = ""


def _to_float(value: Any) -> float | None:
    """标准值、允许偏差登记时多为数字字符串；解析不了就当作无法按数值比较。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class QcService:
    def list_entries(
        self,
        *,
        code: str | None = None,
        category: str | None = None,
        standard_min: float | None = None,
        standard_max: float | None = None,
        deviation_min: float | None = None,
        deviation_max: float | None = None,
        status: str | None = None,
        sort_field: str = "质控编号",
        sort_dir: str = "asc",
        page: int = 1,
        size: int = 20,
    ) -> QcListResult:
        """组合筛选 + 排序 + 分页；落在最后一屏之后时自动回到最后一屏并给出说明。"""
        if sort_field not in SORTABLE_FIELDS:
            raise ValueError(f"暂不支持按「{sort_field}」排序，可选：{'、'.join(SORTABLE_FIELDS)}")
        if sort_dir not in SORT_DIRECTIONS:
            raise ValueError("排序方向只支持升序（asc）或降序（desc）")
        if standard_min is not None and standard_max is not None and standard_min > standard_max:
            raise ValueError("标准值的最小值不能大于最大值，请调整区间后再查询")
        if deviation_min is not None and deviation_max is not None and deviation_min > deviation_max:
            raise ValueError("允许偏差的最小值不能大于最大值，请调整区间后再查询")
        if status and status not in STATUS_ORDER:
            raise ValueError(f"质控状态「{status}」不在允许范围内")

        rows = store.rows(MODULE)
        if code:
            keyword = code.strip()
            rows = [row for row in rows if keyword in str(row.get("质控编号", ""))]
        if category:
            wanted = category.strip()
            rows = [row for row in rows if str(row.get("质控类别", "")).strip() == wanted]
        if standard_min is not None or standard_max is not None:
            rows = self._filter_numeric(rows, "标准值", standard_min, standard_max)
        if deviation_min is not None or deviation_max is not None:
            rows = self._filter_numeric(rows, "允许偏差", deviation_min, deviation_max)
        if status:
            rows = [row for row in rows if row.get("status") == status]

        rows = self._sort(rows, sort_field, sort_dir)
        total = len(rows)

        notice = ""
        if total == 0:
            page = 1
        else:
            last_page = (total - 1) // size + 1
            if page > last_page:
                notice = f"第 {page} 屏已超出结果范围，已为你定位到最后一屏（第 {last_page} 屏）"
                page = last_page
            page = max(page, 1)
        start = (page - 1) * size

        categories = sorted({
            str(row.get("质控类别", "")).strip()
            for row in store.rows(MODULE)
            if str(row.get("质控类别", "")).strip()
        })
        stats = self._build_stats(rows)

        return QcListResult(
            items=rows[start:start + size],
            total=total,
            page=page,
            size=size,
            stats=stats,
            categories=categories,
            notice=notice,
        )

    @staticmethod
    def _filter_numeric(
        rows: list[dict[str, Any]],
        field_name: str,
        lower: float | None,
        upper: float | None,
    ) -> list[dict[str, Any]]:
        """按数值区间筛选；非数值登记值无法参与比较，会被排除在区间结果外。"""
        result: list[dict[str, Any]] = []
        for row in rows:
            number = _to_float(row.get(field_name))
            if number is None:
                continue
            if lower is not None and number < lower:
                continue
            if upper is not None and number > upper:
                continue
            result.append(row)
        return result

    @staticmethod
    def _sort(
        rows: list[dict[str, Any]],
        sort_field: str,
        sort_dir: str,
    ) -> list[dict[str, Any]]:
        """数值字段按大小排，其余按文本排；空值统一沉底，两个方向都稳定。"""
        reverse = sort_dir == "desc"
        numeric = sort_field in NUMERIC_FIELDS

        def value_of(row: dict[str, Any]) -> float | str | None:
            if numeric:
                return _to_float(row.get(sort_field))
            text = str(row.get(sort_field) or "").strip()
            return text or None

        with_value = [row for row in rows if value_of(row) is not None]
        without_value = [row for row in rows if value_of(row) is None]
        with_value.sort(key=value_of, reverse=reverse)
        return with_value + without_value

    @staticmethod
    def _build_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
        """统计口径与当前列表完全一致（同一份筛选结果），并按状态顺序给出待检/受控/失控量。"""
        counts = {status: 0 for status in STATUS_ORDER}
        for row in rows:
            status = row.get("status")
            if status in counts:
                counts[status] += 1
        return {
            "待检质控品": counts["待检测"] + counts["检测中"],
            "受控质控品": counts["受控"],
            "失控质控品": counts["失控"],
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
        entry["pending"] = target not in ("受控", "失控")
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"质控样品已{action}"
