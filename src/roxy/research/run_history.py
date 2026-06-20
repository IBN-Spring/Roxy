"""RunHistory — query collection run history from the log."""

from __future__ import annotations

from typing import Any

from roxy.knowledge.store import KnowledgeStore


class RunHistory:
    """Query collection run history from the collection_log table."""

    def __init__(self, store: KnowledgeStore | None = None):
        self.store = store or KnowledgeStore()
        self.store.init_db()

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent runs grouped by run_id. Returns one summary per run."""
        rows = self.store.conn.execute(
            """SELECT
                run_id,
                MIN(started_at) as started_at,
                MAX(finished_at) as finished_at,
                COUNT(*) as feed_count,
                SUM(items_found) as total_found,
                SUM(items_new) as total_new,
                SUM(items_duplicate) as total_dup,
                SUM(CASE WHEN errors != '' THEN 1 ELSE 0 END) as error_count
            FROM collection_log
            WHERE run_id != ''
            GROUP BY run_id
            ORDER BY started_at DESC
            LIMIT ?""",
            (limit,),
        ).fetchall()

        return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get detailed results for a single run."""
        summary_row = self.store.conn.execute(
            """SELECT
                run_id,
                MIN(started_at) as started_at,
                MAX(finished_at) as finished_at,
                COUNT(*) as feed_count,
                SUM(items_found) as total_found,
                SUM(items_new) as total_new,
                SUM(items_duplicate) as total_dup,
                SUM(CASE WHEN errors != '' THEN 1 ELSE 0 END) as error_count
            FROM collection_log WHERE run_id = ?
            GROUP BY run_id""",
            (run_id,),
        ).fetchone()

        if not summary_row:
            return None

        details = self.store.conn.execute(
            """SELECT source_name, channel_name, feed_url,
                items_found, items_new, items_duplicate, errors,
                started_at, finished_at
            FROM collection_log WHERE run_id = ?
            ORDER BY started_at""",
            (run_id,),
        ).fetchall()

        return {
            **dict(summary_row),
            "feeds": [dict(r) for r in details],
        }

    def latest_run(self) -> dict[str, Any] | None:
        """Get the most recent run."""
        row = self.store.conn.execute(
            "SELECT run_id FROM collection_log WHERE run_id != '' "
            "ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return self.get_run(row["run_id"])
