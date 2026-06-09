# update_market_prices_v3.py
"""
MyPick Market Price Engine v3

목표:
- 기존 market_daily_v2 기록을 건드리지 않고 새 basis_source='market_daily_v3'로 가격을 계산합니다.
- 가격은 역할별 target_price를 향해 하루 최대 ±0.5씩 이동합니다.
- 역할은 batter / starting_pitcher / bullpen_pitcher 세 가지만 사용합니다.
- 투수 역할은 기준일 포함 최근 14일 raw 선발 등판 기록 기준으로 매번 동기화합니다.
- KBO 등록이 말소된 선수는 가격 row는 유지하되 등록 선수 가격 benchmark에는 포함하지 않습니다.
- 상세 포지션 희소성은 반영하지 않습니다.
- dry-run은 DB에 아무것도 저장하지 않습니다.
- apply일 때만 price_update_runs, player_price_adjustments, player_prices에 기록합니다.

안전 원칙:
- DB 파일 삭제 없음
- DROP TABLE 없음
- 기존 테이블 재생성 없음
- player_prices.price 컬럼 유지
- market_daily_v2 / welcometopranking row 수정 없음
- fantasy_daily_scores 이름만으로 신규 선수 자동 등록 없음
"""

import argparse
import os
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, date

from db import get_conn, init_db


BASIS_SOURCE = "market_daily_v3"
SEED_RANKING_SOURCE = "welcometopranking"
MIN_PRICE = 1.0
MAX_PRICE = 15.7
SEASON_START_DATE = "2026-03-28"
PRICING_CURVE_VERSION = "pitcher_score_balance_softcap_955_v4_20260525"

ROLE_DEFAULT_PRICE = {
    "batter": 7.5,
    "starting_pitcher": 6.4,
    "bullpen_pitcher": 5.3,
}

ROLE_PRICE_BANDS = {
    # 4차 미세 조정: v3 sandbox 평균 로스터 가격 96.94는 전략성은 좋지만 약간 빡빡할 수 있어,
    # 유저 체감 목표를 95.5 전후로 낮춥니다.
    # 전체 가격축을 크게 흔들지 않고 각 역할 band를 약 0.1만 완만하게 내립니다.
    "batter": [
        (99.0, 100.0, 15.2, 15.6),
        (95.0, 99.0, 14.0, 15.2),
        (90.0, 95.0, 12.3, 14.0),
        (80.0, 90.0, 10.0, 12.3),
        (65.0, 80.0, 8.0, 10.0),
        (45.0, 65.0, 6.4, 8.0),
        (25.0, 45.0, 4.8, 6.4),
        (10.0, 25.0, 3.2, 4.8),
        (0.0, 10.0, 2.0, 3.2),
    ],
    # 선발투수는 2.0배 점수 체계 기준으로 평균 6점대 초반을 목표로 합니다.
    # 로스터에 1명만 들어가므로 타자/불펜보다 조정폭은 작게 둡니다.
    "starting_pitcher": [
        (99.0, 100.0, 15.0, 15.6),
        (95.0, 99.0, 13.5, 15.0),
        (90.0, 95.0, 11.8, 13.5),
        (80.0, 90.0, 9.3, 11.8),
        (65.0, 80.0, 7.3, 9.3),
        (45.0, 65.0, 5.4, 7.3),
        (25.0, 45.0, 3.7, 5.4),
        (10.0, 25.0, 2.5, 3.7),
        (0.0, 10.0, 1.4, 2.5),
    ],
    # 불펜투수는 1.4배 점수 체계와 5개 로스터 슬롯을 반영해 평균 5.0 안팎을 목표로 합니다.
    # 등판 예측 변동성이 있으므로 상단은 10점대 초반까지만 열어 둡니다.
    "bullpen_pitcher": [
        (99.0, 100.0, 10.1, 10.7),
        (95.0, 99.0, 8.9, 10.1),
        (90.0, 95.0, 7.9, 8.9),
        (80.0, 90.0, 6.7, 7.9),
        (65.0, 80.0, 5.5, 6.7),
        (45.0, 65.0, 4.3, 5.5),
        (25.0, 45.0, 3.1, 4.3),
        (10.0, 25.0, 2.2, 3.1),
        (0.0, 10.0, 1.3, 2.2),
    ],
}

ROLE_SEASON_ANCHOR_FLOORS = {
    # 시즌 누적 상위권 보정도 95.5 평균 로스터 목표에 맞춰 0.1 정도만 완화합니다.
    "batter": [(97.0, 13.5), (95.0, 12.5), (90.0, 11.1), (80.0, 9.1)],
    "starting_pitcher": [(97.0, 12.8), (95.0, 11.8), (90.0, 10.4), (80.0, 8.3)],
    "bullpen_pitcher": [(97.0, 9.4), (95.0, 8.9), (90.0, 7.9), (80.0, 6.7)],
}

TEAM_NAME_MAP = {
    "KIA 타이거즈": "KIA",
    "LG 트윈스": "LG",
    "KT 위즈": "KT",
    "삼성 라이온즈": "삼성",
    "SSG 랜더스": "SSG",
    "두산 베어스": "두산",
    "NC 다이노스": "NC",
    "한화 이글스": "한화",
    "롯데 자이언츠": "롯데",
    "키움 히어로즈": "키움",
    "KIA": "KIA",
    "LG": "LG",
    "KT": "KT",
    "삼성": "삼성",
    "SSG": "SSG",
    "두산": "두산",
    "NC": "NC",
    "한화": "한화",
    "롯데": "롯데",
    "키움": "키움",
}

ROLE_LABEL = {
    "batter": "타자",
    "starting_pitcher": "선발투수",
    "bullpen_pitcher": "불펜투수",
}


# -----------------------------------------------------------------------------
# 기본 유틸
# -----------------------------------------------------------------------------

def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_name(name):
    name = clean_text(name)
    name = name.replace(" ", "")
    return re.sub(r"[·ㆍ\.\-_/]", "", name)


def normalize_team(team):
    team = clean_text(team)
    return TEAM_NAME_MAP.get(team, team)


def parse_date_any(value):
    if isinstance(value, date):
        return value
    value = str(value).strip()
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def to_game_date(value):
    return parse_date_any(value).strftime("%Y-%m-%d")


def clamp_price(value):
    value = float(value or 0)
    value = max(MIN_PRICE, min(MAX_PRICE, value))
    return round(value, 1)


def price_to_integer(price_decimal):
    value = int(math.floor(float(price_decimal or 1.0)))
    return max(1, min(15, value))


def tier_from_price(price_decimal):
    price_decimal = float(price_decimal or 1.0)
    if price_decimal >= 13.0:
        return "S"
    if price_decimal >= 9.0:
        return "A"
    if price_decimal >= 6.0:
        return "B"
    if price_decimal >= 3.0:
        return "C"
    return "D"


def default_price_for_role(price_role):
    return float(ROLE_DEFAULT_PRICE.get(price_role, ROLE_DEFAULT_PRICE["bullpen_pitcher"]))


def signed_change(value):
    value = round(float(value or 0), 1)
    if value == -0.0:
        value = 0.0
    return value


# -----------------------------------------------------------------------------
# 가격 기준 날짜 / 기존 row 조회
# -----------------------------------------------------------------------------

def get_latest_price_date(basis_source=BASIS_SOURCE):
    with get_conn() as conn:
        row = conn.execute("""
            SELECT MAX(basis_date) AS latest_price_date
            FROM player_prices
            WHERE basis_source = ?
        """, (basis_source,)).fetchone()
    return row["latest_price_date"] if row and row["latest_price_date"] else None


def get_latest_game_date():
    with get_conn() as conn:
        row = conn.execute("""
            SELECT MAX(game_date) AS latest_game_date
            FROM fantasy_daily_scores
        """).fetchone()
    return row["latest_game_date"] if row and row["latest_game_date"] else None


def count_price_rows_for_date(basis_date, basis_source=BASIS_SOURCE):
    with get_conn() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM player_prices
            WHERE basis_source = ?
              AND basis_date = ?
        """, (basis_source, basis_date)).fetchone()
    return int(row["cnt"] or 0)


def find_previous_price_date(basis_date, basis_source=BASIS_SOURCE):
    with get_conn() as conn:
        row = conn.execute("""
            SELECT MAX(basis_date) AS previous_price_date
            FROM player_prices
            WHERE basis_source = ?
              AND basis_date < ?
        """, (basis_source, basis_date)).fetchone()
    return row["previous_price_date"] if row and row["previous_price_date"] else None


def has_successful_apply_run(basis_date, basis_source=BASIS_SOURCE):
    with get_conn() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM price_update_runs
            WHERE basis_source = ?
              AND basis_date = ?
              AND run_mode = 'apply'
              AND status = 'success'
        """, (basis_source, basis_date)).fetchone()
    return int(row["cnt"] or 0) > 0


def load_players_with_base_prices(base_price_date, basis_source=BASIS_SOURCE):
    """
    기준 가격 날짜의 player_prices row를 기준으로 가격 계산 대상 선수를 읽습니다.
    fantasy_daily_scores에만 등장한 이름을 registered_players에 새로 만들지는 않습니다.
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                pp.registered_player_id,
                pp.player_id,
                pp.player_name,
                pp.team,
                pp.roster_position,
                pp.fantasy_position_type,
                pp.external_score,
                pp.external_rank,
                pp.price_role AS previous_price_role,
                pp.price_score,
                pp.tier,
                pp.price,
                COALESCE(pp.price_decimal, pp.price, 0) AS current_price_decimal,
                rp.detail_position,
                rp.is_active
            FROM player_prices pp
            JOIN registered_players rp
              ON rp.id = pp.registered_player_id
            WHERE pp.basis_source = ?
              AND pp.basis_date = ?
            ORDER BY pp.price_role, pp.team, pp.player_name, pp.registered_player_id
        """, (basis_source, base_price_date)).fetchall()

    return [dict(row) for row in rows]


def load_new_active_players_missing_from_base(existing_players, basis_date=None):
    """
    기준 가격 row에는 아직 없지만 v3 시장에 포함해야 하는 선수를 기본가로 추가합니다.

    포함 기준:
    1. 공식 등록 상태(is_active=1)인 선수
    2. 비활성/미등록 상태여도 registered_players에 이미 존재하고,
       2026 시즌 fantasy_daily_scores 기록이 있는 선수

    중복 방지:
    - 동일 선수 identity는 (이름, 팀, fantasy_position_type) 기준으로 1명만 가격 시장에 포함합니다.
    - 이미 기준 가격 row에 같은 identity가 있으면 다른 registered_player_id가 있어도 추가하지 않습니다.
    - 새로 추가해야 하는 중복 후보끼리는 active 우선, 시즌 점수 우선, id 작은 순으로 canonical row를 고릅니다.

    중요:
    - fantasy_daily_scores에만 등장한 이름을 registered_players에 새로 자동 등록하지 않습니다.
    - 이미 registered_players에 존재하는 선수만 가격 시장에 편입합니다.
    """
    existing_ids = {int(player["registered_player_id"]) for player in existing_players}
    existing_identity_keys = {
        (
            clean_text(player.get("player_name")),
            clean_text(player.get("team")),
            clean_text(player.get("fantasy_position_type")),
        )
        for player in existing_players
    }

    params = [SEASON_START_DATE]
    score_date_filter = ""
    if basis_date:
        score_date_filter = "AND game_date <= ?"
        params.append(to_game_date(basis_date))

    with get_conn() as conn:
        rows = conn.execute(f"""
            WITH scored AS (
                SELECT
                    player_name,
                    team,
                    position_type,
                    COUNT(*) AS scored_games,
                    SUM(points) AS season_points,
                    MAX(game_date) AS last_game_date
                FROM fantasy_daily_scores
                WHERE game_date >= ?
                  {score_date_filter}
                GROUP BY player_name, team, position_type
            )
            SELECT
                rp.id,
                rp.player_id,
                rp.name,
                rp.team,
                rp.roster_position,
                rp.fantasy_position_type,
                rp.detail_position,
                rp.is_active,
                COALESCE(scored.scored_games, 0) AS scored_games,
                COALESCE(scored.season_points, 0) AS scored_season_points,
                scored.last_game_date
            FROM registered_players rp
            LEFT JOIN scored
              ON scored.player_name = rp.name
             AND scored.team = rp.team
             AND scored.position_type = rp.fantasy_position_type
            WHERE rp.is_active = 1
               OR scored.scored_games IS NOT NULL
            ORDER BY
                rp.is_active DESC,
                scored.season_points DESC,
                scored.scored_games DESC,
                rp.team,
                rp.fantasy_position_type,
                rp.name,
                rp.id
        """, tuple(params)).fetchall()

    canonical_by_identity = {}
    for row in rows:
        row_dict = dict(row)
        identity_key = (
            clean_text(row_dict.get("name")),
            clean_text(row_dict.get("team")),
            clean_text(row_dict.get("fantasy_position_type")),
        )
        if identity_key in existing_identity_keys:
            continue
        if int(row_dict["id"]) in existing_ids:
            continue

        current = canonical_by_identity.get(identity_key)
        if current is None:
            canonical_by_identity[identity_key] = row_dict
            continue

        current_key = (
            int(current.get("is_active") or 0),
            float(current.get("scored_season_points") or 0),
            int(current.get("scored_games") or 0),
            -int(current.get("id") or 0),
        )
        candidate_key = (
            int(row_dict.get("is_active") or 0),
            float(row_dict.get("scored_season_points") or 0),
            int(row_dict.get("scored_games") or 0),
            -int(row_dict.get("id") or 0),
        )
        if candidate_key > current_key:
            canonical_by_identity[identity_key] = row_dict

    new_players = []
    for row in canonical_by_identity.values():
        if row["fantasy_position_type"] == "batter":
            default_role = "batter"
        elif clean_text(row["detail_position"]) == "선발투수":
            default_role = "starting_pitcher"
        else:
            default_role = "bullpen_pitcher"

        default_price = default_price_for_role(default_role)
        new_players.append({
            "registered_player_id": int(row["id"]),
            "player_id": row["player_id"],
            "player_name": row["name"],
            "team": row["team"],
            "roster_position": row["roster_position"],
            "fantasy_position_type": row["fantasy_position_type"],
            "external_score": 0.0,
            "external_rank": None,
            "previous_price_role": default_role,
            "price_score": 0.0,
            "tier": tier_from_price(default_price),
            "price": price_to_integer(default_price),
            "current_price_decimal": default_price,
            "detail_position": row["detail_position"],
            "is_active": row["is_active"],
        })

    new_players.sort(key=lambda player: (
        player["previous_price_role"],
        player["team"],
        player["player_name"],
        player["registered_player_id"],
    ))
    return new_players


# -----------------------------------------------------------------------------
# seed 가격 계산: welcometopranking 기반 3/28 초기 가격
# -----------------------------------------------------------------------------

def get_latest_external_source_date():
    with get_conn() as conn:
        row = conn.execute("""
            SELECT MAX(source_date) AS source_date
            FROM external_player_rankings
            WHERE source_name = ?
        """, (SEED_RANKING_SOURCE,)).fetchone()
    return row["source_date"] if row and row["source_date"] else None


def load_external_rankings(source_date):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                ranking_type,
                external_rank,
                player_name,
                team,
                position_type,
                external_score,
                source_date
            FROM external_player_rankings
            WHERE source_name = ?
              AND source_date = ?
            ORDER BY ranking_type, external_rank
        """, (SEED_RANKING_SOURCE, source_date)).fetchall()
    return [dict(row) for row in rows]


def build_external_indexes(external_rows):
    by_name_team_position = defaultdict(list)
    by_name_team = defaultdict(list)
    by_name = defaultdict(list)

    for row in external_rows:
        name_key = normalize_name(row["player_name"])
        team_key = normalize_team(row["team"])
        position_key = clean_text(row["position_type"])
        by_name_team_position[(name_key, team_key, position_key)].append(row)
        by_name_team[(name_key, team_key)].append(row)
        by_name[name_key].append(row)

    return by_name_team_position, by_name_team, by_name


def choose_best_external_row(rows):
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("external_score") or 0),
            -int(row.get("external_rank") or 999999),
        ),
        reverse=True,
    )[0]


def match_player_to_external(player, indexes):
    by_name_team_position, by_name_team, by_name = indexes
    name_key = normalize_name(player["name"])
    team_key = normalize_team(player["team"])
    position_key = clean_text(player["fantasy_position_type"])

    exact_rows = by_name_team_position.get((name_key, team_key, position_key), [])
    if exact_rows:
        return choose_best_external_row(exact_rows), "exact"

    name_team_rows = by_name_team.get((name_key, team_key), [])
    if len(name_team_rows) == 1:
        return name_team_rows[0], "name_team"
    if len(name_team_rows) > 1:
        return choose_best_external_row(name_team_rows), "name_team_multi_best_score"

    name_only_rows = by_name.get(name_key, [])
    if name_only_rows:
        return None, "name_only_not_auto_matched"

    return None, "not_found"


def canonical_seed_player_ids(seed_date=SEASON_START_DATE):
    """
    v3 초기 cohort를 선택합니다.

    포함 기준:
    1. 최신 market_daily_v2 canonical cohort
    2. market_daily_v2가 없으면 활성 registered_players
    3. registered_players에 이미 존재하고 2026 시즌 fantasy_daily_scores 기록이 있는 선수

    중요:
    - fantasy_daily_scores에만 등장한 이름을 registered_players에 새로 자동 등록하지 않습니다.
    - 이미 registered_players에 존재하는 비활성/미등록 선수라도 시즌 기록이 있으면
      선수 상세에서 0.0 가격/가격 기록 없음이 뜨지 않도록 v3 가격 시장에 포함합니다.
    """
    seed_date = to_game_date(seed_date)

    with get_conn() as conn:
        latest_v2 = conn.execute("""
            SELECT MAX(basis_date) AS basis_date
            FROM player_prices
            WHERE basis_source = 'market_daily_v2'
        """).fetchone()["basis_date"]

        candidate_date = latest_v2 or seed_date
        rows = []
        if candidate_date:
            rows = conn.execute("""
                SELECT
                    pp.registered_player_id,
                    pp.price_role,
                    rp.name,
                    rp.team,
                    rp.fantasy_position_type,
                    rp.is_active
                FROM player_prices pp
                JOIN registered_players rp
                  ON rp.id = pp.registered_player_id
                WHERE pp.basis_source = 'market_daily_v2'
                  AND pp.basis_date = ?
                ORDER BY rp.is_active DESC, rp.team, rp.name, pp.registered_player_id
            """, (candidate_date,)).fetchall()

        if not rows:
            rows = conn.execute("""
                SELECT
                    id AS registered_player_id,
                    NULL AS price_role,
                    name,
                    team,
                    fantasy_position_type,
                    is_active
                FROM registered_players
                WHERE is_active = 1
                ORDER BY team, name, id
            """).fetchall()

        scored_rows = conn.execute("""
            WITH scored AS (
                SELECT
                    player_name,
                    team,
                    position_type,
                    COUNT(*) AS scored_games,
                    SUM(points) AS season_points
                FROM fantasy_daily_scores
                WHERE game_date >= ?
                GROUP BY player_name, team, position_type
            )
            SELECT
                rp.id AS registered_player_id,
                NULL AS price_role,
                rp.name,
                rp.team,
                rp.fantasy_position_type,
                rp.is_active
            FROM registered_players rp
            JOIN scored
              ON scored.player_name = rp.name
             AND scored.team = rp.team
             AND scored.position_type = rp.fantasy_position_type
            ORDER BY rp.is_active DESC, scored.season_points DESC, rp.team, rp.name, rp.id
        """, (SEASON_START_DATE,)).fetchall()

    canonical_by_identity = {}
    previous_role_by_id = {}

    def candidate_priority(row, source_priority):
        # source_priority: market_daily_v2 canonical cohort가 가장 우선입니다.
        # 같은 identity가 여러 registered_player_id로 존재하면 기존 가격 history가 있는 row를 유지합니다.
        return (
            -source_priority,
            int(row["is_active"] or 0),
            -int(row["registered_player_id"] or 0),
        )

    for source_priority, row in [(0, row) for row in rows] + [(1, row) for row in scored_rows]:
        row_dict = dict(row)
        identity_key = (
            clean_text(row_dict.get("name")),
            clean_text(row_dict.get("team")),
            clean_text(row_dict.get("fantasy_position_type")),
        )
        current = canonical_by_identity.get(identity_key)
        if current is None or candidate_priority(row_dict, source_priority) > current["priority"]:
            canonical_by_identity[identity_key] = {
                "row": row_dict,
                "priority": candidate_priority(row_dict, source_priority),
            }

    selected = []
    seen_ids = set()
    for item in sorted(
        canonical_by_identity.values(),
        key=lambda item: (
            clean_text(item["row"].get("team")),
            clean_text(item["row"].get("fantasy_position_type")),
            clean_text(item["row"].get("name")),
            int(item["row"].get("registered_player_id") or 0),
        ),
    ):
        row = item["row"]
        registered_player_id = int(row["registered_player_id"])
        if registered_player_id in seen_ids:
            continue
        seen_ids.add(registered_player_id)
        selected.append(registered_player_id)
        if row.get("price_role"):
            previous_role_by_id[registered_player_id] = row["price_role"]

    return selected, previous_role_by_id


def load_registered_players_by_ids(registered_player_ids):
    if not registered_player_ids:
        return []
    placeholders = ",".join("?" for _ in registered_player_ids)
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                id,
                player_id,
                name,
                team,
                roster_position,
                fantasy_position_type,
                detail_position,
                is_active
            FROM registered_players
            WHERE id IN ({placeholders})
            ORDER BY team, fantasy_position_type, name, id
        """, tuple(registered_player_ids)).fetchall()
    return [dict(row) for row in rows]


def determine_seed_price_role(player, previous_role=None):
    if player["fantasy_position_type"] == "batter":
        return "batter"

    if previous_role in {"starting_pitcher", "bullpen_pitcher"}:
        return previous_role

    if clean_text(player.get("detail_position")) == "선발투수":
        return "starting_pitcher"

    return "bullpen_pitcher"


def assign_seed_prices(seed_rows):
    grouped = defaultdict(list)
    for row in seed_rows:
        grouped[row["price_role"]].append(row)

    for role, rows in grouped.items():
        scored = [row for row in rows if float(row.get("external_score") or 0) > 0]
        unscored = [row for row in rows if float(row.get("external_score") or 0) <= 0]

        scored.sort(
            key=lambda row: (
                float(row.get("external_score") or 0),
                -int(row.get("external_rank") or 999999),
            ),
            reverse=True,
        )

        n = len(scored)
        for index, row in enumerate(scored):
            # 상위권은 넓게, 중하위권은 촘촘하게 분포시킵니다.
            if n <= 1:
                percentile = 100.0
            else:
                percentile = 100.0 * (1.0 - index / (n - 1))

            target = target_price_from_value_percentile(percentile, row["price_role"])
            row["price_decimal"] = clamp_price(target)
            row["price"] = price_to_integer(row["price_decimal"])
            row["tier"] = tier_from_price(row["price_decimal"])
            row["price_score"] = float(row.get("external_score") or 0)

        for row in unscored:
            row["price_decimal"] = default_price_for_role(row["price_role"])
            row["price"] = price_to_integer(row["price_decimal"])
            row["tier"] = tier_from_price(row["price_decimal"])
            row["price_score"] = 0.0

    return seed_rows


def build_seed_price_rows(seed_date=SEASON_START_DATE, external_source_date=None):
    external_source_date = external_source_date or get_latest_external_source_date()
    if not external_source_date:
        raise RuntimeError(
            "external_player_rankings에 welcometopranking 데이터가 없습니다. "
            "먼저 ./venv/bin/python sync_external_topranking.py 2026 을 실행하세요."
        )

    registered_player_ids, previous_role_by_id = canonical_seed_player_ids(seed_date)
    registered_players = load_registered_players_by_ids(registered_player_ids)
    external_rows = load_external_rankings(external_source_date)
    indexes = build_external_indexes(external_rows)

    seed_rows = []
    failed_matches = []
    match_counter = Counter()

    for player in registered_players:
        matched_row, match_type = match_player_to_external(player, indexes)
        match_counter[match_type] += 1
        price_role = determine_seed_price_role(
            player,
            previous_role=previous_role_by_id.get(int(player["id"])),
        )

        if matched_row is None:
            external_score = 0.0
            external_rank = None
            failed_matches.append({
                "registered_player_id": player["id"],
                "player_name": player["name"],
                "team": player["team"],
                "role": price_role,
                "match_type": match_type,
            })
        else:
            external_score = float(matched_row["external_score"] or 0)
            external_rank = matched_row["external_rank"]

        seed_rows.append({
            "registered_player_id": int(player["id"]),
            "player_id": player["player_id"],
            "player_name": player["name"],
            "team": player["team"],
            "roster_position": player["roster_position"],
            "fantasy_position_type": player["fantasy_position_type"],
            "external_score": external_score,
            "external_rank": external_rank,
            "price_role": price_role,
            "price_score": external_score,
            "tier": "D",
            "price": 1,
            "price_decimal": 1.0,
            "basis_source": BASIS_SOURCE,
            "basis_date": seed_date,
            "seed_external_source_date": external_source_date,
        })

    seed_rows = assign_seed_prices(seed_rows)
    return seed_rows, failed_matches, match_counter, external_source_date


def save_seed_price_rows(seed_rows, seed_date):
    if not seed_rows:
        return 0
    with get_conn() as conn:
        for row in seed_rows:
            conn.execute("""
                INSERT INTO player_prices (
                    registered_player_id,
                    player_id,
                    player_name,
                    team,
                    roster_position,
                    fantasy_position_type,
                    external_score,
                    external_rank,
                    price_role,
                    price_score,
                    tier,
                    price,
                    price_decimal,
                    basis_source,
                    basis_date,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(registered_player_id, basis_source, basis_date)
                DO UPDATE SET
                    player_id = excluded.player_id,
                    player_name = excluded.player_name,
                    team = excluded.team,
                    roster_position = excluded.roster_position,
                    fantasy_position_type = excluded.fantasy_position_type,
                    external_score = excluded.external_score,
                    external_rank = excluded.external_rank,
                    price_role = excluded.price_role,
                    price_score = excluded.price_score,
                    tier = excluded.tier,
                    price = excluded.price,
                    price_decimal = excluded.price_decimal,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                row["registered_player_id"],
                row["player_id"],
                row["player_name"],
                row["team"],
                row["roster_position"],
                row["fantasy_position_type"],
                row["external_score"],
                row["external_rank"],
                row["price_role"],
                row["price_score"],
                row["tier"],
                row["price"],
                row["price_decimal"],
                BASIS_SOURCE,
                seed_date,
            ))
    return len(seed_rows)


# -----------------------------------------------------------------------------
# 경기/점수 조회
# -----------------------------------------------------------------------------

def recent_start_count_for_pitcher(conn, player_name, team, basis_date):
    """
    기준일 포함 최근 14일 동안 실제 선발 등판 기록 수를 반환합니다.
    이 값은 시장 활동/말소 추정용 보조 지표로만 사용하고,
    선발/불펜 role 결정에는 사용하지 않습니다.
    """
    end_dt = parse_date_any(basis_date)
    start_dt = end_dt - timedelta(days=13)
    row = conn.execute("""
        SELECT COUNT(*) AS cnt
        FROM raw_pitcher_stats
        WHERE player_name = ?
          AND team = ?
          AND game_date BETWEEN ? AND ?
          AND is_starting_pitcher = 1
    """, (
        player_name,
        team,
        start_dt.strftime("%Y-%m-%d"),
        end_dt.strftime("%Y-%m-%d"),
    )).fetchone()
    return int(row["cnt"] or 0)


def latest_pitching_role_for_date(conn, player_name, team, basis_date):
    """
    기준일 이전/당일의 가장 최근 실제 투수 등판 역할을 반환합니다.

    반환값:
    - "starting_pitcher": 가장 최근 등판이 선발 등판(is_starting_pitcher=1)
    - "bullpen_pitcher": 가장 최근 등판이 불펜 등판(is_starting_pitcher=0)
    - None: 기준일까지 실제 투수 등판 기록이 없음

    중요:
    - 오래 선발 등판이 없다는 이유만으로 불펜으로 강등하지 않습니다.
    - 실제 불펜 등판 row가 있을 때만 bullpen_pitcher를 반환합니다.
    - raw_pitcher_stats.is_starting_pitcher와 pitching_order는 scraper/sync_db가
      투수 기록표 순서 기준으로 저장한 실제 등판 역할입니다.
    """
    basis_date = to_game_date(basis_date)
    row = conn.execute("""
        SELECT
            game_date,
            COALESCE(is_starting_pitcher, 0) AS is_starting_pitcher,
            pitching_order
        FROM raw_pitcher_stats
        WHERE player_name = ?
          AND team = ?
          AND game_date <= ?
        ORDER BY game_date DESC, COALESCE(pitching_order, 999) DESC, game_id DESC
        LIMIT 1
    """, (player_name, team, basis_date)).fetchone()

    if not row:
        return None

    if int(row["is_starting_pitcher"] or 0) == 1:
        return "starting_pitcher"
    return "bullpen_pitcher"


def determine_price_role_for_date(conn, player, basis_date):
    if player["fantasy_position_type"] == "batter":
        return "batter"

    latest_role = latest_pitching_role_for_date(
        conn,
        player["player_name"],
        player["team"],
        basis_date,
    )
    if latest_role in {"starting_pitcher", "bullpen_pitcher"}:
        return latest_role

    # 기준일까지 실제 투수 등판 기록이 없는 경우만 기존 등록 상세 역할을 fallback으로 사용합니다.
    if clean_text(player.get("detail_position")) == "선발투수":
        return "starting_pitcher"
    return "bullpen_pitcher"


def refresh_pitcher_detail_positions_for_date(basis_date):
    """
    화면/팀/가격 role 기준이 어긋나지 않도록 registered_players.detail_position을
    기준일 이전/당일의 가장 최근 실제 투수 등판 역할 기준으로 동기화합니다.

    규칙:
    - 가장 최근 실제 투수 등판이 선발이면 선발투수
    - 가장 최근 실제 투수 등판이 불펜이면 불펜투수
    - 오래 선발 등판이 없다는 이유만으로 불펜투수로 강등하지 않음
    - 실제 불펜 등판 기록이 있을 때만 불펜투수로 변경

    주의:
    - pitcher만 수정합니다.
    - 등판 기록이 전혀 없는 투수의 기존 detail_position은 보존합니다.
    - 선수/팀/유저/가격 row 삭제 없음.
    - dry-run에서는 호출하지 않습니다.
    """
    basis_date = to_game_date(basis_date)
    end_date = basis_date

    with get_conn() as conn:
        latest_role_rows = conn.execute("""
            WITH latest_appearances AS (
                SELECT
                    rp.id AS registered_player_id,
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
                  AND rps.game_date <= ?
            )
            SELECT registered_player_id, new_detail_position
            FROM latest_appearances
            WHERE rn = 1
        """, (end_date,)).fetchall()

        starter_ids = [int(row["registered_player_id"]) for row in latest_role_rows if row["new_detail_position"] == "선발투수"]
        bullpen_ids = [int(row["registered_player_id"]) for row in latest_role_rows if row["new_detail_position"] == "불펜투수"]

        starter_updated_count = 0
        bullpen_updated_count = 0

        if starter_ids:
            placeholders = ",".join("?" for _ in starter_ids)
            cursor = conn.execute(f"""
                UPDATE registered_players
                SET detail_position = '선발투수',
                    detail_position_source = 'latest_actual_pitching_role_v3',
                    detail_position_updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                  AND COALESCE(detail_position, '') != '선발투수'
            """, tuple(starter_ids))
            starter_updated_count = cursor.rowcount

        if bullpen_ids:
            placeholders = ",".join("?" for _ in bullpen_ids)
            cursor = conn.execute(f"""
                UPDATE registered_players
                SET detail_position = '불펜투수',
                    detail_position_source = 'latest_actual_pitching_role_v3',
                    detail_position_updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                  AND COALESCE(detail_position, '') != '불펜투수'
            """, tuple(bullpen_ids))
            bullpen_updated_count = cursor.rowcount

        total_pitchers = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM registered_players
            WHERE fantasy_position_type = 'pitcher'
        """).fetchone()["cnt"]

    return {
        "basis_date": basis_date,
        "start_date": "latest_actual_appearance",
        "end_date": end_date,
        "starting_pitchers": len(starter_ids),
        "bullpen_pitchers": len(bullpen_ids),
        "total_pitchers": int(total_pitchers or 0),
        "starter_updated_count": starter_updated_count,
        "bullpen_updated_count": bullpen_updated_count,
    }

def fetch_daily_score(conn, player, game_date):
    row = conn.execute("""
        SELECT game_id, game_date, points
        FROM fantasy_daily_scores
        WHERE player_name = ?
          AND team = ?
          AND position_type = ?
          AND game_date = ?
        ORDER BY game_id
        LIMIT 1
    """, (
        player["player_name"],
        player["team"],
        player["fantasy_position_type"],
        game_date,
    )).fetchone()

    if not row:
        return {
            "appeared_today": False,
            "today_points": 0.0,
            "today_game_id": None,
            "started_today": False,
            "bullpen_today": False,
        }

    started_today = False
    bullpen_today = False
    if player["fantasy_position_type"] == "pitcher":
        p_row = conn.execute("""
            SELECT is_starting_pitcher
            FROM raw_pitcher_stats
            WHERE game_id = ?
              AND player_name = ?
              AND team = ?
        """, (row["game_id"], player["player_name"], player["team"])).fetchone()
        if p_row:
            started_today = int(p_row["is_starting_pitcher"] or 0) == 1
            bullpen_today = not started_today

    return {
        "appeared_today": True,
        "today_points": float(row["points"] or 0),
        "today_game_id": row["game_id"],
        "started_today": started_today,
        "bullpen_today": bullpen_today,
    }


def fetch_score_rows(conn, player, start_date, end_date):
    rows = conn.execute("""
        SELECT game_id, game_date, points
        FROM fantasy_daily_scores
        WHERE player_name = ?
          AND team = ?
          AND position_type = ?
          AND game_date BETWEEN ? AND ?
        ORDER BY game_date, game_id
    """, (
        player["player_name"],
        player["team"],
        player["fantasy_position_type"],
        start_date,
        end_date,
    )).fetchall()
    return [dict(row) for row in rows]


def fetch_pitcher_role_rows(conn, player, start_date, end_date, starting=True, limit=None):
    order_limit = ""
    if limit is not None:
        order_limit = " LIMIT ?"

    params = [
        player["player_name"],
        player["team"],
        start_date,
        end_date,
        1 if starting else 0,
    ]

    sql = f"""
        SELECT
            fds.game_id,
            fds.game_date,
            fds.points,
            rps.is_starting_pitcher
        FROM raw_pitcher_stats rps
        JOIN fantasy_daily_scores fds
          ON fds.game_id = rps.game_id
         AND fds.player_name = rps.player_name
         AND fds.team = rps.team
         AND fds.position_type = 'pitcher'
        WHERE rps.player_name = ?
          AND rps.team = ?
          AND rps.game_date BETWEEN ? AND ?
          AND rps.is_starting_pitcher = ?
        ORDER BY rps.game_date DESC, rps.game_id DESC
        {order_limit}
    """

    if limit is not None:
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    # 최신순으로 가져온 뒤 계산은 과거→최신 순서가 읽기 좋습니다.
    return [dict(row) for row in reversed(rows)]


def get_team_game_count(conn, team, start_date, end_date):
    row = conn.execute("""
        SELECT COUNT(*) AS cnt
        FROM games
        WHERE game_date BETWEEN ? AND ?
          AND (away_team = ? OR home_team = ?)
    """, (start_date, end_date, team, team)).fetchone()
    return int(row["cnt"] or 0)


def get_teams_with_games_on_date(conn, game_date):
    rows = conn.execute("""
        SELECT away_team, home_team
        FROM games
        WHERE game_date = ?
    """, (game_date,)).fetchall()

    teams = set()
    for row in rows:
        teams.add(normalize_team(row["away_team"]))
        teams.add(normalize_team(row["home_team"]))
    return teams


def get_last_appearance_date(conn, player, end_date, role=None):
    if player["fantasy_position_type"] == "batter" or role == "batter":
        row = conn.execute("""
            SELECT MAX(game_date) AS game_date
            FROM fantasy_daily_scores
            WHERE player_name = ?
              AND team = ?
              AND position_type = ?
              AND game_date <= ?
        """, (
            player["player_name"],
            player["team"],
            player["fantasy_position_type"],
            end_date,
        )).fetchone()
        return row["game_date"] if row and row["game_date"] else None

    if role == "starting_pitcher":
        row = conn.execute("""
            SELECT MAX(game_date) AS game_date
            FROM raw_pitcher_stats
            WHERE player_name = ?
              AND team = ?
              AND game_date <= ?
              AND is_starting_pitcher = 1
        """, (player["player_name"], player["team"], end_date)).fetchone()
        return row["game_date"] if row and row["game_date"] else None

    row = conn.execute("""
        SELECT MAX(game_date) AS game_date
        FROM raw_pitcher_stats
        WHERE player_name = ?
          AND team = ?
          AND game_date <= ?
          AND is_starting_pitcher = 0
    """, (player["player_name"], player["team"], end_date)).fetchone()
    return row["game_date"] if row and row["game_date"] else None


def team_games_since_last_appearance(conn, player, end_date, role):
    last_date = get_last_appearance_date(conn, player, end_date, role)
    if last_date:
        start = (parse_date_any(last_date) + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        start = SEASON_START_DATE
    return get_team_game_count(conn, player["team"], start, end_date), last_date




def get_latest_registered_source_date_for_price(conn):
    row = conn.execute("""
        SELECT MAX(source_date) AS latest_source_date
        FROM registered_players
        WHERE source_date IS NOT NULL
    """).fetchone()
    return row["latest_source_date"] if row else None


def count_player_appearance_on_date(conn, player_name, team, position_type, game_date):
    row = conn.execute("""
        SELECT COUNT(*) AS games, MAX(game_date) AS last_game_date
        FROM fantasy_daily_scores
        WHERE player_name = ?
          AND team = ?
          AND position_type = ?
          AND game_date = ?
    """, (player_name, team, position_type, game_date)).fetchone()
    return int(row["games"] or 0) if row else 0, (row["last_game_date"] if row else None)

def market_activity_status(conn, player, basis_date):
    """
    가격 엔진에서 사용할 활성/말소 기준을 계산합니다.

    최종 기준:
    - KBO 등록 현황 기준 날짜가 basis_date와 같으면 registered_players.is_active만 사용합니다.
    - 등록 현황 기준 날짜가 basis_date와 다르면 등록 현황이 경기 날짜와 어긋난 상황입니다.
      이 경우 basis_date 당일 실제 출전/등판한 선수는 active benchmark에 포함하여
      말소 패널티를 잘못 받지 않게 합니다.

    최근 7일 출전 기록만으로 active 처리하지 않습니다.
    fallback은 오직 등록 현황 날짜 불일치 + 해당 경기일 출전일 때만 적용합니다.
    """
    basis_date = to_game_date(basis_date)

    raw_active = int(player.get("is_active") or 0) == 1
    name = player["player_name"]
    team = player["team"]
    position_type = player["fantasy_position_type"]

    register_source_date = get_latest_registered_source_date_for_price(conn)
    register_date_matches_basis = bool(register_source_date and register_source_date == basis_date)

    appearance_count, last_game_date = count_player_appearance_on_date(
        conn,
        name,
        team,
        position_type,
        basis_date,
    )
    recent_start_count = recent_start_count_for_pitcher(conn, name, team, basis_date) if position_type == "pitcher" else 0

    fallback_active = (not register_date_matches_basis) and appearance_count > 0
    market_active = bool(raw_active or fallback_active)

    if raw_active:
        reason = "registered_active"
    elif fallback_active:
        reason = "basis_date_appearance_register_date_mismatch"
    else:
        reason = "inactive_tracking_only"

    return {
        "raw_is_active": 1 if raw_active else 0,
        "market_active": 1 if market_active else 0,
        "market_activity_reason": reason,
        "recent_activity_games": appearance_count,
        "recent_activity_last_game_date": last_game_date,
        "recent_start_count_14d": recent_start_count,
        "register_source_date": register_source_date,
        "register_date_matches_basis": 1 if register_date_matches_basis else 0,
    }

def previous_absence_total(conn, registered_player_id, basis_date):
    row = conn.execute("""
        SELECT absence_penalty_total
        FROM player_price_adjustments
        WHERE basis_source = ?
          AND registered_player_id = ?
          AND basis_date < ?
          AND is_applied = 1
        ORDER BY basis_date DESC, id DESC
        LIMIT 1
    """, (BASIS_SOURCE, registered_player_id, basis_date)).fetchone()
    if not row:
        return 0.0
    return float(row["absence_penalty_total"] or 0.0)


def starting_correction_count_since_latest_start(conn, player, latest_start_game_id, basis_date):
    if not latest_start_game_id:
        return 0
    rows = conn.execute("""
        SELECT performance_reason_json
        FROM player_price_adjustments
        WHERE basis_source = ?
          AND registered_player_id = ?
          AND basis_date < ?
          AND is_applied = 1
        ORDER BY basis_date DESC, id DESC
        LIMIT 20
    """, (BASIS_SOURCE, player["registered_player_id"], basis_date)).fetchall()

    count = 0
    for row in rows:
        try:
            data = json.loads(row["performance_reason_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if data.get("latest_start_game_id") != latest_start_game_id:
            continue
        if data.get("starting_no_start_market_correction"):
            count += 1
    return count


# -----------------------------------------------------------------------------
# 지표 계산
# -----------------------------------------------------------------------------

def average(values):
    values = [float(v or 0) for v in values]
    if not values:
        return 0.0
    return sum(values) / len(values)


def percentile_scores(values_by_id):
    """
    값이 클수록 높은 percentile을 반환합니다. 0~100 범위입니다.
    동점은 같은 값을 받습니다.
    """
    items = [(pid, float(value or 0)) for pid, value in values_by_id.items()]
    if not items:
        return {}
    if len(items) == 1:
        return {items[0][0]: 100.0}

    sorted_values = sorted(value for _, value in items)
    value_to_percentile = {}
    n = len(sorted_values)

    for value in sorted_values:
        if value in value_to_percentile:
            continue
        less = sum(1 for v in sorted_values if v < value)
        equal = sum(1 for v in sorted_values if v == value)
        rank_position = less + (equal - 1) / 2
        percentile = 100.0 * rank_position / (n - 1)
        value_to_percentile[value] = percentile

    return {pid: value_to_percentile[value] for pid, value in items}



def price_expectation_bucket(price):
    """현재 가격대별 기대 수입 peer group을 나눕니다."""
    price = float(price or 0)
    if price >= 12.0:
        return "elite"
    if price >= 8.0:
        return "high"
    if price >= 4.0:
        return "mid"
    return "low"


def expectation_floor_for_role(role):
    """기대치 분모가 너무 작아져서 작은 점수에도 과민 반응하는 것을 막는 역할별 기준선입니다."""
    if role == "starting_pitcher":
        return 350.0
    if role == "bullpen_pitcher":
        return 120.0
    return 120.0


def expectation_role_average(row, role):
    if role == "starting_pitcher":
        return float(row.get("season_start_avg") or 0.0)
    if role == "bullpen_pitcher":
        return float(row.get("season_bullpen_avg") or 0.0)
    return float(row.get("season_avg") or 0.0)


def calculate_expected_points(row, role, peer_price_bucket_avg, role_avg):
    """
    선수별 기대 수입을 계산합니다.

    절대 점수(예: 300점)가 아니라, 이 선수 기준으로 오늘 얼마나 잘했는지 판단하기 위한 기준입니다.
    표본이 충분하면 자기 시즌/최근 흐름을 더 믿고, 표본이 적으면 같은 역할/가격대 평균을 더 섞습니다.
    """
    peer = float(peer_price_bucket_avg if peer_price_bucket_avg is not None else role_avg or 0.0)
    if role == "starting_pitcher":
        sample = int(row.get("season_starts", 0) or 0)
        season = float(row.get("season_start_avg") or 0.0)
        recent = float(row.get("recent2_start_avg") or 0.0)
        if sample >= 5:
            weights = (0.40, 0.40, 0.20)
        elif sample >= 2:
            weights = (0.25, 0.45, 0.30)
        else:
            weights = (0.10, 0.35, 0.55)
    elif role == "bullpen_pitcher":
        sample = int(row.get("season_bullpen_games", 0) or 0)
        season = float(row.get("season_bullpen_avg") or 0.0)
        recent = float(row.get("recent5_bullpen_avg") or 0.0)
        if sample >= 8:
            weights = (0.35, 0.45, 0.20)
        elif sample >= 3:
            weights = (0.25, 0.45, 0.30)
        else:
            weights = (0.10, 0.35, 0.55)
    else:
        sample = int(row.get("season_appearances", 0) or 0)
        season = float(row.get("season_avg") or 0.0)
        recent = float(row.get("recent5_avg") or 0.0)
        if sample >= 12:
            weights = (0.45, 0.35, 0.20)
        elif sample >= 5:
            weights = (0.35, 0.40, 0.25)
        elif sample >= 2:
            weights = (0.20, 0.40, 0.40)
        else:
            weights = (0.10, 0.30, 0.60)

    expected = season * weights[0] + recent * weights[1] + peer * weights[2]
    # 음수/극저 기대치로 인해 100점 출전만으로 breakout처럼 보이는 현상을 방지합니다.
    reference = max(expected, expectation_floor_for_role(role))
    return round(expected, 4), round(reference, 4), {
        "season_weight": weights[0],
        "recent_weight": weights[1],
        "peer_weight": weights[2],
        "season_component": round(season, 4),
        "recent_component": round(recent, 4),
        "peer_price_bucket_component": round(peer, 4),
        "sample_size": sample,
    }


def event_points_for_expectation(metrics):
    """역할별로 이번 가격 업데이트에서 실제 평가할 당일 이벤트 점수입니다."""
    role = metrics.get("price_role")
    if role == "starting_pitcher":
        if not metrics.get("started_today"):
            return None
        return float(metrics.get("today_points") or metrics.get("latest_start_points") or 0.0)
    if role == "bullpen_pitcher":
        if not metrics.get("bullpen_today"):
            return None
        return float(metrics.get("today_bullpen_points") or metrics.get("today_points") or 0.0)
    if not metrics.get("appeared_today"):
        return None
    return float(metrics.get("today_points") or 0.0)


def target_price_from_value_percentile(percentile, price_role="starting_pitcher"):
    p = max(0.0, min(100.0, float(percentile or 0)))
    bands = ROLE_PRICE_BANDS.get(price_role, ROLE_PRICE_BANDS["starting_pitcher"])

    for low, high, price_low, price_high in bands:
        if p >= low:
            if high == low:
                return clamp_price(price_high)
            ratio = (p - low) / (high - low)
            return clamp_price(price_low + ratio * (price_high - price_low))

    return clamp_price(bands[-1][2] if bands else MIN_PRICE)


def change_from_pressure(pressure):
    pressure = float(pressure or 0)

    # target 근처에서 +0.1/-0.1이 반복되는 진동을 막기 위해
    # 0.5 미만의 괴리는 유지로 둡니다.
    # 그래도 target 괴리가 분명한 선수는 역동적으로 움직이도록
    # 1.4 / 2.8 / 4.2 구간부터 큰 변동폭을 줍니다.
    if pressure >= 4.2:
        return 0.5
    if pressure >= 2.8:
        return 0.4
    if pressure >= 1.4:
        return 0.3
    if pressure >= 0.5:
        return 0.1
    if pressure <= -4.2:
        return -0.5
    if pressure <= -2.8:
        return -0.4
    if pressure <= -1.4:
        return -0.3
    if pressure <= -0.5:
        return -0.1
    return 0.0


def season_anchor_floor(season_total_percentile, price_role="starting_pitcher"):
    p = float(season_total_percentile or 0)
    for threshold, floor in ROLE_SEASON_ANCHOR_FLOORS.get(
        price_role,
        ROLE_SEASON_ANCHOR_FLOORS["starting_pitcher"],
    ):
        if p >= threshold:
            return float(floor)
    return None


def weaken_anchor_floor(anchor_floor, metrics):
    if anchor_floor is None:
        return None, []

    reasons = []
    floor = float(anchor_floor)
    role = metrics["price_role"]

    if metrics.get("is_active") == 0:
        floor -= 2.0
        reasons.append("KBO 등록 말소 상태로 시즌 상위권 보정 약화")

    if role == "batter":
        if metrics.get("team_games_since_last", 0) >= 7:
            floor -= 3.0
            reasons.append("장기 미출전으로 시즌 상위권 보정 약화")
        if metrics.get("recent5_total", 0) <= 0 and metrics.get("season_appearances", 0) >= 5:
            floor -= 1.5
            reasons.append("최근 5경기 부진으로 시즌 상위권 보정 약화")

    elif role == "starting_pitcher":
        if metrics.get("days_since_latest_start", 0) >= 18:
            floor -= 2.0
            reasons.append("최근 선발 공백으로 시즌 상위권 보정 약화")
        if metrics.get("recent2_start_total", 0) <= 0 and metrics.get("season_starts", 0) >= 2:
            floor -= 1.0
            reasons.append("최근 선발 등판 부진으로 시즌 상위권 보정 약화")

    elif role == "bullpen_pitcher":
        if metrics.get("team_games_since_last", 0) >= 8:
            floor -= 2.0
            reasons.append("장기 미등판으로 시즌 상위권 보정 약화")
        if metrics.get("recent5_bullpen_total", 0) <= 0 and metrics.get("season_bullpen_games", 0) >= 5:
            floor -= 1.0
            reasons.append("최근 불펜 등판 부진으로 시즌 상위권 보정 약화")

    floor = max(1.0, floor)
    return floor, reasons


def desired_absence_total(metrics):
    """
    active/benchmark 선수용 미출전 패널티입니다.

    active 선수는 아직 등록 명단에 있고, 휴식/로테이션/상황상 미출전이 자연스러울 수 있으므로
    기존처럼 보수적인 단계별 총량 패널티만 적용합니다.
    """
    role = metrics["price_role"]

    if role == "batter":
        games = int(metrics.get("team_games_since_last", 0) or 0)
        if games >= 10:
            return -0.3, "최근 10팀경기 이상 미출전"
        if games >= 6:
            return -0.2, "최근 6~9팀경기 미출전"
        if games >= 3:
            return -0.1, "최근 3~5팀경기 미출전"
        return 0.0, None

    if role == "starting_pitcher":
        days = int(metrics.get("days_since_latest_start", 0) or 0)
        if days >= 35:
            return -0.3, "최근 35일 이상 선발 미등판"
        if days >= 25:
            return -0.2, "최근 25일 이상 선발 미등판"
        if days >= 18:
            return -0.1, "최근 18일 이상 선발 미등판"
        return 0.0, None

    games = int(metrics.get("team_games_since_last", 0) or 0)
    if games >= 12:
        return -0.3, "최근 12팀경기 이상 불펜 미등판"
    if games >= 8:
        return -0.2, "최근 8~11팀경기 불펜 미등판"
    if games >= 5:
        return -0.1, "최근 5~7팀경기 불펜 미등판"
    return 0.0, None


def desired_inactive_absence_total(metrics, previous_absence):
    """
    inactive/KBO 등록이 말소된 선수용 강한 미출전 패널티입니다.

    inactive 선수는 등록 선수 benchmark에서 제외되므로 성적 percentile/target 가격 변동을 거의 받지 않습니다.
    따라서 가격이 멈춰 보이지 않도록, 장기 미출전 구간에서는 매 가격 업데이트마다 하락시킵니다.

    단, 무한 하락은 막기 위해 역할별 누적 cap을 둡니다.
    - 타자: 최대 -2.5
    - 불펜: 최대 -2.2
    - 선발: 최대 -2.0
    """
    role = metrics["price_role"]
    previous_absence = float(previous_absence or 0.0)

    # inactive로 남아 있더라도 실제로 해당 basis_date에 출전/등판했다면,
    # 말소 패널티를 한 번에 전부 회복하지 않고 최대 +0.2까지만 천천히 회복합니다.
    if metrics.get("appeared_today"):
        recovered_total = min(0.0, previous_absence + 0.2)
        return signed_change(recovered_total), "복귀 후 출전으로 미출전 패널티 일부 회복"

    if role == "batter":
        games = int(metrics.get("team_games_since_last", 0) or 0)
        cap = -2.5
        if games >= 15:
            step, reason = -0.4, "KBO 등록이 말소된 선수: 15팀경기 이상 미출전"
        elif games >= 10:
            step, reason = -0.3, "KBO 등록이 말소된 선수: 10~14팀경기 미출전"
        elif games >= 6:
            step, reason = -0.2, "KBO 등록이 말소된 선수: 6~9팀경기 미출전"
        elif games >= 3:
            step, reason = -0.1, "KBO 등록이 말소된 선수: 3~5팀경기 미출전"
        else:
            return previous_absence, None

        return signed_change(max(cap, previous_absence + step)), reason

    if role == "starting_pitcher":
        days = int(metrics.get("days_since_latest_start", 0) or 0)
        cap = -2.0
        if days >= 45:
            step, reason = -0.4, "KBO 등록이 말소된 선수: 45일 이상 선발 미등판"
        elif days >= 35:
            step, reason = -0.3, "KBO 등록이 말소된 선수: 35~44일 선발 미등판"
        elif days >= 25:
            step, reason = -0.2, "KBO 등록이 말소된 선수: 25~34일 선발 미등판"
        elif days >= 18:
            step, reason = -0.1, "KBO 등록이 말소된 선수: 18~24일 선발 미등판"
        else:
            return previous_absence, None

        return signed_change(max(cap, previous_absence + step)), reason

    games = int(metrics.get("team_games_since_last", 0) or 0)
    cap = -2.2
    if games >= 18:
        step, reason = -0.4, "KBO 등록이 말소된 선수: 18팀경기 이상 불펜 미등판"
    elif games >= 12:
        step, reason = -0.3, "KBO 등록이 말소된 선수: 12~17팀경기 불펜 미등판"
    elif games >= 8:
        step, reason = -0.2, "KBO 등록이 말소된 선수: 8~11팀경기 불펜 미등판"
    elif games >= 5:
        step, reason = -0.1, "KBO 등록이 말소된 선수: 5~7팀경기 불펜 미등판"
    else:
        return previous_absence, None

    return signed_change(max(cap, previous_absence + step)), reason


def build_player_metrics(players, basis_date):
    basis_date = to_game_date(basis_date)
    basis_dt = parse_date_any(basis_date)
    recent14_start = (basis_dt - timedelta(days=13)).strftime("%Y-%m-%d")

    metrics = []
    with get_conn() as conn:
        teams_with_games_today = get_teams_with_games_on_date(conn, basis_date)

        for player in players:
            player = dict(player)
            player["price_role"] = determine_price_role_for_date(conn, player, basis_date)
            today = fetch_daily_score(conn, player, basis_date)

            base = {
                **player,
                **today,
                "basis_date": basis_date,
                "current_price": float(player.get("current_price_decimal") or player.get("price") or 0),
                "is_active": int(player.get("is_active") or 0),
                "team_played_today": normalize_team(player.get("team")) in teams_with_games_today,
            }
            base.update(market_activity_status(conn, player, basis_date))

            if base["price_role"] == "batter":
                season_rows = fetch_score_rows(conn, player, SEASON_START_DATE, basis_date)
                recent14_rows = fetch_score_rows(conn, player, recent14_start, basis_date)
                recent5_rows = season_rows[-5:]
                games_since, last_date = team_games_since_last_appearance(conn, player, basis_date, "batter")

                base.update({
                    "season_total": sum(float(r["points"] or 0) for r in season_rows),
                    "season_appearances": len(season_rows),
                    "season_avg": average([r["points"] for r in season_rows]),
                    "recent5_total": sum(float(r["points"] or 0) for r in recent5_rows),
                    "recent5_avg": average([r["points"] for r in recent5_rows]),
                    "recent14_total": sum(float(r["points"] or 0) for r in recent14_rows),
                    "team_games_since_last": games_since,
                    "last_appearance_date": last_date,
                })

            elif base["price_role"] == "starting_pitcher":
                season_starts = fetch_pitcher_role_rows(conn, player, SEASON_START_DATE, basis_date, starting=True)
                recent14_starts = fetch_pitcher_role_rows(conn, player, recent14_start, basis_date, starting=True)
                recent2_starts = season_starts[-2:]
                latest_start = season_starts[-1] if season_starts else None
                days_since_start = 999
                if latest_start:
                    days_since_start = (basis_dt - parse_date_any(latest_start["game_date"])).days

                base.update({
                    "season_total": sum(float(r["points"] or 0) for r in season_starts),
                    "season_starts": len(season_starts),
                    "season_start_avg": average([r["points"] for r in season_starts]),
                    "recent2_start_total": sum(float(r["points"] or 0) for r in recent2_starts),
                    "recent2_start_avg": average([r["points"] for r in recent2_starts]),
                    "recent14_start_total": sum(float(r["points"] or 0) for r in recent14_starts),
                    "latest_start_points": float(latest_start["points"] or 0) if latest_start else 0.0,
                    "latest_start_game_id": latest_start["game_id"] if latest_start else None,
                    "latest_start_date": latest_start["game_date"] if latest_start else None,
                    "days_since_latest_start": days_since_start,
                })

            else:
                season_bullpen = fetch_pitcher_role_rows(conn, player, SEASON_START_DATE, basis_date, starting=False)
                recent14_bullpen = fetch_pitcher_role_rows(conn, player, recent14_start, basis_date, starting=False)
                recent5_bullpen = season_bullpen[-5:]
                games_since, last_date = team_games_since_last_appearance(conn, player, basis_date, "bullpen_pitcher")

                base.update({
                    "season_total": sum(float(r["points"] or 0) for r in season_bullpen),
                    "season_bullpen_games": len(season_bullpen),
                    "season_bullpen_avg": average([r["points"] for r in season_bullpen]),
                    "recent5_bullpen_total": sum(float(r["points"] or 0) for r in recent5_bullpen),
                    "recent5_bullpen_avg": average([r["points"] for r in recent5_bullpen]),
                    "recent14_bullpen_total": sum(float(r["points"] or 0) for r in recent14_bullpen),
                    "today_bullpen_points": float(base["today_points"] if base.get("bullpen_today") else 0.0),
                    "team_games_since_last": games_since,
                    "last_appearance_date": last_date,
                })

            metrics.append(base)

    return calculate_value_scores(metrics)


def calculate_value_scores(metrics):
    """
    value percentile은 현재 등록/활성 선수(is_active=1)만 benchmark로 사용합니다.

    중요한 분리:
    - price_tracked_pool: 가격 row를 유지해야 하는 전체 선수(active + inactive 기록 보유)
    - market_benchmark_pool: 등록 선수 가격 산정 기준이 되는 active 선수만

    KBO 등록이 말소된 선수는 가격 history는 유지하지만, 등록 선수들의 percentile/target_price에는
    영향을 주지 않습니다. 본인 가격은 별도 tracking 처리에서 carry-forward + 미출전 패널티만 받습니다.

    단기 반응 보정:
    - 장기 value_score/target_price 시스템은 유지합니다.
    - 별도로 같은 역할군 안에서 단기 성적 percentile과 현재 가격 percentile을 저장합니다.
    - 이 값은 뒤쪽 보정층에서 base performance_change의 floor/ceiling으로만 사용합니다.
    """
    by_role = defaultdict(list)
    for item in metrics:
        item["is_benchmark_player"] = int(item.get("market_active") or 0) == 1
        by_role[item["price_role"]].append(item)

    for role, rows in by_role.items():
        benchmark_rows = [row for row in rows if row.get("is_benchmark_player")]
        if not benchmark_rows:
            # 방어적 fallback. 이 경우에도 신규 가격 row 누락을 막기 위해 전체 rows를 사용합니다.
            benchmark_rows = rows
            for row in benchmark_rows:
                row["is_benchmark_player"] = True

        current_price_pct_map = percentile_scores({
            r["registered_player_id"]: r.get("current_price", 0)
            for r in benchmark_rows
        })

        # 선수별 기대 수입 계산용 peer 기준입니다.
        # 같은 역할군 전체 평균 + 같은 현재 가격대 평균을 섞어, 절대 점수가 아니라
        # “이 선수 기준으로 오늘 얼마나 잘했는지”를 판단합니다.
        role_expectation_values = [expectation_role_average(r, role) for r in benchmark_rows]
        role_expectation_avg = average(role_expectation_values)
        bucket_values = defaultdict(list)
        for r in benchmark_rows:
            bucket_values[price_expectation_bucket(r.get("current_price", 0))].append(
                expectation_role_average(r, role)
            )
        bucket_expectation_avg = {
            bucket: average(values)
            for bucket, values in bucket_values.items()
        }

        component_defaults = {}
        short_event_pct_map = {}
        short_event_label = None

        if role == "batter":
            # 당일 경기 반응은 그날 경기가 있었던 팀의 active 타자끼리만 비교합니다.
            # 팀 경기가 없었던 타자는 today component를 중립값(50)으로 두어
            # 경기 없는 날 0점 취급으로 target이 흔들리는 문제를 막습니다.
            batter_today_rows = [r for r in benchmark_rows if r.get("team_played_today")]
            batter_today_pct_map = percentile_scores({
                r["registered_player_id"]: r.get("today_points", 0)
                for r in batter_today_rows
            })
            components = {
                "season_total_pct": percentile_scores({r["registered_player_id"]: r.get("season_total", 0) for r in benchmark_rows}),
                "season_avg_pct": percentile_scores({r["registered_player_id"]: r.get("season_avg", 0) for r in benchmark_rows}),
                "recent5_avg_pct": percentile_scores({r["registered_player_id"]: r.get("recent5_avg", 0) for r in benchmark_rows}),
                "recent14_total_pct": percentile_scores({r["registered_player_id"]: r.get("recent14_total", 0) for r in benchmark_rows}),
                "today_points_pct": batter_today_pct_map,
            }
            component_defaults = {
                "today_points_pct": lambda row: 50.0 if not row.get("team_played_today") else 0.0,
            }
            short_event_pct_map = batter_today_pct_map
            short_event_label = "당일 타자 성적 percentile"
            weights = {
                "season_total_pct": 0.30,
                "season_avg_pct": 0.20,
                "recent5_avg_pct": 0.25,
                "recent14_total_pct": 0.10,
                "today_points_pct": 0.15,
            }

        elif role == "starting_pitcher":
            latest_start_pct_map = percentile_scores({
                r["registered_player_id"]: r.get("latest_start_points", 0)
                for r in benchmark_rows
            })
            components = {
                "recent2_start_avg_pct": percentile_scores({r["registered_player_id"]: r.get("recent2_start_avg", 0) for r in benchmark_rows}),
                "recent14_start_total_pct": percentile_scores({r["registered_player_id"]: r.get("recent14_start_total", 0) for r in benchmark_rows}),
                "season_start_avg_pct": percentile_scores({r["registered_player_id"]: r.get("season_start_avg", 0) for r in benchmark_rows}),
                "season_total_pct": percentile_scores({r["registered_player_id"]: r.get("season_total", 0) for r in benchmark_rows}),
                "latest_start_points_pct": latest_start_pct_map,
            }
            short_event_pct_map = latest_start_pct_map
            short_event_label = "최근 선발 등판 성적 percentile"
            weights = {
                "recent2_start_avg_pct": 0.35,
                "recent14_start_total_pct": 0.20,
                "season_start_avg_pct": 0.25,
                "season_total_pct": 0.10,
                "latest_start_points_pct": 0.10,
            }

        else:
            # 불펜은 한 경기 변동성이 크므로 단기 반응 benchmark는 최근 5번 불펜 등판 평균을 사용합니다.
            # today_bullpen_points_pct는 오늘 실제 불펜 등판자끼리만 비교하고,
            # 오늘 안 던진 선수는 중립값(50)으로 둡니다.
            bullpen_today_rows = [r for r in benchmark_rows if r.get("bullpen_today")]
            bullpen_today_pct_map = percentile_scores({
                r["registered_player_id"]: r.get("today_bullpen_points", 0)
                for r in bullpen_today_rows
            })
            recent5_bullpen_pct_map = percentile_scores({
                r["registered_player_id"]: r.get("recent5_bullpen_avg", 0)
                for r in benchmark_rows
            })
            components = {
                "recent5_bullpen_avg_pct": recent5_bullpen_pct_map,
                "recent14_bullpen_total_pct": percentile_scores({r["registered_player_id"]: r.get("recent14_bullpen_total", 0) for r in benchmark_rows}),
                "season_total_pct": percentile_scores({r["registered_player_id"]: r.get("season_total", 0) for r in benchmark_rows}),
                "season_bullpen_avg_pct": percentile_scores({r["registered_player_id"]: r.get("season_bullpen_avg", 0) for r in benchmark_rows}),
                "today_bullpen_points_pct": bullpen_today_pct_map,
            }
            component_defaults = {
                "today_bullpen_points_pct": lambda row: 50.0 if not row.get("bullpen_today") else 0.0,
            }
            short_event_pct_map = recent5_bullpen_pct_map
            short_event_label = "최근 불펜 등판 성적 percentile"
            weights = {
                "recent5_bullpen_avg_pct": 0.30,
                "recent14_bullpen_total_pct": 0.25,
                "season_total_pct": 0.20,
                "season_bullpen_avg_pct": 0.15,
                "today_bullpen_points_pct": 0.10,
            }

        for row in rows:
            rid = row["registered_player_id"]

            if not row.get("is_benchmark_player"):
                row["value_score"] = None
                row["value_components"] = {}
                row["season_total_percentile"] = None
                row["current_price_percentile"] = None
                row["short_term_event_percentile"] = None
                row["short_term_value_gap"] = None
                row["short_term_event_label"] = None
                row["expectation_price_bucket"] = price_expectation_bucket(row.get("current_price", 0))
                row["expected_points"] = None
                row["expected_reference_points"] = None
                row["expected_points_components"] = {}
                row["benchmark_note"] = "inactive_price_tracking_only"
                continue

            row_components = {}
            value_score = 0.0
            for key, percentile_map in components.items():
                if rid in percentile_map:
                    pct = float(percentile_map.get(rid, 0.0))
                else:
                    default_value = component_defaults.get(key, 0.0)
                    pct = float(default_value(row) if callable(default_value) else default_value)
                row_components[key] = pct
                value_score += pct * weights[key]

            current_price_pct = current_price_pct_map.get(rid)
            short_event_pct = short_event_pct_map.get(rid)
            if short_event_pct is None:
                short_gap = None
            else:
                short_gap = float(short_event_pct) - float(current_price_pct or 0.0)

            row["value_score"] = round(value_score, 4)
            row["value_components"] = row_components
            row["season_total_percentile"] = row_components.get("season_total_pct", 0.0)
            row["current_price_percentile"] = current_price_pct
            row["short_term_event_percentile"] = short_event_pct
            row["short_term_value_gap"] = round(short_gap, 4) if short_gap is not None else None
            row["short_term_event_label"] = short_event_label if short_event_pct is not None else None
            row["benchmark_note"] = "active_market_benchmark"

            bucket = price_expectation_bucket(row.get("current_price", 0))
            expected_points, expected_reference, expected_components = calculate_expected_points(
                row,
                role,
                bucket_expectation_avg.get(bucket, role_expectation_avg),
                role_expectation_avg,
            )
            row["expectation_price_bucket"] = bucket
            row["expected_points"] = expected_points
            row["expected_reference_points"] = expected_reference
            row["expected_points_components"] = expected_components

    return metrics


# -----------------------------------------------------------------------------
# 가격 변동 계산
# -----------------------------------------------------------------------------

def cap_abs(change, max_abs):
    change = float(change or 0)
    max_abs = abs(float(max_abs or 0))
    if change > max_abs:
        return max_abs
    if change < -max_abs:
        return -max_abs
    return change


def cap_by_sample_and_role(change, metrics):
    role = metrics["price_role"]

    if role == "batter":
        n = int(metrics.get("season_appearances", 0) or 0)
        if n <= 0:
            return 0.0, "표본 없음"
        if n == 1:
            return cap_abs(change, 0.2), "타자 표본 1경기 제한"
        if n <= 3:
            return cap_abs(change, 0.3), "타자 표본 2~3경기 제한"
        return cap_abs(change, 0.5), None

    if role == "starting_pitcher":
        n = int(metrics.get("season_starts", 0) or 0)
        if metrics.get("started_today"):
            if n <= 0:
                return 0.0, "선발 표본 없음"
            if n == 1:
                return cap_abs(change, 0.2), "선발 표본 1경기 제한"
            if n == 2:
                return cap_abs(change, 0.4), "선발 표본 2경기 제한"
            return cap_abs(change, 0.5), None

        # 비등판일은 성적 반복 반영을 막기 위해 market correction만 제한적으로 허용합니다.
        extreme = abs(float(metrics.get("price_pressure", 0))) >= 5.0
        return cap_abs(change, 0.2 if extreme else 0.1), "선발 비등판일 시장 보정 제한"

    n = int(metrics.get("season_bullpen_games", 0) or 0)
    if n <= 0:
        return cap_abs(change, 0.1), "불펜 표본 없음"
    if n == 1:
        return cap_abs(change, 0.2), "불펜 표본 1경기 제한"
    if n <= 3:
        return cap_abs(change, 0.3), "불펜 표본 2~3경기 제한"
    if not metrics.get("bullpen_today"):
        extreme = abs(float(metrics.get("price_pressure", 0))) >= 5.0
        return cap_abs(change, 0.2 if extreme else 0.1), "불펜 미등판일 시장 보정 제한"
    return cap_abs(change, 0.5), None


def role_event_happened(metrics):
    """미출전 패널티 회복과 단기 성적 상승 보정에 사용할 실제 출전/등판 여부입니다."""
    role = metrics.get("price_role")
    if role == "batter":
        return bool(metrics.get("appeared_today"))
    if role == "starting_pitcher":
        return bool(metrics.get("started_today"))
    if role == "bullpen_pitcher":
        return bool(metrics.get("bullpen_today"))
    return bool(metrics.get("appeared_today"))


def apply_short_term_percentile_overlay(change, metrics):
    """
    기존 장기 value_score/target_price 결과를 갈아엎지 않고 보정만 합니다.

    - 성적 percentile은 높은데 가격 percentile은 낮거나 비슷하면 최소 상승폭을 보장합니다.
    - 성적 percentile은 낮은데 가격 percentile은 높으면 상승을 막거나 하락 쪽으로 제한합니다.
    - 실제 출전/등판하지 않은 선수는 이 보정층으로 상승하지 못합니다.
    """
    if not metrics.get("is_benchmark_player"):
        return signed_change(change), []

    role = metrics.get("price_role")
    reasons = []
    actual_event = role_event_happened(metrics)

    if not actual_event:
        # 타자는 당일 출전, 투수는 해당 역할 등판이 없으면
        # 장기 target 압력만으로 가격이 오르는 체감을 막습니다.
        # 하락/유지는 기존 엔진의 market correction과 미출전 패널티가 처리합니다.
        if change > 0:
            change = 0.0
            if role == "batter" and metrics.get("team_played_today"):
                reasons.append("당일 팀 경기 미출전으로 상승 제한")
            elif role == "batter":
                reasons.append("당일 팀 경기 없음으로 상승 제한")
            elif role == "starting_pitcher":
                reasons.append("선발 미등판일 상승 제한")
            elif role == "bullpen_pitcher":
                reasons.append("불펜 미등판일 상승 제한")
            else:
                reasons.append("실제 출전/등판 없이 상승 제한")
        return signed_change(change), reasons

    event_pct = metrics.get("short_term_event_percentile")
    price_pct = metrics.get("current_price_percentile")
    if event_pct is None or price_pct is None:
        return signed_change(change), reasons

    event_pct = float(event_pct)
    price_pct = float(price_pct)
    gap = event_pct - price_pct
    label = metrics.get("short_term_event_label") or "단기 성적 percentile"

    min_change = None
    if event_pct >= 97.0 and gap >= 20.0:
        min_change = 0.3
    elif event_pct >= 97.0 and gap >= -10.0:
        min_change = 0.2
    elif event_pct >= 90.0 and gap >= -5.0:
        min_change = 0.1
    elif event_pct >= 80.0 and gap >= 20.0:
        min_change = 0.1

    if min_change is not None and change < min_change:
        change = min_change
        reasons.append(f"{label} 상위권과 가격 대비 저평가 반영")

    max_change = None
    if event_pct <= 5.0 and gap <= -20.0:
        max_change = -0.3
    elif event_pct <= 10.0 and price_pct >= 70.0:
        max_change = -0.2
    elif event_pct <= 25.0 and gap <= -30.0:
        max_change = -0.1

    if max_change is not None and change > max_change:
        change = max_change
        reasons.append(f"{label} 하위권과 고평가 반영")

    return signed_change(change), reasons




def apply_expectation_dynamic_overlay(change, metrics):
    """
    선수별 기대 수입 대비 당일 성과를 반영하는 최종 반응성 보정층입니다.

    목표:
    - 매 출전 경기마다 가격이 살아 움직이도록 한다.
    - 단순 절대 점수 기준이 아니라 자기 기대치 대비 성과를 본다.
    - 저가/중가 breakout은 빠르게 반응하고, 초고가 선수는 기대치를 넘겨야 오른다.
    - 장기 target_price가 당일 활약을 완전히 묻어버리는 체감을 줄인다.
    """
    if not metrics.get("is_benchmark_player"):
        return signed_change(change), []

    event_points = event_points_for_expectation(metrics)
    if event_points is None:
        return signed_change(change), []

    expected_reference = metrics.get("expected_reference_points")
    if expected_reference is None:
        return signed_change(change), []

    expected_reference = max(float(expected_reference or 0.0), expectation_floor_for_role(metrics.get("price_role")))
    if expected_reference <= 0:
        return signed_change(change), []

    ratio = float(event_points or 0.0) / expected_reference
    gap = float(event_points or 0.0) - expected_reference
    role = metrics.get("price_role")
    current_price = float(metrics.get("current_price") or 0.0)
    bucket = price_expectation_bucket(current_price)
    reasons = []

    # 음수/0점은 기존 sanity guard가 상승 금지를 담당하되,
    # 기대치 관점에서도 상승을 막고 저성과 하락을 허용합니다.
    if event_points <= 0:
        if change > 0:
            change = 0.0
            reasons.append("개인 기대치 미달 경기로 상승 제한")
        if ratio <= 0.35 and current_price >= 8.0:
            change = min(change, -0.1)
            reasons.append("개인 기대치 대비 저성과 반영")
        metrics["expectation_event_points"] = round(event_points, 4)
        metrics["expectation_ratio"] = round(ratio, 4)
        metrics["expectation_gap"] = round(gap, 4)
        return signed_change(change), reasons

    # 가격대별 탄력성. 저가/중가는 기대 초과에 더 민감하고,
    # 초고가는 확실히 기대치를 넘어야 상승합니다.
    if bucket == "low":
        small_up_ratio, medium_up_ratio, big_up_ratio = 1.10, 1.45, 2.05
        down_ratio, hard_down_ratio = 0.70, 0.48
        min_small, min_medium, min_big = 0.1, 0.2, 0.3
        max_soft_down, max_hard_down = -0.1, -0.2
    elif bucket == "mid":
        small_up_ratio, medium_up_ratio, big_up_ratio = 1.12, 1.50, 2.10
        down_ratio, hard_down_ratio = 0.72, 0.50
        min_small, min_medium, min_big = 0.1, 0.2, 0.3
        max_soft_down, max_hard_down = -0.1, -0.2
    elif bucket == "high":
        small_up_ratio, medium_up_ratio, big_up_ratio = 1.22, 1.70, 2.30
        down_ratio, hard_down_ratio = 0.76, 0.54
        min_small, min_medium, min_big = 0.0, 0.1, 0.2
        max_soft_down, max_hard_down = -0.1, -0.2
    else:
        small_up_ratio, medium_up_ratio, big_up_ratio = 1.35, 1.95, 2.60
        down_ratio, hard_down_ratio = 0.80, 0.58
        min_small, min_medium, min_big = 0.0, 0.1, 0.2
        max_soft_down, max_hard_down = -0.1, -0.2

    # 선발투수는 한 경기 표본이 크므로 확실한 초과/미달만 floor/ceiling을 강하게 둡니다.
    if role == "starting_pitcher":
        small_up_ratio += 0.05
        medium_up_ratio += 0.05
        big_up_ratio += 0.05
    # 불펜은 한 경기 변동성이 커서 최근 흐름과 함께 보되, 실제 등판일 반응은 유지합니다.
    elif role == "bullpen_pitcher":
        min_big = min(min_big, 0.2)

    if ratio >= big_up_ratio:
        if change < min_big:
            change = min_big
        reasons.append("개인 기대치 대비 대폭 초과 성과 반영")
    elif ratio >= medium_up_ratio:
        if change < min_medium:
            change = min_medium
        reasons.append("개인 기대치 대비 확실한 초과 성과 반영")
    elif ratio >= small_up_ratio:
        if change < min_small:
            change = min_small
        if min_small > 0:
            reasons.append("개인 기대치 대비 초과 성과 반영")
        elif change < 0:
            change = 0.0
            reasons.append("개인 기대치 초과 경기로 하락 방지")
    elif ratio >= 1.03:
        # 기대치를 조금 넘긴 경기는 장기 target 압력 때문에 하락하는 체감만 막습니다.
        if change < 0:
            change = 0.0
            reasons.append("개인 기대치 소폭 초과 경기로 하락 방지")
    elif ratio <= hard_down_ratio:
        if change > max_hard_down:
            change = max_hard_down
        reasons.append("개인 기대치 대비 큰 저성과 반영")
    elif ratio <= down_ratio:
        if change > max_soft_down:
            change = max_soft_down
        reasons.append("개인 기대치 대비 저성과 반영")
    else:
        # 기대치에 크게 못 미치지는 않았는데 장기 target 압력만으로 과하게 떨어지는 체감을 줄입니다.
        if event_points > 0 and change < -0.1:
            change = -0.1
            reasons.append("개인 기대치 근처 경기로 큰 하락 제한")

    # 플러스 수입 경기는 기대치 대비 완전한 실패가 아닌 한 하루 -0.3/-0.4씩 무너지는 것을 막습니다.
    # 가격은 계속 역동적으로 움직이되, 유저가 보는 경기 성과와 가격 방향이 너무 멀어지지 않게 하는 안전장치입니다.
    if event_points > 0:
        if ratio >= down_ratio and change < -0.1:
            change = -0.1
            reasons.append("플러스 경기로 큰 하락 제한")
        elif ratio >= hard_down_ratio and change < -0.2:
            change = -0.2
            reasons.append("플러스 경기로 급락 제한")

    # 사용자가 확인한 price_reactivity_report 이슈 보정입니다.
    # 역할별 단기 성적 percentile이 90 이상이면, 장기 target 압력 때문에 가격이 하락하지 않도록 막습니다.
    # 이 보정은 실제 출전/등판이 있었던 선수에게만 적용됩니다.
    event_pct = metrics.get("short_term_event_percentile")
    if event_pct is not None and float(event_pct) >= 90.0 and change < 0:
        change = 0.0
        reasons.append("상위권 성적 경기로 가격 하락 방지")

    metrics["expectation_event_points"] = round(event_points, 4)
    metrics["expectation_ratio"] = round(ratio, 4)
    metrics["expectation_gap"] = round(gap, 4)
    return signed_change(change), reasons

def apply_sanity_guards(change, metrics, conn):
    role = metrics["price_role"]
    current_price = float(metrics.get("current_price") or 0)
    today_points = float(metrics.get("today_points") or 0)
    appeared_today = bool(metrics.get("appeared_today"))
    guard_reasons = []

    if appeared_today and today_points < 0:
        if change > 0:
            change = 0.0
            guard_reasons.append("당일 음수 점수로 상승 금지")
        if current_price >= 15.0:
            change = min(change, -0.3)
            guard_reasons.append("고가 선수 당일 음수 점수 하락")
        elif current_price >= 13.0:
            change = min(change, -0.2)
            guard_reasons.append("고가 선수 당일 음수 점수 하락")
        else:
            change = min(change, -0.1)
            guard_reasons.append("당일 음수 점수 하락")

    elif appeared_today and today_points == 0:
        if change > 0:
            change = 0.0
            guard_reasons.append("당일 0점으로 상승 금지")
        if current_price >= 15.0:
            change = min(change, -0.2)
            guard_reasons.append("최고가권 0점 하락")
        elif current_price >= 10.0:
            change = min(change, -0.1)
            guard_reasons.append("고가 선수 0점 하락")

    elif appeared_today and today_points > 0:
        if current_price >= 15.0 and today_points < 150 and change > 0:
            change = 0.0
            guard_reasons.append("최고가권 낮은 플러스 점수로 상승 제한")
        elif current_price >= 13.0 and today_points < 100 and change > 0:
            change = 0.0
            guard_reasons.append("고가 선수 낮은 플러스 점수로 상승 제한")

        good_threshold = 600 if role == "batter" else (800 if role == "starting_pitcher" else 300)
        if today_points >= good_threshold and change < -0.1:
            change = -0.1
            guard_reasons.append("당일 활약으로 큰 하락 제한")

    if role == "starting_pitcher" and not metrics.get("started_today"):
        count = starting_correction_count_since_latest_start(
            conn,
            metrics,
            metrics.get("latest_start_game_id"),
            metrics["basis_date"],
        )
        allowed_count = 2 if abs(float(metrics.get("price_pressure", 0))) >= 5.0 else 1
        if count >= allowed_count and change != 0:
            change = 0.0
            guard_reasons.append("다음 선발 등판 전 비등판일 보정 반복 방지")
        elif change != 0:
            metrics["starting_no_start_market_correction"] = True

    # 장기 미출전/미등판 상태에서는 target 기반 상승을 막고 absence 회복만 별도 처리합니다.
    desired_absence, _ = desired_absence_total(metrics)
    if desired_absence < 0 and not appeared_today and change > 0:
        change = 0.0
        guard_reasons.append("장기 미출전 상태로 성적 기반 상승 금지")

    return signed_change(change), guard_reasons


def _reason_is_negative(reason):
    text = str(reason or "")
    return any(word in text for word in ["저성과", "미달", "하락", "부진", "상승 제한", "0점", "음수"])


def _reason_is_positive(reason):
    text = str(reason or "")
    return any(word in text for word in ["초과", "활약", "저평가", "호투", "개선", "하락 방지"])


def reason_from_change(performance_change, absence_change, metrics, guard_reasons, total_change=None):
    reasons = []
    role = metrics["price_role"]
    net_change = signed_change(total_change if total_change is not None else performance_change + absence_change)

    expectation_reasons = [
        r for r in guard_reasons
        if r and ("개인 기대치" in r or "기대치" in r)
    ]
    positive_expectation_reasons = [r for r in expectation_reasons if _reason_is_positive(r) and not _reason_is_negative(r)]
    negative_expectation_reasons = [r for r in expectation_reasons if _reason_is_negative(r)]

    if net_change > 0:
        if absence_change > 0:
            reasons.append("출전/등판 재개로 미출전 패널티 회복")
        if performance_change > 0:
            if positive_expectation_reasons:
                reasons.append(positive_expectation_reasons[0])
            elif role == "starting_pitcher" and metrics.get("started_today"):
                reasons.append("선발 등판 호투와 저평가 반영")
            elif role == "bullpen_pitcher" and metrics.get("bullpen_today"):
                reasons.append("최근 불펜 등판 흐름 개선")
            elif metrics.get("today_points", 0) > 0 and metrics.get("appeared_today"):
                reasons.append("오늘 경기 활약과 저평가 반영")
            elif metrics.get("season_total_percentile", 0) >= 80:
                reasons.append("시즌 상위권 성적 대비 저평가로 상승")
            else:
                reasons.append("최근 성적 대비 저평가로 상승")
        if not reasons:
            reasons.append("가격 상승")

    elif net_change < 0:
        if performance_change < 0:
            if negative_expectation_reasons:
                reasons.append(negative_expectation_reasons[0])
            elif metrics.get("appeared_today") and metrics.get("today_points", 0) < 0:
                reasons.append("오늘 경기 부진으로 하락")
            elif metrics.get("appeared_today") and metrics.get("today_points", 0) == 0:
                reasons.append("고가 대비 당일 0점으로 하락")
            else:
                reasons.append("가격 대비 최근 성적 부진으로 하락")
        if absence_change < 0:
            reasons.append(metrics.get("absence_reason") or "장기 미출전으로 소폭 하락")
        if not reasons:
            reasons.append("가격 하락")

    else:
        if metrics.get("target_price", 0) >= MAX_PRICE and metrics.get("current_price", 0) >= MAX_PRICE:
            reasons.append("최대 가격 도달로 유지")
        elif old_reason := next((r for r in guard_reasons if r and "제한" in r), None):
            reasons.append(old_reason)
        else:
            reasons.append("가격 유지")

    # 중복 제거, 순서 유지
    deduped = []
    for reason in reasons:
        if reason and reason not in deduped:
            deduped.append(reason)

    # 최종 가격 방향과 reason 문구가 충돌하지 않도록 보정한다.
    # 예: 실제 가격은 하락했는데 "상승 제한" 문구가 대표 reason으로 저장되면
    # price_reactivity_report의 direction conflict로 잡힌다.
    cleaned = []
    for reason in deduped[:3]:
        text = str(reason or "")
        if net_change < 0:
            if "상승 제한" in text or "회복" in text:
                text = "개인 기대치 미달로 가격 하락"
            elif "상승" in text and "상승 제한" not in text:
                text = "가격 대비 최근 성적 부진으로 하락"
        elif net_change > 0:
            if "하락" in text and "하락 방지" not in text:
                text = "가격 상승"
        if text and text not in cleaned:
            cleaned.append(text)

    if not cleaned:
        if net_change > 0:
            cleaned.append("가격 상승")
        elif net_change < 0:
            cleaned.append("가격 하락")
        else:
            cleaned.append("가격 유지")

    return " / ".join(cleaned[:3])

def calculate_adjustment_for_player(conn, metrics):
    old_price = float(metrics.get("current_price") or 0)
    is_benchmark_player = bool(metrics.get("is_benchmark_player", True))

    previous_absence = previous_absence_total(
        conn,
        metrics["registered_player_id"],
        metrics["basis_date"],
    )
    if is_benchmark_player:
        desired_absence, absence_reason = desired_absence_total(metrics)
    else:
        desired_absence, absence_reason = desired_inactive_absence_total(metrics, previous_absence)

    metrics["absence_reason"] = absence_reason
    absence_change = signed_change(desired_absence - previous_absence)

    if not is_benchmark_player:
        # KBO 등록이 말소된 선수는 가격 기록은 유지하지만 active 선수 시장 기준선에는 영향을 주지 않습니다.
        # 본인 가격은 target 성적 비교 없이 carry-forward + 미출전/말소 패널티만 반영합니다.
        anchor_floor = None
        weakened_floor = None
        anchor_reasons = ["KBO 등록이 말소된 선수: 등록 선수 가격 기준에서 제외"]
        target_price = old_price
        pressure = 0.0
        metrics["target_price"] = target_price
        metrics["price_pressure"] = pressure
        performance_change = 0.0
        sample_cap_reason = "KBO 등록 말소 선수 가격 기록 유지"
        guard_reasons = ["KBO 등록이 말소된 선수: 등록 선수 가격 기준에서 제외"]

        # 비활성 선수가 실제 출전한 경우를 제외하고, 미출전 패널티 회복만으로 가격이 오르는 현상은 막습니다.
        if absence_change > 0 and not metrics.get("appeared_today"):
            absence_change = 0.0
            guard_reasons.append("미출전 상태에서 패널티 자동 회복 제한")
    else:
        anchor_floor = season_anchor_floor(metrics.get("season_total_percentile"), metrics["price_role"])
        weakened_floor, anchor_reasons = weaken_anchor_floor(anchor_floor, metrics)

        target_price = target_price_from_value_percentile(metrics.get("value_score", 0), metrics["price_role"])
        if weakened_floor is not None:
            target_price = max(target_price, weakened_floor)
        target_price = clamp_price(target_price)

        pressure = round(target_price - old_price, 4)
        metrics["target_price"] = target_price
        metrics["price_pressure"] = pressure

        performance_change = change_from_pressure(pressure)
        performance_change, sample_cap_reason = cap_by_sample_and_role(performance_change, metrics)
        performance_change, guard_reasons = apply_sanity_guards(performance_change, metrics, conn)
        performance_change, overlay_reasons = apply_short_term_percentile_overlay(performance_change, metrics)
        guard_reasons.extend(overlay_reasons)
        performance_change, expectation_reasons = apply_expectation_dynamic_overlay(performance_change, metrics)
        guard_reasons.extend(expectation_reasons)

    if absence_change > 0 and not role_event_happened(metrics):
        absence_change = 0.0
        metrics["absence_recovery_blocked"] = True
        guard_reasons.append("실제 출전/등판 없이 미출전 패널티 회복 제한")

    total_change = signed_change(performance_change + absence_change)
    total_change = cap_abs(total_change, 0.5)
    new_price = clamp_price(old_price + total_change)

    actual_total_change = signed_change(new_price - old_price)
    if actual_total_change == 0.0:
        if old_price <= MIN_PRICE and total_change < 0:
            guard_reasons.append("최저 가격 도달로 유지")
        if old_price >= MAX_PRICE and total_change > 0:
            guard_reasons.append("최대 가격 도달로 유지")

    reason = reason_from_change(
        performance_change=performance_change,
        absence_change=absence_change,
        metrics=metrics,
        guard_reasons=guard_reasons,
        total_change=actual_total_change,
    )

    detail = {
        "engine": "role_based_target_value_pricing_v3",
        "pricing_curve_version": PRICING_CURVE_VERSION,
        "role": metrics["price_role"],
        "is_active": metrics.get("is_active"),
        "market_active": metrics.get("market_active"),
        "market_activity_reason": metrics.get("market_activity_reason"),
        "recent_activity_games": metrics.get("recent_activity_games"),
        "recent_activity_last_game_date": metrics.get("recent_activity_last_game_date"),
        "is_benchmark_player": is_benchmark_player,
        "benchmark_note": metrics.get("benchmark_note"),
        "value_score": metrics.get("value_score"),
        "value_components": metrics.get("value_components"),
        "target_price": target_price,
        "price_pressure": pressure,
        "anchor_floor": anchor_floor,
        "weakened_anchor_floor": weakened_floor,
        "anchor_reasons": anchor_reasons,
        "sample_cap_reason": sample_cap_reason,
        "guard_reasons": guard_reasons,
        "appeared_today": metrics.get("appeared_today"),
        "today_points": metrics.get("today_points"),
        "today_game_id": metrics.get("today_game_id"),
        "started_today": metrics.get("started_today"),
        "bullpen_today": metrics.get("bullpen_today"),
        "latest_start_game_id": metrics.get("latest_start_game_id"),
        "starting_no_start_market_correction": bool(metrics.get("starting_no_start_market_correction")),
        "season_total": metrics.get("season_total"),
        "season_total_percentile": metrics.get("season_total_percentile"),
        "current_price_percentile": metrics.get("current_price_percentile"),
        "short_term_event_percentile": metrics.get("short_term_event_percentile"),
        "short_term_value_gap": metrics.get("short_term_value_gap"),
        "short_term_event_label": metrics.get("short_term_event_label"),
        "expectation_price_bucket": metrics.get("expectation_price_bucket"),
        "expected_points": metrics.get("expected_points"),
        "expected_reference_points": metrics.get("expected_reference_points"),
        "expected_points_components": metrics.get("expected_points_components"),
        "expectation_event_points": metrics.get("expectation_event_points"),
        "expectation_ratio": metrics.get("expectation_ratio"),
        "expectation_gap": metrics.get("expectation_gap"),
        "absence_recovery_blocked": bool(metrics.get("absence_recovery_blocked")),
        "team_played_today": metrics.get("team_played_today"),
        "current_price": old_price,
        "new_price": new_price,
    }

    absence_detail = {
        "previous_absence_penalty_total": previous_absence,
        "desired_absence_penalty_total": desired_absence,
        "absence_penalty_change": absence_change,
        "absence_reason": absence_reason,
        "team_games_since_last": metrics.get("team_games_since_last"),
        "last_appearance_date": metrics.get("last_appearance_date"),
        "days_since_latest_start": metrics.get("days_since_latest_start"),
        "latest_start_date": metrics.get("latest_start_date"),
    }

    return {
        "registered_player_id": metrics["registered_player_id"],
        "player_id": metrics.get("player_id"),
        "player_name": metrics["player_name"],
        "team": metrics["team"],
        "roster_position": metrics.get("roster_position"),
        "fantasy_position_type": metrics["fantasy_position_type"],
        "price_role": metrics["price_role"],
        "is_active": metrics.get("is_active"),
        "market_active": metrics.get("market_active"),
        "market_activity_reason": metrics.get("market_activity_reason"),
        "is_benchmark_player": is_benchmark_player,
        "external_score": metrics.get("external_score") or 0,
        "external_rank": metrics.get("external_rank"),
        "price_score": metrics.get("value_score") or 0,
        "old_price_decimal": old_price,
        "performance_change": performance_change,
        "absence_penalty_change": absence_change,
        "absence_penalty_total": desired_absence,
        "new_price_decimal": new_price,
        "reason": reason,
        "performance_reason_json": json.dumps(detail, ensure_ascii=False, sort_keys=True),
        "absence_reason_json": json.dumps(absence_detail, ensure_ascii=False, sort_keys=True),
        "target_price": target_price,
        "price_pressure": pressure,
        "value_score": metrics.get("value_score") or 0,
    }

def build_adjustments(players, basis_date):
    metric_rows = build_player_metrics(players, basis_date)
    adjustments = []
    with get_conn() as conn:
        for metrics in metric_rows:
            adjustments.append(calculate_adjustment_for_player(conn, metrics))
    return adjustments


# -----------------------------------------------------------------------------
# 저장 / 출력
# -----------------------------------------------------------------------------

def create_price_update_run(basis_date, basis_start_date, basis_end_date, run_mode):
    with get_conn() as conn:
        c = conn.execute("""
            INSERT INTO price_update_runs (
                basis_source,
                basis_date,
                basis_start_date,
                basis_end_date,
                latest_game_date,
                run_mode,
                status,
                started_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'started', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            BASIS_SOURCE,
            basis_date,
            basis_start_date,
            basis_end_date,
            get_latest_game_date(),
            run_mode,
        ))
        return c.lastrowid


def finish_price_update_run(run_id, status, message):
    with get_conn() as conn:
        conn.execute("""
            UPDATE price_update_runs
            SET status = ?,
                message = ?,
                finished_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, message, run_id))


def cleanup_basis_date_for_force(basis_date):
    """
    같은 날짜 v3 force 재적용 시 v3 해당 날짜 기록만 정리합니다.
    market_daily_v2 / welcometopranking / 다른 날짜 기록은 건드리지 않습니다.
    """
    with get_conn() as conn:
        run_rows = conn.execute("""
            SELECT id
            FROM price_update_runs
            WHERE basis_source = ?
              AND basis_date = ?
        """, (BASIS_SOURCE, basis_date)).fetchall()
        run_ids = [int(row["id"]) for row in run_rows]

        conn.execute("""
            DELETE FROM player_prices
            WHERE basis_source = ?
              AND basis_date = ?
        """, (BASIS_SOURCE, basis_date))

        conn.execute("""
            DELETE FROM player_price_adjustments
            WHERE basis_source = ?
              AND basis_date = ?
        """, (BASIS_SOURCE, basis_date))

        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            conn.execute(f"""
                DELETE FROM price_update_runs
                WHERE id IN ({placeholders})
            """, tuple(run_ids))


def save_adjustments(run_id, adjustments, basis_date, basis_start_date, basis_end_date):
    with get_conn() as conn:
        for row in adjustments:
            conn.execute("""
                INSERT INTO player_price_adjustments (
                    run_id,
                    registered_player_id,
                    player_name,
                    team,
                    price_role,
                    basis_source,
                    basis_date,
                    basis_start_date,
                    basis_end_date,
                    old_price_decimal,
                    performance_change,
                    absence_penalty_change,
                    absence_penalty_total,
                    new_price_decimal,
                    is_applied,
                    reason,
                    performance_reason_json,
                    absence_reason_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (
                run_id,
                row["registered_player_id"],
                row["player_name"],
                row["team"],
                row["price_role"],
                BASIS_SOURCE,
                basis_date,
                basis_start_date,
                basis_end_date,
                row["old_price_decimal"],
                row["performance_change"],
                row["absence_penalty_change"],
                row["absence_penalty_total"],
                row["new_price_decimal"],
                row["reason"],
                row["performance_reason_json"],
                row["absence_reason_json"],
            ))


def apply_price_rows(adjustments, basis_date):
    with get_conn() as conn:
        for row in adjustments:
            price_decimal = clamp_price(row["new_price_decimal"])
            conn.execute("""
                INSERT INTO player_prices (
                    registered_player_id,
                    player_id,
                    player_name,
                    team,
                    roster_position,
                    fantasy_position_type,
                    external_score,
                    external_rank,
                    price_role,
                    price_score,
                    tier,
                    price,
                    price_decimal,
                    basis_source,
                    basis_date,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(registered_player_id, basis_source, basis_date)
                DO UPDATE SET
                    player_id = excluded.player_id,
                    player_name = excluded.player_name,
                    team = excluded.team,
                    roster_position = excluded.roster_position,
                    fantasy_position_type = excluded.fantasy_position_type,
                    external_score = excluded.external_score,
                    external_rank = excluded.external_rank,
                    price_role = excluded.price_role,
                    price_score = excluded.price_score,
                    tier = excluded.tier,
                    price = excluded.price,
                    price_decimal = excluded.price_decimal,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                row["registered_player_id"],
                row.get("player_id"),
                row["player_name"],
                row["team"],
                row.get("roster_position"),
                row["fantasy_position_type"],
                row.get("external_score") or 0,
                row.get("external_rank"),
                row["price_role"],
                row.get("price_score") or 0,
                tier_from_price(price_decimal),
                price_to_integer(price_decimal),
                price_decimal,
                BASIS_SOURCE,
                basis_date,
            ))


def summarize_adjustments(adjustments):
    total = len(adjustments)
    up = sum(1 for row in adjustments if row["new_price_decimal"] > row["old_price_decimal"])
    down = sum(1 for row in adjustments if row["new_price_decimal"] < row["old_price_decimal"])
    same = total - up - down
    changed = up + down

    by_role = defaultdict(list)
    for row in adjustments:
        by_role[row["price_role"]].append(row)

    lines = []
    lines.append(f"전체 선수: {total}")
    lines.append(f"상승: {up}")
    lines.append(f"하락: {down}")
    lines.append(f"유지: {same}")
    lines.append(f"변동률: {(changed / total * 100) if total else 0:.1f}%")

    for role in ["batter", "starting_pitcher", "bullpen_pitcher"]:
        rows = by_role.get(role, [])
        if not rows:
            continue
        role_changed = sum(1 for row in rows if row["new_price_decimal"] != row["old_price_decimal"])
        avg_price = sum(float(row["new_price_decimal"] or 0) for row in rows) / len(rows)
        lines.append(
            f"{ROLE_LABEL[role]}: {role_changed}/{len(rows)}명 변동 "
            f"({role_changed / len(rows) * 100:.1f}%), 평균가 {avg_price:.2f}"
        )

    active_rows = [row for row in adjustments if int(row.get("is_active") or 0) == 1]
    inactive_rows = [row for row in adjustments if int(row.get("is_active") or 0) == 0]
    if active_rows:
        active_changed = sum(1 for row in active_rows if row["new_price_decimal"] != row["old_price_decimal"])
        lines.append(
            f"시장 기준 선수 benchmark: {active_changed}/{len(active_rows)}명 변동 "
            f"({active_changed / len(active_rows) * 100:.1f}%)"
        )
    if inactive_rows:
        inactive_changed = sum(1 for row in inactive_rows if row["new_price_decimal"] != row["old_price_decimal"])
        lines.append(
            f"KBO 등록 말소 tracking: {inactive_changed}/{len(inactive_rows)}명 변동 "
            f"({inactive_changed / len(inactive_rows) * 100:.1f}%)"
        )

    return "\n".join(lines)


def print_adjustment_samples(adjustments, limit=15):
    print()
    print("=" * 80)
    print("상승 상위 샘플")
    print("=" * 80)
    for row in sorted(adjustments, key=lambda r: (r["new_price_decimal"] - r["old_price_decimal"], r["price_pressure"]), reverse=True)[:limit]:
        print(
            f"{row['player_name']} {row['team']} {row['price_role']} "
            f"{row['old_price_decimal']:.1f} -> {row['new_price_decimal']:.1f} "
            f"target={row['target_price']:.1f} pressure={row['price_pressure']:.2f} "
            f"reason={row['reason']}"
        )

    print()
    print("=" * 80)
    print("하락 상위 샘플")
    print("=" * 80)
    for row in sorted(adjustments, key=lambda r: (r["new_price_decimal"] - r["old_price_decimal"], r["price_pressure"]))[:limit]:
        print(
            f"{row['player_name']} {row['team']} {row['price_role']} "
            f"{row['old_price_decimal']:.1f} -> {row['new_price_decimal']:.1f} "
            f"target={row['target_price']:.1f} pressure={row['price_pressure']:.2f} "
            f"reason={row['reason']}"
        )


def run_price_update(
    basis_date,
    base_price_date=None,
    basis_start_date=SEASON_START_DATE,
    dry_run=True,
    apply=False,
    force=False,
):
    if os.environ.get("MYPICK_SKIP_PRICE_INIT_DB") != "1":
        init_db()

    basis_date = to_game_date(basis_date)
    basis_start_date = to_game_date(basis_start_date)
    basis_end_date = basis_date

    if dry_run == apply:
        raise ValueError("--dry-run 또는 --apply 중 하나만 선택해야 합니다.")

    if base_price_date is None:
        base_price_date = find_previous_price_date(basis_date)
    else:
        base_price_date = to_game_date(base_price_date)

    if not base_price_date:
        raise RuntimeError(
            f"{BASIS_SOURCE} 기준 이전 가격 날짜가 없습니다. "
            "먼저 rebuild_price_history_v3.py로 seed 가격을 생성하세요."
        )

    if apply:
        role_summary = refresh_pitcher_detail_positions_for_date(basis_date)
        print(
            "투수 역할 동기화:",
            f"{role_summary['start_date']}~{role_summary['end_date']}",
            f"선발 {role_summary['starting_pitchers']}명,",
            f"불펜 {role_summary['bullpen_pitchers']}명"
        )

    if apply and has_successful_apply_run(basis_date) and not force:
        print(f"이미 성공한 {BASIS_SOURCE} apply 기록이 있습니다: {basis_date}")
        print("다시 적용하려면 --force를 사용하세요.")
        return []

    if apply and force:
        cleanup_basis_date_for_force(basis_date)

    players = load_players_with_base_prices(base_price_date)
    if not players:
        raise RuntimeError(f"기준 가격 row가 없습니다: {BASIS_SOURCE} {base_price_date}")

    new_market_players = load_new_active_players_missing_from_base(players, basis_date=basis_date)
    if new_market_players:
        print(f"신규/기록 보유 registered_players 기본가 편입: {len(new_market_players)}명")
        players.extend(new_market_players)

    adjustments = build_adjustments(players, basis_date)

    print()
    print("=" * 80)
    print("MyPick Market Price Engine v3")
    print("=" * 80)
    print("basis_source:", BASIS_SOURCE)
    print("base_price_date:", base_price_date)
    print("basis_date:", basis_date)
    print("mode:", "apply" if apply else "dry-run")
    print("-")
    print(summarize_adjustments(adjustments))
    print_adjustment_samples(adjustments)

    if dry_run:
        print()
        print("dry-run 완료: DB에는 아무것도 저장하지 않았습니다.")
        return adjustments

    run_id = create_price_update_run(
        basis_date=basis_date,
        basis_start_date=basis_start_date,
        basis_end_date=basis_end_date,
        run_mode="apply",
    )

    try:
        save_adjustments(run_id, adjustments, basis_date, basis_start_date, basis_end_date)
        apply_price_rows(adjustments, basis_date)
        message = summarize_adjustments(adjustments)
        finish_price_update_run(run_id, "success", message)
        print()
        print("apply 완료")
        print("run_id:", run_id)
        return adjustments
    except Exception as error:
        finish_price_update_run(run_id, "failed", str(error))
        raise


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="MyPick Market Price Engine v3 가격 업데이트"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="DB 저장 없이 계산 결과만 출력합니다.")
    mode.add_argument("--apply", action="store_true", help="계산 결과를 market_daily_v3로 저장합니다.")
    parser.add_argument("--basis-date", required=True, help="가격을 생성할 날짜입니다. 예: 2026-05-16 또는 20260516")
    parser.add_argument("--base-price-date", help="기준 가격 날짜입니다. 생략하면 basis-date 이전 최신 market_daily_v3 날짜를 사용합니다.")
    parser.add_argument("--basis-start-date", default=SEASON_START_DATE, help="시즌 시작일입니다. 기본값: 2026-03-28")
    parser.add_argument("--force", action="store_true", help="같은 날짜 market_daily_v3 기록을 v3 범위 안에서만 정리하고 재적용합니다.")
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    run_price_update(
        basis_date=args.basis_date,
        base_price_date=args.base_price_date,
        basis_start_date=args.basis_start_date,
        dry_run=args.dry_run,
        apply=args.apply,
        force=args.force,
    )


if __name__ == "__main__":
    main()
