"""SQLite operational store: source freshness, query/usage logs, hash-chained audit trail, MLR reviews and API keys.

The knowledge graph itself lives in NetworkX/Neo4j; this database holds *operational* records that must survive
restarts and be auditable. ``audit_log`` and ``finding_decisions`` are append-only (enforced by triggers).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_state (
    source TEXT PRIMARY KEY, cadence TEXT NOT NULL DEFAULT 'weekly', last_attempt TEXT, last_success TEXT,
    last_error TEXT, watermark TEXT, items INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT, role TEXT, query TEXT NOT NULL, routed_agent TEXT,
    latency_ms REAL, confidence REAL, risk_level TEXT, citations INTEGER, llm_cost_usd REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, query_id INTEGER, rating INTEGER NOT NULL, comment TEXT, actor TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT, action TEXT NOT NULL, target TEXT,
    detail TEXT, prev_hash TEXT, hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TABLE IF NOT EXISTS mlr_reviews (
    id TEXT PRIMARY KEY, ts TEXT NOT NULL, title TEXT, actor TEXT, asset_text TEXT NOT NULL, result TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS finding_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, review_id TEXT NOT NULL, finding_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accepted','rejected','revision')), rationale TEXT, reviewer TEXT
);
CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON finding_decisions BEGIN SELECT RAISE(ABORT, 'finding_decisions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON finding_decisions BEGIN SELECT RAISE(ABORT, 'finding_decisions is append-only'); END;
CREATE TABLE IF NOT EXISTS claims_library (
    normalized TEXT PRIMARY KEY, text TEXT NOT NULL, claim_type TEXT, verdict TEXT NOT NULL, confidence REAL,
    product_ids TEXT, review_id TEXT, ts TEXT NOT NULL, uses INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS label_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, product_key TEXT NOT NULL, setid TEXT, version TEXT,
    section TEXT NOT NULL, sha TEXT NOT NULL, text TEXT
);
CREATE INDEX IF NOT EXISTS label_versions_key ON label_versions(product_key, section, id);
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, tier TEXT NOT NULL DEFAULT 'standard',
    monthly_limit INTEGER NOT NULL DEFAULT 10000, created TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT, tool TEXT NOT NULL, duration_ms REAL, ok INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, provider TEXT, model TEXT, prompt_version TEXT,
    prompt_tokens INTEGER, completion_tokens INTEGER, cost_usd REAL, ok INTEGER NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class OpsDB:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    # ------------------------------------------------------------------ primitives
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, tuple(params)).fetchall()]

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------ audit (hash chained)
    def audit(self, action: str, target: Optional[str] = None, detail: Optional[Dict[str, Any]] = None, actor: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            prev = self._conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
            prev_hash = prev["hash"] if prev else "GENESIS"
            ts = utcnow()
            body = json.dumps(detail or {}, sort_keys=True, default=str)
            h = sha256("|".join([prev_hash, ts, actor or "", action, target or "", body]))
            cur = self._conn.execute("INSERT INTO audit_log (ts, actor, action, target, detail, prev_hash, hash) VALUES (?,?,?,?,?,?,?)",
                                     (ts, actor, action, target, body, prev_hash, h))
            return {"id": cur.lastrowid, "ts": ts, "hash": h}

    def verify_audit_chain(self) -> Dict[str, Any]:
        prev_hash = "GENESIS"
        rows = self.query("SELECT * FROM audit_log ORDER BY id")
        for r in rows:
            expected = sha256("|".join([prev_hash, r["ts"], r["actor"] or "", r["action"], r["target"] or "", r["detail"] or "{}"]))
            if r["prev_hash"] != prev_hash or r["hash"] != expected:
                return {"valid": False, "entries": len(rows), "broken_at": r["id"]}
            prev_hash = r["hash"]
        return {"valid": True, "entries": len(rows), "head": prev_hash}

    # ------------------------------------------------------------------ source freshness
    def mark_source(self, source: str, ok: bool, items: int = 0, error: Optional[str] = None,
                    watermark: Optional[str] = None, cadence: Optional[str] = None) -> None:
        now = utcnow()
        with self._lock:
            self._conn.execute("INSERT OR IGNORE INTO source_state (source, cadence) VALUES (?, ?)", (source, cadence or "weekly"))
            if ok:
                self._conn.execute("UPDATE source_state SET last_attempt=?, last_success=?, last_error=NULL, items=items+?, "
                                   "watermark=COALESCE(?, watermark), cadence=COALESCE(?, cadence) WHERE source=?",
                                   (now, now, items, watermark, cadence, source))
            else:
                self._conn.execute("UPDATE source_state SET last_attempt=?, last_error=?, cadence=COALESCE(?, cadence) WHERE source=?",
                                   (now, (error or "unknown error")[:500], cadence, source))

    def source_status(self) -> List[Dict[str, Any]]:
        rows = self.query("SELECT * FROM source_state ORDER BY source")
        now = time.time()
        cadence_s = {"daily": 86400, "weekly": 7 * 86400, "monthly": 30 * 86400}
        for r in rows:
            age = None
            if r["last_success"]:
                age = now - datetime.fromisoformat(r["last_success"]).timestamp()
            r["age_hours"] = round(age / 3600, 1) if age is not None else None
            r["due"] = age is None or age > cadence_s.get(r["cadence"], 7 * 86400)
            r["status"] = "error" if r["last_error"] and (not r["last_success"] or r["last_attempt"] > r["last_success"]) else (
                "stale" if r["due"] else "fresh")
        return rows

    # ------------------------------------------------------------------ query log / feedback
    def log_query(self, query: str, routed_agent: str, latency_ms: float, confidence: float, risk_level: str, citations: int,
                  actor: Optional[str] = None, role: Optional[str] = None, llm_cost_usd: float = 0.0) -> int:
        cur = self.execute("INSERT INTO query_log (ts, actor, role, query, routed_agent, latency_ms, confidence, risk_level, citations, llm_cost_usd) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (utcnow(), actor, role, query[:2000], routed_agent, latency_ms, confidence, risk_level, citations, llm_cost_usd))
        return int(cur.lastrowid)

    def add_feedback(self, query_id: Optional[int], rating: int, comment: Optional[str], actor: Optional[str]) -> int:
        cur = self.execute("INSERT INTO feedback (ts, query_id, rating, comment, actor) VALUES (?,?,?,?,?)",
                           (utcnow(), query_id, rating, (comment or "")[:2000], actor))
        return int(cur.lastrowid)

    def usage_summary(self) -> Dict[str, Any]:
        q = self.query("SELECT COUNT(*) n, AVG(latency_ms) lat, AVG(confidence) conf, SUM(llm_cost_usd) cost, "
                       "COUNT(DISTINCT actor) users FROM query_log")[0]
        by_agent = self.query("SELECT routed_agent, COUNT(*) n FROM query_log GROUP BY routed_agent ORDER BY n DESC")
        by_risk = self.query("SELECT risk_level, COUNT(*) n FROM query_log GROUP BY risk_level")
        fb = self.query("SELECT COUNT(*) n, SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END) pos FROM feedback")[0]
        daily = self.query("SELECT substr(ts,1,10) day, COUNT(*) n FROM query_log GROUP BY day ORDER BY day DESC LIMIT 14")
        tools = self.query("SELECT tool, COUNT(*) n, AVG(duration_ms) avg_ms, SUM(1-ok) errors FROM tool_calls GROUP BY tool ORDER BY n DESC")
        llm = self.query("SELECT provider, model, COUNT(*) calls, SUM(prompt_tokens) prompt_tokens, SUM(completion_tokens) completion_tokens, "
                         "SUM(cost_usd) cost_usd FROM llm_usage GROUP BY provider, model")
        reviews = self.query("SELECT COUNT(*) n FROM mlr_reviews")[0]["n"]
        decisions = self.query("SELECT decision, COUNT(*) n FROM finding_decisions GROUP BY decision")
        return {
            "queries": q["n"] or 0,
            "unique_users": q["users"] or 0,
            "avg_latency_ms": round(q["lat"] or 0.0, 1),
            "avg_confidence": round(q["conf"] or 0.0, 3),
            "llm_cost_usd": round(q["cost"] or 0.0, 4),
            "by_agent": by_agent,
            "by_risk": by_risk,
            "feedback": {"total": fb["n"] or 0, "positive": fb["pos"] or 0,
                         "satisfaction_pct": round(100.0 * (fb["pos"] or 0) / fb["n"], 1) if fb["n"] else None},
            "daily": daily,
            "tool_calls": tools,
            "llm_usage": llm,
            "mlr_reviews": reviews,
            "mlr_decisions": decisions,
        }

    # ------------------------------------------------------------------ metering
    def log_tool_call(self, tool: str, duration_ms: float, ok: bool, actor: Optional[str] = None) -> None:
        self.execute("INSERT INTO tool_calls (ts, actor, tool, duration_ms, ok) VALUES (?,?,?,?,?)",
                     (utcnow(), actor, tool, round(duration_ms, 2), 1 if ok else 0))

    def log_llm_usage(self, provider: str, model: str, prompt_version: str, prompt_tokens: int, completion_tokens: int,
                      cost_usd: float, ok: bool) -> None:
        self.execute("INSERT INTO llm_usage (ts, provider, model, prompt_version, prompt_tokens, completion_tokens, cost_usd, ok) "
                     "VALUES (?,?,?,?,?,?,?,?)", (utcnow(), provider, model, prompt_version, prompt_tokens, completion_tokens, cost_usd, 1 if ok else 0))

    def monthly_calls(self, actor: str) -> int:
        month = utcnow()[:7]
        return int(self.query("SELECT COUNT(*) n FROM tool_calls WHERE actor=? AND substr(ts,1,7)=?", (actor, month))[0]["n"])


_db: Optional[OpsDB] = None
_db_lock = threading.Lock()


def get_db() -> OpsDB:
    global _db
    with _db_lock:
        if _db is None:
            from app.config import get_settings

            _db = OpsDB(get_settings().ops_db_path)
        return _db


def set_db(db: OpsDB) -> None:
    global _db
    with _db_lock:
        _db = db
