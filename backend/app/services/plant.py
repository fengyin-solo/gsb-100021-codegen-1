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
UNASSIGNED_OWNER = "未指派"


def _capacity_mw(value: Any) -> float:
    """从「120MW」这类装机容量描述里取出兆瓦数，取不到按 0 算。"""
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group()) if match else 0.0


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

    def board(self) -> dict[str, Any]:
        """责任看板：按运维负责人分组，汇总每人名下电站数、运行电站数量与装机容量合计。"""
        groups: dict[str, dict[str, Any]] = {}
        for row in store.rows(MODULE):
            owner = str(row.get("运维负责人") or "").strip() or UNASSIGNED_OWNER
            group = groups.setdefault(
                owner, {"owner": owner, "stations": [], "total": 0, "running": 0, "capacity_mw": 0.0}
            )
            status = str(row.get("status") or "未知")
            group["stations"].append({
                "id": row.get("id"),
                "电站编号": row.get("电站编号") or "—",
                "装机容量": row.get("装机容量") or "—",
                "电站状态": status,
            })
            group["total"] += 1
            group["running"] += 1 if status == RUNNING_STATUS else 0
            group["capacity_mw"] += _capacity_mw(row.get("装机容量"))
        owners = sorted(groups.values(), key=lambda item: (-item["running"], -item["total"], item["owner"]))
        for group in owners:
            group["stations"].sort(key=lambda station: str(station["电站编号"]))
            group["capacity_mw"] = round(group["capacity_mw"], 2)
        return {
            "module": MODULE,
            "owners": owners,
            "total_stations": sum(int(group["total"]) for group in owners),
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
