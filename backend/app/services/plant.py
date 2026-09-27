"""电站档案业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import re
from typing import Any

from app.store import store

MODULE = "plant"
REQUIRED_FIELDS = ["电站编号", "电站名称", "装机容量"]
STATUS_ORDER = ["建设中", "并网运行", "停运维护", "已退役"]
RUNNING_STATUS = "并网运行"
ACTION_RULES = {"确认并网": "并网运行", "进入维护": "停运维护", "标记退役": "已退役"}
NEGATIVE_ACTIONS = []

_CAPACITY_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)\s*(万?kW|MW|GW)?", re.IGNORECASE)


def capacity_mw(value: Any) -> float:
    """把『100MW』『8000kW』『1.2GW』『6万kW』这类口径折算成 MW；解析不出来按 0 处理。"""
    text = str(value or "").strip()
    match = _CAPACITY_PATTERN.search(text)
    if not match:
        return 0.0
    number = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit == "gw":
        number *= 1000
    elif unit == "万kw":
        number *= 10
    elif unit == "kw":
        number /= 1000
    return round(number, 3)


class PlantService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("电站编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def owner_board(self) -> dict[str, Any]:
        """按运维负责人汇总责任看板：负责人名下电站卡片、运行数量与装机口径。

        运行口径与状态流转保持一致，只认「并网运行」；容量统一折算成 MW 便于横向比较。
        分组按总装机容量从大到小排，让看板打开就能看出谁的责任范围更重。
        """
        rows = store.rows(MODULE)
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            owner = str(row.get("运维负责人") or "").strip() or "未分派"
            buckets.setdefault(owner, []).append(row)

        groups: list[dict[str, Any]] = []
        for owner, plants in buckets.items():
            total_capacity = sum(capacity_mw(plant.get("装机容量")) for plant in plants)
            running_plants = [plant for plant in plants if plant.get("status") == RUNNING_STATUS]
            running_capacity = sum(capacity_mw(plant.get("装机容量")) for plant in running_plants)
            status_breakdown = {
                status: sum(1 for plant in plants if plant.get("status") == status)
                for status in STATUS_ORDER
            }
            groups.append({
                "owner": owner,
                "total": len(plants),
                "running": len(running_plants),
                "capacity_mw": round(total_capacity, 3),
                "running_capacity_mw": round(running_capacity, 3),
                "status_breakdown": status_breakdown,
                "plants": plants,
            })
        groups.sort(key=lambda item: item["capacity_mw"], reverse=True)

        return {
            "total_owners": len(groups),
            "total_plants": len(rows),
            "total_running": sum(item["running"] for item in groups),
            "total_capacity_mw": round(sum(item["capacity_mw"] for item in groups), 3),
            "statuses": STATUS_ORDER,
            "groups": groups,
        }

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
            return None, f"光伏电站 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于电站档案可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"光伏电站已{action}"
