# -*- coding: utf-8 -*-
"""群级配置、名片审计与保护名单的 SQLite repository mixin。"""

from typing import Dict, List, Optional


class GroupStorageMixin:
    """依赖宿主提供 ``_connect()``，保持 ``SQLiteStorage`` 公共 API 不变。"""

    def get_group_config(self, group_id: str, key: str):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM group_configs WHERE group_id=? AND key=?",
                (str(group_id), str(key)),
            ).fetchone()
        return row["value"] if row else None

    def get_group_configs(self, group_id: str) -> Dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value FROM group_configs WHERE group_id=?",
                (str(group_id),),
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_group_config(self, group_id: str, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO group_configs(group_id, key, value) "
                "VALUES(?, ?, ?)",
                (str(group_id), str(key), str(value)),
            )
            conn.commit()

    def delete_group_config(self, group_id: str, key: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM group_configs WHERE group_id=? AND key=?",
                (str(group_id), str(key)),
            )
            conn.commit()
        return bool(cursor.rowcount)

    def clear_group_configs(self, group_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM group_configs WHERE group_id=?", (str(group_id),)
            )
            conn.commit()
        return int(cursor.rowcount or 0)

    def list_configured_groups(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT group_id FROM group_configs ORDER BY group_id"
            ).fetchall()
        return [row["group_id"] for row in rows]

    def add_card_change_log(
        self,
        kind: str,
        group_id: str,
        user_id: str,
        user_name: str,
        old_value: str,
        new_value: str,
        action: str,
        ts: int,
        time_str: str,
    ) -> int:
        """记录一条名片变更/管理员任免日志，返回新行 id。"""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO card_change_logs("
                "ts, time, kind, group_id, user_id, user_name, old_value, "
                "new_value, action) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(ts), str(time_str), str(kind), str(group_id),
                    str(user_id), str(user_name or ""), str(old_value or ""),
                    str(new_value or ""), str(action or ""),
                ),
            )
            conn.commit()
        return int(cursor.lastrowid or 0)

    def list_card_change_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        group_id: str = "",
        user_id: str = "",
        kind: str = "",
    ) -> List[dict]:
        sql = "SELECT * FROM card_change_logs WHERE 1=1"
        params: List[object] = []
        if group_id:
            sql += " AND group_id=?"
            params.append(str(group_id))
        if user_id:
            sql += " AND user_id=?"
            params.append(str(user_id))
        if kind:
            sql += " AND kind=?"
            params.append(str(kind))
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([int(limit), int(offset)])
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": row["id"], "ts": row["ts"], "time": row["time"],
                "kind": row["kind"], "group_id": row["group_id"],
                "user_id": row["user_id"], "user_name": row["user_name"],
                "old_value": row["old_value"],
                "new_value": row["new_value"], "action": row["action"],
            }
            for row in rows
        ]

    def count_card_change_logs(
        self, group_id: str = "", user_id: str = "", kind: str = ""
    ) -> int:
        sql = "SELECT COUNT(*) AS c FROM card_change_logs WHERE 1=1"
        params: List[object] = []
        if group_id:
            sql += " AND group_id=?"
            params.append(str(group_id))
        if user_id:
            sql += " AND user_id=?"
            params.append(str(user_id))
        if kind:
            sql += " AND kind=?"
            params.append(str(kind))
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["c"] or 0)

    def clear_card_change_logs(self, group_id: str = "") -> int:
        with self._connect() as conn:
            if group_id:
                cursor = conn.execute(
                    "DELETE FROM card_change_logs WHERE group_id=?",
                    (str(group_id),),
                )
            else:
                cursor = conn.execute("DELETE FROM card_change_logs")
            conn.commit()
        return int(cursor.rowcount or 0)

    def prune_card_change_logs(self, keep: int = 5000) -> int:
        """仅保留最近 keep 条，删除更早的，防止无限增长。"""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM card_change_logs WHERE id NOT IN "
                "(SELECT id FROM card_change_logs ORDER BY id DESC LIMIT ?)",
                (int(keep),),
            )
            conn.commit()
        return int(cursor.rowcount or 0)

    def list_card_protected(self, group_id: str = "") -> List[dict]:
        with self._connect() as conn:
            if group_id:
                rows = conn.execute(
                    "SELECT group_id, user_id, protected_card, created_at "
                    "FROM card_protected_members WHERE group_id=? "
                    "ORDER BY created_at DESC",
                    (str(group_id),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT group_id, user_id, protected_card, created_at "
                    "FROM card_protected_members "
                    "ORDER BY group_id, created_at DESC"
                ).fetchall()
        return [
            {
                "group_id": row["group_id"], "user_id": row["user_id"],
                "protected_card": row["protected_card"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_card_protected(
        self, group_id: str, user_id: str
    ) -> Optional[str]:
        """返回被保护成员的应有名片；不在保护名单返回 None。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT protected_card FROM card_protected_members "
                "WHERE group_id=? AND user_id=?",
                (str(group_id), str(user_id)),
            ).fetchone()
        return row["protected_card"] if row else None

    def add_card_protected(
        self,
        group_id: str,
        user_id: str,
        protected_card: str,
        created_at: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO card_protected_members("
                "group_id, user_id, protected_card, created_at) "
                "VALUES(?, ?, ?, ?)",
                (
                    str(group_id), str(user_id), str(protected_card),
                    int(created_at),
                ),
            )
            conn.commit()

    def remove_card_protected(self, group_id: str, user_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM card_protected_members "
                "WHERE group_id=? AND user_id=?",
                (str(group_id), str(user_id)),
            )
            conn.commit()
        return bool(cursor.rowcount)
