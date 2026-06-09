# sync_db.py
"""
KBO 경기 기록을 가져와서 DB에 저장하는 파일입니다.

이 파일이 하는 일:

1. 특정 날짜의 경기 목록을 가져옵니다.
2. 각 경기의 타자 기록과 투수 기록을 가져옵니다.
3. 타자 점수를 계산합니다.
4. 투수 점수를 계산합니다.
5. raw_batter_stats, raw_pitcher_stats에 원본 기록을 저장합니다.
6. fantasy_daily_scores에 경기별 판타지 점수를 저장합니다.
7. fantasy_player_totals에 선수별 총점을 다시 계산해서 저장합니다.
8. 최근 14일 기준으로 투수를 선발투수/불펜투수로 다시 분류합니다.

중요:
같은 경기를 여러 번 실행해도 점수가 중복으로 올라가면 안 됩니다.
그래서 INSERT OR UPDATE 방식으로 저장합니다.

주의:
- kbo_fantasy.db를 삭제하지 않습니다.
- DROP TABLE을 사용하지 않습니다.
- 기존 점수 계산 흐름은 유지합니다.
- fantasy_player_totals는 누적 총점 보관용으로만 유지합니다.
- 화면의 현재 점수 기준은 app.py에서 fantasy_daily_scores의 최신 game_date 기준으로 처리합니다.
"""

import json
import sys
from datetime import datetime, timedelta

from db import get_conn, init_db
from scraper import get_games_for_date, get_game_boxscore_stats
from scoring import calc_batter_points, calc_pitcher_points
from position_rules import EXACT_BATTER_DETAIL_POSITIONS


def save_game(conn, game):
    """
    경기 기본 정보를 games 테이블에 저장합니다.

    이미 같은 game_id가 있으면 새로 추가하지 않고 업데이트합니다.
    """

    conn.execute("""
        INSERT INTO games
            (game_date, game_id, away_team, home_team, stadium, status, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(game_id) DO UPDATE SET
            game_date = excluded.game_date,
            away_team = excluded.away_team,
            home_team = excluded.home_team,
            stadium = excluded.stadium,
            status = excluded.status,
            updated_at = CURRENT_TIMESTAMP
    """, (
        game["game_date"],
        game["game_id"],
        game["away_team"],
        game["home_team"],
        game["stadium"],
        "finished" if game.get("finished") else "unknown",
    ))


def save_player(conn, player_name, team, position_type):
    """
    선수 기본 정보를 players 테이블에 저장합니다.

    같은 이름, 팀, 포지션 타입이 이미 있으면 업데이트만 합니다.
    """

    conn.execute("""
        INSERT INTO players
            (name, team, position_type, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(name, team, position_type) DO UPDATE SET
            updated_at = CURRENT_TIMESTAMP
    """, (
        player_name,
        team,
        position_type,
    ))


def save_raw_batter_stat(conn, game, batter):
    """
    타자 원본 기록을 raw_batter_stats 테이블에 저장합니다.

    기존 저장 항목:
    hits, doubles, triples, home_runs, rbi, runs,
    game_winning_hit, double_play

    새 점수 규칙을 위해 추가 저장하는 항목:
    hit_by_pitch:
        사구 개수

    walks:
        볼넷 개수

    stolen_bases:
        도루 개수

    strikeouts:
        타자 삼진 개수

    중요:
    같은 경기를 다시 실행해도 ON CONFLICT UPDATE로
    기존 기록과 새 기록값이 다시 갱신됩니다.
    """

    conn.execute("""
        INSERT INTO raw_batter_stats
            (
                game_id,
                game_date,
                player_name,
                team,
                hits,
                doubles,
                triples,
                home_runs,
                rbi,
                runs,
                game_winning_hit,
                double_play,
                hit_by_pitch,
                walks,
                stolen_bases,
                strikeouts,
                batting_order,
                starting_detail_position,
                is_starting_batter,
                lineup_position_source
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id, player_name, team) DO UPDATE SET
            game_date = excluded.game_date,
            hits = excluded.hits,
            doubles = excluded.doubles,
            triples = excluded.triples,
            home_runs = excluded.home_runs,
            rbi = excluded.rbi,
            runs = excluded.runs,
            game_winning_hit = excluded.game_winning_hit,
            double_play = excluded.double_play,
            hit_by_pitch = excluded.hit_by_pitch,
            walks = excluded.walks,
            stolen_bases = excluded.stolen_bases,
            strikeouts = excluded.strikeouts,
            batting_order = excluded.batting_order,
            starting_detail_position = excluded.starting_detail_position,
            is_starting_batter = excluded.is_starting_batter,
            lineup_position_source = excluded.lineup_position_source
    """, (
        game["game_id"],
        game["game_date"],
        batter["player_name"],
        batter["team"],
        batter.get("hits", 0),
        batter.get("doubles", 0),
        batter.get("triples", 0),
        batter.get("home_runs", 0),
        batter.get("rbi", 0),
        batter.get("runs", 0),
        batter.get("game_winning_hit", 0),
        batter.get("double_play", 0),
        batter.get("hit_by_pitch", 0),
        batter.get("walks", 0),
        batter.get("stolen_bases", 0),
        batter.get("strikeouts", 0),
        batter.get("batting_order"),
        batter.get("starting_detail_position"),
        int(batter.get("is_starting_batter") or 0),
        batter.get("lineup_position_source"),
    ))


def save_raw_pitcher_stat(conn, game, pitcher, completed_innings):
    """
    투수 원본 기록을 raw_pitcher_stats 테이블에 저장합니다.

    기존 저장 항목:
    wins, losses, holds, innings_pitched_raw,
    completed_innings, strikeouts, runs_allowed

    선발/불펜 기능을 위해 저장하는 항목:
    is_starting_pitcher:
        해당 경기에서 선발투수이면 1, 아니면 0

    pitching_order:
        해당 팀 투수 기록표에서 몇 번째 투수인지 저장합니다.
        선발투수는 1입니다.

    새 점수 규칙을 위해 추가 저장하는 항목:
    saves:
        세이브 여부

    pitch_count:
        투구수

    hits_allowed:
        피안타

    중요:
    같은 경기를 다시 실행해도 ON CONFLICT UPDATE로
    새 기록값과 선발 플래그가 다시 갱신됩니다.
    """

    is_starting_pitcher = pitcher.get("is_starting_pitcher", 0)
    pitching_order = pitcher.get("pitching_order")

    conn.execute("""
        INSERT INTO raw_pitcher_stats
            (
                game_id,
                game_date,
                player_name,
                team,
                wins,
                losses,
                holds,
                saves,
                innings_pitched_raw,
                completed_innings,
                strikeouts,
                runs_allowed,
                pitch_count,
                hits_allowed,
                is_starting_pitcher,
                pitching_order
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id, player_name, team) DO UPDATE SET
            game_date = excluded.game_date,
            wins = excluded.wins,
            losses = excluded.losses,
            holds = excluded.holds,
            saves = excluded.saves,
            innings_pitched_raw = excluded.innings_pitched_raw,
            completed_innings = excluded.completed_innings,
            strikeouts = excluded.strikeouts,
            runs_allowed = excluded.runs_allowed,
            pitch_count = excluded.pitch_count,
            hits_allowed = excluded.hits_allowed,
            is_starting_pitcher = excluded.is_starting_pitcher,
            pitching_order = excluded.pitching_order
    """, (
        game["game_id"],
        game["game_date"],
        pitcher["player_name"],
        pitcher["team"],
        pitcher.get("wins", 0),
        pitcher.get("losses", 0),
        pitcher.get("holds", 0),
        pitcher.get("saves", 0),
        pitcher.get("innings_pitched_raw", ""),
        completed_innings,
        pitcher.get("strikeouts", 0),
        pitcher.get("runs_allowed", 0),
        pitcher.get("pitch_count", 0),
        pitcher.get("hits_allowed", 0),
        is_starting_pitcher,
        pitching_order,
    ))


def save_daily_score(conn, game, player_name, team, position_type, points, detail):
    """
    경기별 판타지 점수를 저장합니다.

    같은 game_id, player_name, position_type이 이미 있으면 업데이트합니다.
    이 덕분에 같은 경기를 여러 번 실행해도 점수가 중복으로 쌓이지 않습니다.
    """

    conn.execute("""
        INSERT INTO fantasy_daily_scores
            (
                game_id,
                game_date,
                player_name,
                team,
                position_type,
                points,
                score_detail_json,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(game_id, player_name, position_type) DO UPDATE SET
            game_date = excluded.game_date,
            team = excluded.team,
            points = excluded.points,
            score_detail_json = excluded.score_detail_json,
            updated_at = CURRENT_TIMESTAMP
    """, (
        game["game_id"],
        game["game_date"],
        player_name,
        team,
        position_type,
        points,
        json.dumps(detail, ensure_ascii=False),
    ))


def recompute_player_totals(conn):
    """
    선수별 총점을 다시 계산합니다.

    중요한 점:
    기존 총점에 새 점수를 더하는 방식이 아닙니다.
    fantasy_daily_scores에 저장된 경기별 점수를 기준으로 매번 다시 합산합니다.

    그래서 같은 날짜를 여러 번 실행해도 총점이 중복 증가하지 않습니다.

    주의:
    현재 웹사이트 화면의 현재 점수는 이 누적 총점이 아니라,
    app.py에서 fantasy_daily_scores의 최신 game_date 기준으로 표시합니다.
    """

    rows = conn.execute("""
        SELECT
            player_name,
            team,
            position_type,
            SUM(points) AS total_points
        FROM fantasy_daily_scores
        GROUP BY player_name, team, position_type
    """).fetchall()

    for row in rows:
        conn.execute("""
            INSERT INTO fantasy_player_totals
                (
                    player_name,
                    team,
                    position_type,
                    total_points,
                    last_updated_at
                )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(player_name, team, position_type) DO UPDATE SET
                total_points = excluded.total_points,
                last_updated_at = CURRENT_TIMESTAMP
        """, (
            row["player_name"],
            row["team"],
            row["position_type"],
            row["total_points"],
        ))


def get_latest_game_date_for_pitcher_roles(conn):
    """
    선발투수/불펜투수 역할 계산에 사용할 최신 경기 날짜를 가져옵니다.

    우선 fantasy_daily_scores의 MAX(game_date)를 기준으로 합니다.
    현재 사이트의 최근 경기 점수 기준도 fantasy_daily_scores의 최신 game_date이기 때문입니다.

    만약 fantasy_daily_scores가 비어 있으면 raw_pitcher_stats의 최신 날짜를 대신 사용합니다.
    """

    row = conn.execute("""
        SELECT MAX(game_date) AS latest_game_date
        FROM fantasy_daily_scores
    """).fetchone()

    if row is not None and row["latest_game_date"]:
        return row["latest_game_date"]

    row = conn.execute("""
        SELECT MAX(game_date) AS latest_game_date
        FROM raw_pitcher_stats
    """).fetchone()

    if row is not None and row["latest_game_date"]:
        return row["latest_game_date"]

    return None


def update_recent_pitcher_roles(conn):
    """
    실제 투수 등판 기록의 "가장 최근 역할" 기준으로 등록 선수의 투수 역할을 업데이트합니다.

    최종 규칙:
    - raw_pitcher_stats.is_starting_pitcher = 1인 가장 최근 등판이면 선발투수입니다.
    - raw_pitcher_stats.is_starting_pitcher = 0인 가장 최근 등판이면 불펜투수입니다.
    - 오래 선발 등판이 없다는 이유만으로 불펜투수로 강등하지 않습니다.
    - 실제 불펜 등판 기록이 생길 때만 불펜투수로 변경합니다.

    중요:
    - 타자 detail_position은 건드리지 않습니다.
    - fantasy_position_type = 'pitcher'인 활성 등록 선수만 업데이트합니다.
    - 등판 기록이 전혀 없는 투수는 기존 detail_position을 유지합니다.
    - 기존 팀 선수를 자동 삭제하거나 자동 이동하지 않습니다.
      역할이 바뀌어서 슬롯과 맞지 않으면 app.py의 팀 검증에서 오류로 표시합니다.
    """

    latest_game_date = get_latest_game_date_for_pitcher_roles(conn)

    if not latest_game_date:
        print("투수 역할 업데이트 생략: 기준 경기 날짜가 없습니다.")
        return {
            "latest_game_date": None,
            "start_date": None,
            "end_date": None,
            "bullpen_updated_count": 0,
            "starter_updated_count": 0,
            "starter_source_count": 0,
            "bullpen_source_count": 0,
            "appearance_source_count": 0,
        }

    end_date = latest_game_date

    latest_role_rows = conn.execute("""
        WITH latest_appearances AS (
            SELECT
                rp.id AS registered_player_id,
                rp.name,
                rp.team,
                rp.detail_position AS old_detail_position,
                rps.game_date AS last_pitching_date,
                COALESCE(rps.pitching_order, 999) AS last_pitching_order,
                CASE
                    WHEN COALESCE(rps.is_starting_pitcher, 0) = 1 THEN '선발투수'
                    ELSE '불펜투수'
                END AS new_detail_position,
                CASE
                    WHEN COALESCE(rps.is_starting_pitcher, 0) = 1 THEN 'starting_pitcher'
                    ELSE 'bullpen_pitcher'
                END AS new_price_role,
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
    """, (end_date,)).fetchall()

    starter_source_count = sum(1 for row in latest_role_rows if row["new_detail_position"] == "선발투수")
    bullpen_source_count = sum(1 for row in latest_role_rows if row["new_detail_position"] == "불펜투수")
    starter_updated_count = 0
    bullpen_updated_count = 0

    for row in latest_role_rows:
        new_detail_position = row["new_detail_position"]
        cursor = conn.execute("""
            UPDATE registered_players
            SET
                detail_position = ?,
                detail_position_source = 'latest_actual_pitching_role',
                detail_position_updated_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND fantasy_position_type = 'pitcher'
              AND is_active = 1
              AND COALESCE(detail_position, '') != ?
        """, (
            new_detail_position,
            row["registered_player_id"],
            new_detail_position,
        ))

        if new_detail_position == "선발투수":
            starter_updated_count += cursor.rowcount
        else:
            bullpen_updated_count += cursor.rowcount

    print("투수 역할 업데이트 완료")
    print("기준 최신 경기 날짜:", end_date)
    print("역할 기준: 가장 최근 실제 등판 기록")
    print("최근 등판 기준 선발투수 선수 수:", starter_source_count)
    print("최근 등판 기준 불펜투수 선수 수:", bullpen_source_count)
    print("선발투수로 변경한 등록 선수 수:", starter_updated_count)
    print("불펜투수로 변경한 등록 선수 수:", bullpen_updated_count)

    return {
        "latest_game_date": latest_game_date,
        "start_date": None,
        "end_date": end_date,
        "bullpen_updated_count": bullpen_updated_count,
        "starter_updated_count": starter_updated_count,
        "starter_source_count": starter_source_count,
        "bullpen_source_count": bullpen_source_count,
        "appearance_source_count": len(latest_role_rows),
    }

def update_batter_detail_positions_from_starts(conn):
    """선발 라인업 근거로 active 타자의 현재 상세 포지션을 업데이트합니다.

    정책:
    - 선발 수비 포지션(포수/1B/2B/3B/SS/LF/CF/RF)만 상세 포지션으로 업데이트합니다.
    - 교체 기록, 대타, 대주자는 사용하지 않습니다.
    - 지명타자 선발 기록은 기존 수비 포지션을 덮어쓰지 않습니다.
    - 단, 수비 선발 기록이 전혀 없고 지명타자 선발 기록만 있는 타자는
      detail_position='지명타자'로 두어 UTIL 전용 타자로 취급합니다.
    """
    latest_game_date_row = conn.execute("""
        SELECT MAX(game_date) AS latest_game_date
        FROM raw_batter_stats
        WHERE COALESCE(is_starting_batter, 0) = 1
          AND starting_detail_position IS NOT NULL
          AND starting_detail_position <> ''
    """).fetchone()
    latest_game_date = latest_game_date_row["latest_game_date"] if latest_game_date_row else None

    if not latest_game_date:
        print("타자 상세 포지션 업데이트 생략: 선발 라인업 포지션 근거가 없습니다.")
        return {
            "latest_game_date": None,
            "candidate_count": 0,
            "updated_count": 0,
            "defensive_source_count": 0,
            "dh_only_source_count": 0,
            "dh_only_updated_count": 0,
        }

    exact_positions = tuple(sorted(EXACT_BATTER_DETAIL_POSITIONS))
    placeholders = ",".join(["?"] * len(exact_positions))

    defensive_rows = conn.execute(f"""
        WITH latest_defensive_starts AS (
            SELECT
                rp.id AS registered_player_id,
                rp.name,
                rp.team,
                rp.detail_position AS old_detail_position,
                rbs.game_date AS last_start_date,
                rbs.starting_detail_position AS new_detail_position,
                ROW_NUMBER() OVER (
                    PARTITION BY rp.id
                    ORDER BY rbs.game_date DESC, rbs.game_id DESC
                ) AS rn
            FROM registered_players rp
            JOIN raw_batter_stats rbs
              ON rbs.player_name = rp.name
             AND rbs.team = rp.team
            WHERE rp.fantasy_position_type = 'batter'
              AND rp.is_active = 1
              AND COALESCE(rbs.is_starting_batter, 0) = 1
              AND rbs.starting_detail_position IN ({placeholders})
              AND rbs.game_date <= ?
        )
        SELECT *
        FROM latest_defensive_starts
        WHERE rn = 1
    """, (*exact_positions, latest_game_date)).fetchall()

    updated_count = 0
    for row in defensive_rows:
        new_detail = row["new_detail_position"]
        cursor = conn.execute("""
            UPDATE registered_players
            SET
                detail_position = ?,
                detail_position_source = 'starting_lineup_defensive_position',
                detail_position_updated_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND fantasy_position_type = 'batter'
              AND is_active = 1
              AND COALESCE(detail_position, '') != ?
        """, (new_detail, row["registered_player_id"], new_detail))
        updated_count += cursor.rowcount

    # DH-only 업데이트는 수비 선발 기록이 전혀 없는 선수에게만 적용합니다.
    # 기존에 정확한 수비 포지션이 있는 선수는 DH 선발 기록으로 덮어쓰지 않습니다.
    dh_only_rows = conn.execute(f"""
        WITH start_summary AS (
            SELECT
                rp.id AS registered_player_id,
                rp.name,
                rp.team,
                rp.detail_position AS old_detail_position,
                SUM(CASE WHEN rbs.starting_detail_position IN ({placeholders}) THEN 1 ELSE 0 END) AS defensive_start_count,
                SUM(CASE WHEN rbs.starting_detail_position = '지명타자' THEN 1 ELSE 0 END) AS dh_start_count,
                COUNT(rbs.id) AS known_start_count,
                MAX(CASE WHEN rbs.starting_detail_position = '지명타자' THEN rbs.game_date ELSE NULL END) AS last_dh_start_date
            FROM registered_players rp
            JOIN raw_batter_stats rbs
              ON rbs.player_name = rp.name
             AND rbs.team = rp.team
            WHERE rp.fantasy_position_type = 'batter'
              AND rp.is_active = 1
              AND COALESCE(rbs.is_starting_batter, 0) = 1
              AND rbs.starting_detail_position IS NOT NULL
              AND rbs.starting_detail_position <> ''
              AND rbs.game_date <= ?
            GROUP BY rp.id
        )
        SELECT *
        FROM start_summary
        WHERE defensive_start_count = 0
          AND dh_start_count > 0
          AND known_start_count = dh_start_count
    """, (*exact_positions, latest_game_date)).fetchall()

    exact_position_set = set(EXACT_BATTER_DETAIL_POSITIONS)
    dh_only_updated_count = 0
    for row in dh_only_rows:
        old_detail = row["old_detail_position"] or ""
        if old_detail in exact_position_set:
            continue
        cursor = conn.execute("""
            UPDATE registered_players
            SET
                detail_position = '지명타자',
                detail_position_source = 'dh_only_starting_lineup',
                detail_position_updated_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND fantasy_position_type = 'batter'
              AND is_active = 1
              AND COALESCE(detail_position, '') != '지명타자'
        """, (row["registered_player_id"],))
        dh_only_updated_count += cursor.rowcount

    print("타자 상세 포지션 업데이트 완료")
    print("기준 최신 경기 날짜:", latest_game_date)
    print("선발 수비 포지션 근거 선수 수:", len(defensive_rows))
    print("수비 포지션으로 업데이트한 등록 선수 수:", updated_count)
    print("DH-only 후보 선수 수:", len(dh_only_rows))
    print("지명타자로 업데이트한 등록 선수 수:", dh_only_updated_count)

    return {
        "latest_game_date": latest_game_date,
        "candidate_count": len(defensive_rows) + len(dh_only_rows),
        "updated_count": updated_count + dh_only_updated_count,
        "defensive_source_count": len(defensive_rows),
        "dh_only_source_count": len(dh_only_rows),
        "dh_only_updated_count": dh_only_updated_count,
    }

def is_zero_stat_batter_record(batter):
    """타자 row가 실질 기록 없이 출전 +100만 만들 가능성이 높은지 확인합니다."""
    stat_keys = [
        "hits", "doubles", "triples", "home_runs", "rbi", "runs",
        "game_winning_hit", "double_play", "hit_by_pitch", "walks",
        "stolen_bases", "strikeouts",
    ]
    return all(int(batter.get(key) or 0) == 0 for key in stat_keys)


def is_registered_pitcher_identity(conn, player_name, team):
    """같은 이름/팀이 registered_players에서 투수로만 확인되는지 봅니다."""
    rows = conn.execute("""
        SELECT fantasy_position_type, COUNT(*) AS cnt
        FROM registered_players
        WHERE name = ?
          AND team = ?
        GROUP BY fantasy_position_type
    """, (player_name, team)).fetchall()

    if not rows:
        return False

    position_types = {row["fantasy_position_type"] for row in rows}
    return position_types == {"pitcher"}


def should_skip_phantom_pitcher_batter_row(conn, batter):
    """
    KBO 박스스코어 파싱 과정에서 일부 투수명이 타자 테이블에 0스탯 row로 섞여
    fantasy_daily_scores에 batter 출전 +100이 생기는 경우를 방지합니다.

    조건을 아주 보수적으로 둡니다.
    - 모든 타격 스탯이 0
    - 같은 이름/팀이 registered_players에서 투수로만 존재
    이때만 타자 row 저장을 건너뜁니다.
    """
    if not is_zero_stat_batter_record(batter):
        return False
    return is_registered_pitcher_identity(conn, batter["player_name"], batter["team"])


def resolve_numeric_pitcher_name_from_registered_players(conn, pitcher):
    """
    MYPICK NUMERIC PITCHER NAME FIX 2026-06-05

    일부 KBO 투수 박스스코어 row에서 player_name이 선수명이 아니라
    숫자 player_id로 파싱되는 경우가 있습니다.

    예:
    - player_name = "51994"  # 실제 선수명: 한재승

    이 상태로 raw_pitcher_stats / fantasy_daily_scores에 저장되면
    registered_players.name과 연결되지 않아 선수 상세, 가격, 팀 점수 반영이 깨집니다.

    DB에 이미 보유한 registered_players.player_id + team + pitcher 기준으로
    저장 직전에 실제 선수명으로 복구합니다.
    """
    raw_name = str(pitcher.get("player_name") or "").strip()
    team = str(pitcher.get("team") or "").strip()

    if not raw_name.isdigit() or not team:
        return pitcher

    row = conn.execute("""
        SELECT name
        FROM registered_players
        WHERE CAST(player_id AS TEXT) = ?
          AND team = ?
          AND fantasy_position_type = 'pitcher'
        ORDER BY is_active DESC, id DESC
        LIMIT 1
    """, (raw_name, team)).fetchone()

    if not row or not row["name"]:
        print(
            "숫자 투수명 복구 실패:",
            f"player_id={raw_name}",
            f"team={team}",
        )
        return pitcher

    resolved = dict(pitcher)
    resolved["player_name"] = row["name"]
    resolved["source_player_id"] = raw_name

    print(
        "숫자 투수명 복구:",
        f"{team}",
        f"{raw_name}",
        "->",
        row["name"],
    )

    return resolved



def process_one_game(conn, game):
    """
    한 경기의 기록을 가져와서 DB에 저장합니다.
    """

    save_game(conn, game)

    boxscore_result = get_game_boxscore_stats(game)

    batter_count = 0
    pitcher_count = 0
    score_count = 0

    for batter in boxscore_result["batters"]:
        if should_skip_phantom_pitcher_batter_row(conn, batter):
            print(
                "타자 0스탯 phantom row 생략:",
                batter["player_name"],
                batter["team"],
                game["game_id"],
            )
            continue

        save_player(
            conn,
            batter["player_name"],
            batter["team"],
            "batter",
        )

        save_raw_batter_stat(conn, game, batter)

        points, detail = calc_batter_points(batter)

        save_daily_score(
            conn,
            game,
            batter["player_name"],
            batter["team"],
            "batter",
            points,
            detail,
        )

        batter_count += 1
        score_count += 1

    for pitcher in boxscore_result["pitchers"]:
        pitcher = resolve_numeric_pitcher_name_from_registered_players(conn, pitcher)

        save_player(
            conn,
            pitcher["player_name"],
            pitcher["team"],
            "pitcher",
        )

        points, detail, completed_innings = calc_pitcher_points(pitcher)

        save_raw_pitcher_stat(
            conn,
            game,
            pitcher,
            completed_innings,
        )

        save_daily_score(
            conn,
            game,
            pitcher["player_name"],
            pitcher["team"],
            "pitcher",
            points,
            detail,
        )

        pitcher_count += 1
        score_count += 1

    return {
        "batter_count": batter_count,
        "pitcher_count": pitcher_count,
        "score_count": score_count,
    }


def sync_date(target_date, target_game_id=None):
    """
    특정 날짜의 경기들을 DB에 저장합니다.

    target_date:
        20260501 또는 2026-05-01

    target_game_id:
        특정 경기만 테스트하고 싶을 때 사용합니다.
        예: 20260501NCLG0
    """

    init_db()

    print("동기화 시작")
    print("대상 날짜:", target_date)

    if target_game_id:
        print("대상 경기:", target_game_id)
    else:
        print("대상 경기: 전체 경기")

    print()

    games = get_games_for_date(target_date)

    if target_game_id:
        games = [
            game for game in games
            if game["game_id"] == target_game_id
        ]

    print("수집한 경기 수:", len(games))

    processed_game_count = 0
    total_batter_count = 0
    total_pitcher_count = 0
    total_score_count = 0
    failed_games = []

    pitcher_role_result = {
        "latest_game_date": None,
        "start_date": None,
        "end_date": None,
        "bullpen_updated_count": 0,
        "starter_updated_count": 0,
        "starter_source_count": 0,
    }
    batter_position_result = {
        "latest_game_date": None,
        "candidate_count": 0,
        "updated_count": 0,
    }

    with get_conn() as conn:
        for game in games:
            print()
            print("=" * 80)
            print("경기 처리 시작:", game["game_id"])
            print(
                game["away_team"],
                game["away_score"],
                "vs",
                game["home_score"],
                game["home_team"],
                game["stadium"],
            )

            try:
                result = process_one_game(conn, game)

                processed_game_count += 1
                total_batter_count += result["batter_count"]
                total_pitcher_count += result["pitcher_count"]
                total_score_count += result["score_count"]

                print("저장한 타자 기록 수:", result["batter_count"])
                print("저장한 투수 기록 수:", result["pitcher_count"])
                print("저장한 점수 수:", result["score_count"])

            except Exception as e:
                print("경기 처리 실패:", game["game_id"])
                print("에러:", e)
                failed_games.append(game["game_id"])

        recompute_player_totals(conn)

        # 경기 기록과 점수 저장이 끝난 뒤, 타자/투수 현재 포지션을 최신화합니다.
        # 타자는 선발 라인업의 확실한 수비 포지션만 사용하고, 교체/DH는 제외합니다.
        batter_position_result = update_batter_detail_positions_from_starts(conn)
        pitcher_role_result = update_recent_pitcher_roles(conn)

    print()
    print("=" * 80)
    print("동기화 완료")
    print("=" * 80)
    print("오늘 날짜:", target_date)
    print("수집한 경기 수:", len(games))
    print("처리한 경기 수:", processed_game_count)
    print("저장한 타자 기록 수:", total_batter_count)
    print("저장한 투수 기록 수:", total_pitcher_count)
    print("업데이트한 선수 점수 수:", total_score_count)
    print("실패한 경기 목록:", failed_games)
    print("타자 상세 포지션 기준 날짜:", batter_position_result.get("latest_game_date"))
    print("선발 수비 포지션 후보 수:", batter_position_result.get("candidate_count", 0))
    print("타자 상세 포지션 업데이트 수:", batter_position_result.get("updated_count", 0))
    print("투수 역할 기준 날짜:", pitcher_role_result["latest_game_date"])
    print("투수 역할 계산 기준: 가장 최근 실제 등판 기록")
    print("최근 등판 기준 선발투수 선수 수:", pitcher_role_result["starter_source_count"])
    print("최근 등판 기준 불펜투수 선수 수:", pitcher_role_result.get("bullpen_source_count", 0))
    print("선발투수 업데이트 수:", pitcher_role_result["starter_updated_count"])
    print("불펜투수 업데이트 수:", pitcher_role_result.get("bullpen_updated_count", 0))


if __name__ == "__main__":
    """
    실행 예시:

    한 경기만 테스트:
    python sync_db.py 20260501 20260501NCLG0

    날짜 전체 경기 저장:
    python sync_db.py 20260501

    날짜를 입력하지 않으면 오늘 날짜 기준으로 실행:
    python sync_db.py
    """

    if len(sys.argv) >= 2:
        date_arg = sys.argv[1]
    else:
        date_arg = datetime.now().strftime("%Y%m%d")

    game_id_arg = None

    if len(sys.argv) >= 3:
        game_id_arg = sys.argv[2]

    sync_date(date_arg, game_id_arg)