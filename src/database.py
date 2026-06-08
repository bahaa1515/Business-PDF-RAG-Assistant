"""SQLite-based chat history persistence."""
import os
import sqlite3
import json
from datetime import datetime
from src.config import DATA_DIR, CHAT_DB_PATH


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(CHAT_DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            question TEXT,
            answer TEXT,
            sources_json TEXT,
            latency_seconds REAL,
            chunk_size INTEGER,
            chunk_overlap INTEGER,
            top_k INTEGER,
            retrieval_method TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def log_chat(item: dict):
    """Store a chat interaction in the DB. Expects keys matching table columns."""
    init_db()
    conn = sqlite3.connect(CHAT_DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO chat_logs (
            timestamp, question, answer, sources_json, latency_seconds,
            chunk_size, chunk_overlap, top_k, retrieval_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.get("timestamp", datetime.utcnow().isoformat()),
            item.get("question"),
            item.get("answer"),
            json.dumps(item.get("sources", [])),
            item.get("latency_seconds"),
            item.get("chunk_size"),
            item.get("chunk_overlap"),
            item.get("top_k"),
            item.get("retrieval_method"),
        ),
    )
    conn.commit()
    conn.close()


def get_recent_logs(limit: int = 50) -> list[dict]:
    init_db()
    conn = sqlite3.connect(CHAT_DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, timestamp, question, answer, sources_json, latency_seconds, chunk_size, chunk_overlap, top_k, retrieval_method FROM chat_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = c.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append(
            {
                "id": r[0],
                "timestamp": r[1],
                "question": r[2],
                "answer": r[3],
                "sources": json.loads(r[4]) if r[4] else [],
                "latency_seconds": r[5],
                "chunk_size": r[6],
                "chunk_overlap": r[7],
                "top_k": r[8],
                "retrieval_method": r[9],
            }
        )

    return results


def clear_logs():
    init_db()
    conn = sqlite3.connect(CHAT_DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chat_logs")
    conn.commit()
    conn.close()
