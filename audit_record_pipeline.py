"""
MyPick 경기 기록 전체 파이프라인 감사 스크립트.

목적:
- 특정 날짜/기간의 KBO BoxScore 원문을 다시 파싱해서 DB에 저장된 raw_batter_stats,
  raw_pitcher_stats, fantasy_daily_scores와 전수 비교합니다.
- 정수빈/박지훈 같은 샘플만 보는 것이 아니라, 해당 날짜/기간의 모든 경기, 모든 선수,
  모든 주요 타자/투수 기록과 점수까지 확인합니다.
- DB를 절대 수정하지 않습니다. 불일치가 있으면 목록만 출력하고 exit code 1로 종료합니다.
- sync_db.py의 phantom 투수 타자 row 제외 기준을 그대로 사용해, 실제 저장 로직과 감사 기준이 어긋나지 않게 합니다.

실행 예시:
    ./venv/bin/python audit_record_pipeline.py --date 20260528
    ./venv/bin/python audit_record_pipeline.py --start-date 20260328 --end-date 20260528
    ./venv/bin/python audit_record_pipeline.py --date 20260528 --show-all-nonzero
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta

from scraper import get_games_for_date, get_game_boxscore_stats
from scoring import calc_batter_points, calc_pitcher_points
from sync_db import should_skip_phantom_pitcher_batter_row

DB_PATH = "kbo_fantasy.db"

BATTER_FIELDS = [
    "hits",
    "doubles",
    "triples",
    "home_runs",
    "rbi",
    "runs",
    "game_winning_hit",
    "double_play",
    "hit_by_pitch",
    "walks",
    "stolen_bases",
    "strikeouts",
]

# 사용자가 문제를 제기한 반복 기록/상세기록 계열은 따로 강조해서 출력합니다.
SPECIAL_BATTER_FIELDS = [
    "doubles",
    "triples",
    "home_runs",
    "game_winning_hit",
    "double_play",
    "hit_by_pitch",
    "walks",
    "stolen_bases",
    "strikeouts",
]

PITCHER_FIELDS = [
    "wins",
    "losses",
    "holds",
    "saves",
    "completed_innings",
    "strikeouts",
    "runs_allowed",
    "pitch_count",
    "hits_allowed",
    "is_starting_pitcher",
    "pitching_order",
]

FIELD_LABELS = {
    "hits": "안타",
    "doubles": "2루타",
    "triples": "3루타",
    "home_runs": "홈런",
    "rbi": "타점",
    "runs": "득점",
    "game_winning_hit": "결승타",
    "double_play": "병살타",
    "hit_by_pitch": "사구",
    "walks": "볼넷",
    "stolen_bases": "도루",
    "strikeouts": "삼진",
    "wins": "승",
    "losses": "패",
    "holds": "홀드",
    "saves": "세이브",
    "completed_innings": "아웃카운트",
    "runs_allowed": "실점",
    "pitch_count": "투구수",
    "hits_allowed": "피안타",
    "is_starting_pitcher": "선발투수",
    "pitching_order": "등판순서",
    "points": "판타지점수",
}


def parse_date_any(value):
    value = str(value).strip()
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def date_yyyymmdd(value):
    return parse_date_any(value).strftime("%Y%m%d")


def date_iso(value):
    return parse_date_any(value).strftime("%Y-%m-%d")


def iter_dates(start_date, end_date):
    current = parse_date_any(start_date)
    end = parse_date_any(end_date)
    while current <= end:
        yield current.strftime("%Y%m%d")
        current += timedelta(days=1)


def safe_int(value):
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return 0


def safe_float(value):
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def fetch_db_batter(conn, game_id, player_name, team):
    return conn.execute(
        """
        SELECT *
        FROM raw_batter_stats
        WHERE game_id = ?
          AND player_name = ?
          AND team = ?
        """,
        (game_id, player_name, team),
    ).fetchone()


def fetch_db_pitcher(conn, game_id, player_name, team):
    return conn.execute(
        """
        SELECT *
        FROM raw_pitcher_stats
        WHERE game_id = ?
          AND player_name = ?
          AND team = ?
        """,
        (game_id, player_name, team),
    ).fetchone()


def fetch_db_score(conn, game_id, game_date, player_name, team, position_type):
    return conn.execute(
        """
        SELECT *
        FROM fantasy_daily_scores
        WHERE game_id = ?
          AND game_date = ?
          AND player_name = ?
          AND team = ?
          AND position_type = ?
        """,
        (game_id, game_date, player_name, team, position_type),
    ).fetchone()


def add_mismatch(mismatches, kind, game, player_name, team, field, expected, actual, extra=None):
    mismatches.append({
        "kind": kind,
        "date": date_iso(game["game_date"]),
        "game_id": game["game_id"],
        "away": game.get("away_team"),
        "home": game.get("home_team"),
        "team": team,
        "player_name": player_name,
        "field": field,
        "label": FIELD_LABELS.get(field, field),
        "expected": expected,
        "actual": actual,
        "extra": extra or "",
    })


def compare_batter(conn, game, batter, mismatches, nonzero_rows):
    game_id = game["game_id"]
    game_date = date_iso(game["game_date"])
    player_name = batter["player_name"]
    team = batter["team"]

    db_row = fetch_db_batter(conn, game_id, player_name, team)
    if db_row is None:
        add_mismatch(mismatches, "batter_raw_missing", game, player_name, team, "row", "exists", "missing")
        return

    for field in BATTER_FIELDS:
        expected = safe_int(batter.get(field))
        actual = safe_int(db_row[field])
        if expected != actual:
            add_mismatch(mismatches, "batter_raw", game, player_name, team, field, expected, actual)

    nonzero_special = {
        field: safe_int(batter.get(field))
        for field in SPECIAL_BATTER_FIELDS
        if safe_int(batter.get(field)) != 0
    }
    if nonzero_special:
        nonzero_rows.append({
            "kind": "batter_special_nonzero",
            "date": game_date,
            "game_id": game_id,
            "team": team,
            "player_name": player_name,
            "values": nonzero_special,
        })

    expected_points, expected_detail = calc_batter_points(batter)
    db_score = fetch_db_score(conn, game_id, game_date, player_name, team, "batter")
    if db_score is None:
        add_mismatch(mismatches, "batter_score_missing", game, player_name, team, "points", expected_points, "missing")
        return

    actual_points = safe_float(db_score["points"])
    if abs(float(expected_points) - actual_points) > 0.0001:
        add_mismatch(mismatches, "batter_score", game, player_name, team, "points", expected_points, actual_points)

    try:
        actual_detail = json.loads(db_score["score_detail_json"] or "{}")
    except Exception:
        actual_detail = {}

    for key, expected_value in expected_detail.items():
        actual_value = safe_float(actual_detail.get(key))
        if abs(float(expected_value) - actual_value) > 0.0001:
            add_mismatch(
                mismatches,
                "batter_score_detail",
                game,
                player_name,
                team,
                key,
                expected_value,
                actual_value,
                extra="score_detail_json",
            )


def compare_pitcher(conn, game, pitcher, mismatches, nonzero_rows):
    game_id = game["game_id"]
    game_date = date_iso(game["game_date"])
    player_name = pitcher["player_name"]
    team = pitcher["team"]

    expected_points, expected_detail, expected_completed_innings = calc_pitcher_points(pitcher)
    pitcher_for_compare = dict(pitcher)
    pitcher_for_compare["completed_innings"] = expected_completed_innings

    db_row = fetch_db_pitcher(conn, game_id, player_name, team)
    if db_row is None:
        add_mismatch(mismatches, "pitcher_raw_missing", game, player_name, team, "row", "exists", "missing")
        return

    for field in PITCHER_FIELDS:
        expected = safe_int(pitcher_for_compare.get(field))
        actual = safe_int(db_row[field])
        if expected != actual:
            add_mismatch(mismatches, "pitcher_raw", game, player_name, team, field, expected, actual)

    nonzero_pitcher = {
        field: safe_int(pitcher_for_compare.get(field))
        for field in PITCHER_FIELDS
        if field not in {"pitching_order"} and safe_int(pitcher_for_compare.get(field)) != 0
    }
    if nonzero_pitcher:
        nonzero_rows.append({
            "kind": "pitcher_nonzero",
            "date": game_date,
            "game_id": game_id,
            "team": team,
            "player_name": player_name,
            "values": nonzero_pitcher,
        })

    db_score = fetch_db_score(conn, game_id, game_date, player_name, team, "pitcher")
    if db_score is None:
        add_mismatch(mismatches, "pitcher_score_missing", game, player_name, team, "points", expected_points, "missing")
        return

    actual_points = safe_float(db_score["points"])
    if abs(float(expected_points) - actual_points) > 0.0001:
        add_mismatch(mismatches, "pitcher_score", game, player_name, team, "points", expected_points, actual_points)

    try:
        actual_detail = json.loads(db_score["score_detail_json"] or "{}")
    except Exception:
        actual_detail = {}

    for key, expected_value in expected_detail.items():
        actual_value = safe_float(actual_detail.get(key))
        if abs(float(expected_value) - actual_value) > 0.0001:
            add_mismatch(
                mismatches,
                "pitcher_score_detail",
                game,
                player_name,
                team,
                key,
                expected_value,
                actual_value,
                extra="score_detail_json",
            )


def audit_date(conn, target_date, show_all_nonzero=False):
    games = get_games_for_date(target_date)
    if not games:
        print(f"{target_date}: 수집 경기 없음")
        return {
            "date": target_date,
            "games": 0,
            "batters": 0,
            "pitchers": 0,
            "mismatches": [],
            "nonzero_rows": [],
            "failed_games": [],
        }

    print()
    print("=" * 100)
    print("기록 파이프라인 전수 감사:", target_date, f"({len(games)}경기)")
    print("=" * 100)

    mismatches = []
    nonzero_rows = []
    failed_games = []
    batter_count = 0
    pitcher_count = 0
    skipped_phantom_batter_count = 0
    skipped_phantom_batter_rows = []

    for game in games:
        game_id = game["game_id"]
        print(f"- {game_id}: {game.get('away_team')} vs {game.get('home_team')}")
        try:
            result = get_game_boxscore_stats(game)
        except Exception as error:
            failed_games.append({"game_id": game_id, "error": str(error)})
            print("  FETCH/PARSE FAIL:", error)
            continue

        for batter in result.get("batters", []):
            if should_skip_phantom_pitcher_batter_row(conn, batter):
                skipped_phantom_batter_count += 1
                skipped_phantom_batter_rows.append({
                    "date": date_iso(game["game_date"]),
                    "game_id": game_id,
                    "team": batter.get("team"),
                    "player_name": batter.get("player_name"),
                })
                continue

            batter_count += 1
            compare_batter(conn, game, batter, mismatches, nonzero_rows)

        for pitcher in result.get("pitchers", []):
            pitcher_count += 1
            compare_pitcher(conn, game, pitcher, mismatches, nonzero_rows)

        special_summary = result.get("special_records", {})
        any_special = False
        for record_name, count_map in special_summary.items():
            if count_map:
                any_special = True
                print(f"  {record_name}: {count_map}")
        if not any_special:
            print("  special_records: {}")

    if show_all_nonzero and nonzero_rows:
        print()
        print("[모든 non-zero 주요 기록 목록]")
        for row in nonzero_rows:
            values = ", ".join(
                f"{FIELD_LABELS.get(k, k)}={v}" for k, v in sorted(row["values"].items())
            )
            print(
                f"{row['date']} {row['game_id']} {row['team']} {row['player_name']} | {values}"
            )

    return {
        "date": target_date,
        "games": len(games),
        "batters": batter_count,
        "pitchers": pitcher_count,
        "skipped_phantom_batters": skipped_phantom_batter_count,
        "skipped_phantom_batter_rows": skipped_phantom_batter_rows,
        "mismatches": mismatches,
        "nonzero_rows": nonzero_rows,
        "failed_games": failed_games,
    }


def print_mismatch_summary(all_results, max_rows):
    all_mismatches = []
    all_failed_games = []
    all_skipped_phantom_batters = []
    for result in all_results:
        all_mismatches.extend(result["mismatches"])
        all_failed_games.extend(result["failed_games"])
        all_skipped_phantom_batters.extend(result.get("skipped_phantom_batter_rows", []))

    print()
    print("=" * 100)
    print("전체 감사 요약")
    print("=" * 100)
    print("감사 날짜 수:", len(all_results))
    print("경기 수:", sum(r["games"] for r in all_results))
    print("타자 row 수:", sum(r["batters"] for r in all_results))
    print("투수 row 수:", sum(r["pitchers"] for r in all_results))
    print("생산 저장 로직과 동일하게 제외한 투수 phantom 타자 row 수:", len(all_skipped_phantom_batters))
    print("fetch/parse 실패 경기 수:", len(all_failed_games))
    print("불일치 수:", len(all_mismatches))

    if all_skipped_phantom_batters:
        print()
        print("[저장 로직 기준 제외된 투수 phantom 타자 row]")
        for item in all_skipped_phantom_batters[:max_rows]:
            print(f"- {item['date']} {item['game_id']} {item['team']} {item['player_name']}")

    if all_failed_games:
        print()
        print("[fetch/parse 실패 경기]")
        for item in all_failed_games[:max_rows]:
            print(f"- {item['game_id']}: {item['error']}")

    if all_mismatches:
        by_field = defaultdict(int)
        by_kind = defaultdict(int)
        by_date = defaultdict(int)
        for item in all_mismatches:
            by_field[item["field"]] += 1
            by_kind[item["kind"]] += 1
            by_date[item["date"]] += 1

        print()
        print("[불일치 종류별]")
        for key, value in sorted(by_kind.items(), key=lambda x: (-x[1], x[0])):
            print(f"- {key}: {value}")

        print()
        print("[불일치 기록별]")
        for key, value in sorted(by_field.items(), key=lambda x: (-x[1], x[0])):
            print(f"- {FIELD_LABELS.get(key, key)}({key}): {value}")

        print()
        print("[불일치 날짜별]")
        for key, value in sorted(by_date.items()):
            print(f"- {key}: {value}")

        print()
        print(f"[불일치 상세 상위 {max_rows}개]")
        for item in all_mismatches[:max_rows]:
            print(
                f"- {item['date']} {item['game_id']} {item['team']} {item['player_name']} "
                f"{item['label']}({item['field']}): expected={item['expected']} actual={item['actual']} "
                f"kind={item['kind']} {item['extra']}"
            )

    if not all_failed_games and not all_mismatches:
        print()
        print("✅ 감사 통과: 해당 날짜/기간의 모든 경기, 모든 선수, 주요 타자/투수 기록, fantasy_daily_scores가 현재 파서 결과와 일치합니다.")

    return len(all_failed_games), len(all_mismatches)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="KBO 원문 파싱 결과와 DB raw/score를 전수 비교합니다. DB 수정 없음.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", help="단일 날짜. 예: 20260528 또는 2026-05-28")
    group.add_argument("--latest", action="store_true", help="DB의 latest fantasy_daily_scores 날짜를 검사합니다.")
    parser.add_argument("--start-date", help="기간 시작일. --date 대신 --start-date/--end-date 사용 가능")
    parser.add_argument("--end-date", help="기간 종료일. --date 대신 --start-date/--end-date 사용 가능")
    parser.add_argument("--db", default=DB_PATH, help="SQLite DB 경로. 기본 kbo_fantasy.db")
    parser.add_argument("--show-all-nonzero", action="store_true", help="모든 non-zero 주요 기록을 출력합니다.")
    parser.add_argument("--max-rows", type=int, default=120, help="불일치 상세 최대 출력 수")
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    if args.latest:
        latest = conn.execute("SELECT MAX(game_date) FROM fantasy_daily_scores").fetchone()[0]
        if not latest:
            raise RuntimeError("fantasy_daily_scores에 날짜가 없습니다.")
        dates = [date_yyyymmdd(latest)]
    elif args.start_date or args.end_date:
        if not args.start_date or not args.end_date:
            parser.error("기간 검사는 --start-date와 --end-date를 둘 다 입력해야 합니다.")
        dates = list(iter_dates(args.start_date, args.end_date))
    else:
        dates = [date_yyyymmdd(args.date)]

    results = []
    for target_date in dates:
        results.append(audit_date(conn, target_date, show_all_nonzero=args.show_all_nonzero))

    failed_count, mismatch_count = print_mismatch_summary(results, args.max_rows)
    conn.close()

    if failed_count or mismatch_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
