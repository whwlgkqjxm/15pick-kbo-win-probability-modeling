# price_balance_report.py
"""
MyPick market_daily_v3 역할별 가격 밸런스 리포트입니다.

용도:
- 가격 체계 수정/rebuild 전후에 타자/선발투수/불펜투수 가격 분포를 확인합니다.
- DB를 수정하지 않는 읽기 전용 점검 스크립트입니다.

실행 예:
cd /Users/jihochoi/Desktop/kbo_fantasy_real
./venv/bin/python price_balance_report.py
./venv/bin/python price_balance_report.py --date 2026-05-20 --top 20
"""

import argparse
from statistics import mean, median

from db import get_conn

BASIS_SOURCE = "market_daily_v3"
ROLE_LABEL = {
    "batter": "타자",
    "starting_pitcher": "선발투수",
    "bullpen_pitcher": "불펜투수",
}
ROLE_ORDER = ["batter", "starting_pitcher", "bullpen_pitcher"]


def one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    if not row:
        return None
    return row[0]


def latest_price_date(conn):
    return one(
        conn,
        """
        SELECT MAX(basis_date)
        FROM player_prices
        WHERE basis_source = ?
        """,
        (BASIS_SOURCE,),
    )


def fmt(value, digits=2):
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


def role_summary(rows):
    prices = [float(row["price_decimal_effective"]) for row in rows]
    totals = [float(row["season_total"] or 0) for row in rows]
    appearances = [int(row["scored_games"] or 0) for row in rows]
    if not prices:
        return None
    return {
        "count": len(prices),
        "avg_price": mean(prices),
        "median_price": median(prices),
        "min_price": min(prices),
        "max_price": max(prices),
        "avg_total": mean(totals) if totals else 0.0,
        "median_total": median(totals) if totals else 0.0,
        "avg_games": mean(appearances) if appearances else 0.0,
    }


def load_rows(conn, basis_date):
    return conn.execute(
        """
        WITH season AS (
            SELECT
                player_name,
                team,
                position_type,
                SUM(points) AS season_total,
                COUNT(DISTINCT game_date) AS scored_games
            FROM fantasy_daily_scores
            WHERE game_date >= '2026-03-28'
              AND game_date <= ?
            GROUP BY player_name, team, position_type
        )
        SELECT
            rp.id AS registered_player_id,
            rp.name AS player_name,
            rp.team,
            rp.fantasy_position_type,
            rp.is_active,
            pp.price_role,
            COALESCE(pp.price_decimal, pp.price) AS price_decimal_effective,
            pp.price_decimal,
            pp.price,
            COALESCE(season.season_total, 0) AS season_total,
            COALESCE(season.scored_games, 0) AS scored_games
        FROM registered_players rp
        JOIN player_prices pp
          ON pp.registered_player_id = rp.id
         AND pp.basis_source = ?
         AND pp.basis_date = ?
        LEFT JOIN season
          ON season.player_name = rp.name
         AND season.team = rp.team
         AND season.position_type = rp.fantasy_position_type
        ORDER BY pp.price_role, price_decimal_effective DESC, season_total DESC, rp.team, rp.name
        """,
        (basis_date, BASIS_SOURCE, basis_date),
    ).fetchall()


def print_summary(conn, basis_date, top):
    rows = load_rows(conn, basis_date)
    active_rows = [row for row in rows if int(row["is_active"] or 0) == 1]
    inactive_rows = [row for row in rows if int(row["is_active"] or 0) == 0]

    print("=" * 92)
    print("MyPick 가격 밸런스 리포트")
    print("=" * 92)
    print("basis_source:", BASIS_SOURCE)
    print("basis_date:", basis_date)
    print("전체 가격 row:", len(rows))
    print("활성 선수 row:", len(active_rows))
    print("말소/비활성 선수 row:", len(inactive_rows))
    print()

    print("[활성 선수 역할별 분포]")
    print("역할 | 인원 | 평균가 | 중앙값 | 최저 | 최고 | 평균 시즌점수 | 중앙 시즌점수 | 평균 출전/등판")
    print("-" * 92)
    by_role = {role: [] for role in ROLE_ORDER}
    for row in active_rows:
        by_role.setdefault(row["price_role"], []).append(row)

    for role in ROLE_ORDER:
        summary = role_summary(by_role.get(role, []))
        if not summary:
            print(f"{ROLE_LABEL.get(role, role)} | 0 | - | - | - | - | - | - | -")
            continue
        print(
            f"{ROLE_LABEL.get(role, role)} | "
            f"{summary['count']} | "
            f"{fmt(summary['avg_price'], 2)} | "
            f"{fmt(summary['median_price'], 2)} | "
            f"{fmt(summary['min_price'], 1)} | "
            f"{fmt(summary['max_price'], 1)} | "
            f"{fmt(summary['avg_total'], 1)} | "
            f"{fmt(summary['median_total'], 1)} | "
            f"{fmt(summary['avg_games'], 1)}"
        )

    print()
    print("[안전 점검]")
    latest_missing = one(
        conn,
        """
        SELECT COUNT(*)
        FROM registered_players rp
        LEFT JOIN player_prices pp
          ON pp.registered_player_id = rp.id
         AND pp.basis_source = ?
         AND pp.basis_date = ?
        WHERE pp.registered_player_id IS NULL
        """,
        (BASIS_SOURCE, basis_date),
    )
    active_missing = one(
        conn,
        """
        SELECT COUNT(*)
        FROM registered_players rp
        LEFT JOIN player_prices pp
          ON pp.registered_player_id = rp.id
         AND pp.basis_source = ?
         AND pp.basis_date = ?
        WHERE rp.is_active = 1
          AND pp.registered_player_id IS NULL
        """,
        (BASIS_SOURCE, basis_date),
    )
    zero_or_negative = one(
        conn,
        """
        SELECT COUNT(*)
        FROM player_prices
        WHERE basis_source = ?
          AND basis_date = ?
          AND COALESCE(price_decimal, price) <= 0
        """,
        (BASIS_SOURCE, basis_date),
    )
    duplicates = one(
        conn,
        """
        SELECT COUNT(*)
        FROM (
            SELECT registered_player_id, COUNT(*) AS c
            FROM player_prices
            WHERE basis_source = ?
              AND basis_date = ?
            GROUP BY registered_player_id
            HAVING c > 1
        )
        """,
        (BASIS_SOURCE, basis_date),
    )
    print("latest price missing:", latest_missing)
    print("active price missing:", active_missing)
    print("zero_or_negative_prices:", zero_or_negative)
    print("duplicate latest price rows:", duplicates)

    for role in ROLE_ORDER:
        role_rows = by_role.get(role, [])
        if not role_rows:
            continue
        print()
        print(f"[{ROLE_LABEL.get(role, role)} 상위 {top}명]")
        for index, row in enumerate(role_rows[:top], start=1):
            print(
                f"{index:>2}. {row['player_name']} {row['team']} "
                f"가격={float(row['price_decimal_effective']):.1f} "
                f"시즌점수={float(row['season_total'] or 0):.1f} "
                f"출전/등판={int(row['scored_games'] or 0)}"
            )


def build_arg_parser():
    parser = argparse.ArgumentParser(description="market_daily_v3 역할별 가격 밸런스 리포트")
    parser.add_argument("--date", help="확인할 basis_date. 생략하면 최신 market_daily_v3 날짜를 사용합니다.")
    parser.add_argument("--top", type=int, default=15, help="역할별 상위 몇 명을 출력할지 지정합니다. 기본값: 15")
    return parser


def main():
    args = build_arg_parser().parse_args()
    with get_conn() as conn:
        basis_date = args.date or latest_price_date(conn)
        if not basis_date:
            raise SystemExit("market_daily_v3 가격 row가 없습니다.")
        print_summary(conn, basis_date, max(1, args.top))


if __name__ == "__main__":
    main()
