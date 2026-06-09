# audit_mypick_integrity.py
"""
MyPick 핵심 무결성 점검 스크립트입니다.
DB를 수정하지 않고 SELECT만 실행합니다.

확인 항목:
1. 정보: 최근 출전 기록은 있지만 현재 KBO 전체 등록 명단에는 없는 선수
2. 오류: 현재 KBO 등록 선수인데 가격 reason에 등록 말소가 찍힌 선수
3. 오류: 최신 market_daily_v3 price_role과 가장 최근 실제 등판 역할 불일치
4. 오류: registered_players.detail_position과 가장 최근 실제 등판 역할 불일치
5. 최신 market_daily_v3 중복 가격 row
6. 최근 출전했는데 최신 가격 row가 없는 등록 선수
7. 투수로 등록된 선수의 phantom batter score row 후보
8. 팀 점수 계산 파일의 시장가 기준 source 확인
"""

from db import get_conn

BASIS_SOURCE = "market_daily_v3"


def read_team_score_basis_source():
    try:
        with open("calculate_team_daily_scores.py", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("BASIS_SOURCE"):
                    return line.strip()
    except FileNotFoundError:
        return "calculate_team_daily_scores.py 없음"
    return "BASIS_SOURCE line 없음"


def print_rows(title, rows, limit=50):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print("count:", len(rows))
    for row in rows[:limit]:
        print(dict(row))
    if len(rows) > limit:
        print(f"... {len(rows) - limit}개 더 있음")


def main():
    with get_conn() as conn:
        latest_game = conn.execute("SELECT MAX(game_date) FROM fantasy_daily_scores").fetchone()[0]
        latest_price = conn.execute("""
            SELECT MAX(basis_date)
            FROM player_prices
            WHERE basis_source=?
        """, (BASIS_SOURCE,)).fetchone()[0]

        print("latest_game:", latest_game)
        print("latest_price:", latest_price)

        rows = conn.execute("""
            WITH recent_played AS (
                SELECT player_name, team, position_type,
                       MAX(game_date) AS last_game_date,
                       COUNT(*) AS recent_games,
                       SUM(points) AS recent_points
                FROM fantasy_daily_scores
                WHERE game_date BETWEEN date(?, '-6 day') AND ?
                GROUP BY player_name, team, position_type
            )
            SELECT rp.id, rp.name, rp.team, rp.fantasy_position_type,
                   rp.is_active, rp.roster_position, rp.detail_position,
                   recent_played.last_game_date, recent_played.recent_games, recent_played.recent_points
            FROM recent_played
            JOIN registered_players rp
              ON rp.name = recent_played.player_name
             AND rp.team = recent_played.team
             AND rp.fantasy_position_type = recent_played.position_type
            WHERE rp.is_active = 0
            ORDER BY recent_played.last_game_date DESC, recent_played.recent_points DESC
        """, (latest_game, latest_game)).fetchall()
        print_rows("1. 정보: 현재 KBO 등록 말소 선수 중 최근 7일 출전 기록이 있는 선수", rows)

        rows = conn.execute("""
            WITH recent_registered_played AS (
                SELECT rp.id AS registered_player_id,
                       rp.name AS player_name,
                       rp.team,
                       rp.fantasy_position_type AS position_type,
                       MAX(fds.game_date) AS last_game_date,
                       COUNT(*) AS recent_games,
                       SUM(fds.points) AS recent_points
                FROM registered_players rp
                JOIN fantasy_daily_scores fds
                  ON fds.player_name = rp.name
                 AND fds.team = rp.team
                 AND fds.position_type = rp.fantasy_position_type
                WHERE fds.game_date BETWEEN date(?, '-6 day') AND ?
                GROUP BY rp.id, rp.name, rp.team, rp.fantasy_position_type
            )
            SELECT ppa.registered_player_id, ppa.player_name, ppa.team, ppa.price_role,
                   ppa.basis_date, ppa.old_price_decimal, ppa.new_price_decimal,
                   ppa.reason, rp.is_active, rp.roster_position, rp.detail_position,
                   recent_registered_played.last_game_date,
                   recent_registered_played.recent_games,
                   recent_registered_played.recent_points
            FROM player_price_adjustments ppa
            JOIN recent_registered_played
              ON recent_registered_played.registered_player_id = ppa.registered_player_id
            LEFT JOIN registered_players rp
              ON rp.id = ppa.registered_player_id
            WHERE ppa.basis_source=?
              AND ppa.basis_date=?
              AND (ppa.reason LIKE '%말소%' OR ppa.reason LIKE '%등록이 말소%')
              AND COALESCE(rp.is_active, 0) = 1
            ORDER BY recent_registered_played.last_game_date DESC, recent_registered_played.recent_points DESC
        """, (latest_game, latest_game, BASIS_SOURCE, latest_price)).fetchall()
        print_rows("2. 오류: 현재 KBO 등록 선수인데 가격 reason에 등록 말소가 찍힌 선수", rows)

        rows = conn.execute("""
            WITH latest_pitcher_appearance AS (
                SELECT
                    player_name,
                    team,
                    game_date AS latest_appearance_date,
                    CASE
                        WHEN COALESCE(is_starting_pitcher, 0) = 1 THEN 'starting_pitcher'
                        ELSE 'bullpen_pitcher'
                    END AS expected_price_role,
                    CASE
                        WHEN COALESCE(is_starting_pitcher, 0) = 1 THEN '선발투수'
                        ELSE '불펜투수'
                    END AS expected_detail_position,
                    ROW_NUMBER() OVER (
                        PARTITION BY player_name, team
                        ORDER BY game_date DESC, COALESCE(pitching_order, 999) DESC, id DESC
                    ) AS rn
                FROM raw_pitcher_stats
                WHERE game_date <= ?
            )
            SELECT pp.registered_player_id, pp.player_name, pp.team,
                   latest_pitcher_appearance.latest_appearance_date,
                   latest_pitcher_appearance.expected_price_role,
                   pp.price_role AS current_price_role,
                   rp.is_active,
                   rp.detail_position
            FROM player_prices pp
            JOIN latest_pitcher_appearance
              ON latest_pitcher_appearance.player_name = pp.player_name
             AND latest_pitcher_appearance.team = pp.team
             AND latest_pitcher_appearance.rn = 1
            LEFT JOIN registered_players rp
              ON rp.id = pp.registered_player_id
            WHERE pp.basis_source=?
              AND pp.basis_date=?
              AND pp.fantasy_position_type='pitcher'
              AND pp.price_role <> latest_pitcher_appearance.expected_price_role
            ORDER BY pp.team, pp.player_name
        """, (latest_price, BASIS_SOURCE, latest_price)).fetchall()
        print_rows("3. 오류: 최신 market_daily_v3 price_role과 가장 최근 실제 등판 역할 불일치", rows)

        rows = conn.execute("""
            WITH latest_pitcher_appearance AS (
                SELECT
                    player_name,
                    team,
                    game_date AS latest_appearance_date,
                    CASE
                        WHEN COALESCE(is_starting_pitcher, 0) = 1 THEN '선발투수'
                        ELSE '불펜투수'
                    END AS expected_detail_position,
                    ROW_NUMBER() OVER (
                        PARTITION BY player_name, team
                        ORDER BY game_date DESC, COALESCE(pitching_order, 999) DESC, id DESC
                    ) AS rn
                FROM raw_pitcher_stats
                WHERE game_date <= ?
            )
            SELECT rp.id AS registered_player_id,
                   rp.name AS player_name,
                   rp.team,
                   latest_pitcher_appearance.latest_appearance_date,
                   latest_pitcher_appearance.expected_detail_position,
                   rp.detail_position AS current_detail_position,
                   rp.is_active
            FROM registered_players rp
            JOIN latest_pitcher_appearance
              ON latest_pitcher_appearance.player_name = rp.name
             AND latest_pitcher_appearance.team = rp.team
             AND latest_pitcher_appearance.rn = 1
            WHERE rp.fantasy_position_type = 'pitcher'
              AND COALESCE(rp.detail_position, '') <> latest_pitcher_appearance.expected_detail_position
            ORDER BY rp.team, rp.name
        """, (latest_price,)).fetchall()
        print_rows("4. 오류: registered_players.detail_position과 가장 최근 실제 등판 역할 불일치", rows)

        rows = conn.execute("""
            SELECT registered_player_id, basis_date, COUNT(*) AS cnt,
                   GROUP_CONCAT(id) AS price_row_ids
            FROM player_prices
            WHERE basis_source=?
              AND basis_date=?
            GROUP BY registered_player_id, basis_date
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC, registered_player_id
        """, (BASIS_SOURCE, latest_price)).fetchall()
        print_rows("5. 최신 market_daily_v3 동일 registered_player_id 중복 가격 row", rows)

        rows = conn.execute("""
            WITH recent_registered_played AS (
                SELECT rp.id AS registered_player_id,
                       rp.name AS player_name,
                       rp.team,
                       rp.fantasy_position_type AS position_type,
                       MAX(fds.game_date) AS last_game_date,
                       COUNT(*) AS recent_games,
                       SUM(fds.points) AS recent_points
                FROM registered_players rp
                JOIN fantasy_daily_scores fds
                  ON fds.player_name = rp.name
                 AND fds.team = rp.team
                 AND fds.position_type = rp.fantasy_position_type
                WHERE fds.game_date BETWEEN date(?, '-6 day') AND ?
                GROUP BY rp.id, rp.name, rp.team, rp.fantasy_position_type
            )
            SELECT recent_registered_played.*
            FROM recent_registered_played
            LEFT JOIN player_prices pp
              ON pp.registered_player_id = recent_registered_played.registered_player_id
             AND pp.basis_source=?
             AND pp.basis_date=?
            WHERE pp.registered_player_id IS NULL
            ORDER BY recent_registered_played.last_game_date DESC, recent_registered_played.recent_points DESC
        """, (latest_game, latest_game, BASIS_SOURCE, latest_price)).fetchall()
        print_rows("6. 최근 7일 출전한 선수인데 최신 가격 row 없음", rows)

        rows = conn.execute("""
            SELECT fds.game_id, fds.game_date, fds.player_name, fds.team,
                   fds.position_type, fds.points, rp.id AS pitcher_registered_id
            FROM fantasy_daily_scores fds
            JOIN registered_players rp
              ON rp.name = fds.player_name
             AND rp.team = fds.team
             AND rp.fantasy_position_type = 'pitcher'
            WHERE fds.position_type = 'batter'
              AND fds.game_date BETWEEN date(?, '-6 day') AND ?
              AND fds.points = 100
              AND NOT EXISTS (
                  SELECT 1
                  FROM registered_players rp_batter
                  WHERE rp_batter.name = fds.player_name
                    AND rp_batter.team = fds.team
                    AND rp_batter.fantasy_position_type = 'batter'
              )
            ORDER BY fds.game_date DESC, fds.team, fds.player_name
        """, (latest_game, latest_game)).fetchall()
        print_rows("7. 최근 7일 phantom batter score row 후보", rows)

        rows = conn.execute("""
            SELECT fds.game_id, fds.game_date, fds.player_name, fds.team,
                   fds.position_type, fds.points, rp.id AS pitcher_registered_id
            FROM fantasy_daily_scores fds
            JOIN registered_players rp
              ON rp.name = fds.player_name
             AND rp.team = fds.team
             AND rp.fantasy_position_type = 'pitcher'
            WHERE fds.position_type = 'batter'
              AND fds.points = 100
              AND NOT EXISTS (
                  SELECT 1
                  FROM registered_players rp_batter
                  WHERE rp_batter.name = fds.player_name
                    AND rp_batter.team = fds.team
                    AND rp_batter.fantasy_position_type = 'batter'
              )
            ORDER BY fds.game_date DESC, fds.team, fds.player_name
        """).fetchall()
        print_rows("8. 전체 기간 phantom batter score row 후보", rows)

        print("\n" + "=" * 80)
        print("9. 팀 점수 계산 시장가 기준 source")
        print("=" * 80)
        print(read_team_score_basis_source())

        print("\n" + "=" * 80)
        print("10. KBO RegisterAll/Register.aspx 등·말소 transaction 저장 상태")
        print("=" * 80)
        try:
            trx_rows = conn.execute("""
                SELECT
                    source_date,
                    team,
                    transaction_type,
                    CASE
                        WHEN raw_section LIKE 'RegisterAll active diff:%' THEN 'RegisterAll active diff'
                        WHEN raw_section LIKE 'RegisterAll direct:%' THEN 'RegisterAll direct'
                        WHEN source_url LIKE '%Register.aspx%' THEN 'Register.aspx direct'
                        ELSE 'other'
                    END AS source_kind,
                    COUNT(*) AS cnt
                FROM player_register_transactions
                GROUP BY source_date, team, transaction_type, source_kind
                ORDER BY source_date DESC, team, transaction_type, source_kind
                LIMIT 80
            """).fetchall()
            print("count:", len(trx_rows))
            for row in trx_rows:
                print(dict(row))
        except Exception as e:
            print("player_register_transactions 확인 실패:", e)

        rows = conn.execute("""
            SELECT rp.id, rp.name, rp.team, rp.fantasy_position_type, rp.is_active,
                   rp.roster_position, rp.detail_position
            FROM registered_players rp
            LEFT JOIN player_prices pp
              ON pp.registered_player_id = rp.id
             AND pp.basis_source = ?
             AND pp.basis_date = ?
            WHERE pp.registered_player_id IS NULL
            ORDER BY rp.is_active DESC, rp.team, rp.name, rp.id
        """, (BASIS_SOURCE, latest_price)).fetchall()
        print_rows("11. 오류: 최신 market_daily_v3 가격 row가 없는 registered_players", rows)

        rows = conn.execute("""
            SELECT name, team, fantasy_position_type, COUNT(*) AS cnt,
                   GROUP_CONCAT(id) AS ids,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_cnt
            FROM registered_players
            GROUP BY name, team, fantasy_position_type
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC, team, name
        """).fetchall()
        print_rows("12. 정보: registered_players 이름+팀+구분 중복 row", rows)

        rows = conn.execute("""
            SELECT player_name, team, COUNT(DISTINCT fantasy_position_type) AS type_cnt,
                   GROUP_CONCAT(DISTINCT fantasy_position_type) AS types
            FROM player_prices
            WHERE basis_source = ?
              AND basis_date = ?
            GROUP BY player_name, team
            HAVING COUNT(DISTINCT fantasy_position_type) > 1
            ORDER BY team, player_name
        """, (BASIS_SOURCE, latest_price)).fetchall()
        print_rows("13. 정보: 이름+팀만으로 가격 fallback하면 위험한 선수", rows)

        rows = conn.execute("""
            SELECT id, name, team, roster_position, detail_position, fantasy_position_type
            FROM registered_players
            WHERE is_active = 1
              AND fantasy_position_type = 'batter'
              AND (detail_position IS NULL OR detail_position = '' OR detail_position = '미등록')
            ORDER BY team, name
        """).fetchall()
        print_rows("14. 정보: active 타자 중 상세 포지션 미보강 선수", rows)

        rows = conn.execute("""
            SELECT ft.id AS team_id, COALESCE(u.display_name, u.username) AS user_name,
                   ft.is_confirmed, ft.captain_registered_player_id,
                   COUNT(ftp.id) AS roster_count
            FROM fantasy_teams ft
            JOIN users u ON u.id = ft.user_id
            LEFT JOIN fantasy_team_players ftp ON ftp.team_id = ft.id
            GROUP BY ft.id
            HAVING ft.is_confirmed = 1
               AND COUNT(ftp.id) = 15
               AND ft.captain_registered_player_id IS NULL
            ORDER BY ft.id
        """).fetchall()
        print_rows("15. 정보: 확정 15인 팀 중 C 미지정 팀", rows)

        print("\n[판정 기준]")
        print("- 1번은 오류가 아니라 정보입니다. 현재 KBO 등록 명단에는 없지만 최근 출전 기록이 있는 선수 목록입니다.")
        print("- 현재 기준에서 1번 선수들은 등록 현황 날짜가 최신 경기 날짜와 같으면 말소 선수로 표시/가격 tracking 됩니다.")
        print("- 오류로 봐야 하는 핵심 항목은 2, 3, 4, 5, 6, 7, 8, 11번 count가 0인지입니다.")
        print("- 3, 4번 투수 역할 검사는 현재 정책인 '가장 최근 실제 등판 역할' 기준입니다.")
        print("- 10번은 참고/검증용입니다. RegisterAll direct가 전 구단 당일 등록/말소의 1차 기준입니다.")
        print("- Register.aspx direct가 일부 팀만 가능해도 active 여부와 전 구단 transaction은 RegisterAll 기준으로 보강됩니다.")


if __name__ == "__main__":
    main()
