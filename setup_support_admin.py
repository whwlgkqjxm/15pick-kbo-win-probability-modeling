"""
문의하기 기능용 관리자 계정을 안전하게 생성/갱신하는 스크립트입니다.

주의:
- 기존 DB를 삭제하거나 테이블을 재생성하지 않습니다.
- users.is_admin 컬럼과 support_tickets 테이블만 안전하게 보장합니다.
- 비밀번호는 평문으로 저장하지 않고 werkzeug password_hash로 저장합니다.

실행 예:
MYPICK_ADMIN_USERNAME='<관리자아이디>' \
MYPICK_ADMIN_PASSWORD='<관리자비밀번호>' \
./venv/bin/python setup_support_admin.py

주의:
- 실제 관리자 아이디/비밀번호를 코드, README, 프롬프트, 배포 ZIP에 적지 마세요.
- 이 스크립트는 입력받은 비밀번호를 평문 저장하지 않고 password_hash만 저장합니다.
"""

import argparse
import os
import sqlite3

from werkzeug.security import generate_password_hash

from db import get_conn


def add_column_if_missing(conn, table_name, column_name, column_sql):
    rows = conn.execute(f"PRAGMA table_info({table_name});").fetchall()
    columns = {row["name"] for row in rows}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql};")
        print(f"컬럼 추가 완료: {table_name}.{column_name}")


def ensure_support_schema(conn):
    add_column_if_missing(conn, "users", "is_admin", "is_admin INTEGER DEFAULT 0")
    add_column_if_missing(conn, "users", "favorite_kbo_team", "favorite_kbo_team TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            page_url TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            admin_note TEXT,
            admin_reply TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_tickets_user
        ON support_tickets(user_id, created_at DESC);
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_tickets_status
        ON support_tickets(status, created_at DESC);
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_tickets_category
        ON support_tickets(category, created_at DESC);
    """)


def ensure_admin_account(username, password):
    if not username.strip():
        raise ValueError("관리자 아이디가 비어 있습니다.")
    if not password:
        raise ValueError("관리자 비밀번호가 비어 있습니다.")

    username = username.strip()
    password_hash = generate_password_hash(password)

    with get_conn() as conn:
        ensure_support_schema(conn)

        existing = conn.execute("""
            SELECT id
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()

        if existing:
            user_id = int(existing["id"])
            conn.execute("""
                UPDATE users
                SET password_hash = ?,
                    display_name = COALESCE(NULLIF(display_name, ''), '관리자'),
                    is_admin = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (password_hash, user_id))
            print(f"관리자 계정 갱신 완료: {username} (user_id={user_id})")
        else:
            cursor = conn.execute("""
                INSERT INTO users (
                    username,
                    password_hash,
                    display_name,
                    is_admin,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, '관리자', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (username, password_hash))
            user_id = int(cursor.lastrowid)
            print(f"관리자 계정 생성 완료: {username} (user_id={user_id})")

        team = conn.execute("""
            SELECT id
            FROM fantasy_teams
            WHERE user_id = ?
            LIMIT 1
        """, (user_id,)).fetchone()

        if team is None:
            conn.execute("""
                INSERT INTO fantasy_teams (
                    user_id,
                    team_name,
                    budget_limit,
                    cash_balance_decimal,
                    is_confirmed,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, 100, 100.0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (user_id, f"{username}의 팀"))
            print("관리자 기본 팀 생성 완료")

        admin_check = conn.execute("""
            SELECT username, is_admin
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()
        print(f"확인: {admin_check['username']} / is_admin={admin_check['is_admin']}")


def main():
    parser = argparse.ArgumentParser(description="MyPick 문의 관리용 관리자 계정을 생성/갱신합니다.")
    parser.add_argument("--username", default=os.environ.get("MYPICK_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("MYPICK_ADMIN_PASSWORD"))
    args = parser.parse_args()

    if not args.username:
        raise SystemExit(
            "MYPICK_ADMIN_USERNAME 환경변수 또는 --username 인자로 관리자 아이디를 넣어주세요."
        )

    if not args.password:
        raise SystemExit(
            "MYPICK_ADMIN_PASSWORD 환경변수 또는 --password 인자로 관리자 비밀번호를 넣어주세요."
        )

    if len(args.password) < 8:
        raise SystemExit("관리자 비밀번호는 최소 8글자 이상이어야 합니다.")

    try:
        ensure_admin_account(args.username, args.password)
    except sqlite3.Error as exc:
        raise SystemExit(f"DB 작업 실패: {exc}") from exc


if __name__ == "__main__":
    main()
