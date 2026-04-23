"""SQLite 数据库 - 多用户档案存储（替代原单用户 JSON 文件）"""
import os
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "bazi_api.db"
))

_SQL_INIT = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT    UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_premium INTEGER DEFAULT 0,
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
    id         TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    category   TEXT    NOT NULL,
    gender     INTEGER NOT NULL,
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    day        INTEGER NOT NULL,
    hour       INTEGER NOT NULL,
    minute     INTEGER NOT NULL,
    longitude  REAL,
    province   TEXT    DEFAULT '',
    city       TEXT    DEFAULT '',
    district   TEXT    DEFAULT '',
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    action     TEXT    NOT NULL,
    detail     TEXT    DEFAULT '',
    created_at TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    category   TEXT    DEFAULT '建议',
    content    TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ai_predictions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    type       TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    detail     TEXT    DEFAULT '',
    created_at TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(_SQL_INIT)
    conn.commit()
    conn.close()


# ── 用户操作 ──

def get_user_by_username(conn, username: str):
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    return dict(row) if row else None


def get_user_id_by_name(conn, username: str):
    row = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    return row["id"] if row else None


def create_user(conn, username: str, password_hash: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, now),
    )
    conn.commit()


# ── 档案操作（接口对齐原 bazi_db.py，增加 user_id 隔离） ──

_RECORD_COLS = (
    "name", "category", "gender", "year", "month", "day",
    "hour", "minute", "longitude", "province", "city", "district",
)


def get_record_count(conn, user_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM records WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row["cnt"]


def get_records_by_user(conn, user_id: int, category: str = None):
    if category and category != "全部":
        rows = conn.execute(
            "SELECT * FROM records WHERE user_id=? AND category=? ORDER BY created_at DESC",
            (user_id, category),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM records WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_record_db(
    conn, user_id: int,
    name: str, category: str, gender: int,
    year: int, month: int, day: int, hour: int, minute: int,
    longitude: float = None, province: str = "", city: str = "", district: str = "",
) -> str:
    """添加记录，同名覆盖（与原 bazi_db.py 行为一致）"""
    now = datetime.now(timezone.utc).isoformat()

    existing = conn.execute(
        "SELECT id FROM records WHERE user_id=? AND name=?", (user_id, name)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE records SET category=?, gender=?, year=?, month=?, day=?,
               hour=?, minute=?, longitude=?, province=?, city=?, district=?,
               updated_at=? WHERE id=?""",
            (category, gender, year, month, day, hour, minute, longitude,
             province, city, district, now, existing["id"]),
        )
        conn.commit()
        return existing["id"]

    record_id = uuid.uuid4().hex[:8]
    conn.execute(
        """INSERT INTO records
           (id, user_id, name, category, gender, year, month, day,
            hour, minute, longitude, province, city, district, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (record_id, user_id, name, category, gender, year, month, day,
         hour, minute, longitude, province, city, district, now, now),
    )
    conn.commit()
    return record_id


def update_record_db(conn, record_id: str, user_id: int, **kwargs):
    """更新记录（白名单字段）"""
    updates = {k: v for k, v in kwargs.items() if k in _RECORD_COLS}
    if not updates:
        return
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [record_id, user_id]
    conn.execute(f"UPDATE records SET {set_clause} WHERE id=? AND user_id=?", values)
    conn.commit()


def delete_record_db(conn, record_id: str, user_id: int):
    conn.execute(
        "DELETE FROM records WHERE id=? AND user_id=?", (record_id, user_id)
    )
    conn.commit()


def get_record_by_id_db(conn, record_id: str, user_id: int):
    row = conn.execute(
        "SELECT * FROM records WHERE id=? AND user_id=?",
        (record_id, user_id),
    ).fetchone()
    return dict(row) if row else None


# ── 操作日志 ──

def log_action(conn, user_id: int, action: str, detail: str = ""):
    """记录用户操作"""
    conn.execute(
        "INSERT INTO operation_logs (user_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
        (user_id, action, detail, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# ── 用户反馈 ──

FEEDBACK_CATEGORIES = ["Bug反馈", "功能建议", "内容纠错", "体验优化", "其他"]


def add_feedback(conn, user_id: int, category: str, content: str):
    """提交用户反馈"""
    conn.execute(
        "INSERT INTO feedback (user_id, category, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, category, content, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# ── AI 预测记录 ──

PREDICTION_TYPES = ["deep_analysis", "analyze", "predict", "match", "divination", "qa"]

PREDICTION_TYPE_LABELS = {
    "deep_analysis": "深度分析",
    "analyze": "命理分析",
    "predict": "大运流年",
    "match": "八字匹配",
    "divination": "数字起卦",
    "qa": "知识问答",
}


def add_prediction(conn, user_id: int, pred_type: str, title: str, content: str, detail: str = ""):
    """保存 AI 预测结果"""
    conn.execute(
        "INSERT INTO ai_predictions (user_id, type, title, content, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, pred_type, title, content, detail, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_predictions_by_user(conn, user_id: int, pred_type: str = None):
    """查询用户的预测记录"""
    if pred_type:
        rows = conn.execute(
            "SELECT * FROM ai_predictions WHERE user_id=? AND type=? ORDER BY created_at DESC",
            (user_id, pred_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM ai_predictions WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_prediction(conn, prediction_id: int, user_id: int):
    conn.execute(
        "DELETE FROM ai_predictions WHERE id=? AND user_id=?", (prediction_id, user_id)
    )
    conn.commit()
