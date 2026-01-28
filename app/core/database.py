# app/core/database.py
"""DB 연결 및 연결 성공 시 콘솔 메시지 출력."""
import re
from datetime import datetime
from typing import Optional

from app.core.config import settings

# SQLite용 파일 경로 (sqlite:///./name.db -> ./name.db)
_db_path: Optional[str] = None
_connection = None


def _db_path_from_url() -> str:
    url = settings.DATABASE_URL or "sqlite:///./puppytalk.db"
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    return "./puppytalk.db"


def get_connection():
    """SQLite 연결 반환 (로깅·헬스체크용)."""
    global _connection
    if _connection is not None:
        return _connection
    import sqlite3

    path = _db_path_from_url()
    _connection = sqlite3.connect(path, check_same_thread=False)
    return _connection


def init_database() -> bool:
    """DB 연결 후 콘솔에 '데이터베이스 연결 성공' 출력."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{ts}] 데이터베이스 연결 성공"
        print(msg, flush=True)
        return True
    except Exception as e:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] 데이터베이스 연결 실패: {e}", flush=True)
        return False


def close_database() -> None:
    """연결 종료."""
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except Exception:
            pass
        _connection = None


def sql_for_request(method: str, path: str) -> Optional[str]:
    """요청 (method, path)에 대응하는 API 동작의 대표 SQL 문 반환."""
    base = path.split("?")[0] if path else ""

    # Auth
    if method == "POST" and base == "/auth/signup":
        return "INSERT INTO users (email, password, nickname, profileImageUrl, createdAt) VALUES (?, ?, ?, ?, ?)"
    if method == "POST" and base == "/auth/login":
        return "SELECT * FROM users WHERE email = ?"
    if method == "GET" and base == "/auth/me":
        return "SELECT userId, email, nickname, profileImageUrl FROM users WHERE userId = ?"
    if method == "POST" and base == "/auth/logout":
        return "DELETE FROM sessions WHERE session_id = ?"

    # Posts
    if method == "GET" and (base == "/posts" or base.rstrip("/") == "/posts"):
        return "SELECT * FROM posts ORDER BY createdAt DESC LIMIT ? OFFSET ?"
    if method == "GET" and re.match(r"^/posts/\d+$", base):
        return "SELECT * FROM posts WHERE postId = ?"
    if method == "POST" and base == "/posts":
        return "INSERT INTO posts (title, content, authorId, fileUrl, likeCount, createdAt) VALUES (?, ?, ?, ?, 0, ?)"
    if method == "POST" and re.match(r"^/posts/\d+/image$", base):
        return "UPDATE posts SET fileUrl = ? WHERE postId = ?"
    if method == "PATCH" and re.match(r"^/posts/\d+$", base):
        return "UPDATE posts SET title = ?, content = ?, fileUrl = ?, updatedAt = ? WHERE postId = ?"
    if method == "DELETE" and re.match(r"^/posts/\d+$", base):
        return "DELETE FROM posts WHERE postId = ?"

    # Comments (prefix /posts/{id}/comments)
    if method == "GET" and re.match(r"^/posts/\d+/comments$", base):
        return "SELECT * FROM comments WHERE postId = ? ORDER BY createdAt DESC LIMIT ? OFFSET ?"
    if method == "POST" and re.match(r"^/posts/\d+/comments$", base):
        return "INSERT INTO comments (postId, content, authorId, createdAt) VALUES (?, ?, ?, ?)"
    if method == "PATCH" and re.match(r"^/posts/\d+/comments/\d+$", base):
        return "UPDATE comments SET content = ? WHERE commentId = ?"
    if method == "DELETE" and re.match(r"^/posts/\d+/comments/\d+$", base):
        return "DELETE FROM comments WHERE commentId = ?"

    # Likes
    if method == "POST" and re.match(r"^/posts/\d+/likes$", base):
        return "INSERT INTO likes (postId, userId) VALUES (?, ?)"
    if method == "DELETE" and re.match(r"^/posts/\d+/likes$", base):
        return "DELETE FROM likes WHERE postId = ? AND userId = ?"

    # Users
    if method == "GET" and base == "/users/check-email":
        return "SELECT userId FROM users WHERE email = ?"
    if method == "GET" and base == "/users/check-nickname":
        return "SELECT userId FROM users WHERE nickname = ?"
    if method == "GET" and re.match(r"^/users/\d+$", base):
        return "SELECT userId, email, nickname, profileImageUrl, createdAt FROM users WHERE userId = ?"
    if method == "PATCH" and re.match(r"^/users/\d+$", base):
        return "UPDATE users SET nickname = ?, profileImageUrl = ? WHERE userId = ?"
    if method == "PATCH" and re.match(r"^/users/\d+/password$", base):
        return "UPDATE users SET password = ? WHERE userId = ?"
    if method == "DELETE" and re.match(r"^/users/\d+$", base):
        return "DELETE FROM users WHERE userId = ?"
    if method == "POST" and re.match(r"^/users/\d+/profile-image$", base):
        return "UPDATE users SET profileImageUrl = ? WHERE userId = ?"

    return None
