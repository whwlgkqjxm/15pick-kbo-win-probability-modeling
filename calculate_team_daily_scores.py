"""
확정된 판타지 팀의 경기일별 점수를 계산하는 스크립트입니다.

역할:
- 특정 game_date 기준으로 확정된 팀만 가져옵니다.
- 각 팀의 현재 로스터 선수 점수를 fantasy_daily_scores에서 가져옵니다.
- 팀 총점을 fantasy_team_daily_scores에 저장합니다.
- 선수별 기여도 스냅샷을 fantasy_team_daily_player_scores에 저장합니다.

중요 원칙:
- 팀이 확정되지 않았으면 점수를 얻을 수 없습니다.
- 팀이 미확정인 날은 0점 row를 만들지 않고, 기록 자체를 만들지 않습니다.
- 공식 유저 점수는 팀 확정 이후의 경기일부터 기록합니다.
- 과거 날짜를 현재 팀으로 소급 계산하지 않는 것이 원칙입니다.
- 이 스크립트는 테스트 목적으로 과거 날짜 dry-run은 가능하지만,
  공식 기록용으로 과거 날짜 apply를 함부로 실행하면 안 됩니다.

주의:
- DB 삭제 없음
- DROP TABLE 없음
- 기존 테이블 재생성 없음
- 기본 모드에서는 이미 계산된 team_id + game_date 기록은 건너뜁니다.
"""

import argparse
import sys
from datetime import datetime

from db import get_conn, init_db

from position_rules import (
    BATTER_SLOT_DETAIL_MAP,
    PITCHER_SLOT_DETAIL_MAP,
    get_slot_position_mismatch_reason as get_position_mismatch_reason_shared,
    get_slot_requirement as get_slot_requirement_shared,
)


BASIS_SOURCE = "market_daily_v3"


def parse_game_date(value):
    """
    입력 날짜를 YYYY-MM-DD 형식으로 변환합니다.

    허용:
    - 20260512
    - 2026-05-12
    """

    if value is None:
        raise ValueError("날짜가 필요합니다.")

    value = str(value).strip()

    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d")

    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError("날짜는 YYYYMMDD 또는 YYYY-MM-DD 형식이어야 합니다.")


def get_daily_score_count(conn, game_date):
    """
    해당 날짜에 선수별 fantasy_daily_scores가 있는지 확인합니다.

    경기 없는 날 또는 아직 sync_db.py가 실행되지 않은 날이면 0입니다.
    이 경우 팀 점수 row를 만들면 안 됩니다.
    """

    row = conn.execute("""
        SELECT COUNT(*) AS cnt
        FROM fantasy_daily_scores
        WHERE game_date = ?
    """, (
        game_date,
    )).fetchone()

    return int(row["cnt"] or 0)


def get_confirmed_teams(conn):
    """
    확정된 팀만 가져옵니다.

    팀이 확정되지 않은 유저는 해당 경기일 점수를 얻을 수 없습니다.
    """

    rows = conn.execute("""
        SELECT
            ft.id AS team_id,
            ft.user_id,
            ft.team_name,
            ft.budget_limit,
            ft.is_confirmed,
            ft.captain_registered_player_id,
            COALESCE(u.display_name, u.username) AS user_display_name
        FROM fantasy_teams ft
        JOIN users u
          ON u.id = ft.user_id
        WHERE ft.is_confirmed = 1
        ORDER BY ft.id
    """).fetchall()

    return rows


def get_team_roster(conn, team_id):
    """
    팀의 현재 로스터를 가져옵니다.

    점수 계산 시점의 선수 목록을 fantasy_team_daily_player_scores에 저장해
    이후 팀을 수정해도 과거 경기의 선수별 기여도는 유지되게 합니다.
    """

    rows = conn.execute("""
        SELECT
            ftp.registered_player_id,
            ftp.slot,
            ftp.locked_price_decimal,
            ftp.locked_price_basis_date,
            ftp.locked_at,

            rp.name AS player_name,
            rp.team AS player_team,
            rp.fantasy_position_type AS position_type,
            rp.detail_position
        FROM fantasy_team_players ftp
        JOIN registered_players rp
          ON rp.id = ftp.registered_player_id
        WHERE ftp.team_id = ?
        ORDER BY
            CASE ftp.slot
                WHEN 'C' THEN 1
                WHEN '1B' THEN 2
                WHEN '2B' THEN 3
                WHEN '3B' THEN 4
                WHEN 'SS' THEN 5
                WHEN 'LF' THEN 6
                WHEN 'CF' THEN 7
                WHEN 'RF' THEN 8
                WHEN 'UTIL' THEN 9
                WHEN 'P1' THEN 10
                WHEN 'P2' THEN 11
                WHEN 'P3' THEN 12
                WHEN 'P4' THEN 13
                WHEN 'P5' THEN 14
                WHEN 'P6' THEN 15
                ELSE 99
            END
    """, (
        team_id,
    )).fetchall()

    return rows



ROSTER_SLOT_ORDER = [
    "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "UTIL",
    "P1", "P2", "P3", "P4", "P5", "P6",
]


def get_slot_label(slot):
    labels = {
        "C": "포수",
        "1B": "1루수",
        "2B": "2루수",
        "3B": "3루수",
        "SS": "유격수",
        "LF": "좌익수",
        "CF": "중견수",
        "RF": "우익수",
        "UTIL": "지명타자/UTIL",
        "P1": "선발투수",
        "P2": "불펜투수 1",
        "P3": "불펜투수 2",
        "P4": "불펜투수 3",
        "P5": "불펜투수 4",
        "P6": "불펜투수 5",
    }
    return labels.get(slot, slot)


# Slot eligibility rules are centralized in position_rules.py.
def get_slot_requirement(slot):
    return get_slot_requirement_shared(slot)


def get_position_mismatch_reason_for_scoring(row):
    """팀 점수 계산용 슬롯 자격 검사입니다.

    mismatch는 팀 전체 invalid가 아니라 해당 선수만 0점 처리합니다.
    내야수/외야수 broad position은 각각 내야/외야 슬롯 wildcard로 인정합니다.
    """
    return get_position_mismatch_reason_shared(
        row.get("position_type"),
        row.get("scoring_detail_position") or row.get("detail_position"),
        row.get("slot"),
    )


def get_pitcher_detail_position_map_as_of_date(conn, game_date):
    """
    game_date 이하 가장 최근 실제 투수 등판 역할을 가져옵니다.

    선발/불펜 역할은 시간 경과로 자동 강등하지 않고, 실제 다음 등판 역할로만 바뀝니다.
    """
    rows = conn.execute("""
        WITH latest_pitching AS (
            SELECT
                rp.id AS registered_player_id,
                rps.game_date,
                COALESCE(rps.pitching_order, 999) AS pitching_order,
                COALESCE(rps.is_starting_pitcher, 0) AS is_starting_pitcher,
                ROW_NUMBER() OVER (
                    PARTITION BY rp.id
                    ORDER BY
                        rps.game_date DESC,
                        COALESCE(rps.pitching_order, 999) DESC,
                        rps.id DESC
                ) AS rn
            FROM raw_pitcher_stats rps
            JOIN registered_players rp
              ON rp.name = rps.player_name
             AND rp.team = rps.team
             AND rp.fantasy_position_type = 'pitcher'
            WHERE rps.game_date <= ?
        )
        SELECT
            registered_player_id,
            CASE
                WHEN is_starting_pitcher = 1 OR pitching_order = 1 THEN '선발투수'
                ELSE '불펜투수'
            END AS detail_position
        FROM latest_pitching
        WHERE rn = 1
    """, (game_date,)).fetchall()

    return {
        int(row["registered_player_id"]): row["detail_position"]
        for row in rows
    }


def apply_scoring_position_snapshots(conn, roster_rows, game_date):
    """로스터 row에 해당 경기일 기준 포지션 스냅샷을 붙입니다."""
    pitcher_role_map = get_pitcher_detail_position_map_as_of_date(conn, game_date)
    enriched = []

    for row in roster_rows:
        item = dict(row)
        registered_player_id = int(item.get("registered_player_id") or 0)

        if item.get("position_type") == "pitcher":
            item["scoring_detail_position"] = pitcher_role_map.get(
                registered_player_id,
                item.get("detail_position"),
            )
        else:
            # 타자는 DH를 별도 포지션으로 업데이트하지 않습니다.
            # 현재 확정 가능한 수비 포지션만 사용하고, UTIL은 모든 타자를 허용합니다.
            item["scoring_detail_position"] = item.get("detail_position")

        requirement = get_slot_requirement(item.get("slot"))
        mismatch_reason = get_position_mismatch_reason_for_scoring(item)
        item["slot_expected_position_type"] = requirement.get("position_type")
        item["slot_expected_detail_position"] = requirement.get("detail_position")
        item["player_detail_position_snapshot"] = item.get("scoring_detail_position")
        item["is_position_eligible"] = 1 if mismatch_reason is None else 0
        item["position_mismatch_reason"] = mismatch_reason
        enriched.append(item)

    return enriched


def validate_confirmed_roster_for_scoring(roster_rows, budget_limit=100):
    """
    공식 팀 점수 저장 직전의 hard invalid만 검사합니다.

    포지션 변경으로 슬롯과 맞지 않는 선수는 팀 전체를 skip하지 않고 해당 선수만 0점 처리합니다.
    여기서는 선수 수, 빈 슬롯, 중복, 영입가 누락처럼 점수 스냅샷 자체가 깨지는 경우만 막습니다.
    """
    rows = [dict(row) for row in roster_rows]
    selected_slots = [row["slot"] for row in rows]
    selected_player_ids = [row["registered_player_id"] for row in rows]
    problems = []

    missing_slots = [slot for slot in ROSTER_SLOT_ORDER if slot not in selected_slots]
    duplicate_slots = sorted({slot for slot in selected_slots if selected_slots.count(slot) > 1})
    duplicate_player_ids = sorted({pid for pid in selected_player_ids if selected_player_ids.count(pid) > 1})

    if len(rows) != 15:
        problems.append(f"총 선수 수가 15명이 아닙니다. 현재 {len(rows)}명입니다.")

    if missing_slots:
        missing_labels = [f"{slot}({get_slot_label(slot)})" for slot in missing_slots]
        problems.append("비어 있는 슬롯: " + ", ".join(missing_labels))

    if duplicate_slots:
        problems.append("중복 슬롯: " + ", ".join(duplicate_slots))

    if duplicate_player_ids:
        problems.append(f"중복 등록된 선수가 {len(duplicate_player_ids)}명 있습니다.")

    missing_locked_price_count = sum(1 for row in rows if row["locked_price_decimal"] is None)
    if missing_locked_price_count > 0:
        problems.append(f"영입가가 저장되지 않은 선수가 {missing_locked_price_count}명 있습니다.")

    return {
        "is_complete": len(problems) == 0,
        "problems": problems,
    }

def get_player_scores_for_date(conn, game_date):
    """
    특정 날짜의 선수별 점수를 dict로 가져옵니다.

    key:
    (player_name, team, position_type)

    value:
    points
    """

    rows = conn.execute("""
        SELECT
            player_name,
            team,
            position_type,
            points
        FROM fantasy_daily_scores
        WHERE game_date = ?
    """, (
        game_date,
    )).fetchall()

    score_map = {}

    for row in rows:
        key = (
            row["player_name"],
            row["team"],
            row["position_type"],
        )
        score_map[key] = float(row["points"] or 0)

    return score_map


def get_latest_market_price_date(conn, game_date):
    """
    game_date 이하의 최신 market_daily_v3 가격 기준일을 가져옵니다.

    예:
    - game_date = 2026-05-12
    - 최신 market_daily_v3가 2026-05-10까지 있으면 2026-05-10 사용

    만약 game_date 이하 market_daily_v3 가격이 하나도 없으면 전체 최신 market_daily_v3 날짜를 fallback으로 사용합니다.
    """

    row = conn.execute("""
        SELECT MAX(basis_date) AS latest_price_date
        FROM player_prices
        WHERE basis_source = ?
          AND basis_date <= ?
    """, (
        BASIS_SOURCE,
        game_date,
    )).fetchone()

    if row is not None and row["latest_price_date"]:
        return row["latest_price_date"]

    row = conn.execute("""
        SELECT MAX(basis_date) AS latest_price_date
        FROM player_prices
        WHERE basis_source = ?
    """, (
        BASIS_SOURCE,
    )).fetchone()

    if row is not None and row["latest_price_date"]:
        return row["latest_price_date"]

    return None


def get_market_prices(conn, game_date):
    """
    선수별 현재 시장가를 가져옵니다.

    기준:
    - market_daily_v3
    - game_date 이하 최신 basis_date
    """

    latest_price_date = get_latest_market_price_date(conn, game_date)

    if not latest_price_date:
        return {}, None

    rows = conn.execute("""
        SELECT
            registered_player_id,
            COALESCE(price_decimal, price, 0) AS current_market_price
        FROM player_prices
        WHERE basis_source = ?
          AND basis_date = ?
    """, (
        BASIS_SOURCE,
        latest_price_date,
    )).fetchall()

    price_map = {}

    for row in rows:
        price_map[int(row["registered_player_id"])] = float(
            row["current_market_price"] or 0
        )

    return price_map, latest_price_date


def get_existing_team_daily_score(conn, team_id, game_date):
    """
    이미 해당 팀/날짜의 점수 기록이 있는지 확인합니다.
    """

    row = conn.execute("""
        SELECT id
        FROM fantasy_team_daily_scores
        WHERE team_id = ?
          AND game_date = ?
    """, (
        team_id,
        game_date,
    )).fetchone()

    return row


def reset_existing_team_daily_score(conn, team_id, game_date):
    """
    특정 팀/날짜의 기존 팀 점수와 선수별 스냅샷을 안전하게 다시 계산할 수 있게 정리합니다.

    - 전체 테이블 삭제 없음
    - 지정한 team_id + game_date 기록만 정리
    - --force-update 옵션에서만 호출됩니다.
    """

    existing = get_existing_team_daily_score(conn, team_id, game_date)
    if existing is None:
        return False

    team_daily_score_id = int(existing["id"])

    conn.execute("""
        DELETE FROM fantasy_team_daily_player_scores
        WHERE team_daily_score_id = ?
    """, (team_daily_score_id,))

    conn.execute("""
        DELETE FROM fantasy_team_daily_scores
        WHERE id = ?
          AND team_id = ?
          AND game_date = ?
    """, (team_daily_score_id, team_id, game_date))

    return True


def insert_team_daily_score(
    conn,
    team,
    game_date,
    total_points,
    roster_player_count,
    captain_registered_player_id_snapshot=None,
    captain_player_name_snapshot=None,
):
    """
    팀의 경기일 총점을 저장합니다.

    기본적으로 이 함수는 새 row를 INSERT합니다.
    이미 존재하는지는 호출 전에 확인합니다.
    """

    conn.execute("""
        INSERT INTO fantasy_team_daily_scores
            (
                team_id,
                user_id,
                team_name_snapshot,
                user_display_name_snapshot,
                game_date,
                total_points,
                roster_player_count,
                captain_registered_player_id_snapshot,
                captain_player_name_snapshot,
                is_confirmed_snapshot,
                created_at,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        team["team_id"],
        team["user_id"],
        team["team_name"],
        team["user_display_name"],
        game_date,
        total_points,
        roster_player_count,
        captain_registered_player_id_snapshot,
        captain_player_name_snapshot,
    ))

    row = conn.execute("""
        SELECT id
        FROM fantasy_team_daily_scores
        WHERE team_id = ?
          AND game_date = ?
    """, (
        team["team_id"],
        game_date,
    )).fetchone()

    return int(row["id"])


def insert_team_daily_player_score(
    conn,
    team_daily_score_id,
    team,
    game_date,
    roster_row,
    points,
    current_market_price,
    base_points=None,
    captain_multiplier=1.0,
    is_captain=0,
):
    """
    팀 경기일 선수별 기여도 스냅샷을 저장합니다.

    포지션이 맞지 않는 선수는 points/base_points가 0으로 저장되고,
    position_mismatch_reason에 0점 사유를 남깁니다.
    """

    conn.execute("""
        INSERT INTO fantasy_team_daily_player_scores
            (
                team_daily_score_id,
                team_id,
                user_id,
                game_date,
                registered_player_id,
                player_name,
                player_team,
                slot,
                position_type,
                slot_expected_position_type,
                slot_expected_detail_position,
                player_detail_position_snapshot,
                is_position_eligible,
                position_mismatch_reason,
                points,
                base_points,
                captain_multiplier,
                is_captain,
                locked_price_decimal,
                current_market_price,
                created_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(team_daily_score_id, registered_player_id) DO UPDATE SET
            slot_expected_position_type = excluded.slot_expected_position_type,
            slot_expected_detail_position = excluded.slot_expected_detail_position,
            player_detail_position_snapshot = excluded.player_detail_position_snapshot,
            is_position_eligible = excluded.is_position_eligible,
            position_mismatch_reason = excluded.position_mismatch_reason,
            points = excluded.points,
            base_points = excluded.base_points,
            captain_multiplier = excluded.captain_multiplier,
            is_captain = excluded.is_captain,
            locked_price_decimal = excluded.locked_price_decimal,
            current_market_price = excluded.current_market_price
    """, (
        team_daily_score_id,
        team["team_id"],
        team["user_id"],
        game_date,
        roster_row["registered_player_id"],
        roster_row["player_name"],
        roster_row["player_team"],
        roster_row["slot"],
        roster_row["position_type"],
        roster_row.get("slot_expected_position_type"),
        roster_row.get("slot_expected_detail_position"),
        roster_row.get("player_detail_position_snapshot"),
        int(roster_row.get("is_position_eligible") or 0),
        roster_row.get("position_mismatch_reason"),
        points,
        base_points if base_points is not None else points,
        captain_multiplier,
        is_captain,
        roster_row["locked_price_decimal"],
        current_market_price,
    ))

def calculate_one_team(
    conn,
    team,
    game_date,
    score_map,
    market_price_map,
    dry_run=False,
    force_update=False,
):
    """
    한 팀의 특정 경기일 점수를 계산하고 저장합니다.
    """

    team_id = int(team["team_id"])

    existing = get_existing_team_daily_score(conn, team_id, game_date)

    if existing is not None:
        if dry_run or not force_update:
            return {
                "team_id": team_id,
                "team_name": team["team_name"],
                "status": "skipped_existing",
                "total_points": None,
                "roster_player_count": None,
                "message": "이미 해당 날짜 팀 점수 기록이 있어 건너뜀",
            }

        reset_existing_team_daily_score(conn, team_id, game_date)

    roster_rows = get_team_roster(conn, team_id)
    validation = validate_confirmed_roster_for_scoring(
        roster_rows=roster_rows,
        budget_limit=team["budget_limit"],
    )

    if not validation["is_complete"]:
        return {
            "team_id": team_id,
            "team_name": team["team_name"],
            "status": "skipped_invalid_roster",
            "total_points": None,
            "roster_player_count": len(roster_rows),
            "message": "로스터 규정 위반으로 팀 점수 저장 안 함: " + " / ".join(validation["problems"]),
        }

    roster_rows = apply_scoring_position_snapshots(conn, roster_rows, game_date)

    player_results = []
    total_points = 0.0
    captain_registered_player_id = team["captain_registered_player_id"]
    captain_player_name = None
    position_mismatch_count = 0

    for roster_row in roster_rows:
        key = (
            roster_row["player_name"],
            roster_row["player_team"],
            roster_row["position_type"],
        )

        is_position_eligible = int(roster_row.get("is_position_eligible") or 0) == 1
        if is_position_eligible:
            base_points = float(score_map.get(key, 0.0))
        else:
            base_points = 0.0
            position_mismatch_count += 1
        is_captain = (
            captain_registered_player_id is not None
            and int(roster_row["registered_player_id"] or 0) == int(captain_registered_player_id or 0)
        )
        captain_multiplier = 2.0 if is_captain else 1.0
        points = round(base_points * captain_multiplier, 1)
        total_points += points

        if is_captain:
            captain_player_name = roster_row["player_name"]

        current_market_price = market_price_map.get(
            int(roster_row["registered_player_id"])
        )

        player_results.append({
            "roster_row": roster_row,
            "base_points": base_points,
            "points": points,
            "captain_multiplier": captain_multiplier,
            "is_captain": 1 if is_captain else 0,
            "current_market_price": current_market_price,
        })

    total_points = round(total_points, 1)
    roster_player_count = len(roster_rows)

    if dry_run:
        return {
            "team_id": team_id,
            "team_name": team["team_name"],
            "status": "dry_run",
            "total_points": total_points,
            "roster_player_count": roster_player_count,
            "message": "dry-run 계산 완료, DB 저장 안 함" + (f" / 포지션 불일치 0점 {position_mismatch_count}명" if position_mismatch_count else ""),
        }

    team_daily_score_id = insert_team_daily_score(
        conn=conn,
        team=team,
        game_date=game_date,
        total_points=total_points,
        roster_player_count=roster_player_count,
        captain_registered_player_id_snapshot=captain_registered_player_id,
        captain_player_name_snapshot=captain_player_name,
    )

    for item in player_results:
        insert_team_daily_player_score(
            conn=conn,
            team_daily_score_id=team_daily_score_id,
            team=team,
            game_date=game_date,
            roster_row=item["roster_row"],
            points=item["points"],
            current_market_price=item["current_market_price"],
            base_points=item["base_points"],
            captain_multiplier=item["captain_multiplier"],
            is_captain=item["is_captain"],
        )

    return {
        "team_id": team_id,
        "team_name": team["team_name"],
        "status": "saved",
        "total_points": total_points,
        "roster_player_count": roster_player_count,
        "message": "팀 점수 저장 완료" + (f" / 포지션 불일치 0점 {position_mismatch_count}명" if position_mismatch_count else ""),
    }


def calculate_team_daily_scores(game_date, dry_run=False, force_update=False):
    """
    특정 날짜의 확정 팀 점수를 계산합니다.
    """

    init_db()

    print("팀 일별 점수 계산 시작")
    print("대상 경기일:", game_date)
    print("모드:", "dry-run" if dry_run else "apply")
    print("기존 기록 재계산:", "ON" if force_update else "OFF")
    print()

    saved_count = 0
    skipped_existing_count = 0
    skipped_invalid_count = 0
    dry_run_count = 0
    failed_count = 0

    with get_conn() as conn:
        daily_score_count = get_daily_score_count(conn, game_date)

        if daily_score_count <= 0:
            print("해당 날짜의 fantasy_daily_scores가 없습니다.")
            print("경기 없는 날이거나 아직 sync_db.py가 실행되지 않은 날짜입니다.")
            print("팀 점수 row를 생성하지 않습니다.")
            return {
                "game_date": game_date,
                "daily_score_count": 0,
                "confirmed_team_count": 0,
                "saved_count": 0,
                "skipped_existing_count": 0,
                "skipped_invalid_count": 0,
                "dry_run_count": 0,
                "failed_count": 0,
            }

        confirmed_teams = get_confirmed_teams(conn)
        score_map = get_player_scores_for_date(conn, game_date)
        market_price_map, latest_price_date = get_market_prices(conn, game_date)

        print("해당 날짜 선수 점수 row 수:", daily_score_count)
        print("확정 팀 수:", len(confirmed_teams))
        print("시장가 기준 source:", BASIS_SOURCE)
        print("시장가 기준일:", latest_price_date)
        print()

        for team in confirmed_teams:
            try:
                result = calculate_one_team(
                    conn=conn,
                    team=team,
                    game_date=game_date,
                    score_map=score_map,
                    market_price_map=market_price_map,
                    dry_run=dry_run,
                    force_update=force_update,
                )

                status = result["status"]

                if status == "saved":
                    saved_count += 1
                elif status == "skipped_existing":
                    skipped_existing_count += 1
                elif status == "skipped_invalid_roster":
                    skipped_invalid_count += 1
                elif status == "dry_run":
                    dry_run_count += 1

                print(
                    f"[{status}]",
                    f"team_id={result['team_id']}",
                    f"team={result['team_name']}",
                    f"points={result['total_points']}",
                    f"roster={result['roster_player_count']}",
                    "-",
                    result["message"],
                )

            except Exception as e:
                failed_count += 1
                print(
                    "[failed]",
                    f"team_id={team['team_id']}",
                    f"team={team['team_name']}",
                    "에러:",
                    e,
                )

    print()
    print("=" * 80)
    print("팀 일별 점수 계산 완료")
    print("=" * 80)
    print("대상 경기일:", game_date)
    print("저장된 팀 수:", saved_count)
    print("이미 있어서 건너뛴 팀 수:", skipped_existing_count)
    print("규정 위반으로 건너뛴 팀 수:", skipped_invalid_count)
    print("dry-run 계산 팀 수:", dry_run_count)
    print("실패 팀 수:", failed_count)

    return {
        "game_date": game_date,
        "daily_score_count": daily_score_count,
        "confirmed_team_count": len(confirmed_teams),
        "saved_count": saved_count,
        "skipped_existing_count": skipped_existing_count,
        "skipped_invalid_count": skipped_invalid_count,
        "dry_run_count": dry_run_count,
        "failed_count": failed_count,
    }


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="확정된 판타지 팀의 경기일별 점수를 계산합니다."
    )

    parser.add_argument(
        "game_date",
        help="계산할 경기일입니다. 예: 20260512 또는 2026-05-12",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 저장하지 않고 계산 결과만 출력합니다.",
    )

    parser.add_argument(
        "--force-update",
        action="store_true",
        help="이미 저장된 해당 날짜 팀 점수/선수별 스냅샷을 지정 날짜에 한해 다시 계산합니다.",
    )

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        game_date = parse_game_date(args.game_date)
    except ValueError as e:
        print("날짜 형식 오류:", e)
        sys.exit(1)

    calculate_team_daily_scores(
        game_date=game_date,
        dry_run=args.dry_run,
        force_update=args.force_update,
    )


if __name__ == "__main__":
    main()