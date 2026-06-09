"""MyPick 방출 수익 포인트 검증 리포트."""

import argparse
import sqlite3
from config import DB_PATH

DEFAULT_POINTS_PER_UNIT = 500
BUDGET_LIMIT = 100.0


def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return row[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    table_exists = one(conn, """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type='table'
          AND name='fantasy_team_trade_bonus_events'
    """)

    print("=" * 92)
    print("MyPick 방출 수익 포인트 리포트")
    print("=" * 92)

    if not table_exists:
        print("fantasy_team_trade_bonus_events: MISSING")
        conn.close()
        return

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(fantasy_team_trade_bonus_events)").fetchall()}
    print("fantasy_team_trade_bonus_events: OK")
    print("roster_market_value_before column:", "OK" if "roster_market_value_before" in columns else "MISSING")
    print("roster_excess_before_decimal column:", "OK" if "roster_excess_before_decimal" in columns else "MISSING")
    print("event rows:", one(conn, "SELECT COUNT(*) FROM fantasy_team_trade_bonus_events"))
    print("total bonus points:", one(conn, "SELECT COALESCE(SUM(bonus_points), 0) FROM fantasy_team_trade_bonus_events"))

    if "roster_market_value_before" not in columns or "roster_excess_before_decimal" not in columns:
        print("\n[오류] v2 컬럼이 없습니다. ./venv/bin/python db.py 를 먼저 실행하세요.")
        conn.close()
        return

    invalid_formula = one(conn, f"""
        SELECT COUNT(*)
        FROM fantasy_team_trade_bonus_events
        WHERE ABS(bonus_points - (profit_units * COALESCE(points_per_unit, {DEFAULT_POINTS_PER_UNIT}))) > 0.01
           OR ABS(realized_profit_decimal - (profit_units / 10.0)) > 0.01
           OR ABS(realized_profit_decimal - MIN(MAX(current_market_price - locked_price_decimal, 0), roster_excess_before_decimal)) > 0.01
           OR ABS(budget_refund_decimal - MAX(current_market_price - realized_profit_decimal, 0)) > 0.01
           OR realized_profit_decimal < -0.01
           OR budget_refund_decimal <= 0
           OR current_market_price <= 0
           OR locked_price_decimal <= 0
           OR roster_market_value_before < 0
           OR roster_excess_before_decimal < -0.01
    """)
    print("invalid formula rows:", invalid_formula)

    invalid_bonus_without_roster_excess = one(conn, f"""
        SELECT COUNT(*)
        FROM fantasy_team_trade_bonus_events
        WHERE bonus_points > 0
          AND roster_market_value_before <= {BUDGET_LIMIT} + 0.01
    """)
    print("roster <= 100 but bonus paid:", invalid_bonus_without_roster_excess)

    invalid_profit_limit = one(conn, """
        SELECT COUNT(*)
        FROM fantasy_team_trade_bonus_events
        WHERE realized_profit_decimal - MAX(current_market_price - locked_price_decimal, 0) > 0.01
           OR realized_profit_decimal - roster_excess_before_decimal > 0.01
    """)
    print("bonus exceeds individual profit or roster excess:", invalid_profit_limit)

    invalid_refund_formula = one(conn, """
        SELECT COUNT(*)
        FROM fantasy_team_trade_bonus_events
        WHERE ABS(budget_refund_decimal - MAX(current_market_price - realized_profit_decimal, 0)) > 0.01
    """)
    print("budget refund != current price - realized profit:", invalid_refund_formula)

    print("\n[상위 방출 수익 이벤트]")
    rows = q(conn, """
        SELECT
            event_date,
            player_name,
            player_team,
            position_type,
            roster_market_value_before,
            roster_excess_before_decimal,
            locked_price_decimal,
            current_market_price,
            budget_refund_decimal,
            realized_profit_decimal,
            bonus_points,
            user_id,
            team_id
        FROM fantasy_team_trade_bonus_events
        ORDER BY bonus_points DESC, created_at DESC, id DESC
        LIMIT ?
    """, (args.top,))

    if not rows:
        print("아직 방출 수익 포인트 이벤트가 없습니다.")
    else:
        for row in rows:
            print(dict(row))

    print("\n[판정 기준]")
    print("- invalid formula rows: 0이어야 정상")
    print("- roster <= 100 but bonus paid: 0이어야 정상")
    print("- bonus exceeds individual profit or roster excess: 0이어야 정상")
    print("- budget refund != current price - realized profit: 0이어야 정상")
    print("- 방출 수익 포인트는 방출 전 팀 가치가 100.0을 넘을 때만 발생합니다.")
    print("- 팀 가치는 방출 직전 로스터 현재가 합산이며 사용가능 예산은 포함하지 않습니다.")
    print("- realized_profit_decimal은 min(선수 개인 증가분, 방출 전 팀 가치 100.0 초과분)입니다.")
    print("- budget_refund_decimal은 current_market_price - realized_profit_decimal입니다.")
    print(f"- 신규 방출 수익 포인트는 0.1 초과분마다 {DEFAULT_POINTS_PER_UNIT}원 기준입니다.")
    print("- 기존 이벤트는 각 row의 points_per_unit으로 검증하므로 과거 200원 기준 이벤트도 그대로 유효합니다.")

    conn.close()


if __name__ == "__main__":
    main()
