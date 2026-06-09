"""
MyPick 투수 역할 정합성 점검/보정 스크립트.

정책:
- 투수가 한 번이라도 선발 등판하면 선발투수로 분류됩니다.
- 이후 시간이 오래 지나도 자동으로 불펜투수로 강등하지 않습니다.
- 실제 불펜 등판(raw_pitcher_stats.is_starting_pitcher=0)이 가장 최근 등판으로 확인될 때만 불펜투수로 바뀝니다.

이 스크립트는 registered_players.detail_position만 보정합니다.
player_prices 가격 history는 수정하지 않습니다.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from db import DB_PATH


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def one(conn: sqlite3.Connection, sql: str, params=()):
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return row[0]


def find_latest_role_mismatches(conn: sqlite3.Connection, basis_date: str | None = None):
    if basis_date is None:
        basis_date = one(conn, "SELECT MAX(game_date) FROM raw_pitcher_stats")

    rows = conn.execute(
        """
        WITH latest_appearances AS (
            SELECT
                rp.id AS registered_player_id,
                rp.name AS player_name,
                rp.team,
                rp.detail_position AS old_detail_position,
                rp.detail_position_source AS old_detail_position_source,
                rps.game_date AS last_pitching_date,
                COALESCE(rps.pitching_order, 999) AS last_pitching_order,
                COALESCE(rps.is_starting_pitcher, 0) AS last_is_starting_pitcher,
                CASE
                    WHEN COALESCE(rps.is_starting_pitcher, 0) = 1 THEN '선발투수'
                    ELSE '불펜투수'
                END AS new_detail_position,
                ROW_NUMBER() OVER (
                    PARTITION BY rp.id
                    ORDER BY rps.game_date DESC, COALESCE(rps.pitching_order, 999) DESC, rps.game_id DESC
                ) AS rn
            FROM registered_players rp
            JOIN raw_pitcher_stats rps
              ON rps.player_name = rp.name
             AND rps.team = rp.team
            WHERE rp.fantasy_position_type = 'pitcher'
              AND rp.is_active = 1
              AND rps.game_date <= ?
        )
        SELECT *
        FROM latest_appearances
        WHERE rn = 1
          AND COALESCE(old_detail_position, '') != new_detail_position
        ORDER BY team, player_name
        """,
        (basis_date,),
    ).fetchall()
    return basis_date, [dict(row) for row in rows]


def find_latest_price_role_mismatches(conn: sqlite3.Connection, basis_date: str | None = None):
    latest_price_date = one(
        conn,
        """
        SELECT MAX(basis_date)
        FROM player_prices
        WHERE basis_source='market_daily_v3'
        """,
    )
    if latest_price_date is None:
        return None, []
    if basis_date is None:
        basis_date = latest_price_date

    rows = conn.execute(
        """
        WITH latest_appearances AS (
            SELECT
                rp.id AS registered_player_id,
                rp.name AS player_name,
                rp.team,
                rps.game_date AS last_pitching_date,
                COALESCE(rps.pitching_order, 999) AS last_pitching_order,
                COALESCE(rps.is_starting_pitcher, 0) AS last_is_starting_pitcher,
                CASE
                    WHEN COALESCE(rps.is_starting_pitcher, 0) = 1 THEN 'starting_pitcher'
                    ELSE 'bullpen_pitcher'
                END AS expected_price_role,
                ROW_NUMBER() OVER (
                    PARTITION BY rp.id
                    ORDER BY rps.game_date DESC, COALESCE(rps.pitching_order, 999) DESC, rps.game_id DESC
                ) AS rn
            FROM registered_players rp
            JOIN raw_pitcher_stats rps
              ON rps.player_name = rp.name
             AND rps.team = rp.team
            WHERE rp.fantasy_position_type = 'pitcher'
              AND rp.is_active = 1
              AND rps.game_date <= ?
        )
        SELECT
            la.registered_player_id,
            la.player_name,
            la.team,
            la.last_pitching_date,
            la.last_pitching_order,
            la.last_is_starting_pitcher,
            pp.basis_date AS price_date,
            pp.price_role AS old_price_role,
            la.expected_price_role
        FROM latest_appearances la
        JOIN player_prices pp
          ON pp.registered_player_id = la.registered_player_id
         AND pp.basis_source = 'market_daily_v3'
         AND pp.basis_date = ?
        WHERE la.rn = 1
          AND pp.price_role != la.expected_price_role
        ORDER BY la.team, la.player_name
        """,
        (basis_date, latest_price_date),
    ).fetchall()
    return latest_price_date, [dict(row) for row in rows]


def apply_detail_position_updates(conn: sqlite3.Connection, rows: list[dict]) -> int:
    changed = 0
    for row in rows:
        cursor = conn.execute(
            """
            UPDATE registered_players
            SET detail_position = ?,
                detail_position_source = 'latest_actual_pitching_role_repair',
                detail_position_updated_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND fantasy_position_type = 'pitcher'
              AND is_active = 1
            """,
            (row["new_detail_position"], row["registered_player_id"]),
        )
        changed += cursor.rowcount
    return changed


def create_backup(db_path: str) -> Path:
    backup_dir = Path("pitcher_role_backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"kbo_fantasy_before_pitcher_role_repair_{stamp}.db"
    shutil.copy2(db_path, backup_path)
    return backup_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--basis-date", default=None, help="YYYY-MM-DD. 생략 시 raw_pitcher_stats 최신 날짜")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    print("=" * 80)
    print("MyPick 투수 역할 정합성 점검")
    print("=" * 80)
    print("DB:", args.db)
    print("mode:", "APPLY" if args.apply else "DRY-RUN")

    conn = connect(args.db)
    try:
        print("integrity_check:", one(conn, "PRAGMA integrity_check"))
        basis_date, role_mismatches = find_latest_role_mismatches(conn, args.basis_date)
        print("basis_date:", basis_date)
        print()
        print("[registered_players.detail_position 보정 대상]")
        print("count:", len(role_mismatches))
        for row in role_mismatches:
            print({
                "registered_player_id": row["registered_player_id"],
                "player_name": row["player_name"],
                "team": row["team"],
                "last_pitching_date": row["last_pitching_date"],
                "last_pitching_order": row["last_pitching_order"],
                "last_is_starting_pitcher": row["last_is_starting_pitcher"],
                "old_detail_position": row["old_detail_position"],
                "new_detail_position": row["new_detail_position"],
            })

        latest_price_date, price_mismatches = find_latest_price_role_mismatches(conn, basis_date)
        print()
        print("[참고: 최신 market_daily_v3 price_role 불일치]")
        print("latest_price_date:", latest_price_date)
        print("count:", len(price_mismatches))
        for row in price_mismatches:
            print(row)
        print("주의: 이 스크립트는 가격 history를 직접 수정하지 않습니다. 다음 가격 재계산/업데이트부터 새 역할 기준이 적용됩니다.")

        if not args.apply:
            print()
            print("DRY-RUN 완료. 실제 DB는 수정하지 않았습니다.")
            print("실제 보정하려면: ./venv/bin/python repair_pitcher_roles_by_appearance.py --apply")
            return

        backup_path = create_backup(args.db)
        print()
        print("백업 생성:", backup_path.resolve())
        changed = apply_detail_position_updates(conn, role_mismatches)
        conn.commit()
        print("적용 완료")
        print("updated detail_position rows:", changed)
        print("integrity_check:", one(conn, "PRAGMA integrity_check"))

        _, remaining = find_latest_role_mismatches(conn, basis_date)
        print("remaining detail_position issues:", len(remaining))
        if remaining:
            raise SystemExit("검증 실패: 남은 투수 역할 보정 대상이 있습니다.")
        print("검증 통과")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
