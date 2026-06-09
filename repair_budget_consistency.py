"""MyPick 팀 사용가능 예산 정합성 점검/보정 스크립트.

기본은 dry-run입니다. 실제 DB 수정은 --apply를 붙였을 때만 수행합니다.

보정 원칙:
- 팀 가치는 현재 로스터 시장가 합계이며 100.0을 초과할 수 있습니다.
- 사용가능 예산(cash_balance_decimal)은 실제 추가 영입에 사용할 수 있는 금액입니다.
- locked_price_decimal은 선수 증가분 계산 기준이며 사용가능 예산 cap으로 쓰지 않습니다.
- 방출 이벤트의 예산 회복액은 current_market_price - realized_profit_decimal입니다.
- 기존 이벤트의 예산 회복액이 부족하면 이벤트와 팀 cash_balance_decimal을 차액만큼 함께 보정합니다.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH

EPS = 0.01


def one(conn: sqlite3.Connection, sql: str, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def round1(value) -> float:
    try:
        return round(float(value or 0.0), 1)
    except (TypeError, ValueError):
        return 0.0


def expected_cash(budget_limit, locked_sum, raw_cash) -> float:
    # 새 규칙에서 사용가능 예산은 cash_balance_decimal 자체입니다.
    # locked_sum과 budget_limit은 호환용 인자로만 유지합니다.
    return round(max(0.0, round1(raw_cash)), 1)


def expected_refund(locked_price, current_price, realized_profit) -> float:
    # 방출 선수의 현재가 중 초과 수익으로 계산되지 않은 금액은 사용가능 예산으로 돌아옵니다.
    current = round1(current_price)
    realized = round1(realized_profit)
    return round(max(0.0, current - realized), 1)


def collect_team_cash_fixes(conn: sqlite3.Connection):
    rows = conn.execute(
        """
        SELECT
            ft.id AS team_id,
            ft.team_name,
            COALESCE(ft.budget_limit, 100.0) AS budget_limit,
            COALESCE(ft.cash_balance_decimal, 0.0) AS cash_balance_decimal,
            ROUND(COALESCE(SUM(COALESCE(ftp.locked_price_decimal, 0.0)), 0.0), 1) AS locked_sum
        FROM fantasy_teams ft
        LEFT JOIN fantasy_team_players ftp
          ON ftp.team_id = ft.id
        GROUP BY ft.id
        ORDER BY ft.id
        """
    ).fetchall()

    fixes = []
    for row in rows:
        current_cash = round1(row["cash_balance_decimal"])
        fixed_cash = expected_cash(row["budget_limit"], row["locked_sum"], current_cash)
        if abs(current_cash - fixed_cash) > EPS:
            fixes.append({
                "team_id": row["team_id"],
                "team_name": row["team_name"],
                "budget_limit": round1(row["budget_limit"]),
                "locked_sum": round1(row["locked_sum"]),
                "old_cash": current_cash,
                "new_cash": fixed_cash,
                "delta": round(fixed_cash - current_cash, 1),
            })
    return fixes


def collect_event_refund_fixes(conn: sqlite3.Connection):
    table_exists = one(
        conn,
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type='table' AND name='fantasy_team_trade_bonus_events'
        """,
    )
    if not table_exists:
        return []

    rows = conn.execute(
        """
        SELECT
            id,
            event_date,
            team_id,
            player_name,
            locked_price_decimal,
            current_market_price,
            budget_refund_decimal,
            realized_profit_decimal
        FROM fantasy_team_trade_bonus_events
        ORDER BY id
        """
    ).fetchall()

    fixes = []
    for row in rows:
        old_refund = round1(row["budget_refund_decimal"])
        new_refund = expected_refund(
            row["locked_price_decimal"],
            row["current_market_price"],
            row["realized_profit_decimal"],
        )
        if abs(old_refund - new_refund) > EPS:
            fixes.append({
                "event_id": row["id"],
                "event_date": row["event_date"],
                "team_id": row["team_id"],
                "player_name": row["player_name"],
                "locked_price": round1(row["locked_price_decimal"]),
                "current_price": round1(row["current_market_price"]),
                "realized_profit": round1(row["realized_profit_decimal"]),
                "old_budget_refund": old_refund,
                "new_budget_refund": new_refund,
                "delta": round(new_refund - old_refund, 1),
            })
    return fixes


def create_backup(db_path: Path) -> Path:
    backup_dir = db_path.parent / "budget_consistency_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"kbo_fantasy_before_budget_consistency_{stamp}.db"
    shutil.copy2(db_path, backup_path)
    return backup_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="실제 DB를 보정합니다. 없으면 dry-run만 합니다.")
    args = parser.parse_args()

    db_path = Path(DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    print("=" * 80)
    print("MyPick 사용가능 예산/방출 수익 정합성 점검")
    print("=" * 80)
    print("DB:", db_path)
    print("mode:", "APPLY" if args.apply else "DRY-RUN")
    print("integrity_check:", one(conn, "PRAGMA integrity_check"))

    team_fixes = collect_team_cash_fixes(conn)
    event_fixes = collect_event_refund_fixes(conn)

    print("\n[팀 cash_balance_decimal 보정 대상]")
    print("count:", len(team_fixes))
    for item in team_fixes:
        print(item)

    print("\n[방출 수익 이벤트 budget_refund_decimal 보정 대상]")
    print("count:", len(event_fixes))
    for item in event_fixes:
        print(item)

    if not args.apply:
        print("\nDRY-RUN 완료. 실제 DB는 수정하지 않았습니다.")
        print("실제 보정하려면: ./venv/bin/python repair_budget_consistency.py --apply")
        conn.close()
        return

    backup_path = create_backup(db_path)
    print("\n백업 생성:", backup_path)

    try:
        with conn:
            for item in team_fixes:
                conn.execute(
                    """
                    UPDATE fantasy_teams
                    SET cash_balance_decimal = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (item["new_cash"], item["team_id"]),
                )
            for item in event_fixes:
                conn.execute(
                    """
                    UPDATE fantasy_team_trade_bonus_events
                    SET budget_refund_decimal = ?
                    WHERE id = ?
                    """,
                    (item["new_budget_refund"], item["event_id"]),
                )
                if abs(float(item.get("delta") or 0.0)) > EPS:
                    conn.execute(
                        """
                        UPDATE fantasy_teams
                        SET cash_balance_decimal = ROUND(COALESCE(cash_balance_decimal, 0.0) + ?, 1),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (item["delta"], item["team_id"]),
                    )
    except Exception:
        conn.close()
        shutil.copy2(backup_path, db_path)
        raise

    remaining_team_fixes = collect_team_cash_fixes(conn)
    remaining_event_fixes = collect_event_refund_fixes(conn)
    integrity = one(conn, "PRAGMA integrity_check")
    conn.close()

    print("\n적용 완료")
    print("integrity_check:", integrity)
    print("remaining team cash issues:", len(remaining_team_fixes))
    print("remaining event refund issues:", len(remaining_event_fixes))

    if integrity != "ok" or remaining_team_fixes or remaining_event_fixes:
        shutil.copy2(backup_path, db_path)
        raise SystemExit("검증 실패로 백업에서 DB를 복원했습니다.")

    print("검증 통과")


if __name__ == "__main__":
    main()
