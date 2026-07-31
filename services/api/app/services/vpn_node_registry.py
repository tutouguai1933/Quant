"""VPN 节点注册表。

管理主备节点列表、探测状态持久化和候选排序。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class NodeEntry:
    """单个 VPN 节点条目。"""

    name: str
    ip: str | None = None
    whitelisted: bool = False
    role: Literal["primary", "backup", "unknown"] = "unknown"
    last_probe_ok: bool | None = None
    last_probe_at: float | None = None

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "name": self.name,
            "ip": self.ip,
            "whitelisted": self.whitelisted,
            "role": self.role,
            "last_probe_ok": self.last_probe_ok,
            "last_probe_at": self.last_probe_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NodeEntry":
        """从字典反序列化。"""
        return cls(
            name=str(data.get("name", "")),
            ip=data.get("ip"),
            whitelisted=bool(data.get("whitelisted", False)),
            role=data.get("role", "unknown"),
            last_probe_ok=data.get("last_probe_ok"),
            last_probe_at=data.get("last_probe_at"),
        )


class NodeRegistry:
    """VPN 节点注册表。

    管理主备节点列表、探测状态持久化和候选排序。
    """

    def __init__(
        self,
        primary: str,
        backups: list[str],
        whitelisted_ips: set[str],
    ) -> None:
        """初始化节点注册表。

        Args:
            primary: 主节点名称
            backups: 备选节点名称列表
            whitelisted_ips: 白名单 IP 集合
        """
        self._primary = primary
        self._backups = backups
        self._whitelisted_ips = whitelisted_ips
        self._entries: dict[str, NodeEntry] = {}

        # 从配置初始化节点条目
        if primary:
            self._entries[primary] = NodeEntry(
                name=primary,
                whitelisted=True,
                role="primary",
            )
        for i, name in enumerate(backups):
            self._entries[name] = NodeEntry(
                name=name,
                whitelisted=True,
                role="backup",
            )

    @property
    def primary_name(self) -> str:
        """返回主节点名称。"""
        return self._primary

    def known_nodes(self) -> list[NodeEntry]:
        """返回所有已知节点（主 + 备），保持配置顺序。"""
        result: list[NodeEntry] = []
        seen: set[str] = set()
        for name in self._ordered_node_names():
            if name in seen:
                continue
            seen.add(name)
            entry = self._entries.get(name)
            if entry is None:
                entry = NodeEntry(name=name)
                self._entries[name] = entry
            result.append(entry)
        return result

    def mark_probe(self, name: str, ok: bool, ip: str | None) -> None:
        """更新节点探测结果（内存 + 持久化落盘由调用方控制）。

        Args:
            name: 节点名称
            ok: 探测是否通过
            ip: 出口 IP
        """
        entry = self._entries.get(name)
        if entry is None:
            entry = NodeEntry(name=name)
            self._entries[name] = entry
        entry.last_probe_ok = ok
        entry.last_probe_at = time.time()
        if ip:
            entry.ip = ip
            entry.whitelisted = ip in self._whitelisted_ips
        logger.debug(
            "节点 %s 探测: ok=%s, ip=%s, whitelisted=%s",
            name,
            ok,
            ip,
            entry.whitelisted,
        )

    def candidates(self) -> list[NodeEntry]:
        """返回备选节点列表，按优先级排序：

        1. 白名单节点优先
        2. 最近探测通过的优先
        3. 配置顺序
        """
        all_nodes = self.known_nodes()
        # 排除主节点（candidates 只返回备选）
        candidates = [n for n in all_nodes if n.role != "primary"]

        def sort_key(node: NodeEntry) -> tuple[int, int, int]:
            # whitelisted: True(0) before False(1)
            whitelisted_rank = 0 if node.whitelisted else 1
            # last_probe_ok: True(0) before None(1) before False(2)
            if node.last_probe_ok is True:
                probe_rank = 0
            elif node.last_probe_ok is None:
                probe_rank = 1
            else:
                probe_rank = 2
            # config order
            config_order = self._config_order(node.name)
            return (whitelisted_rank, probe_rank, config_order)

        candidates.sort(key=sort_key)
        return candidates

    def get_entry(self, name: str) -> NodeEntry | None:
        """获取指定节点的条目。

        Args:
            name: 节点名称

        Returns:
            节点条目，不存在返回 None
        """
        return self._entries.get(name)

    def save_state(self, path: Path) -> None:
        """持久化节点状态到文件。

        Args:
            path: 持久化文件路径
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "primary": self._primary,
                "backups": self._backups,
                "whitelisted_ips": sorted(self._whitelisted_ips),
                "entries": {
                    name: entry.to_dict() for name, entry in self._entries.items()
                },
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("节点状态已保存到 %s", path)
        except (OSError, IOError) as e:
            logger.warning("保存节点状态失败: %s", e)

    def load_state(self, path: Path) -> None:
        """从文件恢复节点状态。

        Args:
            path: 持久化文件路径
        """
        if not path.exists():
            logger.debug("节点状态文件不存在: %s，使用默认配置", path)
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 恢复条目状态
            entries_data = data.get("entries", {})
            for name, entry_dict in entries_data.items():
                entry = NodeEntry.from_dict(entry_dict)
                # 确保角色信息正确（配置优先）
                if name == self._primary:
                    entry.role = "primary"
                elif name in self._backups:
                    entry.role = "backup"
                # 恢复的白名单状态以配置为准
                if entry.ip and entry.ip in self._whitelisted_ips:
                    entry.whitelisted = True
                else:
                    entry.whitelisted = False
                self._entries[name] = entry

            logger.debug("节点状态已从 %s 恢复（%d 个条目）", path, len(self._entries))
        except (json.JSONDecodeError, OSError, IOError) as e:
            logger.warning("加载节点状态失败: %s", e)

    def _config_order(self, name: str) -> int:
        """返回节点在配置中的顺序。

        Args:
            name: 节点名称

        Returns:
            配置顺序索引（越小越靠前）
        """
        ordered = self._ordered_node_names()
        try:
            return ordered.index(name)
        except ValueError:
            return len(ordered)

    def _ordered_node_names(self) -> list[str]:
        """返回按配置顺序排列的节点名称列表。"""
        result: list[str] = []
        if self._primary:
            result.append(self._primary)
        result.extend(self._backups)
        return result
