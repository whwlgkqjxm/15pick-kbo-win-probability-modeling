"""타자 상세 포지션 해소 상태 리포트.

목적:
- 내야수/외야수 broad 포지션으로 남은 선수를 확인합니다.
- 지명타자(DH-only)로 판정된 선수를 확인합니다.
- raw_batter_stats의 선발 라인업 포지션 컬럼이 얼마나 채워졌는지 확인합니다.
- 실제 DB를 수정하지 않습니다.
"""

import argparse
import sqlite3
from pathlib import Path

from db import init_db

DB_PATH = Path(__file__).resolve().parent / "kbo_fantasy.db"

DETAIL_POSITIONS = ("포수", "1루수", "2루수", "3루수", "유격수", "좌익수", "중견수", "우익수")
BROAD_POSITIONS = ("내야수", "외야수")
DH_ONLY_POSITIONS = ("지명타자",)


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_has_column(conn, table, column):
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def print_rows(rows):
    for row in rows:
        print(dict(row))


def main():
    parser = argparse.ArgumentParser(description="MyPick 타자 상세 포지션 해소 리포트")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    init_db()

    with connect() as conn:
        print("=" * 80)
        print("MyPick 타자 상세 포지션 해소 리포트")
        print("=" * 80)
        print("DB:", DB_PATH)
        print("integrity_check:", conn.execute("PRAGMA integrity_check").fetchone()[0])
        print()

        total_active_batters = conn.execute("""
            SELECT COUNT(*) FROM registered_players
            WHERE is_active = 1 AND fantasy_position_type = 'batter'
        """).fetchone()[0]
        detail_count = conn.execute(f"""
            SELECT COUNT(*) FROM registered_players
            WHERE is_active = 1
              AND fantasy_position_type = 'batter'
              AND detail_position IN ({','.join(['?'] * len(DETAIL_POSITIONS))})
        """, DETAIL_POSITIONS).fetchone()[0]
        broad_count = conn.execute(f"""
            SELECT COUNT(*) FROM registered_players
            WHERE is_active = 1
              AND fantasy_position_type = 'batter'
              AND detail_position IN ({','.join(['?'] * len(BROAD_POSITIONS))})
        """, BROAD_POSITIONS).fetchone()[0]
        dh_only_count = conn.execute("""
            SELECT COUNT(*) FROM registered_players
            WHERE is_active = 1
              AND fantasy_position_type = 'batter'
              AND detail_position = '지명타자'
        """).fetchone()[0]
        missing_count = conn.execute("""
            SELECT COUNT(*) FROM registered_players
            WHERE is_active = 1
              AND fantasy_position_type = 'batter'
              AND (detail_position IS NULL OR detail_position = '' OR detail_position = '미등록')
        """).fetchone()[0]

        print("[요약]")
        print("active_batters:", total_active_batters)
        print("detail_position_resolved:", detail_count)
        print("broad_position_remaining:", broad_count)
        print("dh_only_position:", dh_only_count)
        print("missing_position:", missing_count)
        print()

        print("[active 타자 detail_position 분포]")
        for row in conn.execute("""
            SELECT COALESCE(detail_position, 'NULL') AS detail_position, COUNT(*) AS cnt
            FROM registered_players
            WHERE is_active = 1 AND fantasy_position_type = 'batter'
            GROUP BY COALESCE(detail_position, 'NULL')
            ORDER BY
                CASE detail_position
                    WHEN '포수' THEN 1
                    WHEN '1루수' THEN 2
                    WHEN '2루수' THEN 3
                    WHEN '3루수' THEN 4
                    WHEN '유격수' THEN 5
                    WHEN '내야수' THEN 6
                    WHEN '좌익수' THEN 7
                    WHEN '중견수' THEN 8
                    WHEN '우익수' THEN 9
                    WHEN '외야수' THEN 10
                    WHEN '지명타자' THEN 11
                    ELSE 99
                END,
                detail_position
        """):
            print(dict(row))
        print()

        has_start_cols = all(
            table_has_column(conn, "raw_batter_stats", col)
            for col in ["batting_order", "starting_detail_position", "is_starting_batter"]
        )
        print("[raw_batter_stats 선발 라인업 포지션 컬럼]")
        print("columns_ready:", has_start_cols)
        if has_start_cols:
            row = conn.execute("""
                SELECT
                    COUNT(*) AS raw_rows,
                    SUM(CASE WHEN COALESCE(is_starting_batter, 0) = 1 THEN 1 ELSE 0 END) AS starting_rows,
                    SUM(CASE WHEN starting_detail_position IN ('포수','1루수','2루수','3루수','유격수','좌익수','중견수','우익수') THEN 1 ELSE 0 END) AS starting_defensive_rows,
                    SUM(CASE WHEN starting_detail_position = '지명타자' THEN 1 ELSE 0 END) AS starting_dh_rows,
                    MAX(game_date) AS latest_raw_batter_date
                FROM raw_batter_stats
            """).fetchone()
            print(dict(row))
        print()

        print("[내야수/외야수로 남은 active 타자]")
        rows = conn.execute("""
            SELECT id, name, team, roster_position, detail_position, detail_position_source, detail_position_updated_at
            FROM registered_players
            WHERE is_active = 1
              AND fantasy_position_type = 'batter'
              AND detail_position IN ('내야수', '외야수')
            ORDER BY detail_position, team, name
            LIMIT ?
        """, (args.limit,)).fetchall()
        print_rows(rows)
        print()

        print("[지명타자/UTIL 전용 active 타자]")
        rows = conn.execute("""
            SELECT id, name, team, roster_position, detail_position, detail_position_source, detail_position_updated_at
            FROM registered_players
            WHERE is_active = 1
              AND fantasy_position_type = 'batter'
              AND detail_position = '지명타자'
            ORDER BY team, name
            LIMIT ?
        """, (args.limit,)).fetchall()
        print_rows(rows)
        print()

        if has_start_cols:
            print("[현재 broad 포지션이지만 선발 수비 포지션 근거가 있는 선수 후보]")
            rows = conn.execute("""
                WITH latest_def AS (
                    SELECT
                        rp.id,
                        rp.name,
                        rp.team,
                        rp.detail_position,
                        rbs.game_date,
                        rbs.starting_detail_position,
                        ROW_NUMBER() OVER (
                            PARTITION BY rp.id
                            ORDER BY rbs.game_date DESC, rbs.game_id DESC
                        ) AS rn
                    FROM registered_players rp
                    JOIN raw_batter_stats rbs
                      ON rbs.player_name = rp.name
                     AND rbs.team = rp.team
                    WHERE rp.is_active = 1
                      AND rp.fantasy_position_type = 'batter'
                      AND rp.detail_position IN ('내야수', '외야수')
                      AND COALESCE(rbs.is_starting_batter, 0) = 1
                      AND rbs.starting_detail_position IN ('포수','1루수','2루수','3루수','유격수','좌익수','중견수','우익수')
                )
                SELECT * FROM latest_def WHERE rn = 1
                ORDER BY game_date DESC, team, name
                LIMIT ?
            """, (args.limit,)).fetchall()
            print_rows(rows)
            print()

        print("판정 기준:")
        print("- broad_position_remaining은 가능한 한 줄이는 것이 목표입니다.")
        print("- 내야수/외야수는 각각 내야/외야 슬롯 wildcard로 임시 허용됩니다.")
        print("- 지명타자는 수비 선발 기록 없이 DH 선발 기록만 있는 타자이며 UTIL만 가능합니다.")
        print("- 기존 수비 포지션이 있는 선수는 DH 선발 기록으로 지명타자로 덮어쓰지 않습니다.")


if __name__ == "__main__":
    main()
