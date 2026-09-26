"""质量控制接口：维护质控样品，覆盖检测质控、确认受控、标记失控等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, QcListResult
from app.services.qc import QcService

router = APIRouter(prefix="/api/qc", tags=["质量控制"])

service = QcService()

LIST_FIELDS = ["质控编号", "质控类别", "标准值", "允许偏差", "实测值", "判定结果", "检测日期", "质控状态"]
STATUSES = ["待检测", "检测中", "受控", "失控"]


@router.get("", response_model=QcListResult)
def list_entries(
    keyword: str | None = Query(default=None, description="按质控编号检索"),
    category: str | None = Query(default=None, description="按质控类别检索"),
    standard_value: str | None = Query(default=None, description="按标准值检索"),
    deviation: str | None = Query(default=None, description="按允许偏差检索"),
    standard_min: float | None = Query(default=None, description="标准值下限"),
    standard_max: float | None = Query(default=None, description="标准值上限"),
    deviation_min: float | None = Query(default=None, description="允许偏差下限"),
    deviation_max: float | None = Query(default=None, description="允许偏差上限"),
    status: str | None = Query(default=None, description="待检测、检测中、受控、失控"),
    sort: str | None = Query(default=None, description="排序字段"),
    order: str = Query(default="asc", description="排序方向 asc/desc"),
    page: int = 1,
    size: int = 20,
) -> QcListResult:
    """按质控编号、质控类别、标准值、允许偏差组合筛选并排序；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    try:
        result = service.list_entries(
            keyword=keyword,
            category=category,
            standard_value=standard_value,
            deviation=deviation,
            standard_min=standard_min,
            standard_max=standard_max,
            deviation_min=deviation_min,
            deviation_max=deviation_max,
            status=status,
            sort=sort,
            order=order,
            page=page,
            size=size,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return QcListResult(size=size, **result)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出质量控制清单：返回当前过滤条件下的全量数据。"""
    result = service.list_entries(page=1, size=10000)
    return {"module": "qc", "total": result["total"], "items": result["items"]}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条质控样品明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"质控样品 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条质控样品，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="质控样品已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条质控样品执行检测质控、确认受控、标记失控；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
