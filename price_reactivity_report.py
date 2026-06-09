# price_reactivity_report.py
"""
MyPick market_daily_v3 가격 반응성 점검 리포트.

목적:
- 실제 출전/등판 없이 성적 기반 가격 상승이 발생했는지 확인
- 실제 출전/등판 없이 미출전 패널티 회복이 발생했는지 확인
- 당일/최근 역할군 성적 percentile 상위권인데 가격이 완전히 무반응이거나 하락한 케이스 확인

DB를 수정하지 않는 읽기 전용 점검 스크립트입니다.
"""

import argparse
import json
import sqlite3

BASIS_SOURCE = "market_daily_v3"


def as_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_json(value):
    try:
        return json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}


def role_event_happened(role, detail):
    if role == "batter":
        return bool(detail.get("appeared_today"))
    if role == "starting_pitcher":
        return bool(detail.get("started_today"))
    if role == "bullpen_pitcher":
        return bool(detail.get("bullpen_today"))
    return bool(detail.get("appeared_today"))


def latest_basis_date(conn):
    row = conn.execute(
        """
        SELECT MAX(basis_date) AS basis_date
        FROM player_price_adjustments
        WHERE basis_source = ?
          AND is_applied = 1
        """,
        (BASIS_SOURCE,),
    ).fetchone()
    return row["basis_date"] if row and row["basis_date"] else None


def sample_rows(rows, limit):
    for row in rows[:limit]:
        print(
            f"- {row['player_name']} / {row['team']} / {row['price_role']} | "
            f"{row['old_price_decimal']:.1f} → {row['new_price_decimal']:.1f} | "
            f"perf={row['performance_change']:.1f}, absence={row['absence_penalty_change']:.1f} | "
            f"event_pct={row.get('event_pct')}, price_pct={row.get('price_pct')}, gap={row.get('gap')} | "
            f"reason={row['reason']}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="kbo_fantasy.db")
    parser.add_argument("--basis-date", default=None)
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--min-event-pct", type=float, default=90.0)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    basis_date = args.basis_date or latest_basis_date(conn)
    if not basis_date:
        raise SystemExit("적용된 market_daily_v3 가격 변동 기록이 없습니다.")

    rows = conn.execute(
        """
        SELECT
            registered_player_id,
            player_name,
            team,
            price_role,
            old_price_decimal,
            new_price_decimal,
            performance_change,
            absence_penalty_change,
            reason,
            performance_reason_json
        FROM player_price_adjustments
        WHERE basis_source = ?
          AND basis_date = ?
          AND is_applied = 1
        ORDER BY ABS(new_price_decimal - old_price_decimal) DESC, player_name
        """,
        (BASIS_SOURCE, basis_date),
    ).fetchall()

    positive_without_event = []
    absence_recovery_without_event = []
    high_event_unchanged = []
    high_event_down = []

    for raw in rows:
        row = dict(raw)
        detail = load_json(row.get("performance_reason_json"))
        event_happened = role_event_happened(row["price_role"], detail)
        event_pct = detail.get("short_term_event_percentile")
        price_pct = detail.get("current_price_percentile")
        gap = detail.get("short_term_value_gap")
        row["event_pct"] = None if event_pct is None else round(as_float(event_pct), 2)
        row["price_pct"] = None if price_pct is None else round(as_float(price_pct), 2)
        row["gap"] = None if gap is None else round(as_float(gap), 2)

        performance_change = as_float(row.get("performance_change"))
        absence_change = as_float(row.get("absence_penalty_change"))
        total_change = as_float(row.get("new_price_decimal")) - as_float(row.get("old_price_decimal"))

        if performance_change > 0 and not event_happened:
            positive_without_event.append(row)

        if absence_change > 0 and not event_happened:
            absence_recovery_without_event.append(row)

        if event_happened and event_pct is not None and as_float(event_pct) >= args.min_event_pct:
            if abs(total_change) < 0.0001:
                high_event_unchanged.append(row)
            elif total_change < 0:
                high_event_down.append(row)

    print("=" * 92)
    print("MyPick 가격 반응성 리포트")
    print("=" * 92)
    print(f"basis_source: {BASIS_SOURCE}")
    print(f"basis_date: {basis_date}")
    print(f"adjustment rows: {len(rows)}")
    print()

    print("[핵심 오류 체크]")
    print(f"실제 출전/등판 없이 performance_change > 0: {len(positive_without_event)}")
    sample_rows(positive_without_event, args.top)
    print()
    print(f"실제 출전/등판 없이 absence_penalty_change > 0: {len(absence_recovery_without_event)}")
    sample_rows(absence_recovery_without_event, args.top)
    print()

    print("[상위 성적 반응 체크]")
    print(f"event_pct >= {args.min_event_pct:.1f}인데 가격 유지: {len(high_event_unchanged)}")
    sample_rows(high_event_unchanged, args.top)
    print()
    print(f"event_pct >= {args.min_event_pct:.1f}인데 가격 하락: {len(high_event_down)}")
    sample_rows(high_event_down, args.top)
    print()

    print("[판정 기준]")
    print("- 첫 번째와 두 번째 항목은 0이어야 정상입니다.")
    print("- 현재 MyPick 정책상 event_pct >= 기준값인데 가격 하락한 케이스도 0을 목표로 관리합니다.")
    print("- event_pct >= 기준값인데 가격 유지한 케이스는 오류는 아니지만, 많으면 가격 반응성이 약한 것입니다.")
    print("- event_pct는 타자=당일 경기 타자 percentile, 선발=최근 선발 등판 percentile, 불펜=최근 불펜 등판 percentile입니다.")

    conn.close()


if __name__ == "__main__":
    main()
