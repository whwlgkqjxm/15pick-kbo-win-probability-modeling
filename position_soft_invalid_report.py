# position_soft_invalid_report.py
"""
MyPick 포지션 불일치 0점 처리 리포트.

용도:
- 팀 일별 점수 재계산 후, 포지션 불일치로 0점 처리된 선수 스냅샷을 확인합니다.
- DB를 수정하지 않습니다.
"""

from __future__ import annotations

import argparse
import sqlite3
from db import DB_PATH, init_db, get_conn


def one(conn: sqlite3.Connection, sql: str, params: tuple = ()):  # noqa: ANN001
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return row[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="포지션 불일치 0점 처리 스냅샷을 확인합니다.")
    parser.add_argument("--date", help="확인할 경기일. 생략하면 최신 팀 점수 날짜를 사용합니다.")
    parser.add_argument("--limit", type=int, default=30, help="상세 출력 최대 행 수")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    init_db()

    with get_conn() as conn:
        print("=" * 80)
        print("MyPick 포지션 불일치 0점 처리 리포트")
        print("=" * 80)
        print("DB:", DB_PATH)
        print("integrity_check:", one(conn, "PRAGMA integrity_check"))

        game_date = args.date or one(conn, "SELECT MAX(game_date) FROM fantasy_team_daily_scores")
        print("game_date:", game_date)

        if not game_date:
            print("팀 일별 점수 기록이 없습니다.")
            return

        print("team_daily_scores:", one(conn, "SELECT COUNT(*) FROM fantasy_team_daily_scores WHERE game_date = ?", (game_date,)))
        print("team_daily_player_scores:", one(conn, "SELECT COUNT(*) FROM fantasy_team_daily_player_scores WHERE game_date = ?", (game_date,)))
        print("position_mismatch_zero_rows:", one(conn, """
            SELECT COUNT(*)
            FROM fantasy_team_daily_player_scores
            WHERE game_date = ?
              AND COALESCE(is_position_eligible, 1) = 0
              AND COALESCE(points, 0) = 0
        """, (game_date,)))
        print("position_mismatch_nonzero_rows:", one(conn, """
            SELECT COUNT(*)
            FROM fantasy_team_daily_player_scores
            WHERE game_date = ?
              AND COALESCE(is_position_eligible, 1) = 0
              AND ABS(COALESCE(points, 0)) > 0.0001
        """, (game_date,)))

        print()
        print("[팀별 포지션 불일치 0점 수]")
        rows = conn.execute("""
            SELECT
                t.team_id,
                t.team_name_snapshot,
                COUNT(p.id) AS mismatch_count
            FROM fantasy_team_daily_scores t
            LEFT JOIN fantasy_team_daily_player_scores p
              ON p.team_daily_score_id = t.id
             AND COALESCE(p.is_position_eligible, 1) = 0
            WHERE t.game_date = ?
            GROUP BY t.team_id, t.team_name_snapshot
            HAVING mismatch_count > 0
            ORDER BY mismatch_count DESC, t.team_id
        """, (game_date,)).fetchall()
        if rows:
            for row in rows:
                print(dict(row))
        else:
            print("없음")

        print()
        print("[상세]")
        rows = conn.execute("""
            SELECT
                p.team_id,
                t.team_name_snapshot,
                p.slot,
                p.player_name,
                p.player_team,
                p.position_type,
                p.slot_expected_detail_position,
                p.player_detail_position_snapshot,
                p.points,
                p.position_mismatch_reason
            FROM fantasy_team_daily_player_scores p
            JOIN fantasy_team_daily_scores t ON t.id = p.team_daily_score_id
            WHERE p.game_date = ?
              AND COALESCE(p.is_position_eligible, 1) = 0
            ORDER BY p.team_id, p.slot
            LIMIT ?
        """, (game_date, args.limit)).fetchall()
        if rows:
            for row in rows:
                print(dict(row))
        else:
            print("없음")

        print()
        print("판정 기준:")
        print("- position_mismatch_nonzero_rows는 0이어야 정상입니다.")
        print("- 포지션 불일치 선수는 해당 경기일 팀 점수에서 0점이고, 팀 전체 점수는 저장되어야 합니다.")


if __name__ == "__main__":
    main()
