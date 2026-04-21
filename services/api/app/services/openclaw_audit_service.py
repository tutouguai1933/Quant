"""OpenClaw 动作审计记录服务。

记录 OpenClaw 执行的所有动作，用于审计和追溯。
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


class OpenclawAuditService:
    """OpenClaw 动作审计记录服务。"""

    MAX_RECORDS = 100

    def __init__(self, state_path: Path):
        """初始化审计服务。

        Args:
            state_path: 存储审计记录的文件路径
        """
        self._state_path = state_path
        self._records: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """从文件加载审计记录。"""
        if self._state_path.exists():
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = list(data.get("records", []))
            except (json.JSONDecodeError, IOError):
                self._records = []
        else:
            self._records = []

    def _save(self) -> None:
        """保存审计记录到文件。"""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump({"records": self._records}, f, ensure_ascii=False, indent=2)

    def record_action(self, record: dict) -> dict:
        """记录一条动作审计记录。

        Args:
            record: 包含动作信息的字典，应包含 action、snapshot_id、success、reason 等字段

        Returns:
            记录完成的审计记录
        """
        now = datetime.now(timezone.utc).isoformat()
        audit_record = {
            "recorded_at": now,
            "action": record.get("action", ""),
            "snapshot_id": record.get("snapshot_id", ""),
            "success": bool(record.get("success", False)),
            "reason": str(record.get("reason", "")),
            "executed_at": record.get("executed_at", now),
            "result": record.get("result"),
        }

        self._records.append(audit_record)

        # 保留最近 MAX_RECORDS 条记录
        if len(self._records) > self.MAX_RECORDS:
            self._records = self._records[-self.MAX_RECORDS:]

        self._save()
        return audit_record

    def get_recent_records(self, limit: int = 10) -> list[dict]:
        """获取最近的审计记录。

        Args:
            limit: 返回的最大记录数，默认 10 条

        Returns:
            最近的审计记录列表，按时间倒序
        """
        return list(reversed(self._records[-limit:]))

    def get_records_by_action(self, action: str) -> list[dict]:
        """获取指定动作类型的所有审计记录。

        Args:
            action: 动作名称

        Returns:
            匹配的审计记录列表，按时间倒序
        """
        matched = [r for r in self._records if r.get("action") == action]
        return list(reversed(matched))


# 默认实例
openclaw_audit_service = OpenclawAuditService(
    state_path=Path(".runtime/openclaw_audit_records.json")
)