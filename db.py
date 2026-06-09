"""
SQLite 데이터베이스 연결과 테이블 생성을 담당하는 파일입니다.

주의:
- 기존 kbo_fantasy.db 파일은 절대 삭제하지 않습니다.
- DROP TABLE을 사용하지 않습니다.
- CREATE TABLE IF NOT EXISTS를 사용합니다.
- 새 컬럼은 PRAGMA table_info 확인 후 ALTER TABLE ADD COLUMN으로만 추가합니다.
"""

import sqlite3
from contextlib import contextmanager
from config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_column_if_missing(cursor, table_name, column_name, column_sql):
    """
    SQLite에서 안전하게 컬럼을 추가하는 함수입니다.
    기존 테이블/데이터는 삭제하지 않습니다.
    """
    cursor.execute(f"PRAGMA table_info({table_name});")
    existing_columns = [row["name"] for row in cursor.fetchall()]

    if column_name not in existing_columns:
        cursor.execute(f"""
        ALTER TABLE {table_name}
        ADD COLUMN {column_sql};
        """)
        print(f"컬럼 추가 완료: {table_name}.{column_name}")
    else:
        print(f"이미 존재하는 컬럼: {table_name}.{column_name}")


def init_db():
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            team TEXT NOT NULL,
            position_type TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, team, position_type)
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS registered_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            name TEXT NOT NULL,
            team TEXT NOT NULL,
            team_id TEXT,
            roster_position TEXT NOT NULL,
            fantasy_position_type TEXT NOT NULL,
            back_no TEXT,
            throw_bat TEXT,
            birthdate TEXT,
            height_weight TEXT,
            profile_url TEXT,
            is_active INTEGER DEFAULT 1,
            source_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_id),
            UNIQUE(name, team, roster_position)
        );
        """)

        add_column_if_missing(
            c,
            "registered_players",
            "detail_position",
            "detail_position TEXT"
        )
        add_column_if_missing(
            c,
            "registered_players",
            "detail_position_source",
            "detail_position_source TEXT"
        )
        add_column_if_missing(
            c,
            "registered_players",
            "detail_position_updated_at",
            "detail_position_updated_at TEXT"
        )

        # KBO 구단별 Register.aspx의 당일 등/말소 현황을 보존하는 테이블입니다.
        # 이 테이블은 참고/검증용이며, active 여부의 최종 기준은 RegisterAll.aspx의 현재 등록 명단입니다.
        c.execute("""
        CREATE TABLE IF NOT EXISTS player_register_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_date TEXT NOT NULL,
            team TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            player_name TEXT NOT NULL,
            roster_position TEXT,
            back_no TEXT,
            throw_bat TEXT,
            birthdate TEXT,
            height_weight TEXT,
            source_url TEXT,
            raw_section TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_date, team, transaction_type, player_name, roster_position, back_no)
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date TEXT NOT NULL,
            game_id TEXT NOT NULL UNIQUE,
            away_team TEXT,
            home_team TEXT,
            stadium TEXT,
            status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS raw_batter_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            game_date TEXT NOT NULL,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            hits INTEGER DEFAULT 0,
            doubles INTEGER DEFAULT 0,
            triples INTEGER DEFAULT 0,
            home_runs INTEGER DEFAULT 0,
            rbi INTEGER DEFAULT 0,
            runs INTEGER DEFAULT 0,
            game_winning_hit INTEGER DEFAULT 0,
            double_play INTEGER DEFAULT 0,
            hit_by_pitch INTEGER DEFAULT 0,
            walks INTEGER DEFAULT 0,
            stolen_bases INTEGER DEFAULT 0,
            strikeouts INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(game_id, player_name, team)
        );
        """)

        add_column_if_missing(
            c,
            "raw_batter_stats",
            "hit_by_pitch",
            "hit_by_pitch INTEGER DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "raw_batter_stats",
            "walks",
            "walks INTEGER DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "raw_batter_stats",
            "stolen_bases",
            "stolen_bases INTEGER DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "raw_batter_stats",
            "strikeouts",
            "strikeouts INTEGER DEFAULT 0"
        )

        add_column_if_missing(
            c,
            "raw_batter_stats",
            "batting_order",
            "batting_order INTEGER"
        )
        add_column_if_missing(
            c,
            "raw_batter_stats",
            "starting_detail_position",
            "starting_detail_position TEXT"
        )
        add_column_if_missing(
            c,
            "raw_batter_stats",
            "is_starting_batter",
            "is_starting_batter INTEGER DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "raw_batter_stats",
            "lineup_position_source",
            "lineup_position_source TEXT"
        )

        c.execute("""
        CREATE TABLE IF NOT EXISTS raw_pitcher_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            game_date TEXT NOT NULL,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            holds INTEGER DEFAULT 0,
            innings_pitched_raw TEXT,
            completed_innings INTEGER DEFAULT 0,
            strikeouts INTEGER DEFAULT 0,
            runs_allowed INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            pitch_count INTEGER DEFAULT 0,
            hits_allowed INTEGER DEFAULT 0,
            is_starting_pitcher INTEGER DEFAULT 0,
            pitching_order INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(game_id, player_name, team)
        );
        """)

        add_column_if_missing(
            c,
            "raw_pitcher_stats",
            "is_starting_pitcher",
            "is_starting_pitcher INTEGER DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "raw_pitcher_stats",
            "pitching_order",
            "pitching_order INTEGER"
        )
        add_column_if_missing(
            c,
            "raw_pitcher_stats",
            "saves",
            "saves INTEGER DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "raw_pitcher_stats",
            "pitch_count",
            "pitch_count INTEGER DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "raw_pitcher_stats",
            "hits_allowed",
            "hits_allowed INTEGER DEFAULT 0"
        )

        c.execute("""
        CREATE TABLE IF NOT EXISTS fantasy_daily_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            game_date TEXT NOT NULL,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            position_type TEXT NOT NULL,
            points REAL DEFAULT 0,
            score_detail_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(game_id, player_name, position_type)
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS fantasy_player_totals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            position_type TEXT NOT NULL,
            total_points REAL DEFAULT 0,
            last_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_name, team, position_type)
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS external_player_rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_url TEXT,
            ranking_type TEXT NOT NULL,
            external_rank INTEGER,
            player_name TEXT NOT NULL,
            team TEXT,
            position_text TEXT,
            position_type TEXT NOT NULL,
            external_score REAL DEFAULT 0,
            raw_data_json TEXT,
            source_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_name, ranking_type, player_name, team, source_date)
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS external_player_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_url TEXT,
            position_code TEXT NOT NULL,
            detail_position TEXT NOT NULL,
            external_rank INTEGER,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL DEFAULT '',
            external_score REAL DEFAULT 0,
            raw_data_json TEXT,
            source_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_name, position_code, player_name, team, source_date)
        );
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS player_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registered_player_id INTEGER NOT NULL,
            player_id TEXT,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            roster_position TEXT,
            fantasy_position_type TEXT NOT NULL,
            external_score REAL DEFAULT 0,
            external_rank INTEGER,
            price_role TEXT NOT NULL,
            price_score REAL DEFAULT 0,
            tier TEXT NOT NULL,
            price INTEGER NOT NULL,
            price_decimal REAL,
            basis_source TEXT NOT NULL,
            basis_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(registered_player_id, basis_source, basis_date),
            FOREIGN KEY (registered_player_id)
                REFERENCES registered_players(id)
        );
        """)

        add_column_if_missing(
            c,
            "player_prices",
            "price_decimal",
            "price_decimal REAL"
        )

        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)

        add_column_if_missing(
            c,
            "users",
            "favorite_kbo_team",
            "favorite_kbo_team TEXT"
        )

        add_column_if_missing(
            c,
            "users",
            "is_admin",
            "is_admin INTEGER DEFAULT 0"
        )

        c.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            page_url TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            admin_note TEXT,
            admin_reply TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_tickets_user
        ON support_tickets(user_id, created_at DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_tickets_status
        ON support_tickets(status, created_at DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_tickets_category
        ON support_tickets(category, created_at DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_tickets_resolved_at
        ON support_tickets(status, resolved_at);
        """)

        # 친구 요청과 수락된 친구 관계를 저장합니다.
        # requester_id -> addressee_id 한 방향 row로 관리하되,
        # 애플리케이션 코드에서 역방향 중복 요청을 방지합니다.
        c.execute("""
        CREATE TABLE IF NOT EXISTS user_friendships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER NOT NULL,
            addressee_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            responded_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            CHECK(requester_id != addressee_id),
            UNIQUE(requester_id, addressee_id),
            FOREIGN KEY (requester_id)
                REFERENCES users(id),
            FOREIGN KEY (addressee_id)
                REFERENCES users(id)
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_friendships_requester
        ON user_friendships(requester_id, status);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_friendships_addressee
        ON user_friendships(addressee_id, status);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_friendships_status
        ON user_friendships(status);
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS fantasy_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            team_name TEXT NOT NULL,
            budget_limit INTEGER DEFAULT 100,
            cash_balance_decimal REAL DEFAULT 100.0,
            is_confirmed INTEGER DEFAULT 0,
            confirmed_at TEXT,
            confirmed_budget_used REAL,
            captain_registered_player_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id),
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );
        """)

        add_column_if_missing(
            c,
            "fantasy_teams",
            "cash_balance_decimal",
            "cash_balance_decimal REAL"
        )
        add_column_if_missing(
            c,
            "fantasy_teams",
            "is_confirmed",
            "is_confirmed INTEGER DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "fantasy_teams",
            "confirmed_at",
            "confirmed_at TEXT"
        )
        add_column_if_missing(
            c,
            "fantasy_teams",
            "confirmed_budget_used",
            "confirmed_budget_used REAL"
        )
        add_column_if_missing(
            c,
            "fantasy_teams",
            "captain_registered_player_id",
            "captain_registered_player_id INTEGER"
        )

        c.execute("""
        CREATE TABLE IF NOT EXISTS fantasy_team_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            registered_player_id INTEGER NOT NULL,
            slot TEXT NOT NULL,
            locked_price_decimal REAL,
            locked_price_basis_date TEXT,
            locked_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, slot),
            UNIQUE(team_id, registered_player_id),
            FOREIGN KEY (team_id)
                REFERENCES fantasy_teams(id),
            FOREIGN KEY (registered_player_id)
                REFERENCES registered_players(id)
        );
        """)

        add_column_if_missing(
            c,
            "fantasy_team_players",
            "locked_price_decimal",
            "locked_price_decimal REAL"
        )
        add_column_if_missing(
            c,
            "fantasy_team_players",
            "locked_price_basis_date",
            "locked_price_basis_date TEXT"
        )
        add_column_if_missing(
            c,
            "fantasy_team_players",
            "locked_at",
            "locked_at TEXT"
        )

        c.execute("""
        CREATE TABLE IF NOT EXISTS fantasy_team_trade_bonus_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            registered_player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            player_team TEXT,
            position_type TEXT,
            slot TEXT,
            locked_price_decimal REAL NOT NULL,
            current_market_price REAL NOT NULL,
            roster_market_value_before REAL NOT NULL DEFAULT 0,
            roster_excess_before_decimal REAL NOT NULL DEFAULT 0,
            budget_refund_decimal REAL NOT NULL,
            realized_profit_decimal REAL NOT NULL,
            profit_units INTEGER NOT NULL DEFAULT 0,
            bonus_points REAL NOT NULL DEFAULT 0,
            points_per_unit INTEGER NOT NULL DEFAULT 500,
            basis_source TEXT NOT NULL DEFAULT 'market_daily_v3',
            basis_date TEXT,
            event_date TEXT NOT NULL DEFAULT (date('now')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (team_id)
                REFERENCES fantasy_teams(id),
            FOREIGN KEY (registered_player_id)
                REFERENCES registered_players(id)
        );
        """)


        add_column_if_missing(
            c,
            "fantasy_team_trade_bonus_events",
            "roster_market_value_before",
            "roster_market_value_before REAL NOT NULL DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "fantasy_team_trade_bonus_events",
            "roster_excess_before_decimal",
            "roster_excess_before_decimal REAL NOT NULL DEFAULT 0"
        )

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_bonus_user_date
        ON fantasy_team_trade_bonus_events(user_id, event_date DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_bonus_team_date
        ON fantasy_team_trade_bonus_events(team_id, event_date DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_bonus_player
        ON fantasy_team_trade_bonus_events(registered_player_id, created_at DESC);
        """)

        # 기존 팀의 예산 현금 잔액을 1회 안전 초기화합니다.
        # 기존 영입가는 유지하고, 영입가가 없는 선수는 최신 시장가를 이미 사용한 비용으로 봅니다.
        # 이후 선수 영입/방출은 app.py에서 cash_balance_decimal을 누적 갱신합니다.
        latest_price_row = c.execute("""
            SELECT MAX(basis_date) AS latest_price_date
            FROM player_prices
            WHERE basis_source = 'market_daily_v3'
        """).fetchone()
        latest_price_date_for_cash = None
        if latest_price_row is not None:
            latest_price_date_for_cash = latest_price_row["latest_price_date"]

        teams_without_cash = c.execute("""
            SELECT id, COALESCE(budget_limit, 100) AS budget_limit
            FROM fantasy_teams
            WHERE cash_balance_decimal IS NULL
        """).fetchall()

        for team_row in teams_without_cash:
            team_id = team_row["id"]
            budget_limit = float(team_row["budget_limit"] or 100)

            invested_row = c.execute("""
                SELECT
                    COALESCE(SUM(COALESCE(ftp.locked_price_decimal, pp.price_decimal, pp.price, 0)), 0) AS invested_cost
                FROM fantasy_team_players ftp
                LEFT JOIN player_prices pp
                  ON pp.registered_player_id = ftp.registered_player_id
                 AND pp.basis_source = 'market_daily_v3'
                 AND pp.basis_date = ?
                WHERE ftp.team_id = ?
            """, (
                latest_price_date_for_cash,
                team_id,
            )).fetchone()

            invested_cost = 0.0
            if invested_row is not None:
                invested_cost = float(invested_row["invested_cost"] or 0)

            initial_cash = round(budget_limit - invested_cost, 1)
            if initial_cash < 0:
                initial_cash = 0.0
            if initial_cash > budget_limit:
                initial_cash = budget_limit

            c.execute("""
                UPDATE fantasy_teams
                SET cash_balance_decimal = ?
                WHERE id = ?
                  AND cash_balance_decimal IS NULL
            """, (initial_cash, team_id))

        # 최신 market_daily_v3 기준 가격 row가 없는 registered_players를 안전 보강합니다.
        # 원칙적으로 모든 registered_players는 최신 가격 row를 가져야 하며, 0.0 가격 fallback은 허용하지 않습니다.
        # 같은 이름+팀+타자/투수 구분의 가격이 있으면 그 가격을 복사하고, 정말 없으면 신규/말소 기본가를 부여합니다.
        if latest_price_date_for_cash:
            missing_price_players = c.execute("""
                SELECT
                    rp.id,
                    rp.player_id,
                    rp.name,
                    rp.team,
                    rp.roster_position,
                    rp.fantasy_position_type,
                    rp.detail_position
                FROM registered_players rp
                LEFT JOIN player_prices pp
                  ON pp.registered_player_id = rp.id
                 AND pp.basis_source = 'market_daily_v3'
                 AND pp.basis_date = ?
                WHERE pp.registered_player_id IS NULL
                ORDER BY rp.id
            """, (latest_price_date_for_cash,)).fetchall()

            for rp in missing_price_players:
                fallback = c.execute("""
                    SELECT
                        price_role,
                        tier,
                        price,
                        price_decimal,
                        external_score,
                        external_rank,
                        price_score
                    FROM player_prices
                    WHERE basis_source = 'market_daily_v3'
                      AND basis_date = ?
                      AND player_name = ?
                      AND team = ?
                      AND fantasy_position_type = ?
                      AND COALESCE(price_decimal, price) IS NOT NULL
                      AND COALESCE(price_decimal, price) > 0
                    ORDER BY id DESC
                    LIMIT 1
                """, (
                    latest_price_date_for_cash,
                    rp["name"],
                    rp["team"],
                    rp["fantasy_position_type"],
                )).fetchone()

                if fallback is not None:
                    price_role = fallback["price_role"]
                    tier = fallback["tier"] or "baseline"
                    price_decimal = round(float(fallback["price_decimal"] or fallback["price"] or 5.0), 1)
                    price_int = int(round(float(fallback["price"] or price_decimal)))
                    external_score = float(fallback["external_score"] or 0)
                    external_rank = fallback["external_rank"]
                    price_score = float(fallback["price_score"] or 0)
                else:
                    fantasy_type = rp["fantasy_position_type"]
                    detail_position = rp["detail_position"]
                    if fantasy_type == "pitcher" and detail_position == "선발투수":
                        price_role = "starting_pitcher"
                        price_decimal = 5.5
                    elif fantasy_type == "pitcher":
                        price_role = "bullpen_pitcher"
                        price_decimal = 5.0
                    else:
                        price_role = "batter"
                        price_decimal = 5.0
                    tier = "baseline"
                    price_int = int(round(price_decimal))
                    external_score = 0.0
                    external_rank = None
                    price_score = 0.0

                c.execute("""
                    INSERT OR IGNORE INTO player_prices (
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
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'market_daily_v3', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    rp["id"],
                    rp["player_id"],
                    rp["name"],
                    rp["team"],
                    rp["roster_position"],
                    rp["fantasy_position_type"],
                    external_score,
                    external_rank,
                    price_role,
                    price_score,
                    tier,
                    price_int,
                    price_decimal,
                    latest_price_date_for_cash,
                ))

        # 외부 포지션 정보가 있는데 detail_position이 비어 있는 active 타자는 안전하게 보강합니다.
        c.execute("""
            UPDATE registered_players
            SET
                detail_position = (
                    SELECT epp.detail_position
                    FROM external_player_positions epp
                    WHERE epp.player_name = registered_players.name
                      AND epp.team = registered_players.team
                      AND epp.detail_position IS NOT NULL
                      AND epp.detail_position <> ''
                    ORDER BY epp.source_date DESC, epp.id DESC
                    LIMIT 1
                ),
                detail_position_source = 'external_player_positions_safe_fill',
                detail_position_updated_at = CURRENT_TIMESTAMP
            WHERE is_active = 1
              AND fantasy_position_type = 'batter'
              AND (detail_position IS NULL OR detail_position = '' OR detail_position = '미등록')
              AND EXISTS (
                    SELECT 1
                    FROM external_player_positions epp
                    WHERE epp.player_name = registered_players.name
                      AND epp.team = registered_players.team
                      AND epp.detail_position IS NOT NULL
                      AND epp.detail_position <> ''
              )
        """)

        # 외부 상세 포지션에 없는 active 타자는 KBO 공식 등록 포지션으로 안전하게 fallback합니다.
        # 이 값은 세부 좌익수/중견수/우익수/1루수/2루수/3루수/유격수까지 확정하는 값이 아니라,
        # NULL/미등록 때문에 필터나 팀 편집 후보가 꼬이지 않도록 공식 등록 포지션(포수/내야수/외야수)을 보존하는 최소 보강입니다.
        c.execute("""
            UPDATE registered_players
            SET
                detail_position = roster_position,
                detail_position_source = 'fallback_roster_position',
                detail_position_updated_at = CURRENT_TIMESTAMP
            WHERE is_active = 1
              AND fantasy_position_type = 'batter'
              AND roster_position IN ('포수', '내야수', '외야수')
              AND (detail_position IS NULL OR detail_position = '' OR detail_position = '미등록')
        """)


        # 유저 팀별 경기일 점수 테이블입니다.
        # 확정된 팀만 경기일 점수를 얻으며,
        # 팀이 미확정인 날은 0점 row를 만들지 않고 기록 자체를 만들지 않습니다.
        c.execute("""
        CREATE TABLE IF NOT EXISTS fantasy_team_daily_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,

            -- 과거 기록 보존용 스냅샷입니다.
            -- 나중에 팀명이나 유저 표시명이 바뀌어도 당시 기록을 유지합니다.
            team_name_snapshot TEXT,
            user_display_name_snapshot TEXT,

            -- YYYY-MM-DD 형식입니다.
            game_date TEXT NOT NULL,

            -- 해당 경기일 팀 총점입니다.
            total_points REAL DEFAULT 0,

            -- 해당 경기일 저장된 로스터 선수 수입니다.
            roster_player_count INTEGER DEFAULT 0,

            -- 계산 당시 C 스냅샷입니다. C가 없던 기존 팀 기록은 NULL입니다.
            captain_registered_player_id_snapshot INTEGER,
            captain_player_name_snapshot TEXT,

            -- 계산 당시 팀 확정 상태입니다.
            -- 정상 기록은 1이어야 합니다.
            is_confirmed_snapshot INTEGER DEFAULT 1,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(team_id, game_date),

            FOREIGN KEY (team_id)
                REFERENCES fantasy_teams(id),

            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );
        """)

        add_column_if_missing(
            c,
            "fantasy_team_daily_scores",
            "captain_registered_player_id_snapshot",
            "captain_registered_player_id_snapshot INTEGER"
        )
        add_column_if_missing(
            c,
            "fantasy_team_daily_scores",
            "captain_player_name_snapshot",
            "captain_player_name_snapshot TEXT"
        )

        # 유저 팀별 경기일 선수 기여도 스냅샷 테이블입니다.
        # 팀을 나중에 수정해도 과거 경기일의 선수 구성과 점수는 이 테이블에 남습니다.
        c.execute("""
        CREATE TABLE IF NOT EXISTS fantasy_team_daily_player_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            team_daily_score_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,

            -- YYYY-MM-DD 형식입니다.
            game_date TEXT NOT NULL,

            registered_player_id INTEGER NOT NULL,

            -- 과거 기록 보존용 선수 스냅샷입니다.
            player_name TEXT NOT NULL,
            player_team TEXT NOT NULL,
            slot TEXT NOT NULL,
            position_type TEXT NOT NULL,

            -- 슬롯/포지션 자격 스냅샷입니다.
            -- 선수가 이후 포지션 변경으로 슬롯과 맞지 않으면 해당 선수만 0점 처리합니다.
            slot_expected_position_type TEXT,
            slot_expected_detail_position TEXT,
            player_detail_position_snapshot TEXT,
            is_position_eligible INTEGER DEFAULT 1,
            position_mismatch_reason TEXT,

            -- 해당 경기일 선수 점수입니다. points는 C 보너스 적용 후 팀 기여도입니다.
            points REAL DEFAULT 0,

            -- C 보너스 계산 근거입니다. 기존 기록은 NULL일 수 있습니다.
            base_points REAL,
            captain_multiplier REAL DEFAULT 1.0,
            is_captain INTEGER DEFAULT 0,

            -- 계산 당시 팀에 적용된 고정가입니다.
            locked_price_decimal REAL,

            -- 계산 당시 최신 시장가입니다.
            current_market_price REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(team_daily_score_id, registered_player_id),
            UNIQUE(team_id, game_date, registered_player_id),

            FOREIGN KEY (team_daily_score_id)
                REFERENCES fantasy_team_daily_scores(id),

            FOREIGN KEY (team_id)
                REFERENCES fantasy_teams(id),

            FOREIGN KEY (user_id)
                REFERENCES users(id),

            FOREIGN KEY (registered_player_id)
                REFERENCES registered_players(id)
        );
        """)

        add_column_if_missing(
            c,
            "fantasy_team_daily_player_scores",
            "base_points",
            "base_points REAL"
        )
        add_column_if_missing(
            c,
            "fantasy_team_daily_player_scores",
            "captain_multiplier",
            "captain_multiplier REAL DEFAULT 1.0"
        )
        add_column_if_missing(
            c,
            "fantasy_team_daily_player_scores",
            "is_captain",
            "is_captain INTEGER DEFAULT 0"
        )
        add_column_if_missing(
            c,
            "fantasy_team_daily_player_scores",
            "slot_expected_position_type",
            "slot_expected_position_type TEXT"
        )
        add_column_if_missing(
            c,
            "fantasy_team_daily_player_scores",
            "slot_expected_detail_position",
            "slot_expected_detail_position TEXT"
        )
        add_column_if_missing(
            c,
            "fantasy_team_daily_player_scores",
            "player_detail_position_snapshot",
            "player_detail_position_snapshot TEXT"
        )
        add_column_if_missing(
            c,
            "fantasy_team_daily_player_scores",
            "is_position_eligible",
            "is_position_eligible INTEGER DEFAULT 1"
        )
        add_column_if_missing(
            c,
            "fantasy_team_daily_player_scores",
            "position_mismatch_reason",
            "position_mismatch_reason TEXT"
        )

        # 가격 변동 실행 로그 테이블입니다.
        # 가격 업데이트가 언제, 어떤 기준 날짜로, 어떤 상태로 실행됐는지 기록합니다.
        # 실제 가격을 바꾸기 전 dry-run 기록과 실제 적용 실행 기록을 구분할 수 있게 합니다.
        c.execute("""
        CREATE TABLE IF NOT EXISTS price_update_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- 가격 기준 출처입니다.
            -- 예: welcometopranking
            basis_source TEXT NOT NULL,

            -- 가격 변동 기준 날짜입니다.
            -- 예: 2026-05-10
            basis_date TEXT NOT NULL,

            -- 성적 계산 기준 시작일입니다.
            basis_start_date TEXT,

            -- 성적 계산 기준 종료일입니다.
            basis_end_date TEXT,

            -- fantasy_daily_scores 기준 최신 경기 날짜입니다.
            latest_game_date TEXT,

            -- 실행 모드입니다.
            -- dry_run 또는 apply 같은 값을 저장할 예정입니다.
            run_mode TEXT NOT NULL DEFAULT 'dry_run',

            -- 실행 상태입니다.
            -- started, success, failed 같은 값을 저장할 예정입니다.
            status TEXT NOT NULL DEFAULT 'started',

            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,

            -- 실행 결과 메시지 또는 에러 메시지입니다.
            message TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 선수별 가격 변동 상태 테이블입니다.
        # 미출전 패널티 누적값과 선발투수 성적 중복 반영 방지 정보를 저장합니다.
        c.execute("""
        CREATE TABLE IF NOT EXISTS player_price_states (
            registered_player_id INTEGER PRIMARY KEY,

            -- 미출전 패널티 누적값입니다.
            -- 예: -0.2, -0.4, 0.0
            absence_penalty_total REAL DEFAULT 0,

            -- 선발투수 성적 변동을 같은 경기로 반복 적용하지 않기 위한 마지막 적용 경기 ID입니다.
            last_performance_applied_game_id TEXT,

            -- 마지막으로 성적 기반 가격 변동을 적용한 날짜입니다.
            last_performance_applied_date TEXT,

            -- 마지막으로 가격 업데이트를 확인/실행한 날짜입니다.
            last_price_update_date TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (registered_player_id)
                REFERENCES registered_players(id)
        );
        """)

        # 선수별 가격 변동 상세 기록 테이블입니다.
        # 어떤 선수의 가격이 왜, 얼마에서 얼마로 바뀌었는지 history로 저장합니다.
        c.execute("""
        CREATE TABLE IF NOT EXISTS player_price_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- price_update_runs 테이블의 실행 ID입니다.
            run_id INTEGER,

            -- registered_players 테이블의 id입니다.
            registered_player_id INTEGER NOT NULL,

            player_name TEXT NOT NULL,
            team TEXT NOT NULL,

            -- 가격 계산 역할입니다.
            -- batter, starting_pitcher, bullpen_pitcher 같은 값을 사용할 예정입니다.
            price_role TEXT NOT NULL,

            basis_source TEXT NOT NULL,
            basis_date TEXT NOT NULL,
            basis_start_date TEXT,
            basis_end_date TEXT,

            old_price_decimal REAL NOT NULL,

            -- 성적 기반 변동값입니다.
            performance_change REAL DEFAULT 0,

            -- 이번 실행에서 새로 발생한 미출전 패널티/회복 변동값입니다.
            absence_penalty_change REAL DEFAULT 0,

            -- 이번 실행 후 누적 미출전 패널티 총합입니다.
            absence_penalty_total REAL DEFAULT 0,

            new_price_decimal REAL NOT NULL,

            -- 실제 player_prices에 반영됐는지 여부입니다.
            -- dry-run이면 0, 실제 적용이면 1로 사용할 예정입니다.
            is_applied INTEGER DEFAULT 0,

            -- 화면이나 로그에 보여줄 요약 이유입니다.
            reason TEXT,

            -- 성적 기반 변동 상세 이유 JSON입니다.
            performance_reason_json TEXT,

            -- 미출전 패널티 상세 이유 JSON입니다.
            absence_reason_json TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (run_id)
                REFERENCES price_update_runs(id),

            FOREIGN KEY (registered_player_id)
                REFERENCES registered_players(id)
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_date
        ON fantasy_daily_scores(game_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_player
        ON fantasy_daily_scores(player_name, team);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_totals_points
        ON fantasy_player_totals(total_points DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_registered_players_name
        ON registered_players(name);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_registered_players_team
        ON registered_players(team);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_registered_players_position
        ON registered_players(roster_position, fantasy_position_type);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_registered_players_detail_position
        ON registered_players(detail_position);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_external_rankings_lookup
        ON external_player_rankings(
            source_name,
            source_date,
            ranking_type,
            player_name,
            team
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_external_rankings_score
        ON external_player_rankings(ranking_type, external_score DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_external_rankings_date
        ON external_player_rankings(source_name, source_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_external_positions_lookup
        ON external_player_positions(
            source_name,
            source_date,
            player_name,
            team
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_external_positions_detail
        ON external_player_positions(detail_position);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_external_positions_source_detail
        ON external_player_positions(source_name, source_date, detail_position);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_player_prices_registered
        ON player_prices(registered_player_id);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_player_prices_tier_price
        ON player_prices(tier, price DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_player_prices_role
        ON player_prices(price_role);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_player_prices_basis
        ON player_prices(basis_source, basis_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_username
        ON users(username);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_fantasy_teams_user
        ON fantasy_teams(user_id);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_fantasy_team_players_team
        ON fantasy_team_players(team_id);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_fantasy_team_players_registered
        ON fantasy_team_players(registered_player_id);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_fantasy_team_players_slot
        ON fantasy_team_players(team_id, slot);
        """)

        # 팀 일별 점수 조회용 인덱스입니다.
        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_daily_scores_team_date
        ON fantasy_team_daily_scores(team_id, game_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_daily_scores_user_date
        ON fantasy_team_daily_scores(user_id, game_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_daily_scores_date_points
        ON fantasy_team_daily_scores(game_date, total_points DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_daily_scores_total_points
        ON fantasy_team_daily_scores(total_points DESC);
        """)

        # 팀 일별 선수 기여도 조회용 인덱스입니다.
        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_daily_player_scores_daily
        ON fantasy_team_daily_player_scores(team_daily_score_id);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_daily_player_scores_team_date
        ON fantasy_team_daily_player_scores(team_id, game_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_daily_player_scores_player
        ON fantasy_team_daily_player_scores(registered_player_id, game_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_daily_player_scores_user_date
        ON fantasy_team_daily_player_scores(user_id, game_date);
        """)

        # 가격 변동 실행 로그 조회용 인덱스입니다.
        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_update_runs_basis
        ON price_update_runs(basis_source, basis_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_update_runs_status
        ON price_update_runs(status, run_mode);
        """)

        # 선수별 가격 상태 조회용 인덱스입니다.
        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_player_price_states_updated
        ON player_price_states(last_price_update_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_player_register_transactions_date_team
        ON player_register_transactions(source_date, team, transaction_type);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_player_register_transactions_player
        ON player_register_transactions(player_name, team, source_date);
        """)

        # 가격 변동 기록 조회용 인덱스입니다.
        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_adjustments_run
        ON player_price_adjustments(run_id);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_adjustments_player
        ON player_price_adjustments(registered_player_id, basis_date);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_adjustments_basis
        ON player_price_adjustments(basis_source, basis_date, is_applied);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_adjustments_latest_lookup
        ON player_price_adjustments(
            basis_source,
            is_applied,
            registered_player_id,
            id DESC
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_scores_latest_lookup
        ON fantasy_daily_scores(
            game_date,
            player_name,
            team,
            position_type
        );
        """)


        # 배팅 기능 전용 테이블입니다. 기존 판타지/가격/선수 데이터와 분리합니다.
        c.execute("""
        CREATE TABLE IF NOT EXISTS betting_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date TEXT NOT NULL,
            scheduled_start_at TEXT NOT NULL,
            betting_closes_at TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_team TEXT NOT NULL,
            venue TEXT,
            kbo_game_id TEXT,
            game_no TEXT DEFAULT '0',
            status TEXT NOT NULL DEFAULT 'scheduled',
            away_score INTEGER,
            home_score INTEGER,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(game_date, away_team, home_team, scheduled_start_at)
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_betting_games_date_status
        ON betting_games(game_date, status, scheduled_start_at);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_betting_games_kbo_game_id
        ON betting_games(kbo_game_id);
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS betting_markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            betting_game_id INTEGER NOT NULL,
            market_type TEXT NOT NULL,
            line_value REAL NOT NULL DEFAULT 0,
            period TEXT NOT NULL DEFAULT 'full_game',
            status TEXT NOT NULL DEFAULT 'open',
            settlement_key TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(betting_game_id, market_type, line_value, period),
            FOREIGN KEY (betting_game_id) REFERENCES betting_games(id)
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_betting_markets_game
        ON betting_markets(betting_game_id, status);
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS betting_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id INTEGER NOT NULL,
            selection_key TEXT NOT NULL,
            label TEXT NOT NULL,
            odds_decimal REAL NOT NULL,
            display_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(market_id, selection_key),
            FOREIGN KEY (market_id) REFERENCES betting_markets(id)
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_betting_selections_market
        ON betting_selections(market_id, is_active, display_order);
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS betting_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            betting_game_id INTEGER NOT NULL,
            market_id INTEGER NOT NULL,
            selection_id INTEGER NOT NULL,
            stake_points REAL NOT NULL,
            odds_at_bet REAL NOT NULL,
            potential_payout REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            placed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            settled_at TEXT,
            payout_points REAL DEFAULT 0,
            profit_points REAL DEFAULT 0,
            result_key TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, market_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (betting_game_id) REFERENCES betting_games(id),
            FOREIGN KEY (market_id) REFERENCES betting_markets(id),
            FOREIGN KEY (selection_id) REFERENCES betting_selections(id)
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_betting_bets_user
        ON betting_bets(user_id, placed_at DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_betting_bets_status
        ON betting_bets(status, betting_game_id);
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS betting_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bet_id INTEGER,
            event_type TEXT NOT NULL,
            amount_points REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            note TEXT,
            UNIQUE(bet_id, event_type),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (bet_id) REFERENCES betting_bets(id)
        );
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_betting_ledger_user_date
        ON betting_ledger(user_id, created_at DESC);
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_betting_ledger_event
        ON betting_ledger(event_type, created_at DESC);
        """)

    print("DB 초기화 완료")
    print(f"DB 파일 위치: {DB_PATH}")


if __name__ == "__main__":
    init_db()