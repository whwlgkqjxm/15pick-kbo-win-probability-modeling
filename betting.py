"""MyPick 배팅 기능 전용 helper입니다.

원칙:
- 기존 KBO/판타지/가격 데이터는 삭제하거나 재생성하지 않습니다.
- 배팅은 별도 betting_* 테이블에만 저장합니다.
- 유저 총 재산 반영은 betting_ledger 합산으로 처리합니다.
- 정산은 pending bet만 처리해 여러 번 실행해도 중복 지급되지 않게 합니다.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from db import get_conn
from scraper import (
    KBO_TEAM_CODE_TO_NAME,
    clean_html_text,
    convert_yyyymmdd_to_dash,
    fetch_schedule_list,
    fetch_schedule_page_html,
    get_games_for_date,
    normalize_date_to_yyyymmdd,
    parse_score_from_schedule_text,
    resolve_team_code,
)

KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")
BETTING_MARKET_VERSION = "mypick_betting_v1"
BETTING_MIN_STAKE = 100
BETTING_MAX_STAKE_PER_MARKET = 100_000  # MYPICK BETTING POLICY V1 2026-06-06
BETTING_STAKE_UNIT = 100
BETTING_LOOKAHEAD_DAYS = 21
BETTING_VISIBLE_GAME_DATES = 2
DEFAULT_TOTAL_RUNS_LINE = 8.5
DEFAULT_GAME_TIME = "18:30"

TEAM_NAME_BY_CODE = dict(KBO_TEAM_CODE_TO_NAME)
TEAM_NAMES = list(dict.fromkeys(TEAM_NAME_BY_CODE.values()))

STATUS_LABELS = {
    "pending": "Pending",
    "won": "Won",
    "lost": "Lost",
    "void": "Void",
    "rejected": "Rejected",
}

GAME_STATUS_LABELS = {
    "scheduled": "배팅 가능",
    "locked": "마감",
    "in_progress": "진행중",
    "final": "종료",
    "cancelled": "취소",
    "postponed": "연기",
    "void": "무효",
}

MARKET_TITLES = {
    "moneyline_3way": "승부 예측",
    "win_margin": "점수차",
    "total_runs": "총 득점",
}

MARKET_SUBTITLES = {
    "moneyline_3way": "정규 경기 최종 결과",
    "win_margin": "무승부 시 환불",
    "total_runs": "양 팀 최종 점수 합산",
}


def now_korea() -> datetime:
    return datetime.now(KOREA_TIMEZONE).replace(tzinfo=None)


def normalize_date_dash(value) -> str | None:
    raw = normalize_date_to_yyyymmdd(value)
    if len(raw) != 8 or not raw.isdigit():
        return None
    return convert_yyyymmdd_to_dash(raw)


def parse_db_datetime(value) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("T", " ")
    parse_attempts = [
        (text[:19], "%Y-%m-%d %H:%M:%S"),
        (text[:16], "%Y-%m-%d %H:%M"),
        (text[:10], "%Y-%m-%d"),
    ]
    for candidate, fmt in parse_attempts:
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None




def should_treat_schedule_row_as_final(target_date_dash: str, game_time: str, row_text: str) -> bool:
    """일정 동기화 단계에서는 경기 결과를 함부로 확정하지 않습니다.

    KBO Schedule 응답은 가끔 이미 끝난 경기처럼 점수/종료 텍스트가 섞여 들어올 수 있습니다.
    배팅용 일정 생성은 "앞으로 열릴 경기"를 만드는 단계이므로, 최종 결과 반영은
    settle_betting.py/update_betting_results_for_date 쪽에서만 처리합니다.
    """
    return False


def normalize_schedule_game_payload(game: dict) -> dict:
    """공식 일정에서 만든 배팅 경기 payload를 안전한 scheduled 상태로 보정합니다."""
    status = str(game.get("status") or "scheduled")
    # 취소/연기는 공식 일정에 사전 표시될 수 있으므로 유지한다.
    if status not in {"cancelled", "postponed"}:
        game["status"] = "scheduled"
        game["away_score"] = None
        game["home_score"] = None
    return game

def format_datetime_display(value) -> str:
    dt = parse_db_datetime(value)
    if dt is None:
        return "" if value is None else str(value)
    return f"{dt.month}월 {dt.day}일 {dt.hour:02d}:{dt.minute:02d}"


def format_date_display(value) -> str:
    dt = parse_db_datetime(value)
    if dt is None:
        raw = normalize_date_dash(value)
        if raw:
            year, month, day = raw.split("-")
            return f"{int(month)}월 {int(day)}일"
        return "" if value is None else str(value)
    return f"{dt.month}월 {dt.day}일"


def safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def ensure_betting_tables(conn=None):
    """betting_* 테이블을 안전하게 생성합니다."""
    owns_connection = conn is None
    if owns_connection:
        context = get_conn()
        conn = context.__enter__()
    else:
        context = None

    try:
        conn.execute("""
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_betting_games_date_status
            ON betting_games(game_date, status, scheduled_start_at);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_betting_games_kbo_game_id
            ON betting_games(kbo_game_id);
        """)

        conn.execute("""
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_betting_markets_game
            ON betting_markets(betting_game_id, status);
        """)

        conn.execute("""
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_betting_selections_market
            ON betting_selections(market_id, is_active, display_order);
        """)

        conn.execute("""
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_betting_bets_user
            ON betting_bets(user_id, placed_at DESC);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_betting_bets_status
            ON betting_bets(status, betting_game_id);
        """)

        conn.execute("""
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_betting_ledger_user_date
            ON betting_ledger(user_id, created_at DESC);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_betting_ledger_event
            ON betting_ledger(event_type, created_at DESC);
        """)
    finally:
        if owns_connection:
            context.__exit__(None, None, None)


def get_betting_ledger_sum(conn, user_id, month_value=None, date_value=None) -> float:
    ensure_betting_tables(conn)
    params = [user_id]
    where_sql = "WHERE user_id = ?"
    if month_value:
        where_sql += " AND substr(created_at, 1, 7) = ?"
        params.append(month_value)
    if date_value:
        where_sql += " AND date(created_at) = ?"
        params.append(date_value)
    row = conn.execute(f"""
        SELECT COALESCE(SUM(amount_points), 0) AS amount
        FROM betting_ledger
        {where_sql}
    """, params).fetchone()
    return round(float(row["amount"] if row else 0), 1)


def normalize_team_name(value) -> str | None:
    text = clean_html_text(value).strip()
    if not text:
        return None
    code = resolve_team_code(text)
    if code in TEAM_NAME_BY_CODE:
        return TEAM_NAME_BY_CODE[code]
    for team in TEAM_NAMES:
        if text == team:
            return team
    return None


def extract_time_from_text(text: str) -> str | None:
    match = re.search(r"\b([01]?\d|2[0-3])[:：]([0-5]\d)\b", clean_html_text(text))
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def extract_teams_from_html(html_text) -> list[str]:
    soup = BeautifulSoup(str(html_text or ""), "html.parser")
    candidates = []
    for node in soup.find_all(["span", "strong", "em", "b", "td", "div", "a"]):
        text = node.get_text(" ", strip=True)
        if text:
            candidates.append(text)
    text = soup.get_text(" ", strip=True)
    if text:
        candidates.append(text)

    teams = []
    for candidate in candidates:
        normalized = normalize_team_name(candidate)
        if normalized and (not teams or teams[-1] != normalized):
            teams.append(normalized)
            continue
        for team in TEAM_NAMES:
            if re.search(rf"(?<![가-힣A-Za-z0-9]){re.escape(team)}(?![가-힣A-Za-z0-9])", candidate):
                if not teams or teams[-1] != team:
                    teams.append(team)
    deduped = []
    for team in teams:
        if team not in deduped:
            deduped.append(team)
    return deduped


def extract_teams_from_cells(cells) -> tuple[str | None, str | None]:
    play_cells = []
    other_cells = []
    for cell in cells or []:
        cell_class = str(cell.get("Class", "")) if isinstance(cell, dict) else ""
        html_text = cell.get("Text", "") if isinstance(cell, dict) else str(cell)
        if "play" in cell_class:
            play_cells.append(html_text)
        else:
            other_cells.append(html_text)

    for html_text in play_cells + other_cells:
        teams = extract_teams_from_html(html_text)
        if len(teams) >= 2:
            return teams[0], teams[-1]

    row_text = " ".join(clean_html_text(cell.get("Text", "")) for cell in cells or [] if isinstance(cell, dict))
    found = []
    for team in TEAM_NAMES:
        for match in re.finditer(rf"(?<![가-힣A-Za-z0-9]){re.escape(team)}(?![가-힣A-Za-z0-9])", row_text):
            found.append((match.start(), team))
    found.sort()
    teams = []
    for _, team in found:
        if team not in teams:
            teams.append(team)
    if len(teams) >= 2:
        return teams[0], teams[-1]
    return None, None


def extract_game_id_from_text(text: str) -> str | None:
    match = re.search(r"gameId=([0-9]{8}[A-Z]{4}\d)", str(text or ""))
    if match:
        return match.group(1)
    match = re.search(r"\b([0-9]{8}[A-Z]{4}\d)\b", str(text or ""))
    if match:
        return match.group(1)
    return None


def extract_game_date_from_text(text: str, fallback_year: str | None = None) -> str | None:
    """KBO 일정 row에서 날짜를 YYYYMMDD로 추출합니다.

    월간 일정 HTML/JSON은 첫 경기 row에만 `05.22(금)`처럼 날짜가 있고,
    같은 날짜의 나머지 경기 row는 날짜 칸이 비어 있을 수 있습니다.
    따라서 parser는 이 값을 current_date로 기억해서 다음 row들에 적용합니다.
    """
    raw = clean_html_text(text)
    if not raw:
        return None

    # gameDate=20260522, ?gameDate=20260522 형태가 가장 신뢰도 높다.
    match = re.search(r"gameDate=([0-9]{8})", raw, re.IGNORECASE)
    if match:
        return match.group(1)

    # 2026.05.22 / 2026-05-22 / 2026/05/22
    match = re.search(r"\b(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", raw)
    if match:
        return f"{int(match.group(1)):04d}{int(match.group(2)):02d}{int(match.group(3)):02d}"

    # 05.22(금), 5/22, 5-22 같은 월간 일정 날짜 칸
    # 시간 18:30과 헷갈리지 않게 ':'는 제외한다.
    match = re.search(r"(?<!\d)(\d{1,2})[.\-/](\d{1,2})(?!\d)", raw)
    if match and fallback_year:
        month = int(match.group(1))
        day = int(match.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{int(fallback_year):04d}{month:02d}{day:02d}"

    # 5월 22일
    match = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", raw)
    if match and fallback_year:
        month = int(match.group(1))
        day = int(match.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{int(fallback_year):04d}{month:02d}{day:02d}"

    return None


def extract_game_date_from_cells(cells, fallback_year: str | None = None) -> str | None:
    """KBO JSON cells에서 해당 row의 날짜를 추출합니다."""
    texts = []
    for cell in cells or []:
        if not isinstance(cell, dict):
            texts.append(str(cell))
            continue
        # Text 안에 링크와 날짜가 모두 있을 수 있으므로 HTML 문자열 그대로도 본다.
        texts.append(str(cell.get("Text", "")))
        texts.append(clean_html_text(cell.get("Text", "")))
    for text in texts:
        found = extract_game_date_from_text(text, fallback_year)
        if found:
            return found
    return None


def extract_schedule_link_info(text: str) -> tuple[str | None, str | None]:
    """Preview/Review 링크에서 gameDate/gameId를 동시에 추출합니다."""
    raw = str(text or "")
    date_match = re.search(r"gameDate=([0-9]{8})", raw, re.IGNORECASE)
    id_match = re.search(r"gameId=([0-9]{8}[A-Z]{4}\d)", raw, re.IGNORECASE)
    return (date_match.group(1) if date_match else None, id_match.group(1) if id_match else None)


def teams_from_game_id(game_id: str | None, expected_date_raw: str | None = None) -> tuple[str | None, str | None]:
    """KBO game_id에서 원정/홈 팀을 신뢰도 높게 복원합니다.

    예: 20260522WOLG0 -> 키움 원정, LG 홈
    """
    game_id = str(game_id or "").strip()
    if len(game_id) < 13:
        return None, None
    if expected_date_raw and game_id[:8] != normalize_date_to_yyyymmdd(expected_date_raw):
        return None, None
    away_code = game_id[8:10]
    home_code = game_id[10:12]
    away_team = TEAM_NAME_BY_CODE.get(away_code)
    home_team = TEAM_NAME_BY_CODE.get(home_code)
    if not away_team or not home_team or away_team == home_team:
        return None, None
    return away_team, home_team


def row_effective_date(row_html: str, row_text: str, cells, current_date_raw: str | None, target_year: str) -> tuple[str | None, str | None, str | None]:
    """월간 일정 row가 어느 날짜에 속하는지 계산합니다.

    반환값: (effective_date_raw, new_current_date_raw, link_game_id)
    """
    link_date_raw, link_game_id = extract_schedule_link_info(row_html)
    cell_date_raw = extract_game_date_from_cells(cells, target_year)
    text_date_raw = extract_game_date_from_text(row_text, target_year)
    explicit_date_raw = link_date_raw or cell_date_raw or text_date_raw
    new_current = explicit_date_raw or current_date_raw
    effective = explicit_date_raw or current_date_raw
    return effective, new_current, link_game_id


def build_game_id(target_date_raw: str, away_team: str, home_team: str) -> str | None:
    away_code = resolve_team_code(away_team)
    home_code = resolve_team_code(home_team)
    if not away_code or not home_code or away_code == home_code:
        return None
    return f"{target_date_raw}{away_code}{home_code}0"


def parse_schedule_api_games_for_betting(schedule_json, target_date) -> list[dict]:
    """KBO 월간 Schedule API 응답에서 target_date의 경기만 정확히 추출합니다.

    중요:
    - 월간 응답 전체 row를 모두 훑기 때문에 날짜 필터가 반드시 필요합니다.
    - 날짜 칸은 같은 날 첫 row에만 있고 나머지 row는 비어 있을 수 있어 current_date를 유지합니다.
    - Preview/Review 링크의 gameId가 있으면 팀명은 gameId에서 우선 복원합니다.
    - 일정 동기화 단계에서는 점수/종료 상태를 확정하지 않습니다.
    """
    target_date_raw = normalize_date_to_yyyymmdd(target_date)
    target_date_dash = convert_yyyymmdd_to_dash(target_date_raw)
    target_year = target_date_raw[:4]
    games = []
    seen = set()
    current_date_raw = None

    for item in (schedule_json or {}).get("rows", []):
        cells = item.get("row", []) if isinstance(item, dict) else []
        if not cells:
            continue

        row_html = " ".join(str(cell.get("Text", "")) for cell in cells if isinstance(cell, dict))
        row_text = clean_html_text(row_html)
        effective_date_raw, current_date_raw, link_game_id = row_effective_date(
            row_html, row_text, cells, current_date_raw, target_year
        )
        if effective_date_raw != target_date_raw:
            continue

        game_id = link_game_id or extract_game_id_from_text(row_html)
        away_team, home_team = teams_from_game_id(game_id, target_date_raw)
        if not away_team or not home_team:
            away_team, home_team = extract_teams_from_cells(cells)
        if not away_team or not home_team or away_team == home_team:
            continue

        game_time = None
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            game_time = extract_time_from_text(cell.get("Text", ""))
            if game_time:
                break
        if not game_time:
            game_time = extract_time_from_text(row_text) or DEFAULT_GAME_TIME

        if not game_id:
            game_id = build_game_id(target_date_raw, away_team, home_team)
        if not game_id:
            continue

        venue = ""
        for cell in reversed(cells):
            if not isinstance(cell, dict):
                continue
            text = clean_html_text(cell.get("Text", ""))
            if text in ["잠실", "고척", "문학", "수원", "대전", "대구", "광주", "사직", "창원", "울산", "포항", "청주", "군산", "마산", "목동"]:
                venue = text
                break
        if not venue:
            for stadium in ["잠실", "고척", "문학", "수원", "대전", "대구", "광주", "사직", "창원", "울산", "포항", "청주", "군산", "마산", "목동"]:
                if stadium in row_text:
                    venue = stadium
                    break

        status = "scheduled"
        if "취소" in row_text:
            status = "cancelled"
        elif "연기" in row_text:
            status = "postponed"

        key = (target_date_dash, away_team, home_team, game_time)
        if key in seen:
            continue
        seen.add(key)

        games.append(normalize_schedule_game_payload({
            "game_date": target_date_dash,
            "scheduled_start_at": f"{target_date_dash} {game_time}:00",
            "betting_closes_at": f"{target_date_dash} {game_time}:00",
            "away_team": away_team,
            "home_team": home_team,
            "venue": venue,
            "kbo_game_id": game_id,
            "game_no": game_id[-1:] if game_id else "0",
            "status": status,
            "away_score": None,
            "home_score": None,
            "source": "schedule_api",
        }))

    return games


def parse_schedule_html_games_for_betting(html_text, target_date) -> list[dict]:
    """KBO 월간 Schedule HTML에서 target_date의 경기만 정확히 추출합니다."""
    if not html_text:
        return []
    target_date_raw = normalize_date_to_yyyymmdd(target_date)
    target_date_dash = convert_yyyymmdd_to_dash(target_date_raw)
    target_year = target_date_raw[:4]
    soup = BeautifulSoup(html_text, "html.parser")
    games = []
    seen = set()
    current_date_raw = None

    for tr in soup.find_all("tr"):
        row_html = str(tr)
        row_text = tr.get_text(" ", strip=True)
        if not row_text:
            continue

        effective_date_raw, current_date_raw, link_game_id = row_effective_date(
            row_html, row_text, None, current_date_raw, target_year
        )
        if effective_date_raw != target_date_raw:
            continue

        game_id = link_game_id or extract_game_id_from_text(row_html)
        away_team, home_team = teams_from_game_id(game_id, target_date_raw)
        if not away_team or not home_team:
            teams = extract_teams_from_html(row_html)
            if len(teams) >= 2:
                away_team, home_team = teams[0], teams[-1]
        if not away_team or not home_team or away_team == home_team:
            continue

        game_time = extract_time_from_text(row_text) or DEFAULT_GAME_TIME
        if not game_id:
            game_id = build_game_id(target_date_raw, away_team, home_team)
        if not game_id:
            continue

        venue = ""
        for stadium in ["잠실", "고척", "문학", "수원", "대전", "대구", "광주", "사직", "창원", "울산", "포항", "청주", "군산", "마산", "목동"]:
            if stadium in row_text:
                venue = stadium
                break
        status = "scheduled"
        if "취소" in row_text:
            status = "cancelled"
        elif "연기" in row_text:
            status = "postponed"

        key = (target_date_dash, away_team, home_team, game_time)
        if key in seen:
            continue
        seen.add(key)
        games.append(normalize_schedule_game_payload({
            "game_date": target_date_dash,
            "scheduled_start_at": f"{target_date_dash} {game_time}:00",
            "betting_closes_at": f"{target_date_dash} {game_time}:00",
            "away_team": away_team,
            "home_team": home_team,
            "venue": venue,
            "kbo_game_id": game_id,
            "game_no": game_id[-1:] if game_id else "0",
            "status": status,
            "away_score": None,
            "home_score": None,
            "source": "schedule_html",
        }))
    return games


def fetch_betting_schedule_for_date(target_date) -> list[dict]:
    target_date_raw = normalize_date_to_yyyymmdd(target_date)
    year = target_date_raw[:4]
    month = target_date_raw[4:6]
    schedule_json = fetch_schedule_list(year, month)
    games = parse_schedule_api_games_for_betting(schedule_json, target_date_raw)
    if games:
        return games

    html_text = ""
    if isinstance(schedule_json, dict):
        html_text = schedule_json.get("_html_text") or ""
    games = parse_schedule_html_games_for_betting(html_text, target_date_raw)
    if games:
        return games

    page_html = fetch_schedule_page_html(year, month)
    return parse_schedule_html_games_for_betting(page_html, target_date_raw)


def get_latest_fantasy_game_date(conn) -> str | None:
    row = conn.execute("""
        SELECT MAX(game_date) AS latest_game_date
        FROM fantasy_daily_scores
    """).fetchone()
    return row["latest_game_date"] if row and row["latest_game_date"] else None




def repair_schedule_created_final_games(conn) -> int:
    """일정 동기화 중 잘못 final로 저장된 미래 배팅 경기를 scheduled로 되돌립니다.

    기존 KBO/판타지 데이터는 건드리지 않고 betting_games의 스케줄 생성 row만 보정합니다.
    pending/won/lost 배팅이 이미 연결된 경기는 건드리지 않습니다.
    """
    ensure_betting_tables(conn)
    latest_game_date = get_latest_fantasy_game_date(conn)
    params = []
    where = """
        status = 'final'
        AND source IN ('schedule_api', 'schedule_html')
        AND NOT EXISTS (
            SELECT 1
            FROM betting_bets bb
            WHERE bb.betting_game_id = betting_games.id
        )
    """
    if latest_game_date:
        where += " AND game_date > ?"
        params.append(latest_game_date)
    cursor = conn.execute(f"""
        UPDATE betting_games
        SET status = 'scheduled',
            away_score = NULL,
            home_score = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE {where}
    """, params)
    return int(cursor.rowcount or 0)
def purge_unbet_future_betting_games(conn) -> dict:
    """잘못 생성된 배팅 일정 row를 안전하게 비웁니다.

    대상은 latest fantasy game date 이후의 betting_games 중 아직 유저 bet이 하나도 없는 경기뿐입니다.
    이미 bet이 걸린 경기는 삭제하지 않고 skipped_with_bets로 보고합니다.
    기존 KBO/선수/가격/판타지 데이터는 전혀 건드리지 않습니다.
    """
    latest_game_date = get_latest_fantasy_game_date(conn)
    if not latest_game_date:
        return {"latest_game_date": None, "deleted_games": 0, "skipped_with_bets": 0}

    game_rows = conn.execute("""
        SELECT bg.id,
               COUNT(bb.id) AS bet_count
        FROM betting_games bg
        LEFT JOIN betting_bets bb ON bb.betting_game_id = bg.id
        WHERE bg.game_date > ?
        GROUP BY bg.id
    """, (latest_game_date,)).fetchall()

    deletable_ids = [row["id"] for row in game_rows if int(row["bet_count"] or 0) == 0]
    skipped = sum(1 for row in game_rows if int(row["bet_count"] or 0) > 0)
    if not deletable_ids:
        return {"latest_game_date": latest_game_date, "deleted_games": 0, "skipped_with_bets": skipped}

    placeholders = ",".join("?" for _ in deletable_ids)
    market_rows = conn.execute(f"""
        SELECT id FROM betting_markets
        WHERE betting_game_id IN ({placeholders})
    """, deletable_ids).fetchall()
    market_ids = [row["id"] for row in market_rows]
    if market_ids:
        market_placeholders = ",".join("?" for _ in market_ids)
        conn.execute(f"DELETE FROM betting_selections WHERE market_id IN ({market_placeholders})", market_ids)
        conn.execute(f"DELETE FROM betting_markets WHERE id IN ({market_placeholders})", market_ids)
    conn.execute(f"DELETE FROM betting_games WHERE id IN ({placeholders})", deletable_ids)

    return {"latest_game_date": latest_game_date, "deleted_games": len(deletable_ids), "skipped_with_bets": skipped}



def upsert_betting_game(conn, game: dict) -> int:
    ensure_betting_tables(conn)
    conn.execute("""
        INSERT INTO betting_games (
            game_date, scheduled_start_at, betting_closes_at,
            away_team, home_team, venue, kbo_game_id, game_no,
            status, away_score, home_score, source, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(game_date, away_team, home_team, scheduled_start_at)
        DO UPDATE SET
            betting_closes_at = excluded.betting_closes_at,
            venue = excluded.venue,
            kbo_game_id = COALESCE(excluded.kbo_game_id, betting_games.kbo_game_id),
            game_no = COALESCE(excluded.game_no, betting_games.game_no),
            status = CASE
                WHEN betting_games.status IN ('final', 'void') THEN betting_games.status
                ELSE excluded.status
            END,
            away_score = COALESCE(excluded.away_score, betting_games.away_score),
            home_score = COALESCE(excluded.home_score, betting_games.home_score),
            source = excluded.source,
            updated_at = CURRENT_TIMESTAMP
    """, (
        game["game_date"],
        game["scheduled_start_at"],
        game["betting_closes_at"],
        game["away_team"],
        game["home_team"],
        game.get("venue"),
        game.get("kbo_game_id"),
        game.get("game_no") or "0",
        game.get("status") or "scheduled",
        game.get("away_score"),
        game.get("home_score"),
        game.get("source") or BETTING_MARKET_VERSION,
    ))
    row = conn.execute("""
        SELECT id
        FROM betting_games
        WHERE game_date = ?
          AND away_team = ?
          AND home_team = ?
          AND scheduled_start_at = ?
    """, (game["game_date"], game["away_team"], game["home_team"], game["scheduled_start_at"])).fetchone()
    return int(row["id"])


def default_markets_for_game(game: dict) -> list[dict]:
    away = game["away_team"]
    home = game["home_team"]
    return [
        {
            "market_type": "moneyline_3way",
            "line_value": 0.0,
            "period": "full_game",
            "selections": [
                ("AWAY_WIN", f"{away} 승", 1.90, 1),
                ("DRAW", "무승부", 8.00, 2),
                ("HOME_WIN", f"{home} 승", 1.90, 3),
            ],
        },
        {
            "market_type": "win_margin",
            "line_value": 0.0,
            "period": "full_game",
            "selections": [
                ("MARGIN_1", "1점차", 2.60, 1),
                ("MARGIN_2_3", "2~3점차", 2.10, 2),
                ("MARGIN_4_PLUS", "4점차 이상", 2.80, 3),
            ],
        },
        {
            "market_type": "total_runs",
            "line_value": DEFAULT_TOTAL_RUNS_LINE,
            "period": "full_game",
            "selections": [
                ("OVER", f"Over {DEFAULT_TOTAL_RUNS_LINE:.1f}", 1.90, 1),
                ("UNDER", f"Under {DEFAULT_TOTAL_RUNS_LINE:.1f}", 1.90, 2),
            ],
        },
    ]




def _base_odds_for_selection(market_type: str, selection_key: str) -> float:
    """배팅 쏠림이 거의 없을 때 되돌아갈 기본 배당률입니다."""
    defaults = {
        "moneyline_3way": {
            "AWAY_WIN": 1.90,
            "DRAW": 8.00,
            "HOME_WIN": 1.90,
        },
        "win_margin": {
            "MARGIN_1": 2.60,
            "MARGIN_2_3": 2.10,
            "MARGIN_4_PLUS": 2.80,
        },
        "total_runs": {
            "OVER": 1.90,
            "UNDER": 1.90,
        },
    }
    return float(defaults.get(market_type, {}).get(selection_key, 1.90))


def _odds_bounds_for_market(market_type: str, selection_key: str) -> tuple[float, float]:
    """MyPick 배팅 정책상 시장/선택지별 배당 범위입니다.  # MYPICK BETTING POLICY V1 2026-06-06"""
    if market_type == "moneyline_3way" and selection_key == "DRAW":
        return 4.50, 20.00
    if market_type == "moneyline_3way":
        return 1.25, 10.00
    if market_type == "win_margin":
        if selection_key == "MARGIN_1":
            return 1.60, 6.00
        if selection_key == "MARGIN_2_3":
            return 1.40, 5.00
        if selection_key == "MARGIN_4_PLUS":
            return 1.70, 7.00
        return 1.40, 7.00
    if market_type == "total_runs":
        return 1.35, 4.00
    return 1.25, 20.00


def _virtual_liquidity_for_market(market_type: str) -> float:
    """초반 소액 배팅만으로 배당이 과도하게 흔들리지 않도록 가상 유동성을 둡니다.  # MYPICK BETTING POLICY V2 BALANCE 2026-06-06"""
    if market_type == "moneyline_3way":
        return 60_000.0
    if market_type == "win_margin":
        return 50_000.0
    if market_type == "total_runs":
        return 80_000.0
    return 50_000.0


def _odds_sensitivity_for_selection(market_type: str, selection_key: str) -> float:
    """선택지 쏠림이 배당에 반영되는 강도입니다.  # MYPICK BETTING POLICY V2 BALANCE 2026-06-06"""
    if market_type == "moneyline_3way" and selection_key == "DRAW":
        return 0.40
    if market_type == "moneyline_3way":
        return 0.55
    if market_type == "win_margin":
        return 0.50
    if market_type == "total_runs":
        return 0.45
    return 0.50


def _neutral_band_for_market(market_type: str) -> float:
    """쏠림 차이가 이 범위 안이면 잦은 미세 변동을 막고 기본 배당을 유지합니다."""
    if market_type == "moneyline_3way":
        return 0.05
    if market_type == "total_runs":
        return 0.04
    return 0.05


def _rounded_odds(value: float) -> float:
    """화면과 DB 모두 0.05 단위의 보기 좋은 배당률을 씁니다."""
    return round(round(float(value) / 0.05) * 0.05, 2)


def reprice_market_after_bet(conn, market_id: int) -> dict:
    """
    한 market 안에서 유저 stake가 많이 몰린 선택지는 배당률을 낮추고,
    덜 몰린 선택지는 배당률을 올립니다.

    이미 확정된 betting_bets.odds_at_bet은 절대 바꾸지 않습니다.
    앞으로 새로 배팅하는 유저에게만 갱신된 betting_selections.odds_decimal이 적용됩니다.
    """
    ensure_betting_tables(conn)
    market = conn.execute("""
        SELECT bm.id, bm.market_type, bm.status, bg.status AS game_status
        FROM betting_markets bm
        JOIN betting_games bg ON bg.id = bm.betting_game_id
        WHERE bm.id = ?
    """, (market_id,)).fetchone()
    if market is None:
        return {"updated": 0, "reason": "market_missing"}
    if market["status"] != "open" or market["game_status"] != "scheduled":
        return {"updated": 0, "reason": "market_closed"}

    selection_rows = conn.execute("""
        SELECT id, selection_key, odds_decimal
        FROM betting_selections
        WHERE market_id = ? AND is_active = 1
        ORDER BY display_order ASC, id ASC
    """, (market_id,)).fetchall()
    if not selection_rows:
        return {"updated": 0, "reason": "selection_missing"}

    stake_rows = conn.execute("""
        SELECT selection_id, COALESCE(SUM(stake_points), 0) AS stake_sum
        FROM betting_bets
        WHERE market_id = ?
          AND status = 'pending'
        GROUP BY selection_id
    """, (market_id,)).fetchall()
    stakes_by_selection = {int(row["selection_id"]): float(row["stake_sum"] or 0) for row in stake_rows}
    total_stake = sum(stakes_by_selection.values())

    # 작은 표본에서는 배당률이 흔들리면 오히려 조잡해 보이므로 기본 배당 유지.
    # MYPICK BETTING POLICY V2 BALANCE 2026-06-06: 100,000P 한도에 맞춰 초반 급변을 완화.
    min_reprice_stake = 20_000.0
    market_type = str(market["market_type"])
    if total_stake < min_reprice_stake:
        updated = 0
        for row in selection_rows:
            base = _base_odds_for_selection(market_type, row["selection_key"])
            base = _rounded_odds(base)
            if abs(float(row["odds_decimal"] or 0) - base) >= 0.001:
                conn.execute("""
                    UPDATE betting_selections
                    SET odds_decimal = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (base, row["id"]))
                updated += 1
        return {"updated": updated, "reason": "low_volume", "total_stake": total_stake}

    base_odds = []
    base_implied = []
    for row in selection_rows:
        base = _base_odds_for_selection(market_type, row["selection_key"])
        base_odds.append(base)
        base_implied.append(1.0 / base)
    implied_total = sum(base_implied) or 1.0
    base_share_by_id = {
        int(row["id"]): base_implied[index] / implied_total
        for index, row in enumerate(selection_rows)
    }

    updated = 0
    neutral_band = _neutral_band_for_market(market_type)
    virtual_total = _virtual_liquidity_for_market(market_type)
    effective_total = total_stake + virtual_total

    for index, row in enumerate(selection_rows):
        selection_id = int(row["id"])
        selection_key = str(row["selection_key"])
        base = base_odds[index]
        expected_share = base_share_by_id[selection_id]
        virtual_stake = virtual_total * expected_share
        effective_stake = stakes_by_selection.get(selection_id, 0.0) + virtual_stake
        actual_share = effective_stake / effective_total if effective_total else expected_share
        diff = actual_share - expected_share

        if abs(diff) <= neutral_band:
            target = base
        else:
            # 선택이 몰리면 actual_share > expected_share -> 배당 하락.
            # 선택이 적으면 actual_share < expected_share -> 배당 상승.
            # ratio 방식이라 심한 쏠림에서는 승/패 10.00 같은 고배당까지 자연스럽게 열린다.
            safe_share = max(actual_share, 0.0001)
            ratio = expected_share / safe_share
            sensitivity = _odds_sensitivity_for_selection(market_type, selection_key)
            target = base * (ratio ** sensitivity)

        low, high = _odds_bounds_for_market(market_type, selection_key)
        target = _rounded_odds(max(low, min(high, target)))
        if abs(float(row["odds_decimal"] or 0) - target) >= 0.001:
            conn.execute("""
                UPDATE betting_selections
                SET odds_decimal = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (target, selection_id))
            updated += 1

    return {"updated": updated, "reason": "repriced", "total_stake": total_stake}

def ensure_default_markets(conn, betting_game_id: int, game: dict):
    ensure_betting_tables(conn)
    existing_bets = conn.execute("""
        SELECT COUNT(*) AS cnt
        FROM betting_bets
        WHERE betting_game_id = ?
    """, (betting_game_id,)).fetchone()["cnt"]

    for market in default_markets_for_game(game):
        conn.execute("""
            INSERT INTO betting_markets (
                betting_game_id, market_type, line_value, period, status, updated_at
            )
            VALUES (?, ?, ?, ?, 'open', CURRENT_TIMESTAMP)
            ON CONFLICT(betting_game_id, market_type, line_value, period)
            DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP
        """, (
            betting_game_id,
            market["market_type"],
            market["line_value"],
            market["period"],
        ))
        market_row = conn.execute("""
            SELECT id
            FROM betting_markets
            WHERE betting_game_id = ?
              AND market_type = ?
              AND line_value = ?
              AND period = ?
        """, (
            betting_game_id,
            market["market_type"],
            market["line_value"],
            market["period"],
        )).fetchone()
        market_id = int(market_row["id"])

        for selection_key, label, odds, display_order in market["selections"]:
            if existing_bets:
                conn.execute("""
                    INSERT OR IGNORE INTO betting_selections (
                        market_id, selection_key, label, odds_decimal, display_order, is_active
                    )
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (market_id, selection_key, label, odds, display_order))
                conn.execute("""
                    UPDATE betting_selections
                    SET label = ?, display_order = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE market_id = ? AND selection_key = ?
                """, (label, display_order, market_id, selection_key))
            else:
                conn.execute("""
                    INSERT INTO betting_selections (
                        market_id, selection_key, label, odds_decimal, display_order, is_active, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(market_id, selection_key)
                    DO UPDATE SET
                        label = excluded.label,
                        odds_decimal = excluded.odds_decimal,
                        display_order = excluded.display_order,
                        is_active = 1,
                        updated_at = CURRENT_TIMESTAMP
                """, (market_id, selection_key, label, odds, display_order))


def sync_betting_games_for_dates(target_dates: Iterable[str]) -> dict:
    results = []
    repaired = 0
    with get_conn() as conn:
        ensure_betting_tables(conn)
        for target_date in target_dates:
            date_dash = normalize_date_dash(target_date)
            if not date_dash:
                continue
            games = fetch_betting_schedule_for_date(date_dash)
            saved = 0
            for game in games:
                game_id = upsert_betting_game(conn, game)
                ensure_default_markets(conn, game_id, game)
                saved += 1
            results.append({"date": date_dash, "fetched": len(games), "saved": saved})
        repaired = repair_schedule_created_final_games(conn)
    return {"dates": results, "total_saved": sum(item["saved"] for item in results), "repaired_schedule_finals": repaired}


def sync_next_betting_game_dates(limit=BETTING_VISIBLE_GAME_DATES, max_lookahead_days=BETTING_LOOKAHEAD_DAYS) -> dict:
    with get_conn() as conn:
        latest_game_date = get_latest_fantasy_game_date(conn)
    if latest_game_date:
        start_date = datetime.strptime(latest_game_date, "%Y-%m-%d") + timedelta(days=1)
    else:
        start_date = now_korea().replace(hour=0, minute=0, second=0, microsecond=0)

    selected_dates = []
    per_date_cache = {}
    for offset in range(max_lookahead_days):
        target = (start_date + timedelta(days=offset)).strftime("%Y-%m-%d")
        games = fetch_betting_schedule_for_date(target)
        per_date_cache[target] = games
        if games:
            selected_dates.append(target)
            if len(selected_dates) >= limit:
                break

    results = []
    repaired = 0
    with get_conn() as conn:
        ensure_betting_tables(conn)
        for target in selected_dates:
            saved = 0
            for game in per_date_cache.get(target, []):
                game_id = upsert_betting_game(conn, game)
                ensure_default_markets(conn, game_id, game)
                saved += 1
            results.append({"date": target, "fetched": len(per_date_cache.get(target, [])), "saved": saved})
        repaired = repair_schedule_created_final_games(conn)
    return {
        "latest_game_date": latest_game_date,
        "selected_dates": selected_dates,
        "dates": results,
        "total_saved": sum(item["saved"] for item in results),
        "repaired_schedule_finals": repaired,
    }


def is_game_open_for_betting(game_row) -> bool:
    try:
        keys = set(game_row.keys())
    except AttributeError:
        keys = set(game_row) if isinstance(game_row, dict) else set()
    status_key = "status" if "status" in keys else "game_status"
    status = str(game_row[status_key] or "scheduled") if status_key in keys else "scheduled"
    close_at = parse_db_datetime(game_row["betting_closes_at"])
    return status == "scheduled" and close_at is not None and now_korea() < close_at


def decorate_game_status(game: dict) -> dict:
    close_at = parse_db_datetime(game.get("betting_closes_at"))
    current_status = game.get("status") or "scheduled"
    game["is_open"] = bool(current_status == "scheduled" and close_at and now_korea() < close_at)
    if current_status == "scheduled" and close_at and now_korea() >= close_at:
        game["status_label"] = "마감"
    else:
        game["status_label"] = GAME_STATUS_LABELS.get(current_status, current_status or "-")
    game["game_date_display"] = format_date_display(game.get("game_date"))
    game["scheduled_start_display"] = format_datetime_display(game.get("scheduled_start_at"))
    if close_at and game["is_open"]:
        delta = close_at - now_korea()
        total_seconds = max(0, int(delta.total_seconds()))
        hours, rem = divmod(total_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        game["close_countdown"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        game["close_countdown"] = "마감"
    return game


def get_betting_board_data(user_id=None) -> dict:
    with get_conn() as conn:
        ensure_betting_tables(conn)
        latest_game_date = get_latest_fantasy_game_date(conn)
        date_rows = []
        if latest_game_date:
            date_rows = conn.execute("""
                SELECT DISTINCT game_date
                FROM betting_games
                WHERE game_date > ?
                ORDER BY game_date ASC
                LIMIT ?
            """, (latest_game_date, BETTING_VISIBLE_GAME_DATES)).fetchall()
        if not date_rows:
            date_rows = conn.execute("""
                SELECT DISTINCT game_date
                FROM betting_games
                WHERE game_date >= date('now')
                ORDER BY game_date ASC
                LIMIT ?
            """, (BETTING_VISIBLE_GAME_DATES,)).fetchall()

        game_dates = [row["game_date"] for row in date_rows]
        if not game_dates:
            return {"latest_game_date": latest_game_date, "dates": [], "games_by_date": {}, "user_bets_by_market": {}}

        placeholders = ",".join("?" for _ in game_dates)
        game_rows = conn.execute(f"""
            SELECT *
            FROM betting_games
            WHERE game_date IN ({placeholders})
            ORDER BY game_date ASC, scheduled_start_at ASC, id ASC
        """, game_dates).fetchall()

        game_ids = [row["id"] for row in game_rows]
        market_rows = []
        selection_rows = []
        user_bets = []
        if game_ids:
            game_placeholders = ",".join("?" for _ in game_ids)
            market_rows = conn.execute(f"""
                SELECT *
                FROM betting_markets
                WHERE betting_game_id IN ({game_placeholders})
                  AND status = 'open'
                  AND market_type IN ('moneyline_3way', 'win_margin', 'total_runs')
                ORDER BY betting_game_id ASC,
                    CASE market_type
                        WHEN 'moneyline_3way' THEN 1
                        WHEN 'win_margin' THEN 2
                        WHEN 'total_runs' THEN 3
                        ELSE 9
                    END,
                    id ASC
            """, game_ids).fetchall()
            market_ids = [row["id"] for row in market_rows]
            if market_ids:
                market_placeholders = ",".join("?" for _ in market_ids)
                selection_rows = conn.execute(f"""
                    SELECT *
                    FROM betting_selections
                    WHERE market_id IN ({market_placeholders})
                      AND is_active = 1
                    ORDER BY market_id ASC, display_order ASC, id ASC
                """, market_ids).fetchall()
                if user_id:
                    user_bets = conn.execute(f"""
                        SELECT *
                        FROM betting_bets
                        WHERE user_id = ?
                          AND market_id IN ({market_placeholders})
                    """, [user_id] + market_ids).fetchall()

    selections_by_market = {}
    for row in selection_rows:
        item = dict(row)
        item["odds_display"] = f"{safe_float(item.get('odds_decimal')):.2f}"
        selections_by_market.setdefault(item["market_id"], []).append(item)

    user_bets_by_market = {row["market_id"]: dict(row) for row in user_bets}

    markets_by_game = {}
    for row in market_rows:
        item = dict(row)
        item["title"] = MARKET_TITLES.get(item["market_type"], item["market_type"])
        item["subtitle"] = MARKET_SUBTITLES.get(item["market_type"], "")
        item["selections"] = selections_by_market.get(item["id"], [])
        user_bet = user_bets_by_market.get(item["id"])
        item["user_bet"] = user_bet
        markets_by_game.setdefault(item["betting_game_id"], []).append(item)

    games_by_date = {date_value: [] for date_value in game_dates}
    for row in game_rows:
        game = decorate_game_status(dict(row))
        game["markets"] = markets_by_game.get(game["id"], [])
        games_by_date.setdefault(game["game_date"], []).append(game)

    return {
        "latest_game_date": latest_game_date,
        "dates": game_dates,
        "games_by_date": games_by_date,
        "user_bets_by_market": user_bets_by_market,
    }


def get_selection_for_bet(conn, selection_id: int):
    ensure_betting_tables(conn)
    return conn.execute("""
        SELECT
            bs.id AS selection_id,
            bs.selection_key,
            bs.label AS selection_label,
            bs.odds_decimal,
            bs.is_active,
            bm.id AS market_id,
            bm.market_type,
            bm.line_value,
            bm.period,
            bm.status AS market_status,
            bg.id AS betting_game_id,
            bg.game_date,
            bg.scheduled_start_at,
            bg.betting_closes_at,
            bg.away_team,
            bg.home_team,
            bg.status AS game_status
        FROM betting_selections bs
        JOIN betting_markets bm ON bm.id = bs.market_id
        JOIN betting_games bg ON bg.id = bm.betting_game_id
        WHERE bs.id = ?
    """, (selection_id,)).fetchone()


def parse_stake(value) -> tuple[float | None, str | None]:
    text = str(value or "").replace(",", "").replace("₩", "").strip()
    if not text:
        return None, "배팅 금액을 입력해 주세요."
    try:
        stake = int(float(text))
    except ValueError:
        return None, "배팅 금액은 숫자로 입력해 주세요."
    if stake < BETTING_MIN_STAKE:
        return None, f"최소 배팅 금액은 ₩{BETTING_MIN_STAKE:,}입니다."
    if stake > BETTING_MAX_STAKE_PER_MARKET:
        return None, f"한 항목당 최대 배팅 금액은 ₩{BETTING_MAX_STAKE_PER_MARKET:,}입니다."
    if stake % BETTING_STAKE_UNIT != 0:
        return None, f"배팅 금액은 ₩{BETTING_STAKE_UNIT:,} 단위로 입력해 주세요."
    return float(stake), None


def determine_market_result(market_type: str, line_value: float, home_score: int, away_score: int) -> str | None:
    if market_type == "moneyline_3way":
        if home_score > away_score:
            return "HOME_WIN"
        if away_score > home_score:
            return "AWAY_WIN"
        return "DRAW"
    if market_type == "win_margin":
        diff = abs(int(home_score) - int(away_score))
        if diff == 0:
            return "PUSH"
        if diff == 1:
            return "MARGIN_1"
        if diff in (2, 3):
            return "MARGIN_2_3"
        return "MARGIN_4_PLUS"
    if market_type == "runline_1_5":
        # Legacy market retired by migrate_runline_to_win_margin().
        # If an old pending row is accidentally left behind, refund instead of settling it.
        return "PUSH"
    if market_type == "total_runs":
        line = safe_float(line_value, DEFAULT_TOTAL_RUNS_LINE)
        total_runs = home_score + away_score
        if total_runs > line:
            return "OVER"
        if total_runs < line:
            return "UNDER"
        return "PUSH"
    return None


def update_betting_results_for_date(target_date) -> dict:
    """공식 경기 결과를 가져와 betting_games 점수/status를 업데이트합니다."""
    target_date_dash = normalize_date_dash(target_date)
    if not target_date_dash:
        raise ValueError("날짜 형식이 잘못되었습니다. 예: 20260522 또는 2026-05-22")

    games = get_games_for_date(target_date_dash)
    updated = 0
    with get_conn() as conn:
        ensure_betting_tables(conn)
        for game in games:
            away_team = game.get("away_team")
            home_team = game.get("home_team")
            kbo_game_id = game.get("game_id") or game.get("kbo_game_id")
            away_score = game.get("away_score")
            home_score = game.get("home_score")
            if away_team is None or home_team is None:
                continue
            cursor = conn.execute("""
                UPDATE betting_games
                SET status = 'final',
                    away_score = ?,
                    home_score = ?,
                    kbo_game_id = COALESCE(?, kbo_game_id),
                    updated_at = CURRENT_TIMESTAMP
                WHERE game_date = ?
                  AND away_team = ?
                  AND home_team = ?
            """, (away_score, home_score, kbo_game_id, target_date_dash, away_team, home_team))
            updated += cursor.rowcount
    return {"date": target_date_dash, "fetched_games": len(games), "updated_games": updated}


def settle_betting_for_date(target_date) -> dict:
    target_date_dash = normalize_date_dash(target_date)
    if not target_date_dash:
        raise ValueError("날짜 형식이 잘못되었습니다. 예: 20260522 또는 2026-05-22")

    settled = 0
    won = 0
    lost = 0
    voided = 0
    skipped = 0

    with get_conn() as conn:
        ensure_betting_tables(conn)
        rows = conn.execute("""
            SELECT
                bb.*,
                bg.status AS game_status,
                bg.home_score,
                bg.away_score,
                bm.market_type,
                bm.line_value,
                bs.selection_key
            FROM betting_bets bb
            JOIN betting_games bg ON bg.id = bb.betting_game_id
            JOIN betting_markets bm ON bm.id = bb.market_id
            JOIN betting_selections bs ON bs.id = bb.selection_id
            WHERE bg.game_date = ?
              AND bb.status = 'pending'
            ORDER BY bb.id ASC
        """, (target_date_dash,)).fetchall()

        for row in rows:
            game_status = row["game_status"]
            if game_status in ["cancelled", "postponed", "void"]:
                refund = round(float(row["stake_points"] or 0), 1)
                conn.execute("""
                    UPDATE betting_bets
                    SET status = 'void',
                        settled_at = CURRENT_TIMESTAMP,
                        payout_points = ?,
                        profit_points = 0,
                        result_key = 'VOID',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'pending'
                """, (refund, row["id"]))
                conn.execute("""
                    INSERT OR IGNORE INTO betting_ledger (user_id, bet_id, event_type, amount_points, note)
                    VALUES (?, ?, 'void_refund', ?, ?)
                """, (row["user_id"], row["id"], refund, "경기 취소/연기/무효 환불"))
                voided += 1
                settled += 1
                continue

            if game_status != "final" or row["home_score"] is None or row["away_score"] is None:
                skipped += 1
                continue

            result_key = determine_market_result(
                row["market_type"],
                row["line_value"],
                int(row["home_score"]),
                int(row["away_score"]),
            )
            if result_key is None:
                skipped += 1
                continue

            if result_key == "PUSH":
                refund = round(float(row["stake_points"] or 0), 1)
                conn.execute("""
                    UPDATE betting_bets
                    SET status = 'void',
                        settled_at = CURRENT_TIMESTAMP,
                        payout_points = ?,
                        profit_points = 0,
                        result_key = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'pending'
                """, (refund, result_key, row["id"]))
                refund_note = "승리 점수차 무승부 환불" if row["market_type"] == "win_margin" else "무효/환불"
                conn.execute("""
                    INSERT OR IGNORE INTO betting_ledger (user_id, bet_id, event_type, amount_points, note)
                    VALUES (?, ?, 'void_refund', ?, ?)
                """, (row["user_id"], row["id"], refund, refund_note))
                voided += 1
                settled += 1
                continue

            is_won = str(row["selection_key"]) == result_key
            if is_won:
                payout = round(float(row["stake_points"] or 0) * float(row["odds_at_bet"] or 0), 1)
                profit = round(payout - float(row["stake_points"] or 0), 1)
                conn.execute("""
                    UPDATE betting_bets
                    SET status = 'won',
                        settled_at = CURRENT_TIMESTAMP,
                        payout_points = ?,
                        profit_points = ?,
                        result_key = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'pending'
                """, (payout, profit, result_key, row["id"]))
                conn.execute("""
                    INSERT OR IGNORE INTO betting_ledger (user_id, bet_id, event_type, amount_points, note)
                    VALUES (?, ?, 'payout', ?, ?)
                """, (row["user_id"], row["id"], payout, "배팅 적중 지급"))
                won += 1
            else:
                profit = round(-float(row["stake_points"] or 0), 1)
                conn.execute("""
                    UPDATE betting_bets
                    SET status = 'lost',
                        settled_at = CURRENT_TIMESTAMP,
                        payout_points = 0,
                        profit_points = ?,
                        result_key = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'pending'
                """, (profit, result_key, row["id"]))
                lost += 1
            settled += 1

    return {"date": target_date_dash, "settled": settled, "won": won, "lost": lost, "void": voided, "skipped": skipped}


def get_betting_history(user_id, limit=100) -> dict:
    with get_conn() as conn:
        ensure_betting_tables(conn)
        rows = conn.execute("""
            SELECT
                bb.*,
                bg.game_date,
                bg.scheduled_start_at,
                bg.away_team,
                bg.home_team,
                bg.away_score,
                bg.home_score,
                bm.market_type,
                bm.line_value,
                bs.selection_key,
                bs.label AS selection_label
            FROM betting_bets bb
            JOIN betting_games bg ON bg.id = bb.betting_game_id
            JOIN betting_markets bm ON bm.id = bb.market_id
            JOIN betting_selections bs ON bs.id = bb.selection_id
            WHERE bb.user_id = ?
            ORDER BY bb.placed_at DESC, bb.id DESC
            LIMIT ?
        """, (user_id, int(limit))).fetchall()

    items = []
    total_staked = 0.0
    total_won = 0.0
    total_lost = 0.0
    total_refunded = 0.0
    pending_stake = 0.0
    net = 0.0

    for row in rows:
        item = dict(row)
        item["match_label"] = f"{item['away_team']} vs {item['home_team']}"
        item["placed_at_display"] = format_datetime_display(item.get("placed_at"))
        item["game_date_display"] = format_date_display(item.get("game_date"))
        item["status_label"] = STATUS_LABELS.get(item.get("status"), item.get("status") or "-")
        item["market_label"] = MARKET_TITLES.get(item.get("market_type"), item.get("market_type") or "-")
        item["pick_display"] = f"{item['market_label']} · {item.get('selection_label') or '-'}"
        item["odds_display"] = f"{safe_float(item.get('odds_at_bet')):.2f}"
        item["stake_points"] = round(float(item.get("stake_points") or 0), 1)
        item["payout_points"] = round(float(item.get("payout_points") or 0), 1)
        item["profit_points"] = round(float(item.get("profit_points") or 0), 1)
        total_staked += item["stake_points"]
        if item["status"] == "won":
            total_won += item["payout_points"]
            net += item["profit_points"]
        elif item["status"] == "lost":
            total_lost += abs(item["profit_points"])
            net += item["profit_points"]
        elif item["status"] == "void":
            total_refunded += item["payout_points"]
        elif item["status"] == "pending":
            pending_stake += item["stake_points"]
        items.append(item)

    return {
        "bets": items,
        "summary": {
            "total_staked": round(total_staked, 1),
            "total_won": round(total_won, 1),
            "total_lost": round(total_lost, 1),
            "total_refunded": round(total_refunded, 1),
            "pending_stake": round(pending_stake, 1),
            "net": round(net, 1),
        },
    }


def migrate_runline_to_win_margin(conn=None) -> dict:
    """핸디캡(runline_1_5)을 새 배팅에서는 제거하고 승리 점수차(win_margin)를 생성합니다.

    - 기존 runline 기록은 삭제하지 않고 retired 처리합니다.
    - pending runline bet은 stake를 전액 환불하고 void 처리합니다.
    - 모든 기존 betting_games에 win_margin market/selections를 안전하게 추가합니다.
    """
    owns_connection = conn is None
    if owns_connection:
        context = get_conn()
        conn = context.__enter__()
    else:
        context = None

    try:
        ensure_betting_tables(conn)
        runline_pending = conn.execute("""
            SELECT
                bb.id, bb.user_id, bb.stake_points
            FROM betting_bets bb
            JOIN betting_markets bm ON bm.id = bb.market_id
            WHERE bm.market_type = 'runline_1_5'
              AND bb.status = 'pending'
            ORDER BY bb.id ASC
        """).fetchall()

        refunded = 0
        for row in runline_pending:
            refund = round(float(row["stake_points"] or 0), 1)
            conn.execute("""
                UPDATE betting_bets
                SET status = 'void',
                    settled_at = CURRENT_TIMESTAMP,
                    payout_points = ?,
                    profit_points = 0,
                    result_key = 'RETIRED_RUNLINE',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND status = 'pending'
            """, (refund, row["id"]))
            conn.execute("""
                INSERT OR IGNORE INTO betting_ledger (user_id, bet_id, event_type, amount_points, note)
                VALUES (?, ?, 'void_refund', ?, ?)
            """, (row["user_id"], row["id"], refund, "핸디캡 항목 제거로 인한 환불"))
            refunded += 1

        retired_markets = conn.execute("""
            UPDATE betting_markets
            SET status = 'retired',
                settlement_key = COALESCE(settlement_key, 'RETIRED_RUNLINE'),
                updated_at = CURRENT_TIMESTAMP
            WHERE market_type = 'runline_1_5'
              AND status != 'retired'
        """).rowcount

        retired_selections = conn.execute("""
            UPDATE betting_selections
            SET is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE market_id IN (
                SELECT id FROM betting_markets WHERE market_type = 'runline_1_5'
            )
              AND is_active != 0
        """).rowcount

        games = conn.execute("""
            SELECT *
            FROM betting_games
            ORDER BY game_date ASC, scheduled_start_at ASC, id ASC
        """).fetchall()

        win_margin_before = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM betting_markets
            WHERE market_type = 'win_margin'
        """).fetchone()["cnt"]

        for game_row in games:
            ensure_default_markets(conn, int(game_row["id"]), dict(game_row))

        win_margin_after = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM betting_markets
            WHERE market_type = 'win_margin'
        """).fetchone()["cnt"]

        return {
            "refunded_runline_pending_bets": refunded,
            "retired_runline_markets": retired_markets,
            "retired_runline_selections": retired_selections,
            "games_checked": len(games),
            "created_win_margin_markets": int(win_margin_after or 0) - int(win_margin_before or 0),
        }
    finally:
        if owns_connection:
            context.__exit__(None, None, None)


def main():
    parser = argparse.ArgumentParser(description="MyPick 배팅 helper")
    parser.add_argument("command", choices=["ensure", "sync-next", "sync-date", "repair", "reset-schedule", "migrate-win-margin", "update-results", "settle"])
    parser.add_argument("--date", help="YYYYMMDD 또는 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=BETTING_VISIBLE_GAME_DATES)
    args = parser.parse_args()

    if args.command == "ensure":
        ensure_betting_tables()
        print("betting_* 테이블 확인 완료")
    elif args.command == "sync-next":
        result = sync_next_betting_game_dates(limit=args.days)
        print(result)
    elif args.command == "sync-date":
        if not args.date:
            raise SystemExit("--date가 필요합니다.")
        result = sync_betting_games_for_dates([args.date])
        print(result)
    elif args.command == "repair":
        with get_conn() as conn:
            ensure_betting_tables(conn)
            repaired = repair_schedule_created_final_games(conn)
        print({"repaired_schedule_finals": repaired})
    elif args.command == "reset-schedule":
        with get_conn() as conn:
            ensure_betting_tables(conn)
            result = purge_unbet_future_betting_games(conn)
        print(result)
    elif args.command == "migrate-win-margin":
        result = migrate_runline_to_win_margin()
        print(result)
    elif args.command == "update-results":
        if not args.date:
            raise SystemExit("--date가 필요합니다.")
        result = update_betting_results_for_date(args.date)
        print(result)
    elif args.command == "settle":
        if not args.date:
            raise SystemExit("--date가 필요합니다.")
        update_result = update_betting_results_for_date(args.date)
        settle_result = settle_betting_for_date(args.date)
        print("update:", update_result)
        print("settle:", settle_result)


if __name__ == "__main__":
    main()
