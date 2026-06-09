"""
KBO 판타지 웹페이지를 실행하는 파일입니다.

현재 기능:
- 선수 랭킹 / 타자 랭킹 / 투수 랭킹
- 선수 검색 / 선수 상세
- 회원가입 / 로그인 / 로그아웃
- 내 팀 생성 / 편집 / 선수 추가 / 선수 삭제 / 팀 확정
- market_daily_v3 기준 선수 가격 표시
- 팀 확정 시점 locked price 저장
- 내 팀 페이지 유저 점수 요약 표시

중요:
- 화면에 보이는 선수 현재 점수는 누적 총점이 아니라 fantasy_daily_scores의 최신 game_date 기준 점수입니다.
- fantasy_player_totals는 누적 총점 보관용으로 유지합니다.
- 웹페이지 가격 기준은 market_daily_v3입니다.
- 팀이 확정된 상태에서만 calculate_team_daily_scores.py가 유저 점수를 저장합니다.
"""

import json
import hmac
import os
import re
import secrets
import sqlite3
import time
from functools import wraps
from math import ceil
from datetime import date, datetime, time as datetime_time

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None

from flask import send_from_directory
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
import requests
from bs4 import BeautifulSoup
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_conn

from position_rules import (
    BATTER_SLOT_DETAIL_MAP,
    PITCHER_SLOT_DETAIL_MAP,
    candidate_slots_for_detail,
    detail_positions_for_filter,
    get_slot_position_mismatch_reason as get_position_mismatch_reason_shared,
    get_slot_requirement as get_slot_requirement_shared,
)

from betting import (
    BETTING_MIN_STAKE,
    BETTING_MAX_STAKE_PER_MARKET,
    BETTING_STAKE_UNIT,
    ensure_betting_tables,
    get_betting_board_data,
    get_betting_history,
    get_betting_ledger_sum,
    get_selection_for_bet,
    is_game_open_for_betting,
    parse_stake,
    reprice_market_after_bet,
)


app = Flask(__name__)

# Security configuration
# - Local development may use a local-only fallback key.
# - Production must provide SECRET_KEY through the environment.
#   Example: export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
PASSWORD_MIN_LENGTH = 8
ENV_NAME = (os.environ.get("MYPICK_ENV") or os.environ.get("FLASK_ENV") or "").lower()
IS_PRODUCTION = ENV_NAME in {"prod", "production"}

_secret_key = os.environ.get("SECRET_KEY", "").strip()
if not _secret_key:
    if IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY environment variable is required in production.")
    _secret_key = "local-dev-only-secret-key-do-not-use-in-production"

app.config["SECRET_KEY"] = _secret_key
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
if IS_PRODUCTION:
    app.config["SESSION_COOKIE_SECURE"] = True


# MYPICK DEPLOYMENT SECURITY V2 2026-06-03 START
CSRF_SESSION_KEY = "_mypick_csrf_token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER_NAMES = ("X-CSRFToken", "X-CSRF-Token")


def get_csrf_token():
    """Return a per-session CSRF token for HTML forms and same-origin fetch requests."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf_token():
    expected = session.get(CSRF_SESSION_KEY, "")
    submitted = request.form.get(CSRF_FORM_FIELD, "")
    if not submitted:
        for header_name in CSRF_HEADER_NAMES:
            submitted = request.headers.get(header_name, "")
            if submitted:
                break

    if not expected or not submitted or not hmac.compare_digest(str(expected), str(submitted)):
        abort(400, description="Invalid CSRF token.")


@app.before_request
def enforce_csrf_protection():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        validate_csrf_token()


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if IS_PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.context_processor
def inject_security_helpers():
    return {"csrf_token": get_csrf_token}
# MYPICK DEPLOYMENT SECURITY V2 2026-06-03 END


BASIS_SOURCE = "market_daily_v3"
MAX_PLAYER_PRICE = 15.7
TRADE_BONUS_POINTS_PER_PRICE_TENTH = 500
MONEY_PER_POINT = 1
SIGNUP_STARTING_POINTS = 10000.0


SUPPORT_CATEGORIES = [
    ("score", "수입/점수 오류"),
    ("player", "선수 정보/말소 오류"),
    ("price", "가격/예산 오류"),
    ("team", "팀 편집/C 오류"),
    ("friends", "친구/랭킹 오류"),
    ("account", "계정/로그인 문제"),
    ("ui", "UI/디자인 건의"),
    ("feature", "기능 제안"),
    ("other", "기타"),
]
SUPPORT_CATEGORY_LABELS = dict(SUPPORT_CATEGORIES)

SUPPORT_STATUSES = [
    ("open", "접수됨"),
    ("reviewing", "확인중"),
    ("resolved", "처리완료"),
    ("closed", "닫힘"),
]
SUPPORT_STATUS_LABELS = dict(SUPPORT_STATUSES)
SUPPORT_STATUS_TONE = {
    "open": "open",
    "reviewing": "reviewing",
    "resolved": "resolved",
    "closed": "closed",
}

SUPPORT_TITLE_MAX_LENGTH = 120
SUPPORT_MESSAGE_MAX_LENGTH = 3000
SUPPORT_PAGE_URL_MAX_LENGTH = 500


TEAM_META = {
    "KIA": {"name": "KIA 타이거즈", "short": "KIA", "primary": "#ea0029", "secondary": "#000000"},
    "LG": {"name": "LG 트윈스", "short": "LG", "primary": "#c30452", "secondary": "#000000", "css_class": "team-lg"},
    "두산": {"name": "두산 베어스", "short": "두산", "primary": "#131230", "secondary": "#ed1c24", "css_class": "team-doosan"},
    "삼성": {"name": "삼성 라이온즈", "short": "삼성", "primary": "#074ca1", "secondary": "#c5c5c5", "css_class": "team-samsung"},
    "KT": {"name": "KT 위즈", "short": "KT", "primary": "#000000", "secondary": "#eb1c24", "css_class": "team-kt"},
    "SSG": {"name": "SSG 랜더스", "short": "SSG", "primary": "#ce0e2d", "secondary": "#ffd700", "css_class": "team-ssg"},
    "롯데": {"name": "롯데 자이언츠", "short": "롯데", "primary": "#041e42", "secondary": "#d00f31", "css_class": "team-lotte"},
    "NC": {"name": "NC 다이노스", "short": "NC", "primary": "#315288", "secondary": "#c59f6e", "css_class": "team-nc"},
    "키움": {"name": "키움 히어로즈", "short": "키움", "primary": "#820024", "secondary": "#6e0019", "css_class": "team-kiwoom"},
    "한화": {"name": "한화 이글스", "short": "한화", "primary": "#ff6600", "secondary": "#000000", "css_class": "team-hanwha"},
}


KBO_TEAM_OPTIONS = ["LG", "KT", "SSG", "NC", "두산", "KIA", "삼성", "롯데", "한화", "키움"]


def normalize_kbo_team(team):
    """사용자가 고른 KBO 응원팀 값을 안전하게 정리합니다."""
    team_key = str(team or "").strip()
    if team_key in TEAM_META:
        return team_key
    return None


def get_kbo_team_options():
    """프로필 응원팀 선택용 목록입니다."""
    return [
        {"key": key, **get_team_meta(key)}
        for key in KBO_TEAM_OPTIONS
    ]


def get_team_meta(team):
    """화면 표시용 KBO 팀 메타 정보입니다. DB 변경 없이 UI에서만 사용합니다."""
    key = str(team or "").strip()
    default_meta = {
        "name": key or "-",
        "short": key or "-",
        "primary": "#1e3a5f",
        "secondary": "#8b9cb3",
        "css_class": "team-default",
    }
    return TEAM_META.get(key, default_meta)


def position_type_label(position_type):
    if position_type == "batter":
        return "타자"
    if position_type == "pitcher":
        return "투수"
    return position_type or "-"


def roster_row_by_slot(roster_rows, slot):
    for row in roster_rows or []:
        if row.get("slot") == slot:
            return row
    return {"slot": slot, "label": get_slot_label(slot), "player": None}


def clamp_percent(value, maximum):
    try:
        value = float(value or 0)
        maximum = float(maximum or 1)
    except (TypeError, ValueError):
        return 0

    if maximum <= 0:
        return 0

    return max(0, min(100, round((value / maximum) * 100, 1)))


def score_value_class(value):
    """수익/변동 수치의 화면 색상 class를 반환합니다."""
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0

    if number > 0:
        return "score-positive"
    if number < 0:
        return "score-negative"
    return "score-zero"


def points_to_money_amount(points):
    """내부 포인트 값을 MyPick 머니 표시액으로 변환합니다. DB 값은 바꾸지 않습니다."""
    try:
        numeric_points = float(points or 0)
    except (TypeError, ValueError):
        numeric_points = 0.0
    return int(round(numeric_points * MONEY_PER_POINT))


def format_money_from_points(points):
    """포인트 기반 수익/재산을 원화 스타일 문자열로 표시합니다."""
    amount = points_to_money_amount(points)
    sign = "-" if amount < 0 else ""
    return f"{sign}₩{abs(amount):,}"


@app.template_filter("money")
def money_filter(points):
    return format_money_from_points(points)


def _format_remainder_won_group(value, *, standalone=False):
    """0~9999 범위의 금액을 한국어 금액 보조문구용으로 표시합니다.

    - 97 -> 97
    - 5,000 단독 표기는 5,000으로 둡니다.
    - 75,000 같은 금액의 만 단위 뒤 5,000은 5천으로 짧게 붙입니다.
    - 9,097처럼 천 이하가 섞인 값은 9천97이 아니라 9,097로 읽기 쉽게 표시합니다.
    """
    value = int(value or 0)
    if value <= 0:
        return ""
    if standalone:
        return f"{value:,}"
    if value >= 1000 and value % 1000 == 0:
        return f"{value // 1000}천"
    return f"{value:,}"


def format_korean_won_from_points(points):
    """₩숫자 아래에 보일 짧은 한국어 금액 표기입니다.

    예:
    - 97 -> 97원
    - 7,500 -> 7,500원
    - 75,000 -> 7만5천원
    - 170,097 -> 17만 97원
    """
    amount = points_to_money_amount(points)
    if amount == 0:
        return "0원"

    sign = "-" if amount < 0 else ""
    value = abs(int(amount))

    if value < 10000:
        return f"{sign}{_format_remainder_won_group(value, standalone=True)}원"

    units = [
        (1000000000000, "조"),
        (100000000, "억"),
        (10000, "만"),
    ]
    parts = []
    remainder = value
    for unit_value, unit_name in units:
        if remainder >= unit_value:
            group, remainder = divmod(remainder, unit_value)
            parts.append(f"{group:,}{unit_name}")

    if remainder:
        small = _format_remainder_won_group(remainder, standalone=False)
        if small:
            # 7만5천원은 붙이고, 17만97원처럼 천 단위 미만은 숫자 그대로 붙입니다.
            parts.append(small)

    return f"{sign}{''.join(parts)}원"

@app.template_filter("money_ko")
def money_ko_filter(points):
    return format_korean_won_from_points(points)


def normalize_price_reason_text(reason):
    """가격 변동 사유 문구를 사용자에게 보이는 표현으로 정리합니다."""
    if reason is None:
        return reason

    text = str(reason)
    replacements = {
        "최근 출전 기록이 없어 등록 선수 가격 기준에서 제외": "KBO 등록이 말소된 선수: 등록 선수 가격 기준에서 제외",
        "말소/미등록 선수는 등록 선수 가격 기준에서 제외": "KBO 등록이 말소된 선수: 등록 선수 가격 기준에서 제외",
        "말소/미등록 상태로": "KBO 등록이 말소된 선수:",
        "말소/미등록/비활성 선수": "KBO 등록이 말소된 선수",
        "말소/미등록 선수": "KBO 등록이 말소된 선수",
        "비활성 선수": "KBO 등록이 말소된 선수",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def compact_price_reason_label(reason, change=None, performance_change=None):
    """선수 카드용 가격 변동 이유를 짧게 정리합니다."""
    text = normalize_price_reason_text(reason) or ""

    try:
        perf = float(performance_change or 0)
    except (TypeError, ValueError):
        perf = 0.0

    try:
        price_change = float(change or 0)
    except (TypeError, ValueError):
        price_change = 0.0

    if "KBO 등록이 말소된 선수" in text:
        return "등록 말소", "trend-down"

    if "성적 상승" in text or perf > 0 or price_change > 0:
        return "성적 상승", "trend-up"

    if "성적 하락" in text or perf < 0 or price_change < 0:
        return "성적 하락", "trend-down"

    if text or price_change == 0:
        return "가격 유지", "trend-same"

    return "-", "trend-same"


# ==========================================================
# 공통 helper
# ==========================================================

def set_team_notice(section, message, category="notice", problems=None):
    """
    팀 관련 알림을 session에 임시 저장합니다.
    """
    session["team_notice"] = {
        "section": section,
        "message": message,
        "category": category,
        "problems": problems or [],
    }


def pop_team_notice():
    """
    session에 저장된 팀 관련 알림을 한 번만 꺼냅니다.
    """
    return session.pop("team_notice", None)


def get_safe_next_url(default_endpoint, default_anchor=""):
    """
    POST 요청 후 원래 있던 위치로 돌아가기 위한 URL을 안전하게 가져옵니다.
    """
    next_url = request.form.get("next_url", "").strip()

    if next_url.startswith("/") and not next_url.startswith("//"):
        if default_anchor and "#" not in next_url:
            next_url += default_anchor
        return next_url

    return url_for(default_endpoint) + default_anchor



# ==========================================================
# 팀 편집 마감 helper
# ==========================================================

TEAM_EDIT_UNLOCK_HOUR = 23
TEAM_EDIT_LOCK_MESSAGE = "오늘 경기 시작으로 팀 편집이 마감되었습니다. 선수 영입/방출/C 지정/팀 확정은 밤 11시 이후 다시 가능합니다."
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul") if ZoneInfo is not None else None


def get_korea_now():
    """Return the current time in Korea for game-day lock decisions."""
    if KOREA_TIMEZONE is not None:
        return datetime.now(KOREA_TIMEZONE)
    return datetime.now()


def parse_team_edit_datetime(value, tzinfo=None):
    """Parse DB datetime text and attach KST tzinfo when the value is naive."""
    text = str(value or "").strip()
    if not text:
        return None

    parsed = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            pass

    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

    if parsed.tzinfo is None and tzinfo is not None:
        parsed = parsed.replace(tzinfo=tzinfo)
    return parsed


def format_lock_time(dt):
    if not dt:
        return None
    return dt.strftime("%H:%M")


def get_team_edit_lock_status(now=None):
    """
    Team editing is open until today's first KBO game starts, locked until
    23:00 KST, and open all day when there is no game today.
    """
    now = now or get_korea_now()
    today = now.date().isoformat()
    tzinfo = now.tzinfo
    unlock_at = datetime.combine(now.date(), datetime_time(TEAM_EDIT_UNLOCK_HOUR, 0, 0))
    if tzinfo is not None:
        unlock_at = unlock_at.replace(tzinfo=tzinfo)

    with get_conn() as conn:
        row = conn.execute("""
            SELECT MIN(scheduled_start_at) AS first_game_start
            FROM betting_games
            WHERE game_date = ?
              AND COALESCE(status, 'scheduled') NOT IN ('cancelled', 'postponed', 'void')
        """, (today,)).fetchone()

    first_game_start = parse_team_edit_datetime(row["first_game_start"] if row else None, tzinfo=tzinfo)

    base = {
        "today": today,
        "first_game_start": first_game_start,
        "first_game_start_display": format_lock_time(first_game_start),
        "unlock_at": unlock_at,
        "unlock_display": "밤 11시",
        "message": TEAM_EDIT_LOCK_MESSAGE,
    }

    if first_game_start is None:
        return {**base, "is_locked": False, "reason": "no_game"}

    if now < first_game_start:
        return {**base, "is_locked": False, "reason": "before_first_game"}

    if now >= unlock_at:
        return {**base, "is_locked": False, "reason": "after_unlock"}

    return {**base, "is_locked": True, "reason": "game_started"}


def redirect_if_team_edit_locked():
    """Redirect blocked team-edit actions back to /my-team with a notice."""
    lock_status = get_team_edit_lock_status()
    if not lock_status.get("is_locked"):
        return None

    set_team_notice(
        section="team",
        message=lock_status.get("message") or TEAM_EDIT_LOCK_MESSAGE,
        category="warning",
    )
    return redirect(url_for("my_team") + "#team-status")


def ensure_user_profile_columns():
    """
    프로필 응원팀 선택 기능에 필요한 users 컬럼을 안전하게 보장합니다.
    db.py를 먼저 실행하지 않아도 앱 실행 중 기존 DB를 삭제하지 않고 컬럼만 추가합니다.
    """
    with get_conn() as conn:
        rows = conn.execute("PRAGMA table_info(users);").fetchall()
        existing_columns = {row["name"] for row in rows}

        if "favorite_kbo_team" not in existing_columns:
            conn.execute("ALTER TABLE users ADD COLUMN favorite_kbo_team TEXT;")

        if "is_admin" not in existing_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0;")


def get_current_user():
    """
    현재 로그인한 사용자 정보를 가져옵니다.
    """
    user_id = session.get("user_id")

    if user_id is None:
        return None

    ensure_user_profile_columns()

    with get_conn() as conn:
        user = conn.execute("""
            SELECT
                id,
                username,
                display_name,
                favorite_kbo_team,
                COALESCE(is_admin, 0) AS is_admin,
                created_at,
                updated_at
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

    if user is None:
        session.clear()
        return None

    return dict(user)





def get_user_password_hash(user_id):
    """계정 설정 변경 전 현재 비밀번호 검증에 사용할 password_hash를 가져옵니다."""
    with get_conn() as conn:
        user = conn.execute("""
            SELECT id, password_hash
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

    if user is None:
        return None

    return user["password_hash"]


def verify_current_password(user_id, password):
    """현재 비밀번호가 맞는지 확인합니다."""
    if not password:
        return False

    password_hash = get_user_password_hash(user_id)
    if not password_hash:
        return False

    return check_password_hash(password_hash, password)


def delete_user_account_data(user_id):
    """
    회원탈퇴 시 해당 유저의 계정/팀/랭킹 기록을 실제로 삭제합니다.

    주의:
    - 선수/경기/가격/전체 KBO 데이터는 건드리지 않습니다.
    - 현재 탈퇴하는 유저에게 연결된 판타지 팀 기록만 삭제합니다.
    - 유저 랭킹은 fantasy_teams/users 기반이라 삭제 즉시 제외됩니다.
    """
    with get_conn() as conn:
        team_rows = conn.execute("""
            SELECT id
            FROM fantasy_teams
            WHERE user_id = ?
        """, (user_id,)).fetchall()
        team_ids = [int(row["id"]) for row in team_rows]

        daily_score_rows = conn.execute("""
            SELECT id
            FROM fantasy_team_daily_scores
            WHERE user_id = ?
        """, (user_id,)).fetchall()
        daily_score_ids = [int(row["id"]) for row in daily_score_rows]

        def delete_by_ids(sql_prefix, ids):
            if not ids:
                return
            placeholders = ",".join("?" for _ in ids)
            conn.execute(f"{sql_prefix} ({placeholders})", ids)

        delete_by_ids(
            "DELETE FROM fantasy_team_daily_player_scores WHERE team_daily_score_id IN",
            daily_score_ids
        )
        delete_by_ids(
            "DELETE FROM fantasy_team_daily_player_scores WHERE team_id IN",
            team_ids
        )

        conn.execute("""
            DELETE FROM fantasy_team_daily_player_scores
            WHERE user_id = ?
        """, (user_id,))

        delete_by_ids(
            "DELETE FROM fantasy_team_daily_scores WHERE team_id IN",
            team_ids
        )
        conn.execute("""
            DELETE FROM fantasy_team_daily_scores
            WHERE user_id = ?
        """, (user_id,))

        ensure_trade_bonus_tables(conn)
        conn.execute("""
            DELETE FROM fantasy_team_trade_bonus_events
            WHERE user_id = ?
        """, (user_id,))
        delete_by_ids(
            "DELETE FROM fantasy_team_trade_bonus_events WHERE team_id IN",
            team_ids
        )

        delete_by_ids(
            "DELETE FROM fantasy_team_players WHERE team_id IN",
            team_ids
        )
        conn.execute("""
            DELETE FROM fantasy_teams
            WHERE user_id = ?
        """, (user_id,))
        ensure_friend_tables(conn)
        conn.execute("""
            DELETE FROM user_friendships
            WHERE requester_id = ?
               OR addressee_id = ?
        """, (user_id, user_id))

        ensure_support_tables(conn)
        conn.execute("""
            DELETE FROM support_tickets
            WHERE user_id = ?
        """, (user_id,))

        ensure_betting_tables(conn)
        conn.execute("""
            DELETE FROM betting_ledger
            WHERE user_id = ?
        """, (user_id,))
        conn.execute("""
            DELETE FROM betting_bets
            WHERE user_id = ?
        """, (user_id,))

        conn.execute("""
            DELETE FROM users
            WHERE id = ?
        """, (user_id,))


def ensure_friend_tables(conn=None):
    """친구 요청/친구 관계 테이블을 기존 데이터를 지우지 않고 안전하게 보장합니다."""
    owns_connection = conn is None

    if owns_connection:
        ctx = get_conn()
        conn = ctx.__enter__()
    else:
        ctx = None

    try:
        conn.execute("""
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
                FOREIGN KEY (requester_id) REFERENCES users(id),
                FOREIGN KEY (addressee_id) REFERENCES users(id)
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_friendships_requester
            ON user_friendships(requester_id, status);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_friendships_addressee
            ON user_friendships(addressee_id, status);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_friendships_status
            ON user_friendships(status);
        """)
    finally:
        if owns_connection:
            ctx.__exit__(None, None, None)



def ensure_support_tables(conn=None):
    """문의하기 기능에 필요한 컬럼/테이블/인덱스를 안전하게 보장합니다."""
    owns_connection = conn is None

    if owns_connection:
        ctx = get_conn()
        conn = ctx.__enter__()
    else:
        ctx = None

    try:
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users);").fetchall()}
        if "is_admin" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0;")

        conn.execute("""
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

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_support_tickets_user
            ON support_tickets(user_id, created_at DESC);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_support_tickets_status
            ON support_tickets(status, created_at DESC);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_support_tickets_category
            ON support_tickets(category, created_at DESC);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_support_tickets_resolved_at
            ON support_tickets(status, resolved_at);
        """)
    finally:
        if owns_connection:
            ctx.__exit__(None, None, None)



def ensure_trade_bonus_tables(conn=None):
    """선수 방출 시 100.0 예산 한도 초과분을 방출 수익으로 전환하는 기록 테이블을 안전하게 보장합니다."""
    owns_connection = conn is None

    if owns_connection:
        ctx = get_conn()
        conn = ctx.__enter__()
    else:
        ctx = None

    try:
        conn.execute("""
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
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (team_id) REFERENCES fantasy_teams(id),
                FOREIGN KEY (registered_player_id) REFERENCES registered_players(id)
            );
        """)

        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(fantasy_team_trade_bonus_events);").fetchall()
        }
        if "roster_market_value_before" not in existing_columns:
            conn.execute("""
                ALTER TABLE fantasy_team_trade_bonus_events
                ADD COLUMN roster_market_value_before REAL NOT NULL DEFAULT 0;
            """)
        if "roster_excess_before_decimal" not in existing_columns:
            conn.execute("""
                ALTER TABLE fantasy_team_trade_bonus_events
                ADD COLUMN roster_excess_before_decimal REAL NOT NULL DEFAULT 0;
            """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_bonus_user_date
            ON fantasy_team_trade_bonus_events(user_id, event_date DESC);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_bonus_team_date
            ON fantasy_team_trade_bonus_events(team_id, event_date DESC);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_bonus_player
            ON fantasy_team_trade_bonus_events(registered_player_id, created_at DESC);
        """)
    finally:
        if owns_connection:
            ctx.__exit__(None, None, None)


def price_to_tenth_units(price_value):
    """소수점 가격을 0.1 단위 정수로 변환해 float 오차를 막습니다."""
    if price_value is None:
        return None

    try:
        value = float(price_value)
    except (TypeError, ValueError):
        return None

    return int(round(value * 10))


def calculate_release_trade_values(
    locked_price_decimal,
    current_market_price,
    roster_market_value_before,
    budget_limit=100.0,
):
    """방출 시 사용가능 예산 회복액과 방출 수익 포인트를 계산합니다.

    최종 규칙:
    - 방출 수익은 방출 직전 팀 가치가 100.0을 넘을 때만 발생합니다.
    - 여기서 팀 가치는 현재 로스터 선수들의 시장가 합계입니다. 사용가능 예산은 포함하지 않습니다.
    - 초과 수익은 min(선수 증가분, 방출 전 팀 가치 100.0 초과분)입니다.
    - 방출한 선수의 현재가 중 초과 수익으로 계산되지 않은 금액은 사용가능 예산으로 돌아옵니다.
    - locked_price_decimal은 선수 증가분 계산 기준으로만 사용하며, 예산 회복액 cap으로 쓰지 않습니다.
    """
    locked_units = price_to_tenth_units(locked_price_decimal)
    current_units = price_to_tenth_units(current_market_price)
    roster_units = price_to_tenth_units(roster_market_value_before)
    budget_units = price_to_tenth_units(budget_limit)

    if locked_units is None or locked_units <= 0:
        return None
    if current_units is None or current_units <= 0:
        return None
    if roster_units is None or roster_units < 0:
        return None
    if budget_units is None or budget_units <= 0:
        return None

    individual_profit_units = max(0, current_units - locked_units)
    roster_excess_units = max(0, roster_units - budget_units)

    # 방출 수익은 선수 증가분과 방출 직전 팀 가치 100.0 초과분 중 작은 값까지만 발생합니다.
    profit_units = min(individual_profit_units, roster_excess_units, current_units)

    # 선수 현재가 중 초과 수익으로 분리되지 않은 금액은 모두 사용가능 예산으로 돌아옵니다.
    refund_units = max(0, current_units - profit_units)
    cap_remainder_units = 0

    budget_refund = round(refund_units / 10.0, 1)
    realized_profit = round(profit_units / 10.0, 1)
    roster_excess_before = round(roster_excess_units / 10.0, 1)
    cap_remainder = 0.0
    bonus_points = float(profit_units * TRADE_BONUS_POINTS_PER_PRICE_TENTH)

    return {
        "locked_units": locked_units,
        "current_units": current_units,
        "roster_units": roster_units,
        "budget_units": budget_units,
        "roster_excess_units": roster_excess_units,
        "refund_units": refund_units,
        "profit_units": profit_units,
        "cap_remainder_units": cap_remainder_units,
        "budget_refund": budget_refund,
        "realized_profit": realized_profit,
        "cap_remainder": cap_remainder,
        "roster_market_value_before": round(roster_units / 10.0, 1),
        "roster_excess_before": roster_excess_before,
        "bonus_points": bonus_points,
    }


def calculate_strict_budget_state(budget_limit, acquisition_cost_total, raw_cash_balance=None):
    """팀 편집의 사용가능 예산 상태를 계산합니다.

    사용가능 예산은 DB의 cash_balance_decimal입니다.
    100.0은 시작 예산이며, 이후 방출/영입과 선수 시장가 변화에 따라 cash가 움직입니다.
    locked_price_decimal 합계는 선수별 손익 계산 기준으로만 쓰고, 사용가능 예산 cap으로 쓰지 않습니다.
    """
    try:
        budget_limit_number = round(float(budget_limit or 100.0), 1)
    except (TypeError, ValueError):
        budget_limit_number = 100.0

    try:
        acquisition_total = round(float(acquisition_cost_total or 0.0), 1)
    except (TypeError, ValueError):
        acquisition_total = 0.0

    # 참고값입니다. 실제 영입 가능 예산은 cash_balance_decimal입니다.
    strict_available_budget = round(max(0.0, budget_limit_number - acquisition_total), 1)

    if raw_cash_balance is None:
        raw_cash = strict_available_budget
    else:
        try:
            raw_cash = round(float(raw_cash_balance or 0.0), 1)
        except (TypeError, ValueError):
            raw_cash = 0.0

    raw_cash = round(max(0.0, raw_cash), 1)
    available_budget = raw_cash
    cash_over_cap_amount = 0.0
    acquisition_over_budget_amount = round(max(0.0, acquisition_total - budget_limit_number), 1)

    return {
        "budget_limit": budget_limit_number,
        "acquisition_cost_total": acquisition_total,
        "raw_cash_balance_decimal": raw_cash,
        "strict_available_budget": strict_available_budget,
        "available_budget": available_budget,
        "cash_over_cap_amount": cash_over_cap_amount,
        "acquisition_over_budget_amount": acquisition_over_budget_amount,
        "is_budget_state_valid": available_budget >= -0.0001,
    }
def get_user_wealth_points_from_conn(conn, user_id):
    """유저의 현재 총 자산 포인트를 같은 DB connection 안에서 계산합니다.

    총 자산 = 경기 수익 + 방출 수익 + 배팅 ledger 손익
    방출 수익은 fantasy_team_trade_bonus_events.user_id 기준으로 직접 합산합니다.
    따라서 팀 편집 중 방출로 수익이 생기면, 팀을 다시 확정하기 전에도
    헤더/자산 표시와 랭킹 계산에 바로 반영됩니다.
    배팅 stake는 betting_ledger에 음수로, 적중 payout/무효 환불은 양수로 기록됩니다.
    """
    if not user_id:
        return 0.0

    ensure_trade_bonus_tables(conn)
    ensure_betting_tables(conn)

    game_row = conn.execute("""
        SELECT COALESCE(SUM(ftds.total_points), 0) AS game_points
        FROM fantasy_team_daily_scores ftds
        JOIN fantasy_teams ft
          ON ft.id = ftds.team_id
        WHERE ft.user_id = ?
    """, (user_id,)).fetchone()

    bonus_row = conn.execute("""
        SELECT COALESCE(SUM(bonus_points), 0) AS trade_bonus_points
        FROM fantasy_team_trade_bonus_events
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    game_points = float(game_row["game_points"] or 0) if game_row is not None else 0.0
    trade_bonus_points = float(bonus_row["trade_bonus_points"] or 0) if bonus_row is not None else 0.0
    betting_wealth = get_betting_ledger_sum(conn, user_id)
    return round(game_points + trade_bonus_points + betting_wealth, 1)


def get_user_wealth_points(user_id):
    """로그인 유저의 총 재산 표시용 포인트를 계산합니다.

    총 재산 = 경기 수익 + 방출 수익 + 배팅 손익
    표시 단위는 템플릿에서 MyPick 머니(₩)로 변환합니다.
    """
    if not user_id:
        return 0.0

    with get_conn() as conn:
        return get_user_wealth_points_from_conn(conn, user_id)


def support_category_label(category):
    return SUPPORT_CATEGORY_LABELS.get(str(category or "").strip(), "기타")


def support_status_label(status):
    return SUPPORT_STATUS_LABELS.get(str(status or "").strip(), "접수됨")


def support_status_tone(status):
    return SUPPORT_STATUS_TONE.get(str(status or "").strip(), "open")


def purge_expired_resolved_support_tickets(conn=None):
    """
    처리완료(resolved) 상태가 된 지 24시간이 지난 문의를 영구 삭제합니다.

    주의:
    - 삭제 대상은 support_tickets row뿐입니다.
    - closed 상태는 자동 삭제하지 않고, 관리자가 필요할 때 직접 삭제합니다.
    - KBO 선수/경기/가격/팀 데이터는 건드리지 않습니다.
    """
    owns_connection = conn is None

    if owns_connection:
        ctx = get_conn()
        conn = ctx.__enter__()
    else:
        ctx = None

    try:
        ensure_support_tables(conn)
        cursor = conn.execute("""
            DELETE FROM support_tickets
            WHERE status = 'resolved'
              AND resolved_at IS NOT NULL
              AND resolved_at <= datetime('now', '-24 hours')
        """)
        return int(cursor.rowcount or 0)
    finally:
        if owns_connection:
            ctx.__exit__(None, None, None)


def decorate_support_ticket(row):
    if row is None:
        return None

    item = dict(row)
    item["category_label"] = support_category_label(item.get("category"))
    item["status_label"] = support_status_label(item.get("status"))
    item["status_tone"] = support_status_tone(item.get("status"))
    item["created_at_display"] = format_datetime_for_display(item.get("created_at"))
    item["updated_at_display"] = format_datetime_for_display(item.get("updated_at"))
    item["resolved_at_display"] = format_datetime_for_display(item.get("resolved_at"))
    return item


def get_support_ticket_counts(conn, user_id=None):
    where = ""
    params = []
    if user_id is not None:
        where = "WHERE user_id = ?"
        params.append(user_id)

    rows = conn.execute(f"""
        SELECT status, COUNT(*) AS count
        FROM support_tickets
        {where}
        GROUP BY status
    """, params).fetchall()

    counts = {status: 0 for status, _ in SUPPORT_STATUSES}
    total = 0
    for row in rows:
        status = row["status"]
        count = int(row["count"] or 0)
        counts[status] = count
        total += count

    counts["total"] = total
    return counts


def get_user_support_tickets(user_id):
    ensure_support_tables()
    with get_conn() as conn:
        purge_expired_resolved_support_tickets(conn)
        rows = conn.execute("""
            SELECT
                st.*
            FROM support_tickets st
            WHERE st.user_id = ?
            ORDER BY st.created_at DESC, st.id DESC
        """, (user_id,)).fetchall()
        counts = get_support_ticket_counts(conn, user_id=user_id)

    return {
        "tickets": [decorate_support_ticket(row) for row in rows],
        "counts": counts,
    }


def get_support_ticket_for_user(ticket_id, user_id):
    ensure_support_tables()
    with get_conn() as conn:
        purge_expired_resolved_support_tickets(conn)
        row = conn.execute("""
            SELECT st.*
            FROM support_tickets st
            WHERE st.id = ?
              AND st.user_id = ?
        """, (ticket_id, user_id)).fetchone()

    return decorate_support_ticket(row)


def get_admin_support_tickets(status_filter="all", category_filter="all", search_query=""):
    ensure_support_tables()

    clauses = []
    params = []

    if status_filter != "all" and status_filter in SUPPORT_STATUS_LABELS:
        clauses.append("st.status = ?")
        params.append(status_filter)

    if category_filter != "all" and category_filter in SUPPORT_CATEGORY_LABELS:
        clauses.append("st.category = ?")
        params.append(category_filter)

    search_query = (search_query or "").strip()
    if search_query:
        clauses.append("(st.title LIKE ? OR st.message LIKE ? OR u.username LIKE ? OR u.display_name LIKE ?)")
        like_query = f"%{search_query}%"
        params.extend([like_query, like_query, like_query, like_query])

    where_sql = ""
    if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)

    with get_conn() as conn:
        purge_expired_resolved_support_tickets(conn)
        rows = conn.execute(f"""
            SELECT
                st.*,
                u.username,
                COALESCE(u.display_name, u.username) AS user_display_name
            FROM support_tickets st
            JOIN users u
              ON u.id = st.user_id
            {where_sql}
            ORDER BY
                CASE st.status
                    WHEN 'open' THEN 0
                    WHEN 'reviewing' THEN 1
                    WHEN 'resolved' THEN 2
                    WHEN 'closed' THEN 3
                    ELSE 4
                END,
                st.created_at DESC,
                st.id DESC
        """, params).fetchall()
        counts = get_support_ticket_counts(conn)

    return {
        "tickets": [decorate_support_ticket(row) for row in rows],
        "counts": counts,
    }


def get_admin_support_ticket(ticket_id):
    ensure_support_tables()
    with get_conn() as conn:
        purge_expired_resolved_support_tickets(conn)
        row = conn.execute("""
            SELECT
                st.*,
                u.username,
                COALESCE(u.display_name, u.username) AS user_display_name,
                u.favorite_kbo_team
            FROM support_tickets st
            JOIN users u
              ON u.id = st.user_id
            WHERE st.id = ?
        """, (ticket_id,)).fetchone()

    return decorate_support_ticket(row)


def normalize_support_form(form):
    category = (form.get("category") or "").strip()
    title = (form.get("title") or "").strip()
    message = (form.get("message") or "").strip()
    page_url = (form.get("page_url") or "").strip()

    errors = []

    if category not in SUPPORT_CATEGORY_LABELS:
        errors.append("문의 유형을 선택해주세요.")

    if not title:
        errors.append("제목을 입력해주세요.")
    elif len(title) > SUPPORT_TITLE_MAX_LENGTH:
        errors.append(f"제목은 {SUPPORT_TITLE_MAX_LENGTH}자 이하로 입력해주세요.")

    if not message:
        errors.append("문의 내용을 입력해주세요.")
    elif len(message) > SUPPORT_MESSAGE_MAX_LENGTH:
        errors.append(f"문의 내용은 {SUPPORT_MESSAGE_MAX_LENGTH}자 이하로 입력해주세요.")

    if page_url:
        if len(page_url) > SUPPORT_PAGE_URL_MAX_LENGTH:
            errors.append(f"관련 페이지 주소는 {SUPPORT_PAGE_URL_MAX_LENGTH}자 이하로 입력해주세요.")
        elif not page_url.startswith("/") and not page_url.startswith("http://") and not page_url.startswith("https://"):
            errors.append("관련 페이지는 /team/edit 같은 경로 또는 http(s) 주소로 입력해주세요.")

    return {
        "category": category,
        "title": title,
        "message": message,
        "page_url": page_url,
        "errors": errors,
    }

def get_friend_relation(current_user_id, target_user_id):
    """현재 유저와 대상 유저의 친구 관계 상태를 화면용으로 반환합니다."""
    if not current_user_id or not target_user_id:
        return {"state": "guest", "label": "로그인 필요"}

    current_user_id = int(current_user_id)
    target_user_id = int(target_user_id)

    if current_user_id == target_user_id:
        return {"state": "self", "label": "내 프로필"}

    ensure_friend_tables()

    with get_conn() as conn:
        row = conn.execute("""
            SELECT *
            FROM user_friendships
            WHERE (requester_id = ? AND addressee_id = ?)
               OR (requester_id = ? AND addressee_id = ?)
            ORDER BY
                CASE status WHEN 'accepted' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
                updated_at DESC,
                id DESC
            LIMIT 1
        """, (current_user_id, target_user_id, target_user_id, current_user_id)).fetchone()

    if row is None:
        return {"state": "none", "label": "친구 아님"}

    item = dict(row)
    status = item.get("status")

    if status == "accepted":
        return {"state": "accepted", "label": "친구", "request": item}

    if status == "pending":
        if int(item.get("requester_id") or 0) == current_user_id:
            return {"state": "outgoing_pending", "label": "요청 보냄", "request": item}
        return {"state": "incoming_pending", "label": "받은 요청", "request": item}

    return {"state": "none", "label": "친구 아님"}


def create_friend_request(requester_id, addressee_id):
    """중복/역방향 요청을 안전하게 확인한 뒤 친구 요청을 생성합니다."""
    requester_id = int(requester_id)
    addressee_id = int(addressee_id)

    if requester_id == addressee_id:
        return "self"

    ensure_friend_tables()
    relation = get_friend_relation(requester_id, addressee_id)
    state = relation.get("state")

    if state in ["accepted", "outgoing_pending", "incoming_pending"]:
        return state

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO user_friendships (requester_id, addressee_id, status)
            VALUES (?, ?, 'pending')
        """, (requester_id, addressee_id))

    return "created"


def get_friend_user_ids(user_id, include_self=True):
    """친구 랭킹에 사용할 현재 유저 + 수락된 친구 user_id 목록을 반환합니다."""
    ensure_friend_tables()
    user_id = int(user_id)

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                CASE
                    WHEN requester_id = ? THEN addressee_id
                    ELSE requester_id
                END AS friend_user_id
            FROM user_friendships
            WHERE status = 'accepted'
              AND (requester_id = ? OR addressee_id = ?)
            ORDER BY updated_at DESC, id DESC
        """, (user_id, user_id, user_id)).fetchall()

    ids = []
    if include_self:
        ids.append(user_id)

    for row in rows:
        friend_id = int(row["friend_user_id"] or 0)
        if friend_id and friend_id not in ids:
            ids.append(friend_id)

    return ids


def get_friend_records(user_id):
    """친구 관리 페이지용 받은 요청/보낸 요청/현재 친구 목록을 반환합니다."""
    ensure_friend_tables()
    user_id = int(user_id)

    def decorate_people(rows):
        people = []
        for row in rows:
            item = dict(row)
            favorite_team = normalize_kbo_team(item.get("favorite_kbo_team"))
            item["display_name"] = item.get("display_name") or item.get("username") or "-"
            item["favorite_kbo_team"] = favorite_team
            item["favorite_team_meta"] = get_team_meta(favorite_team) if favorite_team else None
            item["total_points"] = round(float(item.get("total_points") or 0), 1)
            item["recent_points"] = round(float(item.get("recent_points") or 0), 1)
            item["profile_url"] = url_for("public_profile", user_id=item.get("user_id"))
            people.append(item)
        return people

    with get_conn() as conn:
        ensure_trade_bonus_tables(conn)
        incoming_rows = conn.execute("""
            SELECT
                f.id AS request_id,
                f.created_at AS requested_at,
                u.id AS user_id,
                u.username,
                u.display_name,
                u.favorite_kbo_team,
                COALESCE(total_summary.total_points, 0) + COALESCE(trade_bonus_summary.total_bonus_points, 0) AS total_points,
                COALESCE(recent_score.total_points, 0) AS recent_points
            FROM user_friendships f
            JOIN users u
              ON u.id = f.requester_id
            LEFT JOIN fantasy_teams ft
              ON ft.user_id = u.id
            LEFT JOIN (
                SELECT team_id, SUM(total_points) AS total_points
                FROM fantasy_team_daily_scores
                GROUP BY team_id
            ) total_summary
              ON total_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(bonus_points) AS total_bonus_points
                FROM fantasy_team_trade_bonus_events
                GROUP BY team_id
            ) trade_bonus_summary
              ON trade_bonus_summary.team_id = ft.id
            LEFT JOIN fantasy_team_daily_scores recent_score
              ON recent_score.team_id = ft.id
             AND recent_score.game_date = (SELECT MAX(game_date) FROM fantasy_team_daily_scores)
            WHERE f.addressee_id = ?
              AND f.status = 'pending'
            ORDER BY f.created_at DESC, f.id DESC
        """, (user_id,)).fetchall()

        outgoing_rows = conn.execute("""
            SELECT
                f.id AS request_id,
                f.created_at AS requested_at,
                u.id AS user_id,
                u.username,
                u.display_name,
                u.favorite_kbo_team,
                COALESCE(total_summary.total_points, 0) + COALESCE(trade_bonus_summary.total_bonus_points, 0) AS total_points,
                COALESCE(recent_score.total_points, 0) AS recent_points
            FROM user_friendships f
            JOIN users u
              ON u.id = f.addressee_id
            LEFT JOIN fantasy_teams ft
              ON ft.user_id = u.id
            LEFT JOIN (
                SELECT team_id, SUM(total_points) AS total_points
                FROM fantasy_team_daily_scores
                GROUP BY team_id
            ) total_summary
              ON total_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(bonus_points) AS total_bonus_points
                FROM fantasy_team_trade_bonus_events
                GROUP BY team_id
            ) trade_bonus_summary
              ON trade_bonus_summary.team_id = ft.id
            LEFT JOIN fantasy_team_daily_scores recent_score
              ON recent_score.team_id = ft.id
             AND recent_score.game_date = (SELECT MAX(game_date) FROM fantasy_team_daily_scores)
            WHERE f.requester_id = ?
              AND f.status = 'pending'
            ORDER BY f.created_at DESC, f.id DESC
        """, (user_id,)).fetchall()

        friend_rows = conn.execute("""
            SELECT
                f.id AS friendship_id,
                f.updated_at AS friended_at,
                u.id AS user_id,
                u.username,
                u.display_name,
                u.favorite_kbo_team,
                COALESCE(total_summary.total_points, 0) + COALESCE(trade_bonus_summary.total_bonus_points, 0) AS total_points,
                COALESCE(recent_score.total_points, 0) AS recent_points
            FROM user_friendships f
            JOIN users u
              ON u.id = CASE WHEN f.requester_id = ? THEN f.addressee_id ELSE f.requester_id END
            LEFT JOIN fantasy_teams ft
              ON ft.user_id = u.id
            LEFT JOIN (
                SELECT team_id, SUM(total_points) AS total_points
                FROM fantasy_team_daily_scores
                GROUP BY team_id
            ) total_summary
              ON total_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(bonus_points) AS total_bonus_points
                FROM fantasy_team_trade_bonus_events
                GROUP BY team_id
            ) trade_bonus_summary
              ON trade_bonus_summary.team_id = ft.id
            LEFT JOIN fantasy_team_daily_scores recent_score
              ON recent_score.team_id = ft.id
             AND recent_score.game_date = (SELECT MAX(game_date) FROM fantasy_team_daily_scores)
            WHERE f.status = 'accepted'
              AND (f.requester_id = ? OR f.addressee_id = ?)
            ORDER BY f.updated_at DESC, f.id DESC
        """, (user_id, user_id, user_id)).fetchall()

    return {
        "incoming_requests": decorate_people(incoming_rows),
        "outgoing_requests": decorate_people(outgoing_rows),
        "friends": decorate_people(friend_rows),
    }


def get_user_by_id(user_id):
    """공개 프로필 조회용으로 특정 사용자 정보를 가져옵니다."""
    ensure_user_profile_columns()

    with get_conn() as conn:
        user = conn.execute("""
            SELECT
                id,
                username,
                display_name,
                favorite_kbo_team,
                created_at,
                updated_at
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

    if user is None:
        return None

    return dict(user)


def build_profile_context_for_user(profile_user, selected_month=None):
    """내 프로필/공개 프로필이 같은 실제 점수 계산 기준을 사용하도록 공통 데이터를 만듭니다."""
    team = get_my_team(profile_user["id"])

    summary = None
    validation = None
    roster_rows = []
    team_score_summary = None
    recent_team_scores = []
    monthly_summary = get_team_monthly_summary(None)
    player_highlights = get_profile_player_highlights(None)
    profile_status = build_profile_status(None, None, None, None)
    best_daily_rank = None

    if team is not None:
        summary = get_team_summary(
            team_id=team["id"],
            budget_limit=team["budget_limit"]
        )
        validation = validate_team_roster(summary, team["budget_limit"])
        roster_rows = build_roster_rows(summary)
        team_score_summary = get_team_score_summary(team["id"])
        recent_team_scores = get_recent_team_scores(team["id"], limit=5)
        monthly_summary = get_team_monthly_summary(team["id"], selected_month)
        player_highlights = get_profile_player_highlights(team["id"])
        profile_status = build_profile_status(team, summary, validation, team_score_summary)
        best_daily_rank = get_best_daily_rank(team["id"])
        profile_honors = get_profile_honors(team["id"], profile_user["id"]) or []
    else:
        profile_honors = []

    favorite_team = normalize_kbo_team(profile_user.get("favorite_kbo_team"))

    return {
        "user": profile_user,
        "team": team,
        "summary": summary,
        "validation": validation,
        "roster_rows": roster_rows,
        "team_score_summary": team_score_summary,
        "recent_team_scores": recent_team_scores,
        "monthly_summary": monthly_summary,
        "player_highlights": player_highlights,
        "profile_status": profile_status,
        "best_daily_rank": best_daily_rank,
        "profile_honors": profile_honors or [],
        "favorite_team": favorite_team,
        "favorite_team_meta": get_team_meta(favorite_team) if favorite_team else None,
        "kbo_team_options": get_kbo_team_options(),
    }

def login_required(view_func):
    """
    로그인이 필요한 페이지를 보호하는 데코레이터입니다.
    """
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if session.get("user_id") is None:
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for("login", next=next_url))

        return view_func(*args, **kwargs)

    return wrapped_view


def admin_required(view_func):
    """관리자 전용 페이지를 보호합니다."""
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if session.get("user_id") is None:
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for("login", next=next_url))

        current_user = get_current_user()
        if not current_user or int(current_user.get("is_admin") or 0) != 1:
            abort(403)

        return view_func(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_current_user():
    """
    모든 템플릿에서 current_user와 화면 표시 helper를 사용할 수 있게 합니다.
    """
    current_user = get_current_user()
    current_user_wealth_points = get_user_wealth_points(current_user["id"]) if current_user else 0.0

    return {
        "current_user": current_user,
        "current_user_wealth_points": current_user_wealth_points,
        "get_team_meta": get_team_meta,
        "position_type_label": position_type_label,
        "roster_row_by_slot": roster_row_by_slot,
        "clamp_percent": clamp_percent,
        "score_value_class": score_value_class,
        "format_money_from_points": format_money_from_points,
        "format_game_date_for_display": format_game_date_for_display,
        "format_datetime_for_display": format_datetime_for_display,
        "MAX_PLAYER_PRICE": MAX_PLAYER_PRICE,
        "support_category_label": support_category_label,
        "support_status_label": support_status_label,
        "support_status_tone": support_status_tone,
    }


def get_latest_price_date():
    """
    market_daily_v3 기준 최신 가격 기준일을 가져옵니다.
    """
    with get_conn() as conn:
        row = conn.execute("""
            SELECT MAX(basis_date) AS latest_price_date
            FROM player_prices
            WHERE basis_source = ?
        """, (BASIS_SOURCE,)).fetchone()

    if row is None:
        return None

    return row["latest_price_date"]


_PLAYER_LISTING_PERFORMANCE_INDEXES_READY = False


def ensure_player_listing_performance_indexes():
    """
    선수 검색/선수 랭킹에서 반복적으로 쓰는 최신 가격·최신 경기 조회용
    보조 인덱스를 안전하게 준비합니다.

    기존 데이터는 건드리지 않고 CREATE INDEX IF NOT EXISTS만 실행합니다.
    첫 요청에서 한 번만 확인하고, 이후 요청에서는 바로 넘어갑니다.
    """
    global _PLAYER_LISTING_PERFORMANCE_INDEXES_READY

    if _PLAYER_LISTING_PERFORMANCE_INDEXES_READY:
        return

    with get_conn() as conn:
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_adjustments_latest_lookup
            ON player_price_adjustments(
                basis_source,
                is_applied,
                registered_player_id,
                id DESC
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_scores_latest_lookup
            ON fantasy_daily_scores(
                game_date,
                player_name,
                team,
                position_type
            )
        """)

    _PLAYER_LISTING_PERFORMANCE_INDEXES_READY = True


def normalize_market_price_value(value):
    """화면/예산 계산에 쓸 수 있는 양수 시장가만 반환합니다."""
    if value is None:
        return None
    try:
        price = round(float(value), 1)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None
    return price


def fetch_market_price_record(conn, registered_player_id=None, player_name=None, team=None, fantasy_position_type=None):
    """
    market_daily_v3의 최신 선수 가격을 안전하게 찾습니다.

    1순위: registered_players.id와 정확히 연결된 최신 가격
    2순위: 같은 이름+팀+타자/투수 구분의 최신 가격

    이름+팀만으로 fallback하면 동명이인/투타 중복에서 잘못된 가격이 붙을 수 있으므로
    fantasy_position_type까지 반드시 같이 맞춥니다. 그래도 없으면 None을 반환하고
    0.0으로 대체하지 않습니다.
    """
    if registered_player_id is not None:
        try:
            registered_player_id = int(registered_player_id)
        except (TypeError, ValueError):
            registered_player_id = None

    if registered_player_id:
        row = conn.execute("""
            SELECT
                pp.registered_player_id,
                pp.player_name,
                pp.team,
                pp.fantasy_position_type,
                pp.price_role,
                pp.tier,
                pp.price,
                pp.price_decimal,
                pp.external_score,
                pp.external_rank,
                pp.basis_source,
                pp.basis_date,
                'registered_player_id' AS price_resolution
            FROM player_prices pp
            WHERE pp.basis_source = ?
              AND pp.registered_player_id = ?
              AND COALESCE(pp.price_decimal, pp.price) IS NOT NULL
              AND COALESCE(pp.price_decimal, pp.price) > 0
            ORDER BY pp.basis_date DESC, pp.id DESC
            LIMIT 1
        """, (BASIS_SOURCE, registered_player_id)).fetchone()
        if row is not None:
            return dict(row)

    if player_name and team and fantasy_position_type:
        row = conn.execute("""
            SELECT
                pp.registered_player_id,
                pp.player_name,
                pp.team,
                pp.fantasy_position_type,
                pp.price_role,
                pp.tier,
                pp.price,
                pp.price_decimal,
                pp.external_score,
                pp.external_rank,
                pp.basis_source,
                pp.basis_date,
                'name_team_type_fallback' AS price_resolution
            FROM player_prices pp
            WHERE pp.basis_source = ?
              AND pp.player_name = ?
              AND pp.team = ?
              AND pp.fantasy_position_type = ?
              AND COALESCE(pp.price_decimal, pp.price) IS NOT NULL
              AND COALESCE(pp.price_decimal, pp.price) > 0
            ORDER BY pp.basis_date DESC, pp.id DESC
            LIMIT 1
        """, (BASIS_SOURCE, player_name, team, fantasy_position_type)).fetchone()
        if row is not None:
            return dict(row)

    return None


def apply_market_price_record(player, *, price_key="price", current_key=None):
    """
    player dict에 최신 시장가를 적용합니다.
    가격이 없을 때는 0.0을 넣지 않고 None/가격 없음 상태로 둡니다.
    """
    if not player:
        return player

    registered_player_id = player.get("registered_player_id") or player.get("id")
    player_name = player.get("player_name") or player.get("name")
    team = player.get("team")
    fantasy_position_type = player.get("fantasy_position_type") or player.get("position_type")

    # 선수 검색/랭킹/내 팀 조회 SQL에서 이미 market_daily_v3 최신 가격을
    # registered_player_id 기준으로 JOIN한 경우에는 선수마다 DB를 다시 열지 않습니다.
    # 기존에는 화면에 50명만 보여도 전체 후보를 꾸미는 과정에서 선수 수만큼
    # 추가 가격 조회가 발생해 입장 속도가 느려질 수 있었습니다.
    joined_price = normalize_market_price_value(player.get("price_decimal"))
    if joined_price is None:
        joined_price = normalize_market_price_value(player.get(price_key))
    if joined_price is None and price_key != "price":
        joined_price = normalize_market_price_value(player.get("price"))

    joined_basis_date = (
        player.get("basis_date")
        or player.get("price_basis_date")
        or player.get("locked_price_basis_date")
    )

    if joined_price is not None and joined_basis_date:
        player[price_key] = joined_price
        if current_key:
            player[current_key] = joined_price
        player["market_price"] = joined_price
        if player.get("price_integer") is None:
            player["price_integer"] = player.get("price")
        if player.get("price_decimal") is None:
            player["price_decimal"] = joined_price
        if "price_basis_date" in player:
            player["price_basis_date"] = joined_basis_date
        player["basis_date"] = joined_basis_date
        player["basis_source"] = player.get("basis_source") or BASIS_SOURCE
        player["is_price_available"] = True
        player["price_missing_label"] = ""
        player["price_resolution"] = player.get("price_resolution") or "registered_player_id"
        return player

    with get_conn() as conn:
        price_record = fetch_market_price_record(
            conn,
            registered_player_id=registered_player_id,
            player_name=player_name,
            team=team,
            fantasy_position_type=fantasy_position_type,
        )

    if price_record is None:
        player[price_key] = None
        if current_key:
            player[current_key] = None
        player["market_price"] = None
        player["price"] = None if price_key == "price" else player.get("price")
        player["price_integer"] = None
        player["price_decimal"] = None
        player["price_role"] = player.get("price_role")
        player["tier"] = player.get("tier")
        player["basis_source"] = None
        player["basis_date"] = None
        if "price_basis_date" in player:
            player["price_basis_date"] = None
        player["is_price_available"] = False
        player["price_missing_label"] = "가격 없음"
        player["price_resolution"] = None
        return player

    price = normalize_market_price_value(price_record.get("price_decimal"))
    if price is None:
        price = normalize_market_price_value(price_record.get("price"))

    if price is None:
        player[price_key] = None
        if current_key:
            player[current_key] = None
        player["market_price"] = None
        player["is_price_available"] = False
        player["price_missing_label"] = "가격 없음"
        player["price_resolution"] = None
        return player

    player[price_key] = price
    if current_key:
        player[current_key] = price
    player["market_price"] = price
    player["price_integer"] = price_record.get("price")
    player["price_decimal"] = price_record.get("price_decimal")
    player["price_role"] = price_record.get("price_role")
    player["tier"] = price_record.get("tier")
    player["external_score"] = price_record.get("external_score")
    player["external_rank"] = price_record.get("external_rank")
    player["basis_source"] = price_record.get("basis_source")
    player["basis_date"] = price_record.get("basis_date")
    if "price_basis_date" in player:
        player["price_basis_date"] = price_record.get("basis_date")
    player["is_price_available"] = True
    player["price_missing_label"] = ""
    player["price_resolution"] = price_record.get("price_resolution")
    return player



def registered_player_identity_key(player):
    """Return a stable identity key that keeps true same-name KBO players separate.

    MYPICK PLAYER ID IDENTITY FIX 2026-06-05

    Older screens deduped / excluded players by name+team+type only. That can hide
    legitimate same-name players on the same team, especially pitchers. Prefer
    KBO player_id when present, and fall back to name+team+type for legacy rows.
    """
    if not player:
        return ("empty", None)

    position_type = player.get("fantasy_position_type") or player.get("position_type")
    player_id = player.get("player_id") or player.get("kbo_player_id")

    if player_id is not None and str(player_id).strip():
        return ("player_id", str(player_id).strip(), position_type)

    return (
        "name_team_type",
        player.get("name") or player.get("player_name"),
        player.get("team"),
        position_type,
    )


def players_refer_to_same_registered_identity(left, right):
    return registered_player_identity_key(left) == registered_player_identity_key(right)


def resolve_pitcher_display_detail_position(detail_position=None, roster_position=None, price_role=None):
    """Resolve pitcher card label without contradicting filters.

    MYPICK PITCHER DISPLAY BADGE FIX 2026-06-05

    A pitcher can have a temporary market price role or a recent spot start, but
    the search/category badge should reflect registered detail_position first.
    This prevents a player filtered as 불펜투수 from being displayed as 선발투수.
    """
    detail = str(detail_position or "").strip()
    roster = str(roster_position or "").strip()

    if detail in {"선발투수", "불펜투수"}:
        return detail

    if roster in {"선발투수", "불펜투수"}:
        return roster

    if price_role == "starting_pitcher":
        return "선발투수"
    if price_role == "bullpen_pitcher":
        return "불펜투수"

    if detail and not detail_position_is_empty(detail) and detail != "타자":
        return detail

    return "투수"


def dedupe_registered_player_rows(players):
    """
    같은 이름+팀+타자/투수 구분의 registered_players 중복 row가 화면에 여러 번
    보이지 않게 대표 row 하나만 남깁니다.

    우선순위:
    1) 현재 KBO 등록 선수
    2) 가격이 있는 선수
    3) registered_player_id 정확 가격 row가 있는 선수
    4) 시즌 누적/최근 점수가 높은 선수
    5) 더 오래된 id(가격 history가 붙어 있는 기존 row)
    """
    best_by_key = {}

    def score(player):
        price_resolution = player.get("price_resolution") or ""
        return (
            1 if int(player.get("is_active") or 0) == 1 else 0,
            1 if player.get("price") is not None else 0,
            1 if price_resolution == "registered_player_id" else 0,
            float(player.get("cumulative_points") or 0),
            float(player.get("total_points") or 0),
            -int(player.get("id") or player.get("registered_player_id") or 0),
        )

    for player in players:
        key = registered_player_identity_key(player)
        if key not in best_by_key or score(player) > score(best_by_key[key]):
            best_by_key[key] = player

    return list(best_by_key.values())


def get_latest_synced_game_date():
    """
    fantasy_daily_scores에 저장된 최신 경기 날짜를 가져옵니다.
    """
    with get_conn() as conn:
        row = conn.execute("""
            SELECT MAX(game_date) AS latest_game_date
            FROM fantasy_daily_scores
        """).fetchone()

    if row is None:
        return None

    return row["latest_game_date"]


def get_latest_registered_source_date():
    """
    registered_players에 저장된 최신 KBO 등록 현황 기준 날짜를 가져옵니다.

    이 날짜가 최신 경기 날짜와 같으면 화면/가격에서 KBO 등록 명단 기준을 엄격하게 사용합니다.
    이 날짜가 최신 경기 날짜와 다르면 등록 현황이 경기 날짜와 어긋난 상황이므로,
    해당 경기일에 실제 출전한 선수는 말소로 잘못 표시하지 않도록 fallback을 허용합니다.
    """
    with get_conn() as conn:
        row = conn.execute("""
            SELECT MAX(source_date) AS latest_source_date
            FROM registered_players
            WHERE source_date IS NOT NULL
        """).fetchone()

    if row is None:
        return None

    return row["latest_source_date"]


def get_player_recent_market_activity(player_name, team, position_type, basis_date=None):
    """
    기준일 주변 실제 출전/등판 기록을 조회합니다.

    중요: 이 함수의 결과만으로 말소/등록 상태를 결정하지 않습니다.
    최종 말소 표시는 KBO 등록 현황 날짜와 최신 경기 날짜가 일치하면
    registered_players.is_active를 그대로 따릅니다.
    이 기록은 등록 현황 날짜가 경기 날짜와 어긋난 경우에만
    최신 경기 출전 선수를 잘못 말소 처리하지 않기 위한 보조 자료입니다.
    """
    basis_date = basis_date or get_latest_synced_game_date()
    if not basis_date:
        return {
            "is_recent_market_active": False,
            "recent_activity_games": 0,
            "recent_activity_last_game_date": None,
            "recent_start_count_14d": 0,
            "market_activity_reason": "no_game_date",
        }

    with get_conn() as conn:
        if position_type == "pitcher":
            row = conn.execute("""
                SELECT COUNT(*) AS recent_games, MAX(game_date) AS last_game_date
                FROM fantasy_daily_scores
                WHERE player_name = ?
                  AND team = ?
                  AND position_type = 'pitcher'
                  AND game_date BETWEEN date(?, '-6 day') AND ?
            """, (player_name, team, basis_date, basis_date)).fetchone()

            start_row = conn.execute("""
                SELECT COUNT(*) AS recent_start_count
                FROM raw_pitcher_stats
                WHERE player_name = ?
                  AND team = ?
                  AND game_date BETWEEN date(?, '-13 day') AND ?
                  AND is_starting_pitcher = 1
            """, (player_name, team, basis_date, basis_date)).fetchone()

            recent_games = int(row["recent_games"] or 0) if row else 0
            recent_start_count = int(start_row["recent_start_count"] or 0) if start_row else 0
            last_game_date = row["last_game_date"] if row else None
        else:
            row = conn.execute("""
                SELECT COUNT(*) AS recent_games, MAX(game_date) AS last_game_date
                FROM fantasy_daily_scores
                WHERE player_name = ?
                  AND team = ?
                  AND position_type = 'batter'
                  AND game_date BETWEEN date(?, '-6 day') AND ?
            """, (player_name, team, basis_date, basis_date)).fetchone()

            recent_games = int(row["recent_games"] or 0) if row else 0
            recent_start_count = 0
            last_game_date = row["last_game_date"] if row else None

    if recent_start_count > 0:
        reason = "recent_14_days_starting_pitcher"
    elif recent_games > 0:
        reason = "recent_7_days_appearance"
    else:
        reason = "no_recent_appearance"

    return {
        "is_recent_market_active": recent_games > 0 or recent_start_count > 0,
        "recent_activity_games": recent_games,
        "recent_activity_last_game_date": last_game_date,
        "recent_start_count_14d": recent_start_count,
        "market_activity_reason": reason,
    }


def decorate_market_status(player):
    """
    화면용 등록/말소 상태를 계산합니다.

    최종 기준:
    1. KBO 등록 현황 기준 날짜가 최신 경기 날짜와 같으면
       registered_players.is_active를 엄격하게 따릅니다.
       - is_active=1 -> 일반 선수
       - is_active=0 -> 말소 선수
    2. KBO 등록 현황 기준 날짜가 최신 경기 날짜와 다르면
       등록 현황이 아직 해당 경기일 기준으로 업데이트되지 않았을 수 있으므로,
       최신 경기일에 실제 출전/등판한 선수만 임시로 일반 선수처럼 표시합니다.

    즉, 최근 7일 출전 기록만으로 말소 표시를 숨기지 않습니다.
    fallback은 오직 "등록 현황 날짜 불일치 + 최신 경기일 출전"일 때만 적용합니다.
    """
    if not player:
        return player

    name = player.get("player_name") or player.get("name")
    team = player.get("team")
    position_type = player.get("position_type") or player.get("fantasy_position_type")

    raw_active = int(player.get("is_active") or 0) == 1
    latest_game_date = get_latest_synced_game_date()
    latest_register_date = get_latest_registered_source_date()
    register_date_matches_game = bool(latest_game_date and latest_register_date and latest_register_date == latest_game_date)

    if not name or not team or not position_type:
        player["is_market_active"] = raw_active
        player["is_display_inactive"] = not raw_active
        player["market_status_label"] = "등록" if raw_active else "말소"
        player["register_source_date"] = latest_register_date
        player["register_date_matches_game"] = register_date_matches_game
        return player

    activity = get_player_recent_market_activity(name, team, position_type, latest_game_date)
    appeared_on_latest_game = (
        bool(latest_game_date)
        and int(activity.get("recent_activity_games") or 0) > 0
        and activity.get("recent_activity_last_game_date") == latest_game_date
    )

    # 등록 현황 날짜가 최신 경기 날짜와 맞으면 KBO 등록 명단 기준을 엄격하게 사용합니다.
    # 날짜가 어긋난 경우에만 최신 경기 출전 선수를 보호합니다.
    fallback_active = (not register_date_matches_game) and appeared_on_latest_game
    is_market_active = bool(raw_active or fallback_active)

    player.update(activity)
    player["raw_is_active"] = 1 if raw_active else 0
    player["is_market_active"] = is_market_active
    # 화면 표시는 KBO 등록 현황 기준을 우선합니다.
    # 단, 등록 현황 날짜가 최신 경기 날짜와 어긋나고 최신 경기일에 실제 출전한 경우에만 보호합니다.
    player["is_display_inactive"] = (not raw_active) and (not fallback_active)
    player["market_status_label"] = "등록" if not player["is_display_inactive"] else "말소"
    player["register_source_date"] = latest_register_date
    player["register_date_matches_game"] = register_date_matches_game
    player["display_status_reason"] = (
        "registered_active" if raw_active
        else "latest_game_appearance_register_date_mismatch" if fallback_active
        else "kbo_register_inactive"
    )

    display_detail = player.get("detail_position")
    roster_position = player.get("roster_position")
    price_role = player.get("price_role")

    if position_type == "pitcher":
        display_detail = resolve_pitcher_display_detail_position(
            detail_position=display_detail,
            roster_position=roster_position,
            price_role=price_role,
        )
    else:
        if not display_detail or detail_position_is_empty(display_detail) or display_detail == "타자":
            if roster_position and roster_position not in ["미등록", "투수", "타자"]:
                display_detail = roster_position
            else:
                # 수비 포지션 근거가 없는 타자는 수비 슬롯에 배정하지 않고 UTIL 전용으로 취급합니다.
                display_detail = "지명타자"

    player["display_detail_position"] = display_detail
    return player


def detail_position_is_empty(value):
    return value is None or str(value).strip() == "" or str(value).strip() == "미등록"

def _extract_date_parts(value):
    """
    YYYYMMDD, YYYY-MM-DD, YYYY-MM-DD HH:MM:SS 형태에서 연/월/일을 추출합니다.
    화면 표시용 helper에서만 사용하며 DB 값은 변경하지 않습니다.
    """
    if value is None:
        return None

    text = str(value).strip()

    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        year = text[0:4]
        month = text[5:7]
        day = text[8:10]
    elif len(text) >= 8 and text[0:8].isdigit():
        year = text[0:4]
        month = text[4:6]
        day = text[6:8]
    else:
        return None

    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None

    return int(year), int(month), int(day), text


def format_game_date_for_display(value):
    """
    날짜를 화면 표시용 'M월 D일'로 바꿉니다.
    DB 저장값은 그대로 유지하고, 화면에서만 2026년 표기를 제거합니다.
    """
    parts = _extract_date_parts(value)

    if parts is None:
        return "" if value is None else str(value).strip()

    _, month, day, _ = parts
    return f"{month}월 {day}일"


def format_datetime_for_display(value):
    """
    날짜/시간을 화면 표시용 'M월 D일 HH:MM'으로 바꿉니다.
    시간이 없으면 'M월 D일'만 반환합니다.
    """
    parts = _extract_date_parts(value)

    if parts is None:
        return "" if value is None else str(value).strip()

    _, month, day, text = parts
    date_text = f"{month}월 {day}일"

    if len(text) >= 16 and text[10] in [" ", "T"]:
        return f"{date_text} {text[11:16]}"

    return date_text


def get_page_number(default=1):
    """현재 요청의 page query 값을 안전하게 정수로 변환합니다."""
    try:
        page = int(request.args.get("page", default))
    except (TypeError, ValueError):
        page = default

    return max(1, page)


MOBILE_PLAYER_PAGE_SIZE = 20


def is_mobile_browser_request():
    """모바일 브라우저 요청에서만 선수 목록 페이지 크기를 줄입니다."""
    user_agent = (request.headers.get("User-Agent") or "").lower()
    if not user_agent:
        return False

    mobile_markers = (
        "mobile",
        "iphone",
        "ipod",
        "android",
        "ipad",
        "naver(inapp",
        "gsa/",
    )
    return any(marker in user_agent for marker in mobile_markers)


def get_player_result_page_size(default=50):
    # MYPICK MOBILE-ONLY PLAYER PAGINATION 2026-06-06
    # Desktop keeps the existing page size. Mobile shows 20 cards per page.
    return MOBILE_PLAYER_PAGE_SIZE if is_mobile_browser_request() else default


def paginate_items(items, page=1, per_page=50):
    """목록을 per_page 단위로 잘라 페이지네이션 정보를 반환합니다."""
    total_count = len(items or [])
    total_pages = max(1, ceil(total_count / per_page)) if total_count else 1
    page = min(max(1, int(page or 1)), total_pages)
    start = (page - 1) * per_page
    end = start + per_page

    return {
        "items": list(items or [])[start:end],
        "page": page,
        "per_page": per_page,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < total_pages else None,
        "start_rank": start + 1 if total_count else 0,
        "end_rank": min(end, total_count),
        "pages": list(range(1, total_pages + 1)),
    }


def parse_price_filter(value):
    """
    가격 필터 값을 소수점 숫자로 바꿉니다.
    """
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    try:
        price = float(value)
    except ValueError:
        return None

    if price < 1:
        price = 1.0

    if price > MAX_PLAYER_PRICE:
        price = MAX_PLAYER_PRICE

    return round(price, 1)


def decorate_price_change(row_dict):
    """
    선수 row에 가격 변동 표시용 필드를 추가합니다.
    """
    change = row_dict.get("latest_price_change")

    if change is None:
        old_price = row_dict.get("latest_old_price_decimal")
        new_price = row_dict.get("latest_new_price_decimal")

        if old_price is not None and new_price is not None:
            change = float(new_price) - float(old_price)

    if change is None:
        row_dict["latest_price_change"] = None
        row_dict["latest_price_change_label"] = "-"
        row_dict["latest_price_change_class"] = "price-same"
        row_dict["latest_price_reason_compact"] = "-"
        row_dict["latest_price_reason_class"] = "trend-same"
        return row_dict

    change = round(float(change or 0), 1)
    row_dict["latest_price_change"] = change

    if change > 0:
        row_dict["latest_price_change_label"] = f"+{change:.1f}"
        row_dict["latest_price_change_class"] = "price-up"
    elif change < 0:
        row_dict["latest_price_change_label"] = f"{change:.1f}"
        row_dict["latest_price_change_class"] = "price-down"
    else:
        row_dict["latest_price_change_label"] = "0.0"
        row_dict["latest_price_change_class"] = "price-same"

    row_dict["latest_price_reason"] = normalize_price_reason_text(row_dict.get("latest_price_reason"))

    compact_label, compact_class = compact_price_reason_label(
        row_dict.get("latest_price_reason"),
        change=change,
        performance_change=row_dict.get("latest_performance_change"),
    )
    row_dict["latest_price_reason_compact"] = compact_label
    row_dict["latest_price_reason_class"] = compact_class

    return row_dict


# ==========================================================
# 선수 조회 / 랭킹
# ==========================================================

def get_player_price_history(registered_player_id, limit=None):
    """
    선수 상세 페이지에 보여줄 가격 변동 history를 가져옵니다.
    limit=None이면 전체 적용 기록을 가져오고, limit 값이 있으면 최신 N개만 가져옵니다.
    """
    if not registered_player_id:
        return []

    limit_sql = ""
    params = [registered_player_id, BASIS_SOURCE]

    if limit is not None:
        limit_sql = "LIMIT ?"
        params.append(int(limit))

    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                ppa.id,
                ppa.run_id,
                ppa.registered_player_id,
                ppa.player_name,
                ppa.team,
                ppa.price_role,
                ppa.basis_date,
                ppa.basis_start_date,
                ppa.basis_end_date,
                ppa.old_price_decimal,
                ppa.performance_change,
                ppa.absence_penalty_change,
                ppa.absence_penalty_total,
                ppa.new_price_decimal,
                ppa.reason,
                ppa.created_at
            FROM player_price_adjustments ppa
            JOIN (
                SELECT
                    basis_date,
                    MAX(id) AS latest_adjustment_id
                FROM player_price_adjustments
                WHERE registered_player_id = ?
                  AND basis_source = ?
                  AND is_applied = 1
                GROUP BY basis_date
            ) latest
              ON ppa.id = latest.latest_adjustment_id
            ORDER BY ppa.basis_date DESC, ppa.id DESC
            {limit_sql}
        """, params).fetchall()

    history = []

    for row in rows:
        item = dict(row)
        item["reason"] = normalize_price_reason_text(item.get("reason"))
        old_price = float(item.get("old_price_decimal") or 0)
        new_price = float(item.get("new_price_decimal") or 0)
        change = round(new_price - old_price, 1)

        item["old_price_decimal"] = round(old_price, 1)
        item["new_price_decimal"] = round(new_price, 1)
        item["price_change"] = change
        item["basis_date_display"] = format_game_date_for_display(item.get("basis_date"))
        item["chart_label"] = item["basis_date_display"]

        if change > 0:
            item["price_change_label"] = f"+{change:.1f}"
            item["price_change_class"] = "price-up"
        elif change < 0:
            item["price_change_label"] = f"{change:.1f}"
            item["price_change_class"] = "price-down"
        else:
            item["price_change_label"] = "0.0"
            item["price_change_class"] = "price-same"

        item["graph_width"] = max(
            4,
            min(100, round((new_price / MAX_PLAYER_PRICE) * 100, 1))
        )

        history.append(item)

    history.reverse()
    return history


def filter_price_history_by_days(history, days):
    """가격 history 목록에서 최신 기준일로부터 N일 범위만 남깁니다."""
    if not history:
        return []

    if days is None:
        return history

    with get_conn() as conn:
        latest = history[-1].get("basis_date")
        rows = conn.execute(
            """
            SELECT date(?, ?) AS cutoff_date
            """,
            (latest, f"-{int(days)} days"),
        ).fetchone()

    cutoff_date = rows["cutoff_date"] if rows else None

    if not cutoff_date:
        return history

    return [
        item
        for item in history
        if str(item.get("basis_date") or "") >= str(cutoff_date)
    ]

def get_rankings(position_type=None):
    """
    선수 랭킹을 시즌 총점 기준으로 가져옵니다.
    """
    ensure_player_listing_performance_indexes()
    latest_game_date = get_latest_synced_game_date()
    latest_price_date = get_latest_price_date()

    conditions = []
    params = [latest_game_date, BASIS_SOURCE, latest_price_date]

    if position_type is not None:
        conditions.append("rp.fantasy_position_type = ?")
        params.append(position_type)

    where_sql = " AND ".join(conditions) if conditions else "1 = 1"

    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                rp.id AS registered_player_id,
                rp.name AS player_name,
                rp.team,
                rp.is_active,
                rp.back_no,
                rp.detail_position,
                rp.fantasy_position_type AS position_type,
                COALESCE(fds_daily.daily_points, 0) AS total_points,
                fds_daily.last_updated_at,
                COALESCE(fpt.total_points, 0) AS cumulative_points,
                COALESCE(pp.price_decimal, pp.price, 0) AS price,
                pp.basis_date AS price_basis_date
            FROM registered_players rp
            LEFT JOIN (
                SELECT
                    player_name,
                    team,
                    position_type,
                    SUM(points) AS daily_points,
                    MAX(updated_at) AS last_updated_at
                FROM fantasy_daily_scores
                WHERE game_date = ?
                GROUP BY player_name, team, position_type
            ) fds_daily
              ON rp.name = fds_daily.player_name
             AND rp.team = fds_daily.team
             AND rp.fantasy_position_type = fds_daily.position_type
            LEFT JOIN fantasy_player_totals fpt
              ON rp.name = fpt.player_name
             AND rp.team = fpt.team
             AND rp.fantasy_position_type = fpt.position_type
            LEFT JOIN player_prices pp
              ON rp.id = pp.registered_player_id
             AND pp.basis_source = ?
             AND pp.basis_date = ?
            WHERE {where_sql}
            ORDER BY
                COALESCE(fpt.total_points, 0) DESC,
                COALESCE(fds_daily.daily_points, 0) DESC,
                COALESCE(pp.price_decimal, pp.price, 0) DESC,
                rp.team ASC,
                rp.name ASC
        """, params).fetchall()

    rankings = []
    for index, row in enumerate(rows, start=1):
        item = dict(row)
        apply_market_price_record(item, price_key="price")
        decorate_market_status(item)
        if item.get("price") is not None:
            item["price"] = round(float(item["price"]), 1)
        item["display_rank"] = index
        item["price_basis_date_display"] = format_game_date_for_display(item.get("price_basis_date"))
        item["last_updated_at_display"] = format_datetime_for_display(item.get("last_updated_at"))
        rankings.append(item)

    return rankings


def get_registered_players(
    name=None,
    team=None,
    roster_position=None,
    detail_position=None,
    fantasy_position_type=None,
    price_min=None,
    price_max=None
):
    ensure_player_listing_performance_indexes()
    latest_price_date = get_latest_price_date()
    latest_game_date = get_latest_synced_game_date()

    conditions = []

    params = [
        latest_game_date,
        BASIS_SOURCE,
        latest_price_date,
        BASIS_SOURCE,
    ]

    if name:
        conditions.append("rp.name LIKE ?")
        params.append(f"%{name}%")

    if team:
        conditions.append("rp.team = ?")
        params.append(team)

    if roster_position:
        conditions.append("rp.roster_position = ?")
        params.append(roster_position)

    if detail_position:
        expanded_detail_positions = detail_positions_for_filter(detail_position)
        if detail_position == "지명타자":
            placeholders = ", ".join(["?"] * len(expanded_detail_positions))
            conditions.append(f"""
                (
                    rp.detail_position IN ({placeholders})
                    OR (
                        rp.fantasy_position_type = 'batter'
                        AND (rp.detail_position IS NULL OR TRIM(rp.detail_position) = '' OR rp.detail_position = '미등록')
                        AND (rp.roster_position IS NULL OR TRIM(rp.roster_position) = '' OR rp.roster_position IN ('미등록', '타자'))
                    )
                )
            """)
            params.extend(expanded_detail_positions)
        else:
            placeholders = ", ".join(["?"] * len(expanded_detail_positions))
            conditions.append(f"rp.detail_position IN ({placeholders})")
            params.extend(expanded_detail_positions)

    if fantasy_position_type:
        conditions.append("rp.fantasy_position_type = ?")
        params.append(fantasy_position_type)

    price_min_value = parse_price_filter(price_min)
    price_max_value = parse_price_filter(price_max)

    if (
        price_min_value is not None
        and price_max_value is not None
        and price_min_value > price_max_value
    ):
        price_min_value, price_max_value = price_max_value, price_min_value

    # 가격은 registered_player_id 정확 매칭 후 이름+팀 fallback까지 적용해야 하므로
    # SQL에서 바로 필터링하지 않고, 아래 Python 루프에서 최종 가격 기준으로 필터링합니다.

    where_sql = " AND ".join(conditions) if conditions else "1 = 1"

    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                rp.id,
                rp.player_id,
                rp.name,
                rp.team,
                rp.team_id,
                rp.is_active,
                rp.roster_position,
                rp.detail_position,
                rp.detail_position_source,
                rp.detail_position_updated_at,
                rp.fantasy_position_type,
                rp.back_no,
                rp.throw_bat,
                rp.birthdate,
                rp.height_weight,
                rp.profile_url,
                rp.source_date,
                COALESCE(fds_daily.daily_points, 0) AS total_points,
                fds_daily.last_updated_at,
                COALESCE(fpt.total_points, 0) AS cumulative_points,
                pp.price_role,
                pp.tier,
                COALESCE(pp.price_decimal, pp.price, 0) AS price,
                pp.price AS price_integer,
                pp.price_decimal,
                pp.external_score,
                pp.external_rank,
                pp.basis_source,
                pp.basis_date,
                latest_adj.old_price_decimal AS latest_old_price_decimal,
                latest_adj.new_price_decimal AS latest_new_price_decimal,
                ROUND(
                    latest_adj.new_price_decimal - latest_adj.old_price_decimal,
                    1
                ) AS latest_price_change,
                latest_adj.performance_change AS latest_performance_change,
                latest_adj.absence_penalty_change AS latest_absence_change,
                latest_adj.reason AS latest_price_reason,
                latest_adj.basis_date AS latest_price_change_date
            FROM registered_players rp
            LEFT JOIN (
                SELECT
                    player_name,
                    team,
                    position_type,
                    SUM(points) AS daily_points,
                    MAX(updated_at) AS last_updated_at
                FROM fantasy_daily_scores
                WHERE game_date = ?
                GROUP BY player_name, team, position_type
            ) fds_daily
              ON rp.name = fds_daily.player_name
             AND rp.team = fds_daily.team
             AND rp.fantasy_position_type = fds_daily.position_type
            LEFT JOIN fantasy_player_totals fpt
              ON rp.name = fpt.player_name
             AND rp.team = fpt.team
             AND rp.fantasy_position_type = fpt.position_type
            LEFT JOIN player_prices pp
              ON rp.id = pp.registered_player_id
             AND pp.basis_source = ?
             AND pp.basis_date = ?
            LEFT JOIN (
                SELECT
                    ppa.*
                FROM player_price_adjustments ppa
                JOIN (
                    SELECT
                        registered_player_id,
                        MAX(id) AS latest_adjustment_id
                    FROM player_price_adjustments
                    WHERE basis_source = ?
                      AND is_applied = 1
                    GROUP BY registered_player_id
                ) latest_ids
                  ON ppa.id = latest_ids.latest_adjustment_id
            ) latest_adj
              ON rp.id = latest_adj.registered_player_id
            WHERE {where_sql}
            ORDER BY
                COALESCE(fpt.total_points, 0) DESC,
                COALESCE(fds_daily.daily_points, 0) DESC,
                CASE
                    WHEN COALESCE(pp.price_decimal, pp.price) IS NULL THEN 1
                    ELSE 0
                END ASC,
                COALESCE(pp.price_decimal, pp.price, 0) DESC,
                pp.external_score DESC,
                rp.team ASC,
                CASE rp.detail_position
                    WHEN '선발투수' THEN 1
                    WHEN '불펜투수' THEN 2
                    WHEN '투수' THEN 3
                    WHEN '포수' THEN 4
                    WHEN '1루수' THEN 5
                    WHEN '2루수' THEN 6
                    WHEN '3루수' THEN 7
                    WHEN '유격수' THEN 8
                    WHEN '좌익수' THEN 9
                    WHEN '중견수' THEN 10
                    WHEN '우익수' THEN 11
                    WHEN '내야수' THEN 12
                    WHEN '외야수' THEN 13
                    ELSE 14
                END,
                CAST(rp.back_no AS INTEGER) ASC,
                rp.name ASC
        """, params).fetchall()

    players = []

    for row in rows:
        player = dict(row)
        apply_market_price_record(player, price_key="price")

        if price_min_value is not None and (player.get("price") is None or player["price"] < price_min_value):
            continue
        if price_max_value is not None and (player.get("price") is None or player["price"] > price_max_value):
            continue

        decorate_market_status(player)

        if player.get("price") is not None:
            player["price"] = round(float(player["price"]), 1)

        player["basis_date_display"] = format_game_date_for_display(player.get("basis_date"))
        player["latest_price_change_date_display"] = format_game_date_for_display(player.get("latest_price_change_date"))
        player["last_updated_at_display"] = format_datetime_for_display(player.get("last_updated_at"))

        decorate_price_change(player)
        players.append(player)

    players = dedupe_registered_player_rows(players)
    players.sort(key=lambda player: (
        -float(player.get("cumulative_points") or 0),
        -float(player.get("total_points") or 0),
        1 if player.get("price") is None else 0,
        -float(player.get("price") or 0),
        str(player.get("team") or ""),
        int(player.get("id") or 0),
    ))
    return players


def get_registered_player_detail(player_name, team, position_type):
    latest_price_date = get_latest_price_date()
    latest_game_date = get_latest_synced_game_date()

    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                rp.id AS registered_player_id,
                rp.player_id,
                rp.name AS player_name,
                rp.team,
                rp.is_active,
                rp.roster_position,
                rp.detail_position,
                rp.detail_position_source,
                rp.detail_position_updated_at,
                rp.fantasy_position_type AS position_type,
                rp.back_no,
                rp.throw_bat,
                rp.birthdate,
                rp.height_weight,
                rp.profile_url,
                rp.source_date,
                COALESCE(fds_daily.daily_points, 0) AS total_points,
                fds_daily.last_updated_at,
                COALESCE(fpt.total_points, 0) AS cumulative_points,
                pp.price_role,
                pp.tier,
                COALESCE(pp.price_decimal, pp.price, 0) AS price,
                pp.price AS price_integer,
                pp.price_decimal,
                pp.external_score,
                pp.external_rank,
                pp.basis_source,
                pp.basis_date,
                latest_adj.old_price_decimal AS latest_old_price_decimal,
                latest_adj.new_price_decimal AS latest_new_price_decimal,
                ROUND(
                    latest_adj.new_price_decimal - latest_adj.old_price_decimal,
                    1
                ) AS latest_price_change,
                latest_adj.performance_change AS latest_performance_change,
                latest_adj.absence_penalty_change AS latest_absence_change,
                latest_adj.reason AS latest_price_reason,
                latest_adj.basis_date AS latest_price_change_date
            FROM registered_players rp
            LEFT JOIN (
                SELECT
                    player_name,
                    team,
                    position_type,
                    SUM(points) AS daily_points,
                    MAX(updated_at) AS last_updated_at
                FROM fantasy_daily_scores
                WHERE game_date = ?
                GROUP BY player_name, team, position_type
            ) fds_daily
              ON rp.name = fds_daily.player_name
             AND rp.team = fds_daily.team
             AND rp.fantasy_position_type = fds_daily.position_type
            LEFT JOIN fantasy_player_totals fpt
              ON rp.name = fpt.player_name
             AND rp.team = fpt.team
             AND rp.fantasy_position_type = fpt.position_type
            LEFT JOIN player_prices pp
              ON rp.id = pp.registered_player_id
             AND pp.basis_source = ?
             AND pp.basis_date = ?
            LEFT JOIN (
                SELECT
                    ppa.*
                FROM player_price_adjustments ppa
                JOIN (
                    SELECT
                        registered_player_id,
                        MAX(id) AS latest_adjustment_id
                    FROM player_price_adjustments
                    WHERE basis_source = ?
                      AND is_applied = 1
                    GROUP BY registered_player_id
                ) latest_ids
                  ON ppa.id = latest_ids.latest_adjustment_id
            ) latest_adj
              ON rp.id = latest_adj.registered_player_id
            WHERE rp.name = ?
              AND rp.team = ?
              AND rp.fantasy_position_type = ?
            ORDER BY
                CASE WHEN pp.registered_player_id IS NOT NULL THEN 0 ELSE 1 END,
                rp.is_active DESC,
                rp.id ASC
            LIMIT 1

        """, (
            latest_game_date,
            BASIS_SOURCE,
            latest_price_date,
            BASIS_SOURCE,
            player_name,
            team,
            position_type,
        )).fetchone()

    if row:
        player = dict(row)
        apply_market_price_record(player, price_key="price")

        if player.get("price") is not None:
            player["price"] = round(float(player["price"]), 1)

        player["basis_date_display"] = format_game_date_for_display(player.get("basis_date"))
        player["latest_price_change_date_display"] = format_game_date_for_display(player.get("latest_price_change_date"))
        player["last_updated_at_display"] = format_datetime_for_display(player.get("last_updated_at"))
        player["birthdate_display"] = format_game_date_for_display(player.get("birthdate"))

        decorate_market_status(player)
        decorate_price_change(player)
        return player

    return None


def get_registered_player_by_id(registered_player_id):
    """
    팀에 선수를 추가할 때 registered_players.id 기준으로 선수 정보를 가져옵니다.
    """
    latest_price_date = get_latest_price_date()
    latest_game_date = get_latest_synced_game_date()

    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                rp.id,
                rp.player_id,
                rp.name,
                rp.team,
                rp.back_no,
                rp.is_active,
                rp.back_no,
                rp.detail_position,
                rp.fantasy_position_type,
                COALESCE(pp.price_decimal, pp.price, 0) AS price,
                pp.price AS price_integer,
                pp.price_decimal,
                pp.tier,
                COALESCE(fds_daily.daily_points, 0) AS total_points,
                COALESCE(fpt.total_points, 0) AS cumulative_points
            FROM registered_players rp
            LEFT JOIN (
                SELECT
                    player_name,
                    team,
                    position_type,
                    SUM(points) AS daily_points
                FROM fantasy_daily_scores
                WHERE game_date = ?
                GROUP BY player_name, team, position_type
            ) fds_daily
              ON rp.name = fds_daily.player_name
             AND rp.team = fds_daily.team
             AND rp.fantasy_position_type = fds_daily.position_type
            LEFT JOIN player_prices pp
              ON rp.id = pp.registered_player_id
             AND pp.basis_source = ?
             AND pp.basis_date = ?
            LEFT JOIN fantasy_player_totals fpt
              ON rp.name = fpt.player_name
             AND rp.team = fpt.team
             AND rp.fantasy_position_type = fpt.position_type
            WHERE rp.id = ?
        """, (
            latest_game_date,
            BASIS_SOURCE,
            latest_price_date,
            registered_player_id,
        )).fetchone()

    if row is None:
        return None

    player = dict(row)
    apply_market_price_record(player, price_key="price")
    decorate_market_status(player)

    if player.get("price") is not None:
        player["price"] = round(float(player["price"]), 1)

    return player


def get_player_total(player_name, team, position_type):
    """
    등록 선수 테이블에 없는 예외 상황을 위한 현재 점수 조회입니다.
    """
    latest_game_date = get_latest_synced_game_date()

    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                fpt.player_name,
                fpt.team,
                fpt.position_type,
                COALESCE(fds_daily.daily_points, 0) AS total_points,
                fds_daily.last_updated_at,
                COALESCE(fpt.total_points, 0) AS cumulative_points
            FROM fantasy_player_totals fpt
            LEFT JOIN (
                SELECT
                    player_name,
                    team,
                    position_type,
                    SUM(points) AS daily_points,
                    MAX(updated_at) AS last_updated_at
                FROM fantasy_daily_scores
                WHERE game_date = ?
                GROUP BY player_name, team, position_type
            ) fds_daily
              ON fpt.player_name = fds_daily.player_name
             AND fpt.team = fds_daily.team
             AND fpt.position_type = fds_daily.position_type
            WHERE fpt.player_name = ?
              AND fpt.team = ?
              AND fpt.position_type = ?
        """, (
            latest_game_date,
            player_name,
            team,
            position_type,
        )).fetchone()

    if row:
        row_dict = dict(row)

        row_dict["roster_position"] = None
        row_dict["detail_position"] = None
        row_dict["detail_position_source"] = None
        row_dict["detail_position_updated_at"] = None
        row_dict["back_no"] = None
        row_dict["throw_bat"] = None
        row_dict["birthdate"] = None
        row_dict["height_weight"] = None
        row_dict["profile_url"] = None
        row_dict["player_id"] = None
        row_dict["source_date"] = None
        row_dict["price_role"] = None
        row_dict["tier"] = None
        row_dict["price"] = None
        row_dict["price_integer"] = None
        row_dict["price_decimal"] = None
        row_dict["external_score"] = None
        row_dict["external_rank"] = None
        row_dict["basis_source"] = None
        row_dict["basis_date"] = None
        row_dict["registered_player_id"] = None
        row_dict["latest_old_price_decimal"] = None
        row_dict["latest_new_price_decimal"] = None
        row_dict["latest_price_change"] = None
        row_dict["latest_price_change_label"] = "-"
        row_dict["latest_price_change_class"] = "price-same"
        row_dict["latest_performance_change"] = None
        row_dict["latest_absence_change"] = None
        row_dict["latest_price_reason"] = None
        row_dict["latest_price_reason_compact"] = "-"
        row_dict["latest_price_reason_class"] = "trend-same"
        row_dict["latest_price_change_date"] = None
        row_dict["basis_date_display"] = ""
        row_dict["latest_price_change_date_display"] = ""
        row_dict["last_updated_at_display"] = format_datetime_for_display(row_dict.get("last_updated_at"))
        row_dict["birthdate_display"] = ""

        return row_dict

    return None


def get_player_season_total_points(
    player_name,
    team,
    position_type,
    season_start_date="2026-03-28"
):
    """
    선수 상세 페이지에 표시할 2026 시즌 총 획득 포인트를 계산합니다.

    기준:
    - fantasy_daily_scores에 저장된 해당 선수의 모든 경기 점수 합계
    - 2026 시즌 시작일은 기본값 2026-03-28입니다.
    - 최근 경기 점수와 달리 누적 시즌 점수입니다.
    """
    with get_conn() as conn:
        row = conn.execute("""
            SELECT COALESCE(SUM(points), 0) AS season_total_points
            FROM fantasy_daily_scores
            WHERE player_name = ?
              AND team = ?
              AND position_type = ?
              AND game_date >= ?
        """, (
            player_name,
            team,
            position_type,
            season_start_date,
        )).fetchone()

    if row is None:
        return 0.0

    return round(float(row["season_total_points"] or 0), 1)



def get_player_season_stats(
    player_name,
    team,
    position_type,
    season_start_date="2026-03-28"
):
    """
    선수 상세 페이지용 2026 시즌 주요 스탯을 계산합니다.
    기존 raw 기록과 fantasy_daily_scores만 읽으며 DB 구조는 변경하지 않습니다.
    """
    stats = []

    with get_conn() as conn:
        avg_row = conn.execute("""
            SELECT
                COUNT(*) AS scored_games,
                COALESCE(SUM(points), 0) AS total_points,
                COALESCE(AVG(points), 0) AS average_points
            FROM fantasy_daily_scores
            WHERE player_name = ?
              AND team = ?
              AND position_type = ?
              AND game_date >= ?
        """, (
            player_name,
            team,
            position_type,
            season_start_date,
        )).fetchone()

        scored_games = int(avg_row["scored_games"] or 0) if avg_row else 0
        average_points = round(float(avg_row["average_points"] or 0), 1) if avg_row else 0.0

        if position_type == "batter":
            row = conn.execute("""
                SELECT
                    COUNT(DISTINCT game_id) AS games,
                    COALESCE(SUM(hits), 0) AS hits,
                    COALESCE(SUM(doubles), 0) AS doubles,
                    COALESCE(SUM(triples), 0) AS triples,
                    COALESCE(SUM(home_runs), 0) AS home_runs,
                    COALESCE(SUM(game_winning_hit), 0) AS game_winning_hit,
                    COALESCE(SUM(rbi), 0) AS rbi,
                    COALESCE(SUM(runs), 0) AS runs,
                    COALESCE(SUM(stolen_bases), 0) AS stolen_bases,
                    COALESCE(SUM(hit_by_pitch), 0) AS hit_by_pitch,
                    COALESCE(SUM(walks), 0) AS walks,
                    COALESCE(SUM(strikeouts), 0) AS strikeouts,
                    COALESCE(SUM(double_play), 0) AS double_play
                FROM raw_batter_stats
                WHERE player_name = ?
                  AND team = ?
                  AND game_date >= ?
            """, (
                player_name,
                team,
                season_start_date,
            )).fetchone()

            if row:
                stats = [
                    {"label": "출전 경기", "value": int(row["games"] or 0)},
                    {"label": "안타", "value": int(row["hits"] or 0)},
                    {"label": "2루타", "value": int(row["doubles"] or 0)},
                    {"label": "3루타", "value": int(row["triples"] or 0)},
                    {"label": "홈런", "value": int(row["home_runs"] or 0)},
                    {"label": "결승타", "value": int(row["game_winning_hit"] or 0)},
                    {"label": "타점", "value": int(row["rbi"] or 0)},
                    {"label": "득점", "value": int(row["runs"] or 0)},
                    {"label": "도루", "value": int(row["stolen_bases"] or 0)},
                    {"label": "출루", "value": int((row["walks"] or 0) + (row["hit_by_pitch"] or 0))},
                    {"label": "삼진", "value": int(row["strikeouts"] or 0)},
                    {"label": "병살타", "value": int(row["double_play"] or 0)},
                    {"label": "평균 수입", "value": average_points},
                ]
        elif position_type == "pitcher":
            row = conn.execute("""
                SELECT
                    COUNT(DISTINCT game_id) AS games,
                    COALESCE(SUM(is_starting_pitcher), 0) AS starts,
                    COALESCE(SUM(wins), 0) AS wins,
                    COALESCE(SUM(losses), 0) AS losses,
                    COALESCE(SUM(holds), 0) AS holds,
                    COALESCE(SUM(saves), 0) AS saves,
                    COALESCE(SUM(completed_innings), 0) AS completed_innings,
                    COALESCE(SUM(strikeouts), 0) AS strikeouts,
                    COALESCE(SUM(runs_allowed), 0) AS runs_allowed,
                    COALESCE(SUM(hits_allowed), 0) AS hits_allowed,
                    COALESCE(SUM(pitch_count), 0) AS pitch_count
                FROM raw_pitcher_stats
                WHERE player_name = ?
                  AND team = ?
                  AND game_date >= ?
            """, (
                player_name,
                team,
                season_start_date,
            )).fetchone()

            if row:
                stats = [
                    {"label": "등판 경기", "value": int(row["games"] or 0)},
                    {"label": "승", "value": int(row["wins"] or 0)},
                    {"label": "패", "value": int(row["losses"] or 0)},
                    {"label": "홀드", "value": int(row["holds"] or 0)},
                    {"label": "세이브", "value": int(row["saves"] or 0)},
                    {"label": "정수 이닝", "value": int(row["completed_innings"] or 0)},
                    {"label": "탈삼진", "value": int(row["strikeouts"] or 0)},
                    {"label": "실점", "value": int(row["runs_allowed"] or 0)},
                    {"label": "총 투구수", "value": int(row["pitch_count"] or 0)},
                    {"label": "피안타", "value": int(row["hits_allowed"] or 0)},
                    {"label": "평균 수입", "value": average_points},
                ]

    if not stats and scored_games:
        stats = [
            {"label": "기록 경기", "value": scored_games},
            {"label": "평균 수입", "value": average_points},
        ]

    return stats

def translate_score_detail_key(key):
    """
    score_detail_json 안의 영어 key를 화면 표시용 한국어로 바꿉니다.
    """
    key_map = {
        "appearance": "출전",
        "hits": "안타",
        "hit": "안타",
        "single_hits": "단타",
        "singles": "단타",
        "doubles": "2루타",
        "double": "2루타",
        "triples": "3루타",
        "triple": "3루타",
        "home_runs": "홈런",
        "home_run": "홈런",
        "rbi": "타점",
        "runs": "득점",
        "run": "득점",
        "game_winning_hit": "결승타",
        "on_base": "출루",
        "hit_by_pitch": "출루",
        "walks": "출루",
        "stolen_bases": "도루",
        "double_play": "병살타",
        "wins": "승",
        "win": "승",
        "losses": "패",
        "loss": "패",
        "holds": "홀드",
        "hold": "홀드",
        "saves": "세이브",
        "save": "세이브",
        "innings": "이닝",
        "innings_pitched": "이닝",
        "completed_innings": "정수 이닝",
        "strikeouts": "삼진",
        "strikeout": "삼진",
        "pitch_count": "투구수",
        "hits_allowed": "피안타",
        "runs_allowed": "실점",
        "run_allowed": "실점",
        "hit_points": "안타 수입",
        "single_hit_points": "단타 수입",
        "double_points": "2루타 수입",
        "triple_points": "3루타 수입",
        "home_run_points": "홈런 수입",
        "rbi_points": "타점 수입",
        "run_points": "득점 수입",
        "game_winning_hit_points": "결승타 수입",
        "hit_by_pitch_points": "사구 수입",
        "walk_points": "볼넷 수입",
        "stolen_base_points": "도루 수입",
        "double_play_points": "병살타 수입",
        "win_points": "승 수입",
        "loss_points": "패 수입",
        "hold_points": "홀드 수입",
        "save_points": "세이브 수입",
        "inning_points": "이닝 수입",
        "strikeout_points": "삼진 수입",
        "pitch_count_points": "투구수 수입",
        "hits_allowed_points": "피안타 수입",
        "run_allowed_points": "실점 수입",
        "total": "합계",
        "points": "수입",
        "total_points": "총수입",
        "starting_pitcher_bonus": "선발 투수 × 2.0",
        "bullpen_pitcher_bonus": "불펜 투수 × 1.4",
    }

    return key_map.get(key, key)


def get_player_daily_scores(player_name, team, position_type):
    """
    특정 선수의 최근 5경기 점수 기록을 가져옵니다.
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                fds.game_date,
                fds.game_id,
                fds.points,
                fds.score_detail_json,
                fds.updated_at,
                g.away_team,
                g.home_team,
                g.stadium
            FROM fantasy_daily_scores fds
            LEFT JOIN games g
              ON fds.game_id = g.game_id
            WHERE fds.player_name = ?
              AND fds.team = ?
              AND fds.position_type = ?
            ORDER BY fds.game_date DESC, fds.game_id DESC
            LIMIT 5
        """, (
            player_name,
            team,
            position_type,
        )).fetchall()

    result = []

    for row in rows:
        row_dict = dict(row)
        away_team = row_dict.get("away_team")
        home_team = row_dict.get("home_team")

        if away_team and home_team:
            if team == away_team:
                row_dict["opponent"] = home_team
            elif team == home_team:
                row_dict["opponent"] = away_team
            else:
                row_dict["opponent"] = f"{away_team} vs {home_team}"
        else:
            row_dict["opponent"] = "-"

        row_dict["game_date_display"] = format_game_date_for_display(row_dict.get("game_date"))
        row_dict["updated_at_display"] = format_datetime_for_display(row_dict.get("updated_at"))

        try:
            raw_detail = json.loads(row["score_detail_json"])
        except Exception:
            raw_detail = {}

        if not isinstance(raw_detail, dict):
            raw_detail = {}

        translated_detail = {}

        for key, value in raw_detail.items():
            korean_key = translate_score_detail_key(key)
            translated_detail[korean_key] = value

        row_dict["score_detail"] = translated_detail
        result.append(row_dict)

    return result


# ==========================================================
# 팀 / 로스터 / 유저 점수
# ==========================================================

def get_my_team(user_id):
    """
    현재 로그인한 사용자의 판타지 팀을 가져옵니다.
    """
    with get_conn() as conn:
        team = conn.execute("""
            SELECT
                id,
                user_id,
                team_name,
                budget_limit,
                cash_balance_decimal,
                COALESCE(is_confirmed, 0) AS is_confirmed,
                confirmed_at,
                confirmed_budget_used,
                captain_registered_player_id,
                created_at,
                updated_at
            FROM fantasy_teams
            WHERE user_id = ?
        """, (user_id,)).fetchone()

    if team is None:
        return None

    return dict(team)


def build_internal_team_name(user_or_display_name=None, username=None):
    """
    fantasy_teams.team_name 컬럼은 DB 호환을 위해 유지하지만,
    화면에는 더 이상 유저가 만든 팀 이름으로 노출하지 않습니다.
    내부 저장값은 표시 이름 기반으로만 채웁니다.
    """
    if isinstance(user_or_display_name, dict):
        display_name = user_or_display_name.get("display_name")
        username = user_or_display_name.get("username")
    else:
        display_name = user_or_display_name

    base_name = (display_name or username or "MyPick Manager").strip()
    return base_name or "MyPick Manager"


def create_default_team_for_user(user_id, display_name=None, username=None):
    """
    팀 이름 입력 없이 기본 스쿼드를 생성합니다.

    주의:
    - 기존 팀이 있으면 새로 만들지 않습니다.
    - fantasy_teams.team_name은 DB 호환용 내부값으로만 사용합니다.
    """
    internal_team_name = build_internal_team_name(display_name, username)

    with get_conn() as conn:
        existing_team = conn.execute("""
            SELECT
                id,
                user_id,
                team_name,
                budget_limit,
                cash_balance_decimal,
                COALESCE(is_confirmed, 0) AS is_confirmed,
                confirmed_at,
                confirmed_budget_used,
                captain_registered_player_id,
                created_at,
                updated_at
            FROM fantasy_teams
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if existing_team is not None:
            return dict(existing_team)

        cursor = conn.execute("""
            INSERT INTO fantasy_teams (
                user_id,
                team_name,
                budget_limit,
                cash_balance_decimal
            )
            VALUES (?, ?, 100, 100.0)
        """, (
            user_id,
            internal_team_name,
        ))

        team_id = cursor.lastrowid
        created_team = conn.execute("""
            SELECT
                id,
                user_id,
                team_name,
                budget_limit,
                cash_balance_decimal,
                COALESCE(is_confirmed, 0) AS is_confirmed,
                confirmed_at,
                confirmed_budget_used,
                captain_registered_player_id,
                created_at,
                updated_at
            FROM fantasy_teams
            WHERE id = ?
        """, (team_id,)).fetchone()

    return dict(created_team) if created_team is not None else None


def get_team_summary(team_id, budget_limit=100):
    """
    팀의 현재 상태를 계산합니다.

    예산 원칙:
    - locked_price_decimal은 선수의 영입가이며 자동으로 시장가로 바뀌지 않습니다.
    - cash_balance_decimal은 실제 추가 영입에 사용할 수 있는 사용가능 예산입니다.
    - 팀 가치는 현재 시장가 합산으로 보여주며 100.0을 초과할 수 있습니다.
    - 선수 방출의 기본 회수액은 시장가입니다.
    - 단, 방출 전 로스터 시장가 합산이 100.0을 초과하고 해당 선수에게 상승분이 있을 때만
      초과분 일부를 방출 수익로 전환합니다.
    """
    latest_price_date = get_latest_price_date()
    latest_game_date = get_latest_synced_game_date()

    try:
        budget_limit_number = float(budget_limit or 100)
    except (TypeError, ValueError):
        budget_limit_number = 100.0

    with get_conn() as conn:
        team_row = conn.execute("""
            SELECT
                id,
                budget_limit,
                cash_balance_decimal,
                COALESCE(is_confirmed, 0) AS is_confirmed,
                confirmed_at,
                confirmed_budget_used,
                captain_registered_player_id
            FROM fantasy_teams
            WHERE id = ?
        """, (team_id,)).fetchone()

        team_is_confirmed = 0
        confirmed_at = None
        confirmed_budget_used = None
        captain_registered_player_id = None
        raw_cash_balance = None

        if team_row is not None:
            if team_row["budget_limit"] is not None:
                try:
                    budget_limit_number = float(team_row["budget_limit"] or budget_limit_number)
                except (TypeError, ValueError):
                    pass
            team_is_confirmed = int(team_row["is_confirmed"] or 0)
            confirmed_at = team_row["confirmed_at"]
            confirmed_budget_used = team_row["confirmed_budget_used"]
            captain_registered_player_id = team_row["captain_registered_player_id"]
            raw_cash_balance = team_row["cash_balance_decimal"]

        players = conn.execute("""
            SELECT
                ftp.slot,
                ftp.locked_price_decimal,
                ftp.locked_price_basis_date,
                ftp.locked_at,
                rp.id AS registered_player_id,
                rp.player_id,
                rp.name,
                rp.team,
                rp.back_no,
                rp.is_active,
                rp.detail_position,
                rp.fantasy_position_type,
                COALESCE(pp.price_decimal, pp.price, 0) AS current_market_price,
                pp.price AS price_integer,
                pp.price_decimal,
                pp.tier,
                COALESCE(fds_daily.daily_points, 0) AS total_points,
                COALESCE(fpt.total_points, 0) AS cumulative_points
            FROM fantasy_team_players ftp
            JOIN registered_players rp
              ON ftp.registered_player_id = rp.id
            LEFT JOIN (
                SELECT
                    player_name,
                    team,
                    position_type,
                    SUM(points) AS daily_points
                FROM fantasy_daily_scores
                WHERE game_date = ?
                GROUP BY player_name, team, position_type
            ) fds_daily
              ON rp.name = fds_daily.player_name
             AND rp.team = fds_daily.team
             AND rp.fantasy_position_type = fds_daily.position_type
            LEFT JOIN player_prices pp
              ON rp.id = pp.registered_player_id
             AND pp.basis_source = ?
             AND pp.basis_date = ?
            LEFT JOIN fantasy_player_totals fpt
              ON rp.name = fpt.player_name
             AND rp.team = fpt.team
             AND rp.fantasy_position_type = fpt.position_type
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
            latest_game_date,
            BASIS_SOURCE,
            latest_price_date,
            team_id,
        )).fetchall()

    player_list = []

    for player in players:
        player_dict = dict(player)
        player_dict["is_captain"] = (
            captain_registered_player_id is not None
            and int(player_dict.get("registered_player_id") or 0) == int(captain_registered_player_id or 0)
        )
        decorate_market_status(player_dict)
        apply_market_price_record(player_dict, price_key="current_market_price", current_key="current_market_price")

        current_market_price = player_dict.get("current_market_price")
        if current_market_price is not None:
            current_market_price = round(float(current_market_price or 0), 1)

        locked_price = player_dict.get("locked_price_decimal")
        if locked_price is not None:
            locked_price = round(float(locked_price or 0), 1)

        if locked_price is not None:
            applied_price = locked_price
            applied_price_label = "영입가"
        else:
            applied_price = current_market_price
            applied_price_label = "시장가"

        if applied_price is not None:
            applied_price = round(float(applied_price or 0), 1)

        market_reference_price = locked_price if locked_price is not None else applied_price
        market_price_delta = None
        market_price_trend_class = "market-price-same"

        if current_market_price is not None and market_reference_price is not None:
            market_price_delta = round(float(current_market_price or 0) - float(market_reference_price or 0), 1)
            if market_price_delta > 0:
                market_price_trend_class = "market-price-up"
            elif market_price_delta < 0:
                market_price_trend_class = "market-price-down"

        base_daily_points = round(float(player_dict.get("total_points") or 0), 1)
        captain_multiplier = 2.0 if player_dict.get("is_captain") else 1.0
        team_daily_points = round(base_daily_points * captain_multiplier, 1)

        player_dict["base_points"] = base_daily_points
        player_dict["captain_multiplier"] = captain_multiplier
        player_dict["team_points"] = team_daily_points
        player_dict["total_points"] = team_daily_points
        player_dict["current_market_price"] = current_market_price
        player_dict["market_price"] = current_market_price
        player_dict["market_price_delta"] = market_price_delta
        player_dict["market_price_trend_class"] = market_price_trend_class
        player_dict["stored_locked_price_decimal"] = locked_price
        player_dict["locked_price_decimal"] = locked_price
        player_dict["applied_price"] = applied_price
        player_dict["applied_price_decimal"] = applied_price
        player_dict["effective_price"] = applied_price
        player_dict["price"] = applied_price
        player_dict["applied_price_label"] = applied_price_label

        slot_requirement = get_slot_requirement(player_dict.get("slot"))
        mismatch_reason = get_slot_position_mismatch_reason(player_dict, player_dict.get("slot"))
        player_dict["slot_expected_position_type"] = slot_requirement.get("position_type")
        player_dict["slot_expected_detail_position"] = slot_requirement.get("detail_position")
        player_dict["is_position_eligible"] = mismatch_reason is None
        player_dict["position_mismatch_reason"] = mismatch_reason

        player_list.append(player_dict)

    acquisition_cost_total = round(
        sum(float(player["price"] or 0) for player in player_list),
        1
    )

    team_market_value = round(
        sum(float(player.get("current_market_price") or 0) for player in player_list),
        1
    )
    # 현재 팀 가치는 시장가 합산 그대로 보여줍니다. 가격 상승 보상이 의미 있게 보이도록
    # 100.0 화면 상한을 적용하지 않습니다. 기존 키는 템플릿 호환을 위해 유지합니다.
    team_market_value_capped = team_market_value
    is_team_market_value_capped = False

    budget_state = calculate_strict_budget_state(
        budget_limit=budget_limit_number,
        acquisition_cost_total=acquisition_cost_total,
        raw_cash_balance=raw_cash_balance,
    )
    raw_cash_balance_decimal = budget_state["raw_cash_balance_decimal"]
    strict_available_budget = budget_state["strict_available_budget"]
    cash_balance_decimal = budget_state["available_budget"]
    remaining_budget = cash_balance_decimal
    available_budget = cash_balance_decimal
    cash_over_cap_amount = budget_state["cash_over_cap_amount"]
    acquisition_over_budget_amount = budget_state["acquisition_over_budget_amount"]
    is_budget_state_valid = budget_state["is_budget_state_valid"]

    # 팀 가치는 현재 시장가 합산 그대로이며, 사용가능 예산은 실제 cash_balance_decimal입니다.
    gross_operating_value = round(available_budget + team_market_value, 1)
    team_operating_value = gross_operating_value
    budget_usage_value = acquisition_cost_total

    total_points = sum(player["total_points"] or 0 for player in player_list)
    selected_count = len(player_list)

    captain_player = None
    for player in player_list:
        if player.get("is_captain"):
            captain_player = player
            break

    return {
        "players": player_list,
        "selected_count": selected_count,
        "used_budget": acquisition_cost_total,
        "acquisition_cost_total": acquisition_cost_total,
        "cash_balance_decimal": cash_balance_decimal,
        "raw_cash_balance_decimal": raw_cash_balance_decimal,
        "strict_available_budget": strict_available_budget,
        "cash_over_cap_amount": cash_over_cap_amount,
        "acquisition_over_budget_amount": acquisition_over_budget_amount,
        "is_budget_state_valid": is_budget_state_valid,
        "gross_operating_value": gross_operating_value,
        "team_operating_value": team_operating_value,
        "budget_usage_value": budget_usage_value,
        "remaining_budget": remaining_budget,
        "available_budget": available_budget,
        "total_points": total_points,
        "team_market_value": team_market_value,
        "team_market_value_capped": team_market_value_capped,
        "is_team_market_value_capped": is_team_market_value_capped,
        "latest_game_date": latest_game_date,
        "latest_game_date_display": format_game_date_for_display(latest_game_date),
        "latest_price_date": latest_price_date,
        "is_confirmed": team_is_confirmed,
        "confirmed_at": confirmed_at,
        "confirmed_budget_used": confirmed_budget_used,
        "captain_registered_player_id": captain_registered_player_id,
        "captain_player": captain_player,
    }

def get_best_total_rank(team_id):
    """경기 수익, 방출 수익, 배팅 손익을 날짜순 누적해 역대 최고 전체 순위를 계산합니다."""
    if not team_id:
        return None

    with get_conn() as conn:
        ensure_trade_bonus_tables(conn)
        ensure_betting_tables(conn)
        rows = conn.execute("""
            SELECT
                team_id,
                game_date AS event_date,
                total_points AS points
            FROM fantasy_team_daily_scores

            UNION ALL

            SELECT
                team_id,
                event_date,
                bonus_points AS points
            FROM fantasy_team_trade_bonus_events
            WHERE bonus_points <> 0

            UNION ALL

            SELECT
                ft.id AS team_id,
                date(bl.created_at) AS event_date,
                bl.amount_points AS points
            FROM betting_ledger bl
            JOIN fantasy_teams ft
              ON ft.user_id = bl.user_id
            WHERE bl.amount_points <> 0

            ORDER BY event_date ASC, team_id ASC
        """).fetchall()

    if not rows:
        return None

    totals = {}
    best_rank = None
    current_date = None
    date_rows = []

    def apply_date_rows(items):
        nonlocal best_rank

        if not items:
            return

        for item in items:
            item_team_id = int(item["team_id"])
            totals[item_team_id] = totals.get(item_team_id, 0.0) + float(item["points"] or 0)

        ranked_team_ids = [
            ranked_team_id
            for ranked_team_id, _ in sorted(
                totals.items(),
                key=lambda pair: (-pair[1], pair[0])
            )
            if totals.get(ranked_team_id, 0) > 0
        ]

        target_id = int(team_id)
        if target_id in ranked_team_ids:
            current_rank = ranked_team_ids.index(target_id) + 1
            if best_rank is None or current_rank < best_rank:
                best_rank = current_rank

    for row in rows:
        row_date = row["event_date"]
        if current_date is None:
            current_date = row_date

        if row_date != current_date:
            apply_date_rows(date_rows)
            current_date = row_date
            date_rows = []

        date_rows.append(row)

    apply_date_rows(date_rows)
    return best_rank


def get_team_score_summary(team_id):
    """
    /my-team과 프로필에 표시할 유저 팀 재산 요약을 가져옵니다.

    총 재산 = 경기 수익 + 방출 수익 + 배팅 손익
    최근 경기 수익은 실제 fantasy_team_daily_scores의 최신 경기 점수만 표시합니다.
    """
    empty_summary = {
        "total_points": 0.0,
        "trade_bonus_points": 0.0,
        "betting_points": 0.0,
        "recent_points": None,
        "recent_game_date": None,
        "recent_game_date_display": "-",
        "game_count": 0,
        "last_scored_date": None,
        "last_scored_date_display": "-",
        "total_rank": None,
        "total_rank_count": 0,
        "total_rank_percent": None,
        "best_total_rank": None,
        "recent_rank": None,
        "recent_rank_count": 0,
        "has_scores": False,
    }

    if not team_id:
        return empty_summary

    with get_conn() as conn:
        ensure_trade_bonus_tables(conn)
        ensure_betting_tables(conn)

        own = conn.execute("""
            SELECT
                ft.user_id,
                COALESCE(score_summary.total_points, 0) AS game_points,
                COALESCE(score_summary.game_count, 0) AS game_count,
                score_summary.last_scored_date,
                COALESCE(bonus_summary.trade_bonus_points, 0) AS trade_bonus_points,
                COALESCE(betting_summary.betting_points, 0) AS betting_points
            FROM fantasy_teams ft
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(total_points) AS total_points,
                    COUNT(*) AS game_count,
                    MAX(game_date) AS last_scored_date
                FROM fantasy_team_daily_scores
                GROUP BY team_id
            ) score_summary
              ON score_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(bonus_points) AS trade_bonus_points
                FROM fantasy_team_trade_bonus_events
                GROUP BY team_id
            ) bonus_summary
              ON bonus_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    user_id,
                    SUM(amount_points) AS betting_points
                FROM betting_ledger
                GROUP BY user_id
            ) betting_summary
              ON betting_summary.user_id = ft.user_id
            WHERE ft.id = ?
        """, (team_id,)).fetchone()

        if own is None:
            return empty_summary

        game_count = int(own["game_count"] or 0)
        game_points = round(float(own["game_points"] or 0), 1)
        trade_bonus_points = round(float(own["trade_bonus_points"] or 0), 1)
        betting_points = round(float(own["betting_points"] or 0), 1)
        total_points = round(game_points + trade_bonus_points + betting_points, 1)
        last_scored_date = own["last_scored_date"]

        if game_count <= 0 and trade_bonus_points == 0 and betting_points == 0:
            return empty_summary

        recent_row = conn.execute("""
            SELECT
                game_date,
                total_points
            FROM fantasy_team_daily_scores
            WHERE team_id = ?
            ORDER BY game_date DESC, id DESC
            LIMIT 1
        """, (team_id,)).fetchone()

        total_rank_rows = conn.execute("""
            SELECT
                ft.id AS team_id,
                COALESCE(score_summary.total_points, 0)
                + COALESCE(bonus_summary.trade_bonus_points, 0)
                + COALESCE(betting_summary.betting_points, 0) AS total_points,
                COALESCE(score_summary.game_count, 0) AS game_count,
                score_summary.last_scored_date
            FROM fantasy_teams ft
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(total_points) AS total_points,
                    COUNT(*) AS game_count,
                    MAX(game_date) AS last_scored_date
                FROM fantasy_team_daily_scores
                GROUP BY team_id
            ) score_summary
              ON score_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(bonus_points) AS trade_bonus_points
                FROM fantasy_team_trade_bonus_events
                GROUP BY team_id
            ) bonus_summary
              ON bonus_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    user_id,
                    SUM(amount_points) AS betting_points
                FROM betting_ledger
                GROUP BY user_id
            ) betting_summary
              ON betting_summary.user_id = ft.user_id
            WHERE COALESCE(score_summary.total_points, 0)
                + COALESCE(bonus_summary.trade_bonus_points, 0)
                + COALESCE(betting_summary.betting_points, 0) > 0
            ORDER BY
                total_points DESC,
                game_count DESC,
                score_summary.last_scored_date ASC,
                ft.id ASC
        """).fetchall()

        latest_scored_game_date_row = conn.execute("""
            SELECT MAX(game_date) AS latest_game_date
            FROM fantasy_team_daily_scores
        """).fetchone()

        latest_scored_game_date = None
        if latest_scored_game_date_row is not None:
            latest_scored_game_date = latest_scored_game_date_row["latest_game_date"]

        recent_rank_rows = []
        if latest_scored_game_date:
            recent_rank_rows = conn.execute("""
                SELECT
                    team_id,
                    total_points
                FROM fantasy_team_daily_scores
                WHERE game_date = ?
                  AND total_points > 0
                ORDER BY
                    total_points DESC,
                    team_id ASC
            """, (latest_scored_game_date,)).fetchall()

    total_rank = None
    for index, row in enumerate(total_rank_rows, start=1):
        if int(row["team_id"]) == int(team_id):
            total_rank = index
            break

    recent_rank = None
    for index, row in enumerate(recent_rank_rows, start=1):
        if int(row["team_id"]) == int(team_id):
            recent_rank = index
            break

    recent_points = None
    recent_game_date = None
    best_total_rank = get_best_total_rank(team_id)

    total_rank_percent = None
    if total_rank is not None and len(total_rank_rows) > 0:
        total_rank_percent = round((float(total_rank) / float(len(total_rank_rows))) * 100, 1)

    if recent_row is not None:
        recent_points = round(float(recent_row["total_points"] or 0), 1)
        recent_game_date = recent_row["game_date"]

    return {
        "total_points": total_points,
        "trade_bonus_points": trade_bonus_points,
        "betting_points": betting_points,
        "recent_points": recent_points,
        "recent_game_date": recent_game_date,
        "recent_game_date_display": format_game_date_for_display(recent_game_date),
        "game_count": game_count,
        "last_scored_date": last_scored_date,
        "last_scored_date_display": format_game_date_for_display(last_scored_date),
        "total_rank": total_rank,
        "total_rank_count": len(total_rank_rows),
        "total_rank_percent": total_rank_percent,
        "best_total_rank": best_total_rank,
        "recent_rank": recent_rank,
        "recent_rank_count": len(recent_rank_rows),
        "has_scores": True,
    }


def get_recent_team_scores(team_id, limit=5):
    """
    /my-team에 표시할 최근 팀 점수 기록을 가져옵니다.
    """
    if not team_id:
        return []

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                id,
                game_date,
                total_points,
                roster_player_count,
                is_confirmed_snapshot,
                created_at,
                updated_at
            FROM fantasy_team_daily_scores
            WHERE team_id = ?
            ORDER BY game_date DESC, id DESC
            LIMIT ?
        """, (
            team_id,
            limit,
        )).fetchall()

    result = []

    for row in rows:
        item = dict(row)
        item["game_date_display"] = format_game_date_for_display(item["game_date"])
        item["total_points"] = round(float(item["total_points"] or 0), 1)
        result.append(item)

    return result


def get_team_score_history(team_id, limit=370):
    """
    /my-team 총 점수 변동 그래프용 누적 점수 history를 가져옵니다.
    경기 점수와 방출 수익를 같은 누적 포인트 흐름에 합산합니다.
    """
    if not team_id:
        return []

    with get_conn() as conn:
        ensure_trade_bonus_tables(conn)
        rows = conn.execute("""
            SELECT
                id,
                game_date AS event_date,
                total_points AS points,
                'game' AS event_type
            FROM fantasy_team_daily_scores
            WHERE team_id = ?

            UNION ALL

            SELECT
                id,
                event_date,
                bonus_points AS points,
                'trade_bonus' AS event_type
            FROM fantasy_team_trade_bonus_events
            WHERE team_id = ?
              AND bonus_points > 0

            ORDER BY event_date DESC, id DESC
            LIMIT ?
        """, (
            team_id,
            team_id,
            int(limit or 370),
        )).fetchall()

    rows = list(reversed(rows))
    result = []
    cumulative_points = 0.0

    for row in rows:
        item = dict(row)
        event_points = round(float(item.get("points") or 0), 1)
        cumulative_points = round(cumulative_points + event_points, 1)

        result.append({
            "id": item.get("id"),
            "game_date": item.get("event_date"),
            "game_date_display": format_game_date_for_display(item.get("event_date")),
            "game_points": event_points,
            "cumulative_points": cumulative_points,
            "event_type": item.get("event_type"),
        })

    return result


def get_roster_slots():
    """
    판타지 팀 로스터 슬롯 목록입니다.
    """
    return [
        {"slot": "C", "label": "포수"},
        {"slot": "1B", "label": "1루수"},
        {"slot": "2B", "label": "2루수"},
        {"slot": "3B", "label": "3루수"},
        {"slot": "SS", "label": "유격수"},
        {"slot": "LF", "label": "좌익수"},
        {"slot": "CF", "label": "중견수"},
        {"slot": "RF", "label": "우익수"},
        {"slot": "UTIL", "label": "지명타자/UTIL"},
        {"slot": "P1", "label": "SP"},
        {"slot": "P2", "label": "P1"},
        {"slot": "P3", "label": "P2"},
        {"slot": "P4", "label": "P3"},
        {"slot": "P5", "label": "P4"},
        {"slot": "P6", "label": "P5"},
    ]


def get_valid_slot_values():
    return [slot_info["slot"] for slot_info in get_roster_slots()]


def get_slot_label(slot):
    for slot_info in get_roster_slots():
        if slot_info["slot"] == slot:
            return slot_info["label"]
    return slot


# Slot eligibility rules are centralized in position_rules.py so that
# search, add, validation, and scoring all use the same standard.
def get_slot_requirement(slot):
    return get_slot_requirement_shared(slot)


def get_slot_position_mismatch_reason(player, slot):
    """선수가 현재 슬롯에서 뛸 수 없으면 사유를 반환하고, 가능하면 None을 반환합니다."""
    return get_position_mismatch_reason_shared(
        player.get("fantasy_position_type") or player.get("position_type"),
        player.get("detail_position"),
        slot,
    )


def is_player_eligible_for_slot(player, slot):
    return get_slot_position_mismatch_reason(player, slot) is None


def build_roster_rows(summary):
    """
    템플릿에서 15개 슬롯을 항상 보여주기 위한 로스터 행을 만듭니다.
    """
    players_by_slot = {}

    if summary is not None:
        for player in summary["players"]:
            players_by_slot[player["slot"]] = player

    roster_rows = []

    for slot_info in get_roster_slots():
        slot = slot_info["slot"]
        roster_rows.append({
            "slot": slot,
            "label": slot_info["label"],
            "player": players_by_slot.get(slot),
        })

    return roster_rows


def find_auto_slot_for_player(player, summary):
    """선수의 현재 포지션을 보고 자동으로 들어갈 슬롯을 찾습니다.

    원칙:
    - 영입 시점에는 현재 포지션에 맞는 슬롯만 허용합니다.
    - UTIL/지명타자 슬롯은 별도 DH 포지션을 요구하지 않고 모든 타자를 허용합니다.
    - 내야수는 1B/2B/3B/SS 중 빈 슬롯, 외야수는 LF/CF/RF 중 빈 슬롯을 허용합니다.
    """
    used_slots = {selected_player["slot"] for selected_player in summary["players"]}

    for candidate_slot in candidate_slots_for_detail(
        player.get("fantasy_position_type"),
        player.get("detail_position"),
    ):
        if candidate_slot not in used_slots and is_player_eligible_for_slot(player, candidate_slot):
            return candidate_slot

    return None

def validate_team_roster(summary, budget_limit):
    """
    팀이 완성 조건을 만족하는지 검사합니다.
    """
    required_slots = get_valid_slot_values()
    hitter_slots = [
        "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "UTIL"
    ]
    pitcher_slots = [
        "P1", "P2", "P3", "P4", "P5", "P6"
    ]
    bullpen_slots = [
        "P2", "P3", "P4", "P5", "P6"
    ]

    selected_slots = [
        player["slot"]
        for player in summary["players"]
    ]

    players_by_slot = {
        player["slot"]: player
        for player in summary["players"]
    }

    missing_slots = [
        slot
        for slot in required_slots
        if slot not in selected_slots
    ]

    missing_hitter_slots = [
        slot
        for slot in hitter_slots
        if slot not in selected_slots
    ]

    missing_pitcher_slots = [
        slot
        for slot in pitcher_slots
        if slot not in selected_slots
    ]

    pitcher_players = [
        player
        for player in summary["players"]
        if player["fantasy_position_type"] == "pitcher"
    ]

    starter_players = [
        player
        for player in pitcher_players
        if player.get("detail_position") == "선발투수"
    ]

    bullpen_players = [
        player
        for player in pitcher_players
        if player.get("detail_position") == "불펜투수"
    ]

    unknown_role_pitchers = [
        player
        for player in pitcher_players
        if player.get("detail_position") not in ["선발투수", "불펜투수"]
    ]

    problems = []

    if summary["selected_count"] != 15:
        problems.append(f'총 선수 수가 15명이 아닙니다. 현재 {summary["selected_count"]}명입니다.')

    if missing_slots:
        missing_labels = [
            f"{slot}({get_slot_label(slot)})"
            for slot in missing_slots
        ]
        problems.append("비어 있는 슬롯: " + ", ".join(missing_labels))

    if missing_hitter_slots:
        missing_labels = [
            f"{slot}({get_slot_label(slot)})"
            for slot in missing_hitter_slots
        ]
        problems.append("비어 있는 타자 슬롯: " + ", ".join(missing_labels))

    if missing_pitcher_slots:
        missing_labels = [
            f"{slot}({get_slot_label(slot)})"
            for slot in missing_pitcher_slots
        ]
        problems.append("비어 있는 투수 슬롯: " + ", ".join(missing_labels))

    for slot, player in players_by_slot.items():
        mismatch_reason = get_slot_position_mismatch_reason(player, slot)
        if mismatch_reason:
            problems.append(mismatch_reason)

    if len(starter_players) != 1:
        problems.append(f"선발투수는 정확히 1명이어야 합니다. 현재 {len(starter_players)}명입니다.")

    if len(bullpen_players) != 5:
        problems.append(f"불펜투수는 정확히 5명이어야 합니다. 현재 {len(bullpen_players)}명입니다.")

    if unknown_role_pitchers:
        unknown_names = [
            f'{player["name"]}({player["team"]})'
            for player in unknown_role_pitchers
        ]
        problems.append(
            "선발/불펜 역할 정보가 없는 투수가 있습니다: " + ", ".join(unknown_names)
        )

    if summary.get("captain_registered_player_id") and summary.get("captain_player") is None:
        problems.append("지정된 C 선수가 현재 로스터에 없습니다. C를 다시 지정해주세요.")

    try:
        budget_limit_number = round(float(budget_limit or 100.0), 1)
    except (TypeError, ValueError):
        budget_limit_number = 100.0

    acquisition_total = round(float(summary.get("acquisition_cost_total") or summary.get("used_budget") or 0.0), 1)
    available_budget = round(float(summary.get("available_budget") or summary.get("remaining_budget") or 0.0), 1)
    cash_over_cap_amount = round(float(summary.get("cash_over_cap_amount") or 0.0), 1)
    acquisition_over_budget_amount = round(float(summary.get("acquisition_over_budget_amount") or 0.0), 1)

    # 새 예산 규칙에서 locked_price_decimal 합계는 선수 손익 계산 기준이며,
    # 팀 확정 가능 여부를 막는 100.0 cap으로 사용하지 않습니다.
    if available_budget < -0.01:
        problems.append("사용가능 예산이 음수입니다. 팀 예산을 확인해주세요.")

    missing_slot_labels = [
        f"{slot}({get_slot_label(slot)})"
        for slot in missing_slots
    ]

    missing_hitter_slot_labels = [
        f"{slot}({get_slot_label(slot)})"
        for slot in missing_hitter_slots
    ]

    missing_pitcher_slot_labels = [
        f"{slot}({get_slot_label(slot)})"
        for slot in missing_pitcher_slots
    ]

    return {
        "is_complete": len(problems) == 0,
        "is_valid": len(problems) == 0,
        "problems": problems,
        "missing_slots": missing_slots,
        "missing_slot_labels": missing_slot_labels,
        "missing_hitter_slots": missing_hitter_slots,
        "missing_hitter_slot_labels": missing_hitter_slot_labels,
        "missing_pitcher_slots": missing_pitcher_slots,
        "missing_pitcher_slot_labels": missing_pitcher_slot_labels,
        "selected_count": summary["selected_count"],
        "used_budget": summary["used_budget"],
        "budget_limit": budget_limit,
        "is_budget_ok": available_budget >= -0.01,
        "starter_count": len(starter_players),
        "bullpen_count": len(bullpen_players),
    }


# ==========================================================
# 라우트
# ==========================================================

def format_month_for_display(month_value):
    """YYYY-MM 값을 화면용 월 표기로 바꿉니다."""
    text = str(month_value or "").strip()
    parts = text.split("-")

    if len(parts) != 2:
        return "-"

    try:
        year = int(parts[0])
        month = int(parts[1])
    except (TypeError, ValueError):
        return "-"

    if month < 1 or month > 12:
        return "-"

    return f"{year}년 {month}월"


def get_ranking_month_options():
    """경기 점수와 방출 수익가 있는 월을 모두 반환합니다."""
    with get_conn() as conn:
        ensure_trade_bonus_tables(conn)
        rows = conn.execute("""
            SELECT month_value
            FROM (
                SELECT DISTINCT substr(game_date, 1, 7) AS month_value
                FROM fantasy_team_daily_scores
                WHERE game_date IS NOT NULL
                  AND length(game_date) >= 7

                UNION

                SELECT DISTINCT substr(event_date, 1, 7) AS month_value
                FROM fantasy_team_trade_bonus_events
                WHERE event_date IS NOT NULL
                  AND length(event_date) >= 7

                UNION

                SELECT DISTINCT substr(created_at, 1, 7) AS month_value
                FROM betting_ledger
                WHERE created_at IS NOT NULL
                  AND length(created_at) >= 7
            )
            WHERE month_value IS NOT NULL
            ORDER BY month_value DESC
        """).fetchall()

    return [
        {
            "value": row["month_value"],
            "label": format_month_for_display(row["month_value"]),
        }
        for row in rows
        if row["month_value"]
    ]




def get_closed_ranking_month_options(month_options=None):
    """프로필의 최고 월별 순위 계산용으로 종료된 월만 반환합니다.

    진행 중인 달은 아직 최종 월별 순위가 확정되지 않았으므로
    '최고 월별 순위' 후보에서 제외합니다.
    """
    options = month_options if month_options is not None else get_ranking_month_options()
    current_month = date.today().strftime("%Y-%m")
    return [
        option
        for option in options
        if option.get("value") and option["value"] < current_month
    ]


def normalize_ranking_month(month_value, month_options=None):
    """월별 랭킹 기준 월을 실제 기록이 있는 월 중 하나로 정리합니다."""
    options = month_options if month_options is not None else get_ranking_month_options()
    available_values = [item["value"] for item in options]

    requested = str(month_value or "").strip()
    if requested in available_values:
        return requested

    if available_values:
        return available_values[0]

    return None


def get_best_daily_rank(team_id):
    """해당 팀이 실제 점수를 얻은 경기일 중 최고 일일 순위를 계산합니다."""
    if not team_id:
        return None

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                game_date,
                team_id,
                total_points
            FROM fantasy_team_daily_scores
            ORDER BY game_date ASC, total_points DESC, team_id ASC
        """).fetchall()

    if not rows:
        return None

    best_rank = None
    current_date = None
    date_rows = []

    def apply_date(items):
        nonlocal best_rank
        ranked_items = [item for item in items if float(item["total_points"] or 0) > 0]
        ranked_items.sort(key=lambda item: (-float(item["total_points"] or 0), int(item["team_id"] or 0)))

        for index, item in enumerate(ranked_items, start=1):
            if int(item["team_id"] or 0) == int(team_id):
                if best_rank is None or index < best_rank:
                    best_rank = index
                break

    for row in rows:
        row_date = row["game_date"]
        if current_date is None:
            current_date = row_date

        if row_date != current_date:
            apply_date(date_rows)
            current_date = row_date
            date_rows = []

        date_rows.append(dict(row))

    apply_date(date_rows)
    return best_rank


def get_monthly_rankings_for_month(month_value):
    """특정 월의 팀별 월간 수익 랭킹 원자료를 계산합니다.

    월간 수익 = 경기 수익 + 방출 수익 + 해당 월 배팅 ledger 손익
    """
    if isinstance(month_value, dict):
        month_value = month_value.get("value")
    if not month_value:
        return []

    with get_conn() as conn:
        ensure_trade_bonus_tables(conn)
        ensure_betting_tables(conn)
        rows = conn.execute("""
            SELECT
                ft.id AS team_id,
                COALESCE(game_summary.monthly_points, 0)
                + COALESCE(trade_summary.monthly_bonus_points, 0)
                + COALESCE(betting_summary.monthly_betting_points, 0) AS monthly_points,
                COALESCE(game_summary.monthly_game_count, 0) AS monthly_game_count,
                game_summary.last_monthly_date
            FROM fantasy_teams ft
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(total_points) AS monthly_points,
                    COUNT(*) AS monthly_game_count,
                    MAX(game_date) AS last_monthly_date
                FROM fantasy_team_daily_scores
                WHERE substr(game_date, 1, 7) = ?
                GROUP BY team_id
            ) game_summary
              ON game_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(bonus_points) AS monthly_bonus_points
                FROM fantasy_team_trade_bonus_events
                WHERE substr(event_date, 1, 7) = ?
                GROUP BY team_id
            ) trade_summary
              ON trade_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    ft_inner.id AS team_id,
                    SUM(bl.amount_points) AS monthly_betting_points
                FROM betting_ledger bl
                JOIN fantasy_teams ft_inner
                  ON ft_inner.user_id = bl.user_id
                WHERE substr(bl.created_at, 1, 7) = ?
                GROUP BY ft_inner.id
            ) betting_summary
              ON betting_summary.team_id = ft.id
            WHERE COALESCE(game_summary.monthly_points, 0)
                + COALESCE(trade_summary.monthly_bonus_points, 0)
                + COALESCE(betting_summary.monthly_betting_points, 0) <> 0
            ORDER BY
                monthly_points DESC,
                monthly_game_count DESC,
                game_summary.last_monthly_date ASC,
                ft.id ASC
        """, (month_value, month_value, month_value)).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["monthly_points"] = round(float(item.get("monthly_points") or 0), 1)
        item["monthly_game_count"] = int(item.get("monthly_game_count") or 0)
        result.append(item)

    return result


def get_team_monthly_summary(team_id, selected_month=None):
    """프로필용 월간 순위/최고 월간 순위를 계산합니다."""
    empty = {
        "selected_month": selected_month,
        "selected_month_display": format_month_for_display(selected_month),
        "monthly_points": 0.0,
        "monthly_rank": None,
        "monthly_rank_count": 0,
        "best_monthly_rank": None,
        "best_month": None,
        "best_month_display": "-",
        "best_month_points": 0.0,
        "best_monthly_note": "종료된 월 기준",
    }

    if not team_id:
        return empty

    month_options = get_ranking_month_options()
    selected_month = normalize_ranking_month(selected_month, month_options)
    empty["selected_month"] = selected_month
    empty["selected_month_display"] = format_month_for_display(selected_month)

    if not selected_month:
        return empty

    current_month_rows = get_monthly_rankings_for_month(selected_month)
    ranked_current = [row for row in current_month_rows if row["monthly_points"] > 0]

    for index, row in enumerate(ranked_current, start=1):
        if int(row["team_id"] or 0) == int(team_id):
            empty["monthly_points"] = row["monthly_points"]
            empty["monthly_rank"] = index
            break

    empty["monthly_rank_count"] = len(ranked_current)

    best_rank = None
    best_month = None
    best_month_points = 0.0

    closed_month_options = get_closed_ranking_month_options(month_options)

    for option in closed_month_options:
        month_value = option["value"]
        month_rows = get_monthly_rankings_for_month(month_value)
        ranked_month_rows = [row for row in month_rows if row["monthly_points"] > 0]

        for index, row in enumerate(ranked_month_rows, start=1):
            if int(row["team_id"] or 0) == int(team_id):
                if (
                    best_rank is None
                    or index < best_rank
                    or (index == best_rank and row["monthly_points"] > best_month_points)
                ):
                    best_rank = index
                    best_month = month_value
                    best_month_points = row["monthly_points"]
                break

    empty["best_monthly_rank"] = best_rank
    empty["best_month"] = best_month
    empty["best_month_display"] = format_month_for_display(best_month)
    empty["best_month_points"] = round(float(best_month_points or 0), 1)

    return empty


def get_profile_player_highlights(team_id):
    """프로필에 표시할 내 팀 기여 선수 하이라이트를 계산합니다."""
    highlights = {
        "top_contributor": None,
        "recent_ace": None,
        "best_profit_player": None,
    }

    if not team_id:
        return highlights

    latest_price_date = get_latest_price_date()

    with get_conn() as conn:
        top_contributor = conn.execute("""
            SELECT
                ftdps.registered_player_id,
                ftdps.player_name AS name,
                ftdps.player_team AS team,
                ftdps.position_type AS fantasy_position_type,
                rp.back_no,
                rp.is_active,
                rp.detail_position,
                SUM(ftdps.points) AS contribution_points,
                COUNT(*) AS game_count,
                SUM(COALESCE(ftdps.is_captain, 0)) AS captain_game_count
            FROM fantasy_team_daily_player_scores ftdps
            LEFT JOIN registered_players rp
              ON rp.id = ftdps.registered_player_id
            WHERE ftdps.team_id = ?
            GROUP BY ftdps.registered_player_id, ftdps.player_name, ftdps.player_team, ftdps.position_type
            HAVING SUM(ftdps.points) > 0
            ORDER BY SUM(ftdps.points) DESC, COUNT(*) DESC, ftdps.player_name ASC
            LIMIT 1
        """, (team_id,)).fetchone()

        if top_contributor is not None:
            item = dict(top_contributor)
            item["contribution_points"] = round(float(item.get("contribution_points") or 0), 1)
            item["game_count"] = int(item.get("game_count") or 0)
            item["captain_game_count"] = int(item.get("captain_game_count") or 0)
            item["is_captain"] = item["captain_game_count"] > 0
            highlights["top_contributor"] = item

        recent_ace = conn.execute("""
            WITH recent_dates AS (
                SELECT DISTINCT game_date
                FROM fantasy_team_daily_player_scores
                WHERE team_id = ?
                ORDER BY game_date DESC
                LIMIT 5
            )
            SELECT
                ftdps.registered_player_id,
                ftdps.player_name AS name,
                ftdps.player_team AS team,
                ftdps.position_type AS fantasy_position_type,
                rp.back_no,
                rp.is_active,
                rp.detail_position,
                SUM(ftdps.points) AS contribution_points,
                COUNT(*) AS game_count,
                SUM(COALESCE(ftdps.is_captain, 0)) AS captain_game_count
            FROM fantasy_team_daily_player_scores ftdps
            JOIN recent_dates rd
              ON rd.game_date = ftdps.game_date
            LEFT JOIN registered_players rp
              ON rp.id = ftdps.registered_player_id
            WHERE ftdps.team_id = ?
            GROUP BY ftdps.registered_player_id, ftdps.player_name, ftdps.player_team, ftdps.position_type
            HAVING SUM(ftdps.points) > 0
            ORDER BY SUM(ftdps.points) DESC, COUNT(*) DESC, ftdps.player_name ASC
            LIMIT 1
        """, (team_id, team_id)).fetchone()

        if recent_ace is not None:
            item = dict(recent_ace)
            item["contribution_points"] = round(float(item.get("contribution_points") or 0), 1)
            item["game_count"] = int(item.get("game_count") or 0)
            item["captain_game_count"] = int(item.get("captain_game_count") or 0)
            item["is_captain"] = item["captain_game_count"] > 0
            highlights["recent_ace"] = item

        best_profit_rows = conn.execute("""
            SELECT
                rp.id AS registered_player_id,
                rp.name,
                rp.team,
                rp.fantasy_position_type,
                rp.back_no,
                rp.is_active,
                rp.detail_position,
                ftp.locked_price_decimal,
                NULL AS current_market_price,
                CASE
                    WHEN ft.captain_registered_player_id = rp.id THEN 1
                    ELSE 0
                END AS is_captain
            FROM fantasy_team_players ftp
            JOIN fantasy_teams ft
              ON ft.id = ftp.team_id
            JOIN registered_players rp
              ON rp.id = ftp.registered_player_id
            WHERE ftp.team_id = ?
              AND ftp.locked_price_decimal IS NOT NULL
        """, (team_id,)).fetchall()

        best_profit_candidates = []
        for best_profit_row in best_profit_rows:
            item = dict(best_profit_row)
            price_record = fetch_market_price_record(
                conn,
                registered_player_id=item.get("registered_player_id"),
                player_name=item.get("name"),
                team=item.get("team"),
                fantasy_position_type=item.get("fantasy_position_type"),
            )
            if price_record is None:
                continue
            current = normalize_market_price_value(price_record.get("price_decimal"))
            if current is None:
                current = normalize_market_price_value(price_record.get("price"))
            if current is None:
                continue
            locked = round(float(item.get("locked_price_decimal") or 0), 1)
            item["locked_price_decimal"] = locked
            item["current_market_price"] = current
            item["profit"] = round(current - locked, 1)
            best_profit_candidates.append(item)

        if best_profit_candidates:
            best_profit_candidates.sort(
                key=lambda item: (
                    -(item.get("profit") or 0),
                    -(item.get("current_market_price") or 0),
                    str(item.get("name") or ""),
                )
            )
            highlights["best_profit_player"] = best_profit_candidates[0]

    return highlights


def build_profile_status(team, summary, validation, team_score_summary):
    """프로필의 운영 상태 카드에 필요한 안전한 상태값을 만듭니다."""
    if team is None:
        return {
            "label": "팀 없음",
            "tone": "neutral",
            "message": "팀을 만들고 15인 로스터를 확정하면 공식 수익을 받을 수 있습니다.",
            "items": [],
        }

    is_confirmed = bool(team.get("is_confirmed"))
    validation_ok = True
    if validation is not None:
        validation_ok = bool(validation.get("is_valid", validation.get("is_complete", False)))
    has_roster_issue = bool(validation is not None and not validation_ok)

    if has_roster_issue:
        label = "수정 필요"
        tone = "warning"
        message = "현재 로스터가 규칙을 만족하지 않아 수익 획득 전에 수정이 필요합니다."
    elif is_confirmed:
        label = "확정됨"
        tone = "success"
        message = "확정된 팀입니다. 경기일에 저장된 수익 기록이 있으면 재산 랭킹에 반영됩니다."
    else:
        label = "미확정"
        tone = "neutral"
        message = "팀을 확정해야 다음 경기일 수익을 받을 수 있습니다."

    inactive_count = 0
    if summary:
        inactive_count = sum(
            1
            for player in summary.get("players", [])
            if bool(player.get("is_display_inactive"))
        )

    items = [
        {"label": "선택 선수", "value": f"{summary.get('selected_count', 0) if summary else 0}/15"},
        {"label": "누적 경기", "value": f"{team_score_summary.get('game_count', 0) if team_score_summary else 0}경기"},
    ]

    if inactive_count > 0:
        items.append({
            "label": "말소 선수",
            "value": f"{inactive_count}명",
            "tone": "inactive",
        })

    return {
        "label": label,
        "tone": tone,
        "message": message,
        "items": items,
    }


def get_latest_team_scored_date():
    """
    유저 랭킹 기준으로 사용할 최신 팀 점수 기록 날짜를 가져옵니다.

    calendar 오늘이 아니라 fantasy_team_daily_scores에 실제 저장된 최신 game_date입니다.
    """
    with get_conn() as conn:
        row = conn.execute("""
            SELECT MAX(game_date) AS latest_scored_date
            FROM fantasy_team_daily_scores
        """).fetchone()

    if row is None:
        return None

    return row["latest_scored_date"]


def get_user_rankings(ranking_type="total", ranking_month=None, search_query="", scope_user_ids=None):
    """
    /user-rankings 페이지에 표시할 유저 팀 랭킹을 가져옵니다.

    total/monthly 기준 점수에는 배팅 ledger 손익을 포함합니다.
    recent 기준은 가장 최근 팀 경기 수익만 사용하며 배팅 ledger 손익은 포함하지 않습니다.
    배팅 전용 랭킹은 만들지 않고, 기존 유저/친구 랭킹의 총 재산 기준에 자연스럽게 합산합니다.
    """
    if ranking_type not in ["total", "monthly", "recent"]:
        ranking_type = "total"

    ensure_user_profile_columns()

    current_user = get_current_user()
    current_user_id = None

    if current_user is not None:
        current_user_id = current_user.get("id")

    latest_scored_date = get_latest_team_scored_date()
    month_options = get_ranking_month_options()
    ranking_month = normalize_ranking_month(ranking_month, month_options)
    search_query = str(search_query or "").strip()
    search_query_lower = search_query.lower()

    scope_user_ids = [int(value) for value in (scope_user_ids or []) if value is not None]
    where_sql = ""
    query_params = [
        latest_scored_date,
        ranking_month,
        ranking_month,
        ranking_month,
    ]

    if scope_user_ids:
        placeholders = ",".join("?" for _ in scope_user_ids)
        where_sql = f"WHERE ft.user_id IN ({placeholders})"
        query_params.extend(scope_user_ids)

    with get_conn() as conn:
        ensure_trade_bonus_tables(conn)
        ensure_betting_tables(conn)
        rows = conn.execute(f"""
            SELECT
                ft.id AS team_id,
                ft.user_id,
                COALESCE(latest_score.team_name_snapshot, ft.team_name) AS team_name_snapshot,
                COALESCE(u.display_name, u.username) AS user_display_name_snapshot,
                u.favorite_kbo_team,
                COALESCE(recent_score.total_points, 0) AS recent_points,
                0 AS recent_betting_points,
                recent_score.game_date AS recent_game_date,
                COALESCE(total_summary.total_points, 0)
                    + COALESCE(trade_bonus_summary.total_bonus_points, 0)
                    + COALESCE(betting_summary.total_betting_points, 0) AS total_points,
                COALESCE(trade_bonus_summary.total_bonus_points, 0) AS trade_bonus_points,
                COALESCE(betting_summary.total_betting_points, 0) AS betting_points,
                COALESCE(total_summary.game_count, 0) AS game_count,
                total_summary.last_scored_date,
                COALESCE(monthly_summary.monthly_points, 0)
                    + COALESCE(monthly_trade_bonus_summary.monthly_bonus_points, 0)
                    + COALESCE(monthly_betting_summary.monthly_betting_points, 0) AS monthly_points,
                COALESCE(monthly_trade_bonus_summary.monthly_bonus_points, 0) AS monthly_trade_bonus_points,
                COALESCE(monthly_betting_summary.monthly_betting_points, 0) AS monthly_betting_points,
                COALESCE(monthly_summary.monthly_game_count, 0) AS monthly_game_count,
                monthly_summary.last_monthly_date
            FROM fantasy_teams ft
            JOIN users u
              ON u.id = ft.user_id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(total_points) AS total_points,
                    COUNT(*) AS game_count,
                    MAX(game_date) AS last_scored_date
                FROM fantasy_team_daily_scores
                GROUP BY team_id
            ) total_summary
              ON total_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(bonus_points) AS total_bonus_points
                FROM fantasy_team_trade_bonus_events
                GROUP BY team_id
            ) trade_bonus_summary
              ON trade_bonus_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    user_id,
                    SUM(amount_points) AS total_betting_points
                FROM betting_ledger
                GROUP BY user_id
            ) betting_summary
              ON betting_summary.user_id = ft.user_id
            LEFT JOIN fantasy_team_daily_scores recent_score
              ON recent_score.team_id = ft.id
             AND recent_score.game_date = ?
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(total_points) AS monthly_points,
                    COUNT(*) AS monthly_game_count,
                    MAX(game_date) AS last_monthly_date
                FROM fantasy_team_daily_scores
                WHERE substr(game_date, 1, 7) = ?
                GROUP BY team_id
            ) monthly_summary
              ON monthly_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(bonus_points) AS monthly_bonus_points
                FROM fantasy_team_trade_bonus_events
                WHERE substr(event_date, 1, 7) = ?
                GROUP BY team_id
            ) monthly_trade_bonus_summary
              ON monthly_trade_bonus_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    user_id,
                    SUM(amount_points) AS monthly_betting_points
                FROM betting_ledger
                WHERE substr(created_at, 1, 7) = ?
                GROUP BY user_id
            ) monthly_betting_summary
              ON monthly_betting_summary.user_id = ft.user_id
            LEFT JOIN fantasy_team_daily_scores latest_score
              ON latest_score.team_id = ft.id
             AND latest_score.game_date = total_summary.last_scored_date
            {where_sql}
        """, query_params).fetchall()

    rankings = []

    for row in rows:
        item = dict(row)
        favorite_team = normalize_kbo_team(item.get("favorite_kbo_team"))

        item["is_my_team"] = (
            current_user_id is not None
            and int(item.get("user_id") or 0) == int(current_user_id)
        )
        item["profile_url"] = (
            url_for("profile")
            if item["is_my_team"]
            else url_for("public_profile", user_id=item.get("user_id"))
        )
        item["team_name"] = item.get("user_display_name_snapshot") or "-"
        item["user_display_name"] = item.get("user_display_name_snapshot") or "-"
        item["favorite_kbo_team"] = favorite_team
        item["favorite_team_meta"] = get_team_meta(favorite_team) if favorite_team else None
        item["total_points"] = round(float(item.get("total_points") or 0), 1)
        item["trade_bonus_points"] = round(float(item.get("trade_bonus_points") or 0), 1)
        item["betting_points"] = round(float(item.get("betting_points") or 0), 1)
        item["recent_points"] = round(float(item.get("recent_points") or 0), 1)
        item["recent_betting_points"] = round(float(item.get("recent_betting_points") or 0), 1)
        item["monthly_points"] = round(float(item.get("monthly_points") or 0), 1)
        item["monthly_trade_bonus_points"] = round(float(item.get("monthly_trade_bonus_points") or 0), 1)
        item["monthly_betting_points"] = round(float(item.get("monthly_betting_points") or 0), 1)
        item["game_count"] = int(item.get("game_count") or 0)
        item["monthly_game_count"] = int(item.get("monthly_game_count") or 0)
        item["recent_game_date_display"] = format_game_date_for_display(
            item.get("recent_game_date")
        )
        item["last_scored_date_display"] = format_game_date_for_display(
            item.get("last_scored_date")
        )
        item["last_monthly_date_display"] = format_game_date_for_display(
            item.get("last_monthly_date")
        )

        if ranking_type == "recent":
            ranking_score = item["recent_points"]
            secondary_score = item["total_points"]
        elif ranking_type == "monthly":
            ranking_score = item["monthly_points"]
            secondary_score = item["total_points"]
        else:
            ranking_score = item["total_points"]
            secondary_score = item["recent_points"]

        item["ranking_score"] = ranking_score
        item["secondary_score"] = secondary_score
        rankings.append(item)

    rankings.sort(
        key=lambda item: (
            0 if item["ranking_score"] > 0 else 1,
            -item["ranking_score"],
            -item["secondary_score"],
            -item["game_count"],
            item.get("last_scored_date") or "",
            int(item.get("team_id") or 0),
        )
    )

    rank_counter = 0
    for item in rankings:
        if item["ranking_score"] > 0:
            rank_counter += 1
            item["rank"] = rank_counter
            item["rank_label"] = str(rank_counter)
        else:
            item["rank"] = None
            item["rank_label"] = "-"

    podium_by_rank = {
        item["rank"]: item
        for item in rankings
        if item.get("rank") in [1, 2, 3]
    }

    filtered_rankings = rankings
    if search_query_lower:
        def matches_search(item):
            favorite_meta = item.get("favorite_team_meta") or {}
            searchable_values = [
                item.get("user_display_name") or "",
                favorite_meta.get("name") or "",
                favorite_meta.get("short") or "",
                item.get("favorite_kbo_team") or "",
            ]
            if not item.get("favorite_kbo_team"):
                searchable_values.extend(["미선택", "응원팀 미선택"])
            return any(search_query_lower in str(value).lower() for value in searchable_values)

        filtered_rankings = [item for item in rankings if matches_search(item)]

    return {
        "ranking_type": ranking_type,
        "latest_scored_date": latest_scored_date,
        "latest_scored_date_display": format_game_date_for_display(latest_scored_date),
        "ranking_month": ranking_month,
        "ranking_month_display": format_month_for_display(ranking_month),
        "month_options": month_options,
        "rankings": filtered_rankings,
        "ranking_count": len(filtered_rankings),
        "total_count": len(rankings),
        "ranked_count": rank_counter,
        "podium_by_rank": podium_by_rank,
        "search_query": search_query,
        "is_filtered": bool(search_query_lower),
    }



# ------------------------------------------------------------
# Home center / honor helpers
# ------------------------------------------------------------
SLOT_ORDER = ["LF", "CF", "RF", "SS", "2B", "3B", "1B", "P1", "C", "UTIL", "P2", "P3", "P4", "P5", "P6"]
FIELD_SLOT_ORDER = ["LF", "CF", "RF", "SS", "2B", "3B", "1B", "P1", "C", "UTIL"]
BULLPEN_SLOT_ORDER = ["P2", "P3", "P4", "P5", "P6"]


def get_home_display_position(fantasy_position_type=None, detail_position=None, roster_position=None, price_role=None):
    detail = str(detail_position or "").strip()
    roster = str(roster_position or "").strip()
    if fantasy_position_type == "pitcher":
        return resolve_pitcher_display_detail_position(
            detail_position=detail,
            roster_position=roster,
            price_role=price_role,
        )
    if detail and detail not in ["미등록", "타자"]:
        return detail
    if roster and roster not in ["미등록", "투수", "타자"]:
        return roster
    return "지명타자"


def build_score_roster_rows(team_id, game_date):
    """특정 경기일의 저장된 팀 점수 스냅샷으로 야구장 미니 라인업을 구성합니다."""
    rows_by_slot = {slot: {"slot": slot, "label": get_slot_label(slot), "player": None} for slot in SLOT_ORDER}
    if not team_id or not game_date:
        return [rows_by_slot[slot] for slot in SLOT_ORDER]

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                fps.slot,
                fps.registered_player_id,
                fps.player_name,
                fps.player_team,
                fps.position_type,
                fps.points,
                fps.base_points,
                fps.is_captain,
                fps.current_market_price,
                fps.locked_price_decimal,
                fps.is_position_eligible,
                fps.position_mismatch_reason,
                rp.back_no,
                rp.roster_position,
                rp.detail_position,
                rp.fantasy_position_type
            FROM fantasy_team_daily_player_scores fps
            LEFT JOIN registered_players rp
              ON rp.id = fps.registered_player_id
            WHERE fps.team_id = ?
              AND fps.game_date = ?
        """, (team_id, game_date)).fetchall()

    for row in rows:
        item = dict(row)
        slot = item.get("slot")
        if slot not in rows_by_slot:
            continue
        fantasy_type = item.get("fantasy_position_type") or item.get("position_type")
        player = {
            "registered_player_id": item.get("registered_player_id"),
            "name": item.get("player_name"),
            "team": item.get("player_team"),
            "back_no": item.get("back_no"),
            "fantasy_position_type": fantasy_type,
            "detail_position": item.get("detail_position"),
            "display_detail_position": get_home_display_position(
                fantasy_position_type=fantasy_type,
                detail_position=item.get("detail_position"),
                roster_position=item.get("roster_position"),
            ),
            "price": item.get("locked_price_decimal"),
            "current_market_price": item.get("current_market_price"),
            "total_points": item.get("points") or 0,
            "is_captain": bool(item.get("is_captain")),
            "is_position_eligible": bool(item.get("is_position_eligible")) if item.get("is_position_eligible") is not None else True,
            "position_mismatch_reason": item.get("position_mismatch_reason"),
        }
        rows_by_slot[slot] = {"slot": slot, "label": get_slot_label(slot), "player": player}

    return [rows_by_slot[slot] for slot in SLOT_ORDER]


def get_top_score_player(team_id, game_date):
    if not team_id or not game_date:
        return None
    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                fps.registered_player_id,
                fps.player_name AS name,
                fps.player_team AS team,
                fps.position_type,
                fps.points,
                fps.is_captain,
                rp.back_no,
                rp.detail_position,
                rp.roster_position,
                rp.fantasy_position_type
            FROM fantasy_team_daily_player_scores fps
            LEFT JOIN registered_players rp
              ON rp.id = fps.registered_player_id
            WHERE fps.team_id = ?
              AND fps.game_date = ?
            ORDER BY fps.points DESC, fps.is_captain DESC, fps.id ASC
            LIMIT 1
        """, (team_id, game_date)).fetchone()
    if row is None:
        return None
    item = dict(row)
    fantasy_type = item.get("fantasy_position_type") or item.get("position_type")
    item["fantasy_position_type"] = fantasy_type
    item["display_detail_position"] = get_home_display_position(
        fantasy_position_type=fantasy_type,
        detail_position=item.get("detail_position"),
        roster_position=item.get("roster_position"),
    )
    item["profile_url"] = url_for("player_detail", position_type=fantasy_type, team=item.get("team"), player_name=item.get("name"))
    return item


def build_best_team_card(row, score_key="total_points", score_date_key="game_date"):
    item = dict(row)
    score_date = item.get(score_date_key) or item.get("game_date") or item.get("last_monthly_date")
    team_id = item.get("team_id")
    item["score"] = round(float(item.get(score_key) or 0), 1)
    item["score_date"] = score_date
    item["score_date_display"] = format_game_date_for_display(score_date)
    item["profile_url"] = url_for("public_profile", user_id=item.get("user_id")) if item.get("user_id") else "#"
    item["roster_rows"] = build_score_roster_rows(team_id, score_date)
    item["top_player"] = get_top_score_player(team_id, score_date)
    favorite_team = normalize_kbo_team(item.get("favorite_kbo_team"))
    item["favorite_kbo_team"] = favorite_team
    item["favorite_team_meta"] = get_team_meta(favorite_team) if favorite_team else None
    return item


def get_recent_best_teams(limit=3):
    with get_conn() as conn:
        latest_row = conn.execute("""
            SELECT MAX(game_date) AS game_date
            FROM fantasy_team_daily_scores
            WHERE total_points > 0
        """).fetchone()
        latest_date = latest_row["game_date"] if latest_row else None
        if not latest_date:
            return [], None
        max_row = conn.execute("""
            SELECT MAX(total_points) AS best_points
            FROM fantasy_team_daily_scores
            WHERE game_date = ?
              AND total_points > 0
        """, (latest_date,)).fetchone()
        best_points = max_row["best_points"] if max_row else None
        if best_points is None:
            return [], latest_date
        rows = conn.execute("""
            SELECT
                ftds.team_id,
                ftds.user_id,
                ftds.team_name_snapshot,
                ftds.user_display_name_snapshot,
                ftds.game_date,
                ftds.total_points,
                ftds.captain_player_name_snapshot,
                u.favorite_kbo_team
            FROM fantasy_team_daily_scores ftds
            LEFT JOIN users u
              ON u.id = ftds.user_id
            WHERE ftds.game_date = ?
              AND ABS(ftds.total_points - ?) < 0.0001
            ORDER BY ftds.team_id ASC
            LIMIT ?
        """, (latest_date, best_points, limit)).fetchall()
    return [build_best_team_card(row, "total_points", "game_date") for row in rows], latest_date


def get_monthly_best_teams(limit=3):
    """Return the best team from the latest fully closed scoring month.

    The center card should not crown the current in-progress month as a
    monthly best team. For example, while the current date is in June, the
    monthly best card should show the finalized May winner if May has team
    score data.
    """
    current_month = date.today().strftime("%Y-%m")
    with get_conn() as conn:
        month_row = conn.execute("""
            SELECT MAX(substr(game_date, 1, 7)) AS month_value
            FROM fantasy_team_daily_scores
            WHERE game_date IS NOT NULL
              AND length(game_date) >= 7
              AND substr(game_date, 1, 7) < ?
        """, (current_month,)).fetchone()
        month_value = month_row["month_value"] if month_row else None
        if not month_value:
            return [], None

        rows = conn.execute("""
            SELECT
                ft.id AS team_id,
                ft.user_id,
                COALESCE(last_score.team_name_snapshot, ft.team_name) AS team_name_snapshot,
                COALESCE(u.display_name, u.username) AS user_display_name_snapshot,
                u.favorite_kbo_team,
                COALESCE(game_summary.monthly_team_points, 0) AS monthly_team_points,
                COALESCE(game_summary.monthly_game_count, 0) AS monthly_game_count,
                game_summary.last_monthly_date
            FROM fantasy_teams ft
            JOIN users u
              ON u.id = ft.user_id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(total_points) AS monthly_team_points,
                    COUNT(*) AS monthly_game_count,
                    MAX(game_date) AS last_monthly_date
                FROM fantasy_team_daily_scores
                WHERE substr(game_date, 1, 7) = ?
                GROUP BY team_id
            ) game_summary
              ON game_summary.team_id = ft.id
            LEFT JOIN fantasy_team_daily_scores last_score
              ON last_score.team_id = ft.id
             AND last_score.game_date = game_summary.last_monthly_date
            WHERE COALESCE(game_summary.monthly_team_points, 0) > 0
            ORDER BY monthly_team_points DESC, monthly_game_count DESC, ft.id ASC
        """, (month_value,)).fetchall()
    if not rows:
        return [], month_value
    best_score = float(rows[0]["monthly_team_points"] or 0)
    best_rows = [row for row in rows if abs(float(row["monthly_team_points"] or 0) - best_score) < 0.0001][:limit]
    cards = []
    for row in best_rows:
        card = build_best_team_card(row, "monthly_team_points", "last_monthly_date")
        card["monthly_game_count"] = int(row["monthly_game_count"] or 0)
        cards.append(card)
    return cards, month_value

def build_sparkline_points(values, width=132, height=42, padding=4, x_padding=None):
    """Build SVG points for the home market mini chart.

    Keep horizontal padding inside the SVG coordinate system so the first/last
    circle markers are not clipped by the chart panel.
    """
    clean = []
    for value in values or []:
        try:
            clean.append(float(value))
        except (TypeError, ValueError):
            pass
    if not clean:
        return ""
    x_pad = padding if x_padding is None else x_padding
    if len(clean) == 1:
        y_mid = height / 2
        return f"{x_pad:.1f},{y_mid:.1f} {width - x_pad:.1f},{y_mid:.1f}"
    min_value = min(clean)
    max_value = max(clean)
    span = max(max_value - min_value, 0.0001)
    usable_width = max(width - (x_pad * 2), 1)
    step = usable_width / (len(clean) - 1)
    points = []
    for index, value in enumerate(clean):
        x = x_pad + (step * index)
        y = height - ((value - min_value) / span * (height - (padding * 2))) - padding
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def build_sparkline_area_points(points, width=220, height=92, padding=8, x_padding=None):
    if not points:
        return ""
    x_pad = padding if x_padding is None else x_padding
    baseline = height - padding
    return f"{x_pad:.1f},{baseline:.1f} {points} {width - x_pad:.1f},{baseline:.1f}"


def build_sparkline_chart_nodes(history, width=220, height=92, padding=8, x_padding=None):
    clean = []
    for row in history or []:
        try:
            value = float(row.get("price_value"))
        except (TypeError, ValueError, AttributeError):
            continue
        clean.append({
            "basis_date": row.get("basis_date"),
            "price_value": value,
        })
    if not clean:
        return []
    x_pad = padding if x_padding is None else x_padding
    if len(clean) == 1:
        clean[0]["x"] = round(width / 2, 1)
        clean[0]["y"] = round(height / 2, 1)
        clean[0]["label"] = f"{clean[0].get('basis_date') or ''} · {clean[0]['price_value']:.1f}"
        return clean
    values = [row["price_value"] for row in clean]
    min_value = min(values)
    max_value = max(values)
    span = max(max_value - min_value, 0.0001)
    usable_width = max(width - (x_pad * 2), 1)
    step = usable_width / (len(clean) - 1)
    for index, row in enumerate(clean):
        x = x_pad + (step * index)
        y = height - ((row["price_value"] - min_value) / span * (height - (padding * 2))) - padding
        row["x"] = round(x, 1)
        row["y"] = round(y, 1)
        row["label"] = f"{row.get('basis_date') or ''} · {row['price_value']:.1f}"
    return clean


def get_price_history_for_player(registered_player_id, limit=14):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT basis_date, COALESCE(price_decimal, price) AS price_value
            FROM player_prices
            WHERE registered_player_id = ?
              AND basis_source = ?
              AND COALESCE(price_decimal, price) > 0
            ORDER BY basis_date DESC
            LIMIT ?
        """, (registered_player_id, BASIS_SOURCE, limit)).fetchall()
    history = [dict(row) for row in rows][::-1]
    values = [row["price_value"] for row in history]
    points = build_sparkline_points(values, width=260, height=112, padding=10, x_padding=26)
    nodes = build_sparkline_chart_nodes(history, width=260, height=112, padding=10, x_padding=26)
    area_points = build_sparkline_area_points(points, width=260, height=112, padding=10, x_padding=26)
    clean_values = []
    for value in values:
        try:
            clean_values.append(float(value))
        except (TypeError, ValueError):
            pass
    min_label = f"{min(clean_values):.1f}" if clean_values else ""
    max_label = f"{max(clean_values):.1f}" if clean_values else ""
    return history, points, nodes, area_points, min_label, max_label


def get_price_movers(direction="up", limit=5):
    latest_price_date = get_latest_price_date()
    if not latest_price_date:
        return []
    direction_sql = "(ppa.new_price_decimal - ppa.old_price_decimal) > 0" if direction == "up" else "(ppa.new_price_decimal - ppa.old_price_decimal) < 0"
    order_sql = "price_change DESC" if direction == "up" else "price_change ASC"
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                ppa.registered_player_id,
                ppa.player_name AS name,
                ppa.team,
                ppa.price_role,
                ppa.old_price_decimal,
                ppa.new_price_decimal,
                ROUND(ppa.new_price_decimal - ppa.old_price_decimal, 1) AS price_change,
                rp.back_no,
                rp.roster_position,
                rp.detail_position,
                rp.fantasy_position_type
            FROM player_price_adjustments ppa
            JOIN registered_players rp
              ON rp.id = ppa.registered_player_id
            WHERE ppa.basis_source = ?
              AND ppa.basis_date = ?
              AND ppa.is_applied = 1
              AND rp.is_active = 1
              AND {direction_sql}
            ORDER BY {order_sql}, ppa.player_name ASC
            LIMIT ?
        """, (BASIS_SOURCE, latest_price_date, limit)).fetchall()
    movers = []
    for row in rows:
        item = dict(row)
        history, points, chart_nodes, area_points, min_label, max_label = get_price_history_for_player(item["registered_player_id"], limit=14)
        item["sparkline_points"] = points
        item["sparkline_nodes"] = chart_nodes
        item["sparkline_area_points"] = area_points
        item["sparkline_min_label"] = min_label
        item["sparkline_max_label"] = max_label
        item["history"] = history
        item["back_no_display"] = f"No.{item.get('back_no')}" if item.get("back_no") else "No.-"
        item["role_label"] = {
            "starting_pitcher": "선발투수",
            "bullpen_pitcher": "불펜투수",
            "batter": "타자",
        }.get(item.get("price_role"), "선수")
        item["display_detail_position"] = get_home_display_position(
            fantasy_position_type=item.get("fantasy_position_type"),
            detail_position=item.get("detail_position"),
            roster_position=item.get("roster_position"),
            price_role=item.get("price_role"),
        )
        item["profile_url"] = url_for("player_detail", position_type=item.get("fantasy_position_type"), team=item.get("team"), player_name=item.get("name"))
        movers.append(item)
    return movers


def get_popular_players(limit=7):
    latest_price_date = get_latest_price_date()
    with get_conn() as conn:
        total_teams_row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM fantasy_teams
            WHERE is_confirmed = 1
        """).fetchone()
        total_teams = int(total_teams_row["cnt"] or 0) if total_teams_row else 0
        rows = conn.execute("""
            SELECT
                rp.id AS registered_player_id,
                rp.name,
                rp.team,
                rp.back_no,
                rp.roster_position,
                rp.detail_position,
                rp.fantasy_position_type,
                COUNT(DISTINCT ftp.team_id) AS roster_count,
                COALESCE(pp.price_decimal, pp.price) AS current_market_price
            FROM fantasy_team_players ftp
            JOIN fantasy_teams ft
              ON ft.id = ftp.team_id
             AND ft.is_confirmed = 1
            JOIN registered_players rp
              ON rp.id = ftp.registered_player_id
            LEFT JOIN player_prices pp
              ON pp.registered_player_id = rp.id
             AND pp.basis_source = ?
             AND pp.basis_date = ?
            GROUP BY rp.id
            ORDER BY roster_count DESC, current_market_price DESC, rp.name ASC
            LIMIT ?
        """, (BASIS_SOURCE, latest_price_date, limit)).fetchall()
    players = []
    for row in rows:
        item = dict(row)
        item["roster_count"] = int(item.get("roster_count") or 0)
        item["roster_rate"] = round((item["roster_count"] / total_teams) * 100, 1) if total_teams else 0
        item["display_detail_position"] = get_home_display_position(
            fantasy_position_type=item.get("fantasy_position_type"),
            detail_position=item.get("detail_position"),
            roster_position=item.get("roster_position"),
        )
        item["profile_url"] = url_for("player_detail", position_type=item.get("fantasy_position_type"), team=item.get("team"), player_name=item.get("name"))
        players.append(item)
    return {"players": players, "total_confirmed_teams": total_teams}


KBO_TEAM_RANKING_URL = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
KBO_STANDINGS_CACHE_TTL_SECONDS = 600
_kbo_standings_cache = {"fetched_at": 0.0, "data": None}


def parse_standing_number(value, default=0):
    text = str(value or "").strip().replace(",", "")
    if text in {"", "-"}:
        return default
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return default


def decorate_kbo_standing_row(item):
    team_key = normalize_kbo_team(item.get("team"))
    item["team"] = team_key or str(item.get("team") or "").strip()
    item["meta"] = get_team_meta(team_key) if team_key else get_team_meta(item.get("team"))
    item["games"] = int(parse_standing_number(item.get("games"), 0))
    item["wins"] = int(parse_standing_number(item.get("wins"), 0))
    item["losses"] = int(parse_standing_number(item.get("losses"), 0))
    item["draws"] = int(parse_standing_number(item.get("draws"), 0))
    pct_value = parse_standing_number(item.get("pct"), 0.0)
    item["pct"] = float(pct_value or 0)
    item["pct_display"] = f"{item['pct']:.3f}" if item["pct"] else "0.000"
    gb_raw = str(item.get("gb", "")).strip()
    item["gb"] = 0.0 if gb_raw in {"", "-", "0"} else float(parse_standing_number(gb_raw, 0.0))
    item["gb_display"] = "-" if item["gb"] == 0 else (str(int(item["gb"])) if float(item["gb"]).is_integer() else f"{item['gb']:.1f}")
    item["recent10"] = str(item.get("recent10") or "-").strip()
    item["streak"] = str(item.get("streak") or "-").strip()
    item["home"] = str(item.get("home") or "-").strip()
    item["away"] = str(item.get("away") or "-").strip()
    return item


def fetch_kbo_official_standings():
    """KBO 공식 일자별 팀 순위 페이지를 홈 표시용으로 읽어옵니다.

    외부 페이지 실패 시에는 호출부에서 로컬 DB fallback을 사용합니다.
    """
    response = requests.get(
        KBO_TEAM_RANKING_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) MyPick/1.0",
            "Referer": "https://www.koreabaseball.com/",
        },
        timeout=2.0,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    date_match = re.search(r"(20\d{2})[.]\s*(\d{1,2})[.]\s*(\d{1,2})", text)
    source_date = None
    source_label = "KBO 공식 순위"
    if date_match:
        yyyy, mm, dd = date_match.groups()
        source_date = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
        source_label = f"KBO 공식 {int(mm)}월 {int(dd)}일 기준"

    rows = []
    for tr in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
        if len(cells) < 10:
            continue
        if not re.fullmatch(r"\d+", cells[0] or ""):
            continue
        team = normalize_kbo_team(cells[1])
        if not team:
            continue
        row = decorate_kbo_standing_row({
            "rank": int(cells[0]),
            "team": team,
            "games": cells[2],
            "wins": cells[3],
            "losses": cells[4],
            "draws": cells[5],
            "pct": cells[6],
            "gb": cells[7],
            "recent10": cells[8] if len(cells) > 8 else "-",
            "streak": cells[9] if len(cells) > 9 else "-",
            "home": cells[10] if len(cells) > 10 else "-",
            "away": cells[11] if len(cells) > 11 else "-",
        })
        rows.append(row)
    if not rows:
        raise ValueError("KBO standings table not found")
    return {
        "rows": rows[:10],
        "source_label": source_label,
        "source_date": source_date,
        "source_url": KBO_TEAM_RANKING_URL,
        "is_official": True,
    }


def get_kbo_standings_from_synced_games():
    """공식 순위 fetch 실패 시 사용하는 로컬 완료 경기 fallback입니다."""
    stats = {
        team: {"team": team, "wins": 0, "losses": 0, "draws": 0, "games": 0}
        for team in KBO_TEAM_OPTIONS
    }
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT game_date, away_team, home_team, away_score, home_score
            FROM betting_games
            WHERE status = 'final'
              AND away_score IS NOT NULL
              AND home_score IS NOT NULL
            ORDER BY game_date ASC, id ASC
        """).fetchall()
    for row in rows:
        away = normalize_kbo_team(row["away_team"])
        home = normalize_kbo_team(row["home_team"])
        if not away or not home:
            continue
        away_score = int(row["away_score"] or 0)
        home_score = int(row["home_score"] or 0)
        stats[away]["games"] += 1
        stats[home]["games"] += 1
        if away_score > home_score:
            stats[away]["wins"] += 1
            stats[home]["losses"] += 1
        elif away_score < home_score:
            stats[home]["wins"] += 1
            stats[away]["losses"] += 1
        else:
            stats[away]["draws"] += 1
            stats[home]["draws"] += 1
    standings = []
    for team, item in stats.items():
        decisions = item["wins"] + item["losses"]
        item["pct"] = round(item["wins"] / decisions, 3) if decisions else 0
        standings.append(item)
    standings.sort(key=lambda item: (-item["pct"], -item["wins"], item["losses"], KBO_TEAM_OPTIONS.index(item["team"])))
    if standings:
        leader = standings[0]
        for index, item in enumerate(standings, start=1):
            item["rank"] = index
            item["gb"] = round(((leader["wins"] - item["wins"]) + (item["losses"] - leader["losses"])) / 2, 1)
            if index == 1:
                item["gb"] = 0.0
            decorate_kbo_standing_row(item)
    return {
        "rows": standings,
        "source_label": "로컬 완료 경기 기준",
        "game_count": len(rows),
        "is_official": False,
    }


def get_kbo_standings():
    """홈 센터용 KBO 순위 데이터입니다.

    /center 접속 때마다 KBO 공식 사이트를 직접 호출하면 외부 응답 지연으로
    페이지 로딩이 길어질 수 있어, 짧은 메모리 캐시를 우선 사용합니다.
    공식 fetch 실패 시에는 기존 로컬 완료 경기 fallback을 유지합니다.
    """
    now = time.monotonic()
    cached_data = _kbo_standings_cache.get("data")
    fetched_at = float(_kbo_standings_cache.get("fetched_at") or 0)

    if cached_data is not None and now - fetched_at < KBO_STANDINGS_CACHE_TTL_SECONDS:
        return cached_data

    try:
        standings = fetch_kbo_official_standings()
        _kbo_standings_cache["data"] = standings
        _kbo_standings_cache["fetched_at"] = now
        return standings
    except Exception as error:
        if cached_data is not None:
            cached_data = dict(cached_data)
            cached_data["fetch_error"] = str(error)
            cached_data["served_from_cache"] = True
            return cached_data

        fallback = get_kbo_standings_from_synced_games()
        fallback["fetch_error"] = str(error)
        _kbo_standings_cache["data"] = fallback
        _kbo_standings_cache["fetched_at"] = now
        return fallback


def get_home_center_data():
    recent_best_teams, latest_score_date = get_recent_best_teams(limit=4)
    monthly_best_teams, ranking_month = get_monthly_best_teams(limit=4)
    price_gainers = get_price_movers("up", limit=5)
    price_losers = get_price_movers("down", limit=5)
    popular_players = get_popular_players(limit=7)
    kbo_standings = get_kbo_standings()

    hero_cards = []
    if recent_best_teams:
        hero_cards.append({
            "label": "최근 경기 베스트 팀",
            "title": recent_best_teams[0].get("user_display_name_snapshot") or recent_best_teams[0].get("team_name_snapshot") or "-",
            "value": recent_best_teams[0]["score"],
            "value_type": "money",
            "meta": recent_best_teams[0].get("score_date_display") or "최근 경기 기준",
        })
    if monthly_best_teams:
        hero_cards.append({
            "label": "월별 베스트 팀",
            "title": monthly_best_teams[0].get("user_display_name_snapshot") or monthly_best_teams[0].get("team_name_snapshot") or "-",
            "value": monthly_best_teams[0]["score"],
            "value_type": "money",
            "meta": (f"{format_month_for_display(ranking_month)} · 스쿼드 경기 수익 기준" if ranking_month else "스쿼드 경기 수익 기준"),
        })
    if price_gainers:
        hero_cards.append({
            "label": "가격 급등 선수",
            "title": price_gainers[0].get("name"),
            "value": price_gainers[0].get("price_change"),
            "value_type": "decimal_change",
            "meta": f"{price_gainers[0].get('team')} · {price_gainers[0].get('display_detail_position')}",
        })
    if popular_players.get("players"):
        top_popular = popular_players["players"][0]
        hero_cards.append({
            "label": "인기 영입 선수",
            "title": top_popular.get("name"),
            "value": top_popular.get("roster_count"),
            "value_type": "count_team",
            "meta": f"확정 팀 보유율 {top_popular.get('roster_rate')}%",
        })

    return {
        "latest_score_date": latest_score_date,
        "latest_score_date_display": format_game_date_for_display(latest_score_date),
        "ranking_month": ranking_month,
        "ranking_month_display": format_month_for_display(ranking_month) if ranking_month else "",
        "hero_cards": hero_cards,
        "recent_best_teams": recent_best_teams,
        "monthly_best_teams": monthly_best_teams,
        "price_gainers": price_gainers,
        "price_losers": price_losers,
        "popular_players": popular_players,
        "kbo_standings": kbo_standings,
    }


def rank_rows_with_ties(rows, score_key):
    ranked = []
    previous_score = None
    previous_rank = 0
    for index, row in enumerate(rows, start=1):
        score = float(row.get(score_key) or 0)
        if previous_score is None or abs(score - previous_score) >= 0.0001:
            rank = index
        else:
            rank = previous_rank
        item = dict(row)
        item["rank"] = rank
        ranked.append(item)
        previous_score = score
        previous_rank = rank
    return ranked


def get_monthly_team_only_rankings(month_value):
    if isinstance(month_value, dict):
        month_value = month_value.get("value")
    if not month_value:
        return []
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                ft.id AS team_id,
                ft.user_id,
                COALESCE(game_summary.monthly_team_points, 0) AS monthly_team_points,
                COALESCE(game_summary.monthly_game_count, 0) AS monthly_game_count,
                game_summary.last_monthly_date
            FROM fantasy_teams ft
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(total_points) AS monthly_team_points,
                    COUNT(*) AS monthly_game_count,
                    MAX(game_date) AS last_monthly_date
                FROM fantasy_team_daily_scores
                WHERE substr(game_date, 1, 7) = ?
                GROUP BY team_id
            ) game_summary
              ON game_summary.team_id = ft.id
            WHERE COALESCE(game_summary.monthly_team_points, 0) > 0
            ORDER BY monthly_team_points DESC, monthly_game_count DESC, ft.id ASC
        """, (month_value,)).fetchall()
    return [dict(row) for row in rows]


def get_achievement_season_month_label(month_value):
    """업적 카드에서 쓰는 '2026 시즌 6월' 형식의 월 표기입니다."""
    text = str(month_value or "").strip()
    parts = text.split("-")
    if len(parts) != 2:
        return format_month_for_display(month_value)
    try:
        year = int(parts[0])
        month = int(parts[1])
    except (TypeError, ValueError):
        return format_month_for_display(month_value)
    if month < 1 or month > 12:
        return format_month_for_display(month_value)
    return f"{year} 시즌 {month}월"


def get_profile_honors(team_id, user_id, limit=24):
    """프로필 업적 6개 카테고리 요약을 만든다.

    반드시 리스트를 반환한다. 기록이 0인 카테고리도 카드로 보여야 하므로
    일일/월별/배팅/방출/우승/준우승 6개 항목을 항상 포함한다.
    """
    if not team_id or not user_id:
        return []

    daily_count = 0
    latest_daily_label = "아직 선정 기록 없음"
    monthly_count = 0
    latest_monthly_label = "아직 선정 기록 없음"
    champion_count = 0
    runner_up_count = 0
    season_year = "2026"
    season_rank = None
    current_rank_label = "2026 시즌 기록 없음"

    betting_hit_count = 0
    betting_hit_rate_label = "적중 기록 없음"

    trade_profit_total = 0.0
    trade_profit_rank_label = "아직 수익 기록 없음"

    # 일일 베스트 팀: 해당 날짜 팀 수익 공동 1위 모두 인정한다.
    with get_conn() as conn:
        daily_rows = conn.execute("""
            SELECT ftds.game_date, ftds.total_points
            FROM fantasy_team_daily_scores ftds
            JOIN (
                SELECT game_date, MAX(total_points) AS best_points
                FROM fantasy_team_daily_scores
                WHERE total_points > 0
                GROUP BY game_date
            ) daily_best
              ON daily_best.game_date = ftds.game_date
             AND ABS(daily_best.best_points - ftds.total_points) < 0.0001
            WHERE ftds.team_id = ?
              AND ftds.total_points > 0
            ORDER BY ftds.game_date DESC
        """, (team_id,)).fetchall()

    daily_count = len(daily_rows)
    if daily_rows:
        latest_daily_label = f"최근 {format_game_date_for_display(daily_rows[0]['game_date'])}"

    # 월별 베스트 팀: 닫힌 월의 스쿼드 경기 수익 공동 1위 모두 인정한다.
    closed_months = get_closed_ranking_month_options()
    for month_option in closed_months:
        month_value = month_option.get("value") if isinstance(month_option, dict) else month_option
        if not month_value:
            continue

        team_rows = get_monthly_team_only_rankings(month_value)
        if not team_rows:
            continue

        best_score = float(team_rows[0].get("monthly_team_points") or 0)
        for row in team_rows:
            if int(row.get("team_id") or 0) == int(team_id) and abs(float(row.get("monthly_team_points") or 0) - best_score) < 0.0001:
                monthly_count += 1
                if latest_monthly_label == "아직 선정 기록 없음":
                    latest_monthly_label = f"최근 {get_achievement_season_month_label(month_value)}"
                break

    with get_conn() as conn:
        ensure_trade_bonus_tables(conn)
        ensure_betting_tables(conn)

        latest_date_row = conn.execute("""
            SELECT MAX(game_date) AS latest_game_date
            FROM fantasy_team_daily_scores
        """).fetchone()
        latest_game_date = latest_date_row["latest_game_date"] if latest_date_row else None
        season_year = str(latest_game_date or "2026")[:4] if latest_game_date else "2026"

        season_rows = conn.execute("""
            SELECT
                ft.id AS team_id,
                COALESCE(score_summary.total_points, 0)
                    + COALESCE(trade_bonus_summary.trade_bonus_points, 0)
                    + COALESCE(betting_summary.betting_points, 0) AS season_points,
                COALESCE(score_summary.game_count, 0) AS game_count,
                score_summary.last_scored_date
            FROM fantasy_teams ft
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(total_points) AS total_points,
                    COUNT(*) AS game_count,
                    MAX(game_date) AS last_scored_date
                FROM fantasy_team_daily_scores
                WHERE substr(game_date, 1, 4) = ?
                GROUP BY team_id
            ) score_summary
              ON score_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    team_id,
                    SUM(bonus_points) AS trade_bonus_points
                FROM fantasy_team_trade_bonus_events
                WHERE substr(event_date, 1, 4) = ?
                GROUP BY team_id
            ) trade_bonus_summary
              ON trade_bonus_summary.team_id = ft.id
            LEFT JOIN (
                SELECT
                    user_id,
                    SUM(amount_points) AS betting_points
                FROM betting_ledger
                WHERE substr(created_at, 1, 4) = ?
                GROUP BY user_id
            ) betting_summary
              ON betting_summary.user_id = ft.user_id
            WHERE COALESCE(score_summary.total_points, 0)
                + COALESCE(trade_bonus_summary.trade_bonus_points, 0)
                + COALESCE(betting_summary.betting_points, 0) > 0
            ORDER BY
                season_points DESC,
                game_count DESC,
                score_summary.last_scored_date ASC,
                ft.id ASC
        """, (season_year, season_year, season_year)).fetchall()

        betting_row = conn.execute("""
            SELECT
                SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) AS won_count,
                SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) AS lost_count
            FROM betting_bets
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        trade_rows = conn.execute("""
            SELECT
                ft.user_id,
                COALESCE(SUM(events.bonus_points), 0) AS trade_profit_points
            FROM fantasy_teams ft
            LEFT JOIN fantasy_team_trade_bonus_events events
              ON events.team_id = ft.id
            GROUP BY ft.user_id
            ORDER BY trade_profit_points DESC, ft.user_id ASC
        """).fetchall()

    for index, row in enumerate(season_rows, start=1):
        if int(row["team_id"] or 0) == int(team_id):
            season_rank = index
            break

    # 시즌 우승/준우승은 현재 순위가 아니라 시즌 종료 후 최종 순위로만 인정한다.
    # 현재 프로젝트에는 별도 시즌 종료 플래그가 없으므로 12월 1일 이후 집계 데이터만
    # 최종 시즌 업적으로 처리하고, 그 전에는 "진행 중" 설명만 보여준다.
    season_awards_closed = bool(latest_game_date and str(latest_game_date) >= f"{season_year}-12-01")

    if season_awards_closed and season_rank == 1:
        champion_count = 1
    elif season_awards_closed and season_rank == 2:
        runner_up_count = 1

    if season_rank:
        if season_awards_closed:
            current_rank_label = f"{season_year} 시즌 최종 {season_rank}위"
        else:
            current_rank_label = f"현재 {season_year} 시즌 {season_rank}위"
    else:
        current_rank_label = f"{season_year} 시즌 기록 없음"

    betting_hit_count = int((betting_row["won_count"] if betting_row else 0) or 0)
    betting_lost_count = int((betting_row["lost_count"] if betting_row else 0) or 0)
    betting_settled_count = betting_hit_count + betting_lost_count
    if betting_settled_count > 0:
        betting_hit_rate = betting_hit_count / betting_settled_count * 100
        betting_hit_rate_label = f"적중 확률 {betting_hit_rate:.1f}%"

    current_trade_rank = None
    previous_trade_profit = None
    display_rank = 0
    total_trade_rank_users = len(trade_rows)

    for position, row in enumerate(trade_rows, start=1):
        row_profit = round(float(row["trade_profit_points"] or 0), 1)
        if previous_trade_profit is None or abs(row_profit - previous_trade_profit) >= 0.0001:
            display_rank = position
            previous_trade_profit = row_profit

        if int(row["user_id"] or 0) == int(user_id):
            trade_profit_total = row_profit
            current_trade_rank = display_rank
            break

    if trade_profit_total > 0 and current_trade_rank and total_trade_rank_users:
        trade_profit_rank_label = f"상위 {current_trade_rank / total_trade_rank_users * 100:.1f}%"

    return [
        {
            "type": "daily_best_team",
            "tone": "cyan",
            "badge": "DAILY BEST",
            "title": "일일 베스트 팀 선정",
            "count": daily_count,
            "count_label": f"{daily_count}회",
            "subtitle": "누적 선정 횟수",
            "description": latest_daily_label,
            "score": None,
        },
        {
            "type": "monthly_best_team",
            "tone": "cyan" if monthly_count else "neutral",
            "badge": "MONTHLY BEST",
            "title": "월별 베스트 팀 선정",
            "count": monthly_count,
            "count_label": f"{monthly_count}회",
            "subtitle": "누적 선정 횟수",
            "description": latest_monthly_label,
            "score": None,
        },
        {
            "type": "betting_hit",
            "tone": "cyan" if betting_hit_count else "neutral",
            "badge": "BETTING HIT",
            "title": "배팅 적중",
            "count": betting_hit_count,
            "count_label": f"{betting_hit_count}회",
            "subtitle": "완료된 배팅 기준",
            "description": betting_hit_rate_label,
            "score": None,
        },
        {
            "type": "trade_profit",
            "tone": "cyan" if trade_profit_total > 0 else "neutral",
            "badge": "TRADE PROFIT",
            "title": "방출 수익",
            "count": 0,
            "count_label": format_money_from_points(trade_profit_total),
            "subtitle": "누적 방출 수익",
            "description": trade_profit_rank_label,
            "score": None,
        },
        {
            "type": "season_champion",
            "tone": "gold" if champion_count else "neutral",
            "badge": "CHAMPION",
            "title": "시즌 우승",
            "count": champion_count,
            "count_label": f"{champion_count}회",
            "subtitle": f"{season_year} 시즌",
            "description": current_rank_label if not champion_count else f"{season_year} 시즌 챔피언",
            "score": None,
        },
        {
            "type": "season_runner_up",
            "tone": "silver" if runner_up_count else "neutral",
            "badge": "RUNNER-UP",
            "title": "시즌 준우승",
            "count": runner_up_count,
            "count_label": f"{runner_up_count}회",
            "subtitle": f"{season_year} 시즌",
            "description": current_rank_label if not runner_up_count else f"{season_year} 시즌 최종 2위",
            "score": None,
        },
    ]


# MYPICK SEO BASICS V1 2026-06-04 START
SITE_BASE_URL = "https://mypickkbo.com"
SEO_DEFAULT_TITLE = "MyPick KBO - KBO 판타지 스포츠"
SEO_DEFAULT_DESCRIPTION = (
    "MyPick은 실제 KBO 기록을 기반으로 판타지 팀 구성, 선수 순위, 그리고 승부예측과 포인트 기반 배팅을 제공하는 판타지 KBO 스포츠 웹사이트입니다."
)

SEO_META_BY_ENDPOINT = {
    "index": {
        "title": "MyPick KBO - KBO 판타지 스포츠",
        "description": "MyPick은 KBO 선수 기록을 기반으로 판타지 팀을 만들고, 선수 순위, 가격 변동, 유저 랭킹, 승부예측과 베팅을 즐길 수 있는 판타지 야구 웹사이트입니다.",
    },
    "center": {
        "title": "MyPick KBO 센터 - KBO 판타지 스포츠",
        "description": "MyPick 센터에서 KBO 순위, 인기 선수, 판타지 팀 랭킹, 선수 가격 변동과 KBO 판타지 스포츠 주요 정보를 확인하세요.",
    },
    "rankings": {
        "title": "KBO 판타지 선수 순위 - MyPick KBO",
        "description": "KBO 경기 기록을 기반으로 계산한 MyPick 판타지 점수, 선수 가격, 포지션별 랭킹 기준 KBO 선수 순위를 확인하세요.",
    },
    "batters": {
        "title": "KBO 타자 판타지 순위 - MyPick KBO",
        "description": "KBO 타자들의 판타지 점수, 선수 가격, 최근 경기 기록을 기반으로 한 KBO 타자 순위를 MyPick KBO에서 확인하세요.",
    },
    "pitchers": {
        "title": "KBO 투수 판타지 순위 - MyPick KBO",
        "description": "KBO 투수들의 판타지 점수, 선수 가격, 최근 등판 기록을 기반으로 한 선발투수와 불펜투수 순위를 확인하세요.",
    },
    "players": {
        "title": "KBO 선수 검색과 선수 가격 - MyPick KBO",
        "description": "KBO 선수 검색, 판타지 포지션, 선수 가격, 최근 경기 기록과 KBO 선수 순위 정보를 MyPick KBO에서 확인하세요.",
    },
    "user_rankings": {
        "title": "KBO 판타지 유저 랭킹 - MyPick KBO",
        "description": "MyPick KBO 유저들의 판타지 야구 팀 수익, 월간 수익, 총 자산 랭킹을 확인하세요.",
    },
    "betting": {
        "title": "KBO 승부예측 & 판타지 배팅 - MyPick KBO",
        "description": "MyPick KBO에서 KBO 경기 승부예측, 점수차 예측, 총 득점 예측을 즐겨보세요. 판타지 팀 수익과 연결되는 포인트 기반 KBO 배팅과 야구 승부예측 시스템을 제공합니다.",
    },
    "play_guide": {
        "title": "KBO 판타지 야구 플레이 가이드 - MyPick KBO",
        "description": "MyPick KBO에서 KBO 판타지 야구 팀을 만들고, 선수 가격 변동, 팀 점수, 캡틴, KBO 승부예측과 포인트 기반 배팅 시스템을 이용하는 방법을 확인하세요.",
    },
}

SEO_PUBLIC_PATHS = [
    "/",
    "/center",
    "/play-guide",
    "/rankings",
    "/batters",
    "/pitchers",
    "/players",
    "/user-rankings",
    "/betting",
]


@app.context_processor
def inject_seo_meta():
    endpoint = request.endpoint or ""
    meta = SEO_META_BY_ENDPOINT.get(endpoint, {})
    title = meta.get("title", SEO_DEFAULT_TITLE)
    description = meta.get("description", SEO_DEFAULT_DESCRIPTION)
    canonical_path = request.path or "/"
    canonical_url = f"{SITE_BASE_URL}{canonical_path}"
    return {
        "seo_title": title,
        "seo_description": description,
        "seo_canonical_url": canonical_url,
        "site_base_url": SITE_BASE_URL,
    }



# MYPICK FAVICON ICO ROUTE FIX 2026-06-05
# Google/Browsers often request /favicon.ico directly.
# Serve the user-provided static/favicon.png at the root favicon path.
@app.route("/favicon.ico")
def favicon_ico():
    return send_from_directory(
        app.static_folder,
        "favicon.png",
        mimetype="image/png",
        max_age=604800,
    )


@app.route("/robots.txt")
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /settings",
        "Disallow: /profile",
        "Disallow: /profile/",
        "Disallow: /friends",
        "Disallow: /friend-rankings",
        "Disallow: /my-team",
        "Disallow: /team/",
        "Disallow: /support",
        "Disallow: /my-support",
        "Disallow: /betting/history",
        "Disallow: /logout",
        "",
        f"Sitemap: {SITE_BASE_URL}/sitemap.xml",
        "",
    ]
    return app.response_class("\n".join(lines), mimetype="text/plain; charset=utf-8")


@app.route("/sitemap.xml")
def sitemap_xml():
    urls = "\n".join(
        f"""  <url>
    <loc>{SITE_BASE_URL}{path}</loc>
    <changefreq>daily</changefreq>
    <priority>{'1.0' if path == '/' else '0.8'}</priority>
  </url>"""
        for path in SEO_PUBLIC_PATHS
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>
"""
    return app.response_class(xml, mimetype="application/xml; charset=utf-8")
# MYPICK SEO BASICS V1 2026-06-04 END

@app.route("/")
def index():
    return render_template(
        "index.html",
        page_title="MyPick",
        active_tab="",
        body_class="is-home-page",
        main_class="home-page-wrap",
    )


@app.route("/center")
def center():
    home_center = get_home_center_data()
    return render_template(
        "home_center.html",
        page_title="MyPick 센터",
        active_tab="main",
        home_center=home_center,
    )


def render_player_rankings(position_type=None, page_title="선수 랭킹", active_tab="all"):
    all_rankings = get_rankings(position_type)
    pagination = paginate_items(all_rankings, page=get_page_number(), per_page=50)

    return render_template(
        "rankings.html",
        page_title=page_title,
        active_tab=active_tab,
        rankings=pagination["items"],
        ranking_total_count=len(all_rankings),
        pagination=pagination,
    )


@app.route("/rankings")
def rankings():
    return render_player_rankings(
        position_type=None,
        page_title="선수 랭킹",
        active_tab="all",
    )


@app.route("/batters")
def batters():
    return render_player_rankings(
        position_type="batter",
        page_title="선수 랭킹 - 타자",
        active_tab="batters",
    )


@app.route("/pitchers")
def pitchers():
    return render_player_rankings(
        position_type="pitcher",
        page_title="선수 랭킹 - 투수",
        active_tab="pitchers",
    )


@app.route("/user-rankings")
def user_rankings():
    """
    유저 랭킹 페이지입니다.

    type=total: 총 재산 랭킹
    type=monthly: 월간 수익 랭킹
    type=recent: 최근 경기 수익 랭킹
    """
    ranking_type = request.args.get("type", "total").strip()
    ranking_month = request.args.get("month", "").strip()
    search_query = request.args.get("q", "").strip()

    if ranking_type not in ["total", "monthly", "recent"]:
        ranking_type = "total"

    ranking_data = get_user_rankings(
        ranking_type=ranking_type,
        ranking_month=ranking_month,
        search_query=search_query,
    )
    pagination = paginate_items(
        ranking_data["rankings"],
        page=get_page_number(),
        per_page=50,
    )

    return render_template(
        "user_rankings.html",
        page_title="유저 랭킹",
        active_tab="user_rankings",
        ranking_type=ranking_type,
        ranking_month=ranking_data.get("ranking_month"),
        search_query=ranking_data.get("search_query", ""),
        ranking_data=ranking_data,
        rankings=pagination["items"],
        pagination=pagination,
        ranking_endpoint="user_rankings",
        is_friend_ranking=False,
    )


@app.route("/friend-rankings")
@login_required
def friend_rankings():
    """현재 로그인 유저와 친구로 수락된 유저들만 보는 친구 랭킹입니다."""
    current_user = get_current_user()
    ranking_type = request.args.get("type", "total").strip()
    ranking_month = request.args.get("month", "").strip()
    search_query = request.args.get("q", "").strip()

    if ranking_type not in ["total", "monthly", "recent"]:
        ranking_type = "total"

    friend_scope_user_ids = get_friend_user_ids(current_user["id"], include_self=True)
    ranking_data = get_user_rankings(
        ranking_type=ranking_type,
        ranking_month=ranking_month,
        search_query=search_query,
        scope_user_ids=friend_scope_user_ids,
    )
    pagination = paginate_items(
        ranking_data["rankings"],
        page=get_page_number(),
        per_page=50,
    )

    return render_template(
        "user_rankings.html",
        page_title="친구 랭킹",
        active_tab="friend_rankings",
        ranking_type=ranking_type,
        ranking_month=ranking_data.get("ranking_month"),
        search_query=ranking_data.get("search_query", ""),
        ranking_data=ranking_data,
        rankings=pagination["items"],
        pagination=pagination,
        ranking_endpoint="friend_rankings",
        is_friend_ranking=True,
    )


@app.route("/players")
def players():
    name = request.args.get("name", "").strip()
    team = request.args.get("team", "").strip()
    roster_position = request.args.get("roster_position", "").strip()
    detail_position = request.args.get("detail_position", "").strip()
    fantasy_position_type = request.args.get("fantasy_position_type", "").strip()
    price_min = request.args.get("price_min", "").strip()
    price_max = request.args.get("price_max", "").strip()

    registered_players = get_registered_players(
        name=name,
        team=team,
        roster_position=roster_position,
        detail_position=detail_position,
        fantasy_position_type=fantasy_position_type,
        price_min=price_min,
        price_max=price_max
    )

    filters = {
        "name": name,
        "team": team,
        "roster_position": roster_position,
        "detail_position": detail_position,
        "fantasy_position_type": fantasy_position_type,
        "price_min": price_min,
        "price_max": price_max,
    }

    pagination = paginate_items(
        registered_players,
        page=get_page_number(),
        per_page=get_player_result_page_size(50),
    )

    return render_template(
        "players.html",
        page_title="선수 검색",
        active_tab="players",
        players=pagination["items"],
        filters=filters,
        pagination=pagination,
    )


@app.route("/player/<position_type>/<team>/<player_name>")
def player_detail(position_type, team, player_name):
    player = get_registered_player_detail(player_name, team, position_type)

    if player is None:
        player = get_player_total(player_name, team, position_type)

    daily_scores = get_player_daily_scores(player_name, team, position_type)
    season_total_points = get_player_season_total_points(
        player_name=player_name,
        team=team,
        position_type=position_type
    )
    price_history = []
    price_history_month = []
    price_history_year = []
    season_stats = get_player_season_stats(
        player_name=player_name,
        team=team,
        position_type=position_type
    )

    if player and player.get("registered_player_id"):
        full_price_history = get_player_price_history(player["registered_player_id"], limit=366)
        price_history = full_price_history[-5:]
        price_history_month = filter_price_history_by_days(full_price_history, 31)
        price_history_year = full_price_history

    return render_template(
        "player_detail.html",
        page_title=f"{player_name} 선수 상세",
        active_tab="players",
        player=player,
        daily_scores=daily_scores,
        price_history=price_history,
        price_history_month=price_history_month,
        price_history_year=price_history_year,
        season_total_points=season_total_points,
        season_stats=season_stats
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not username:
            flash("아이디를 입력해주세요.")
            return redirect(url_for("register"))

        if len(username) < 3:
            flash("아이디는 최소 3글자 이상이어야 합니다.")
            return redirect(url_for("register"))

        if not password:
            flash("비밀번호를 입력해주세요.")
            return redirect(url_for("register"))

        if len(password) < PASSWORD_MIN_LENGTH:
            flash(f"비밀번호는 최소 {PASSWORD_MIN_LENGTH}글자 이상이어야 합니다.")
            return redirect(url_for("register"))

        if password != password_confirm:
            flash("비밀번호 확인이 일치하지 않습니다.")
            return redirect(url_for("register"))

        if not display_name:
            display_name = username

        password_hash = generate_password_hash(password)

        try:
            with get_conn() as conn:
                cursor = conn.execute("""
                    INSERT INTO users (
                        username,
                        password_hash,
                        display_name
                    )
                    VALUES (?, ?, ?)
                """, (
                    username,
                    password_hash,
                    display_name,
                ))
                new_user_id = cursor.lastrowid

                conn.execute("""
                    INSERT INTO fantasy_teams (
                        user_id,
                        team_name,
                        budget_limit,
                        cash_balance_decimal
                    )
                    VALUES (?, ?, 100, 100.0)
                """, (
                    new_user_id,
                    build_internal_team_name(display_name, username),
                ))

                ensure_betting_tables(conn)
                conn.execute("""
                    INSERT INTO betting_ledger (
                        user_id,
                        bet_id,
                        event_type,
                        amount_points,
                        note
                    )
                    VALUES (?, NULL, 'signup_bonus', ?, ?)
                """, (
                    new_user_id,
                    SIGNUP_STARTING_POINTS,
                    "신규 가입 시작 자산",
                ))
        except sqlite3.IntegrityError:
            flash("이미 사용 중인 아이디입니다.")
            return redirect(url_for("register"))

        session.clear()
        session["user_id"] = new_user_id
        return redirect(url_for("index"))

    return render_template(
        "register.html",
        page_title="회원가입",
        active_tab="register"
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next", "").strip()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = request.form.get("next", next_url).strip()

        if not username or not password:
            flash("아이디와 비밀번호를 모두 입력해주세요.")
            return redirect(url_for("login", next=next_url) if next_url else url_for("login"))

        with get_conn() as conn:
            user = conn.execute("""
                SELECT
                    id,
                    username,
                    password_hash,
                    display_name
                FROM users
                WHERE username = ?
            """, (username,)).fetchone()

        if user is None:
            flash("아이디 또는 비밀번호가 올바르지 않습니다.")
            return redirect(url_for("login", next=next_url) if next_url else url_for("login"))

        if not check_password_hash(user["password_hash"], password):
            flash("아이디 또는 비밀번호가 올바르지 않습니다.")
            return redirect(url_for("login", next=next_url) if next_url else url_for("login"))

        session.clear()
        session["user_id"] = user["id"]

        if next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)

        return redirect(url_for("center"))

    return render_template(
        "login.html",
        page_title="로그인",
        active_tab="login",
        next_url=next_url
    )


@app.route("/profile")
@login_required
def profile():
    current_user = get_current_user()
    selected_month = request.args.get("month", "").strip()

    if get_my_team(current_user["id"]) is None:
        create_default_team_for_user(
            current_user["id"],
            current_user.get("display_name"),
            current_user.get("username")
        )
        return redirect(url_for("team_edit"))

    context = build_profile_context_for_user(current_user, selected_month)

    return render_template(
        "profile.html",
        page_title="프로필",
        active_tab="profile",
        is_public_profile=False,
        **context,
    )


@app.route("/profile/<int:user_id>")
def public_profile(user_id):
    current_user = get_current_user()

    if current_user is not None and int(current_user["id"]) == int(user_id):
        return redirect(url_for("profile"))

    profile_user = get_user_by_id(user_id)

    if profile_user is None:
        abort(404)

    selected_month = request.args.get("month", "").strip()
    context = build_profile_context_for_user(profile_user, selected_month)
    friend_relation = None
    if current_user is not None:
        friend_relation = get_friend_relation(current_user["id"], profile_user["id"])

    return render_template(
        "profile.html",
        page_title=f"{profile_user.get('display_name') or profile_user.get('username')} 프로필",
        active_tab="user_rankings",
        is_public_profile=True,
        friend_relation=friend_relation,
        **context,
    )


@app.route("/profile/favorite-team", methods=["POST"])
@login_required
def update_favorite_team():
    ensure_user_profile_columns()

    raw_team = (request.form.get("favorite_kbo_team") or "").strip()
    selected_team = normalize_kbo_team(raw_team) if raw_team else None

    if raw_team and selected_team is None:
        flash("응원팀을 다시 선택해 주세요.")
        return redirect(url_for("profile"))

    with get_conn() as conn:
        conn.execute("""
            UPDATE users
            SET favorite_kbo_team = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            selected_team,
            session.get("user_id"),
        ))

    return redirect(url_for("profile"))

@app.route("/friends")
@login_required
def friends():
    """친구 요청/현재 친구를 관리하는 페이지입니다."""
    current_user = get_current_user()
    friend_records = get_friend_records(current_user["id"])

    return render_template(
        "friends.html",
        page_title="친구 관리",
        active_tab="friends",
        friend_records=friend_records,
    )


@app.route("/friends/request/<int:user_id>", methods=["POST"])
@login_required
def send_friend_request(user_id):
    current_user = get_current_user()
    target_user = get_user_by_id(user_id)

    if target_user is None:
        abort(404)

    result = create_friend_request(current_user["id"], user_id)

    if result == "created":
        flash("친구 추가 요청을 보냈습니다.")
    elif result == "accepted":
        flash("이미 친구로 추가된 유저입니다.")
    elif result == "outgoing_pending":
        flash("이미 친구 요청을 보낸 유저입니다.")
    elif result == "incoming_pending":
        flash("이미 받은 친구 요청이 있습니다. 친구 관리에서 확인해주세요.")
    else:
        flash("친구 요청을 보낼 수 없습니다.")

    return redirect(url_for("public_profile", user_id=user_id))


@app.route("/friends/respond/<int:request_id>", methods=["POST"])
@login_required
def respond_friend_request(request_id):
    current_user = get_current_user()
    action = request.form.get("action", "").strip()

    ensure_friend_tables()
    with get_conn() as conn:
        row = conn.execute("""
            SELECT *
            FROM user_friendships
            WHERE id = ?
              AND addressee_id = ?
              AND status = 'pending'
        """, (request_id, current_user["id"])).fetchone()

        if row is None:
            flash("처리할 친구 요청을 찾을 수 없습니다.")
            return redirect(url_for("friends"))

        if action == "accept":
            conn.execute("""
                UPDATE user_friendships
                SET status = 'accepted',
                    responded_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (request_id,))
            flash("친구 요청을 수락했습니다.")
        elif action == "decline":
            conn.execute("""
                DELETE FROM user_friendships
                WHERE id = ?
            """, (request_id,))
            flash("친구 요청을 거절했습니다.")
        else:
            flash("알 수 없는 친구 요청 처리입니다.")

    return redirect(url_for("friends"))


@app.route("/friends/remove/<int:user_id>", methods=["POST"])
@login_required
def remove_friend(user_id):
    current_user = get_current_user()
    next_url = request.form.get("next_url", "").strip()

    ensure_friend_tables()
    with get_conn() as conn:
        conn.execute("""
            DELETE FROM user_friendships
            WHERE status = 'accepted'
              AND (
                    (requester_id = ? AND addressee_id = ?)
                 OR (requester_id = ? AND addressee_id = ?)
              )
        """, (current_user["id"], user_id, user_id, current_user["id"]))

    flash("친구를 삭제했습니다.")

    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)

    return redirect(url_for("friends"))


@app.route("/support", methods=["GET", "POST"])
@login_required
def support():
    """유저 문의 작성 페이지입니다."""
    current_user = get_current_user()
    ensure_support_tables()
    purge_expired_resolved_support_tickets()

    initial_form = {
        "category": request.args.get("category", "").strip(),
        "title": "",
        "message": "",
        "page_url": request.args.get("page_url", "").strip(),
    }

    if request.method == "POST":
        form_data = normalize_support_form(request.form)

        if form_data["errors"]:
            for error in form_data["errors"]:
                flash(error)
            return render_template(
                "support.html",
                page_title="문의하기",
                active_tab="support",
                categories=SUPPORT_CATEGORIES,
                form_data=form_data,
            )

        with get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO support_tickets (
                    user_id,
                    category,
                    title,
                    message,
                    page_url,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'open', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                current_user["id"],
                form_data["category"],
                form_data["title"],
                form_data["message"],
                form_data["page_url"] or None,
            ))
            ticket_id = cursor.lastrowid

        flash("문의가 접수되었습니다. 진행 상태는 내 문의 내역에서 확인할 수 있습니다.")
        return redirect(url_for("my_support_detail", ticket_id=ticket_id))

    return render_template(
        "support.html",
        page_title="문의하기",
        active_tab="support",
        categories=SUPPORT_CATEGORIES,
        form_data=initial_form,
    )


@app.route("/my-support")
@login_required
def my_support():
    """현재 유저가 제출한 문의 목록입니다."""
    current_user = get_current_user()
    data = get_user_support_tickets(current_user["id"])

    return render_template(
        "my_support.html",
        page_title="내 문의 내역",
        active_tab="support",
        tickets=data["tickets"],
        counts=data["counts"],
    )


@app.route("/my-support/<int:ticket_id>")
@login_required
def my_support_detail(ticket_id):
    """현재 유저가 제출한 문의 상세입니다."""
    current_user = get_current_user()
    ticket = get_support_ticket_for_user(ticket_id, current_user["id"])

    if ticket is None:
        abort(404)

    return render_template(
        "my_support_detail.html",
        page_title=f"문의 #{ticket_id}",
        active_tab="support",
        ticket=ticket,
    )


@app.route("/admin/support")
@admin_required
def admin_support():
    """관리자 문의 목록 페이지입니다."""
    status_filter = request.args.get("status", "all").strip() or "all"
    category_filter = request.args.get("category", "all").strip() or "all"
    search_query = request.args.get("q", "").strip()

    if status_filter != "all" and status_filter not in SUPPORT_STATUS_LABELS:
        status_filter = "all"
    if category_filter != "all" and category_filter not in SUPPORT_CATEGORY_LABELS:
        category_filter = "all"

    data = get_admin_support_tickets(
        status_filter=status_filter,
        category_filter=category_filter,
        search_query=search_query,
    )

    return render_template(
        "admin_support.html",
        page_title="문의 관리",
        active_tab="admin_support",
        tickets=data["tickets"],
        counts=data["counts"],
        statuses=SUPPORT_STATUSES,
        categories=SUPPORT_CATEGORIES,
        status_filter=status_filter,
        category_filter=category_filter,
        search_query=search_query,
    )


@app.route("/admin/support/<int:ticket_id>", methods=["GET", "POST"])
@admin_required
def admin_support_detail(ticket_id):
    """관리자 문의 상세/상태 변경 페이지입니다."""
    ensure_support_tables()
    purge_expired_resolved_support_tickets()

    if request.method == "POST":
        status = request.form.get("status", "").strip()
        admin_note = request.form.get("admin_note", "").strip()
        admin_reply = request.form.get("admin_reply", "").strip()

        if status not in SUPPORT_STATUS_LABELS:
            flash("올바르지 않은 문의 상태입니다.")
            return redirect(url_for("admin_support_detail", ticket_id=ticket_id))

        with get_conn() as conn:
            existing = conn.execute("""
                SELECT id
                FROM support_tickets
                WHERE id = ?
            """, (ticket_id,)).fetchone()

            if existing is None:
                abort(404)

            conn.execute("""
                UPDATE support_tickets
                SET status = ?,
                    admin_note = ?,
                    admin_reply = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    resolved_at = CASE
                        WHEN ? = 'resolved' THEN COALESCE(resolved_at, CURRENT_TIMESTAMP)
                        ELSE NULL
                    END
                WHERE id = ?
            """, (
                status,
                admin_note or None,
                admin_reply or None,
                status,
                ticket_id,
            ))

        flash("문의 상태와 메모를 저장했습니다.")
        return redirect(url_for("admin_support_detail", ticket_id=ticket_id))

    ticket = get_admin_support_ticket(ticket_id)
    if ticket is None:
        abort(404)

    return render_template(
        "admin_support_detail.html",
        page_title=f"문의 관리 #{ticket_id}",
        active_tab="admin_support",
        ticket=ticket,
        statuses=SUPPORT_STATUSES,
    )


@app.route("/admin/support/<int:ticket_id>/delete", methods=["POST"])
@admin_required
def admin_support_delete(ticket_id):
    """관리자가 문의를 수동으로 영구 삭제합니다."""
    ensure_support_tables()
    purge_expired_resolved_support_tickets()

    with get_conn() as conn:
        existing = conn.execute("""
            SELECT id
            FROM support_tickets
            WHERE id = ?
        """, (ticket_id,)).fetchone()

        if existing is None:
            flash("이미 삭제되었거나 존재하지 않는 문의입니다.")
            return redirect(url_for("admin_support"))

        conn.execute("""
            DELETE FROM support_tickets
            WHERE id = ?
        """, (ticket_id,))

    flash("문의가 영구 삭제되었습니다.")
    return redirect(url_for("admin_support"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """계정 설정 페이지입니다. 응원팀 변경은 프로필 페이지에 유지합니다."""
    current_user = get_current_user()

    if current_user is None:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        action = request.form.get("action", "").strip()
        current_password = request.form.get("current_password", "")
        user_id = current_user["id"]

        if action == "change_username":
            new_username = request.form.get("new_username", "").strip()

            if not verify_current_password(user_id, current_password):
                flash("현재 비밀번호가 올바르지 않습니다.")
                return redirect(url_for("settings"))

            if not new_username:
                flash("새 아이디를 입력해주세요.")
                return redirect(url_for("settings"))

            if len(new_username) < 3:
                flash("아이디는 최소 3글자 이상이어야 합니다.")
                return redirect(url_for("settings"))

            if len(new_username) > 32:
                flash("아이디는 32글자 이하로 입력해주세요.")
                return redirect(url_for("settings"))

            if any(char.isspace() for char in new_username):
                flash("아이디에는 공백을 사용할 수 없습니다.")
                return redirect(url_for("settings"))

            with get_conn() as conn:
                existing = conn.execute("""
                    SELECT id
                    FROM users
                    WHERE username = ?
                      AND id != ?
                """, (new_username, user_id)).fetchone()

                if existing is not None:
                    flash("이미 사용 중인 아이디입니다.")
                    return redirect(url_for("settings"))

                conn.execute("""
                    UPDATE users
                    SET username = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_username, user_id))

            flash("아이디가 변경되었습니다.")
            return redirect(url_for("settings"))

        if action == "change_display_name":
            new_display_name = request.form.get("new_display_name", "").strip()

            if not verify_current_password(user_id, current_password):
                flash("현재 비밀번호가 올바르지 않습니다.")
                return redirect(url_for("settings"))

            if not new_display_name:
                flash("새 표시 이름을 입력해주세요.")
                return redirect(url_for("settings"))

            if len(new_display_name) > 24:
                flash("표시 이름은 24글자 이하로 입력해주세요.")
                return redirect(url_for("settings"))

            with get_conn() as conn:
                conn.execute("""
                    UPDATE users
                    SET display_name = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_display_name, user_id))
                conn.execute("""
                    UPDATE fantasy_teams
                    SET team_name = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (
                    build_internal_team_name(new_display_name, current_user.get("username")),
                    user_id,
                ))

            flash("표시 이름이 변경되었습니다.")
            return redirect(url_for("settings"))

        if action == "change_password":
            new_password = request.form.get("new_password", "")
            new_password_confirm = request.form.get("new_password_confirm", "")

            if not verify_current_password(user_id, current_password):
                flash("현재 비밀번호가 올바르지 않습니다.")
                return redirect(url_for("settings"))

            if len(new_password) < PASSWORD_MIN_LENGTH:
                flash(f"새 비밀번호는 최소 {PASSWORD_MIN_LENGTH}글자 이상이어야 합니다.")
                return redirect(url_for("settings"))

            if new_password != new_password_confirm:
                flash("새 비밀번호 확인이 일치하지 않습니다.")
                return redirect(url_for("settings"))

            with get_conn() as conn:
                conn.execute("""
                    UPDATE users
                    SET password_hash = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (generate_password_hash(new_password), user_id))

            flash("비밀번호가 변경되었습니다. 다음 로그인부터 새 비밀번호를 사용하세요.")
            return redirect(url_for("settings"))

        if action == "delete_account":
            delete_confirm = request.form.get("delete_confirm", "").strip()

            if not verify_current_password(user_id, current_password):
                flash("현재 비밀번호가 올바르지 않습니다.")
                return redirect(url_for("settings"))

            if delete_confirm != "회원탈퇴":
                flash("회원탈퇴를 진행하려면 확인 문구에 '회원탈퇴'를 정확히 입력해주세요.")
                return redirect(url_for("settings"))

            delete_user_account_data(user_id)
            session.clear()
            flash("회원탈퇴가 완료되었습니다. 이용해주셔서 감사합니다.")
            return redirect(url_for("index"))

        flash("알 수 없는 설정 요청입니다.")
        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        page_title="환경설정",
        active_tab="settings",
        user=current_user,
    )


@app.route("/my-team")
@login_required
def my_team():
    current_user = get_current_user()
    team = get_my_team(current_user["id"])

    summary = None
    validation = None
    roster_rows = []
    team_score_summary = None
    recent_team_scores = []
    team_score_history = []

    latest_game_date = get_latest_synced_game_date()
    latest_game_date_display = format_game_date_for_display(latest_game_date)

    if team is None:
        create_default_team_for_user(
            current_user["id"],
            current_user.get("display_name"),
            current_user.get("username")
        )
        return redirect(url_for("team_edit"))

    if team is not None:
        summary = get_team_summary(
            team_id=team["id"],
            budget_limit=team["budget_limit"]
        )

        validation = validate_team_roster(
            summary=summary,
            budget_limit=team["budget_limit"]
        )

        roster_rows = build_roster_rows(summary)
        team_score_summary = get_team_score_summary(team["id"])
        recent_team_scores = get_recent_team_scores(team["id"], limit=5)
        team_score_history = get_team_score_history(team["id"], limit=370)

    return render_template(
        "my_team.html",
        page_title="내 팀",
        active_tab="my_team",
        team=team,
        summary=summary,
        validation=validation,
        roster_rows=roster_rows,
        team_score_summary=team_score_summary,
        recent_team_scores=recent_team_scores,
        team_score_history=team_score_history,
        team_notice=pop_team_notice(),
        team_edit_lock=get_team_edit_lock_status(),
        latest_game_date=latest_game_date,
        latest_game_date_display=latest_game_date_display,
        score_date=latest_game_date,
        score_date_input=latest_game_date_display
    )


@app.route("/my-team/create", methods=["POST"])
@login_required
def create_my_team():
    current_user = get_current_user()
    existing_team = get_my_team(current_user["id"])

    if existing_team is not None:
        set_team_notice(
            section="team",
            message="이미 팀이 있습니다.",
            category="error"
        )
        return redirect(url_for("my_team") + "#team-status")

    create_default_team_for_user(
        current_user["id"],
        current_user.get("display_name"),
        current_user.get("username")
    )

    return redirect(url_for("team_edit") + "#roster-section")


@app.route("/team/edit")
@login_required
def team_edit():
    current_user = get_current_user()
    team = get_my_team(current_user["id"])

    if team is None:
        return redirect(url_for("my_team"))

    locked_response = redirect_if_team_edit_locked()
    if locked_response is not None:
        return locked_response

    name = request.args.get("name", "").strip()
    team_filter = request.args.get("team", "").strip()
    detail_position = request.args.get("detail_position", "").strip()
    fantasy_position_type = request.args.get("fantasy_position_type", "").strip()
    price_min = request.args.get("price_min", "").strip()
    price_max = request.args.get("price_max", "").strip()

    summary = get_team_summary(
        team_id=team["id"],
        budget_limit=team["budget_limit"]
    )

    validation = validate_team_roster(
        summary=summary,
        budget_limit=team["budget_limit"]
    )

    roster_rows = build_roster_rows(summary)

    selected_player_ids = [
        player["registered_player_id"]
        for player in summary["players"]
    ]
    selected_player_keys = {
        registered_player_identity_key(player)
        for player in summary["players"]
    }

    all_players = get_registered_players(
        name=name,
        team=team_filter,
        detail_position=detail_position,
        fantasy_position_type=fantasy_position_type,
        price_min=price_min,
        price_max=price_max
    )

    players = [
        player
        for player in all_players
        if player["id"] not in selected_player_ids
        and registered_player_identity_key(player) not in selected_player_keys
        and player.get("price") is not None
    ]

    team_market_pagination = None
    if is_mobile_browser_request():
        team_market_pagination = paginate_items(
            players,
            page=get_page_number(),
            per_page=MOBILE_PLAYER_PAGE_SIZE,
        )
        players = team_market_pagination["items"]

    available_budget = round(float(summary.get("available_budget") or summary.get("remaining_budget") or 0), 1)
    for player in players:
        price = player.get("price")
        try:
            price_value = round(float(price), 1) if price is not None else None
        except (TypeError, ValueError):
            price_value = None
        player["can_afford"] = price_value is not None and price_value <= available_budget + 1e-9
        player["available_budget"] = available_budget

    filters = {
        "name": name,
        "team": team_filter,
        "detail_position": detail_position,
        "fantasy_position_type": fantasy_position_type,
        "price_min": price_min,
        "price_max": price_max,
    }

    return render_template(
        "team_edit.html",
        page_title="팀 편집",
        active_tab="my_team",
        team=team,
        summary=summary,
        validation=validation,
        roster_rows=roster_rows,
        players=players,
        selected_player_ids=selected_player_ids,
        filters=filters,
        team_market_pagination=team_market_pagination,
        team_notice=pop_team_notice()
    )


@app.route("/team/add", methods=["POST"])
@login_required
def team_add():
    current_user = get_current_user()
    team = get_my_team(current_user["id"])
    redirect_url = get_safe_next_url("team_edit", "#search-results")

    if team is None:
        flash("먼저 팀을 만들어주세요.")
        return redirect(url_for("my_team"))

    locked_response = redirect_if_team_edit_locked()
    if locked_response is not None:
        return locked_response

    registered_player_id = request.form.get("registered_player_id")

    if not registered_player_id:
        set_team_notice(
            section="search",
            message="선수를 선택해주세요.",
            category="error"
        )
        return redirect(redirect_url)

    player = get_registered_player_by_id(registered_player_id)

    if player is None:
        set_team_notice(
            section="search",
            message="존재하지 않는 선수입니다.",
            category="error"
        )
        return redirect(redirect_url)

    summary = get_team_summary(
        team_id=team["id"],
        budget_limit=team["budget_limit"]
    )

    if summary["selected_count"] >= 15:
        set_team_notice(
            section="search",
            message="이미 15명을 모두 선택했습니다.",
            category="error"
        )
        return redirect(redirect_url)

    for selected_player in summary["players"]:
        if selected_player["registered_player_id"] == player["id"]:
            set_team_notice(
                section="search",
                message="이미 선택한 선수입니다.",
                category="error"
            )
            return redirect(redirect_url)

        if players_refer_to_same_registered_identity(selected_player, player):
            set_team_notice(
                section="search",
                message="같은 선수는 중복으로 영입할 수 없습니다.",
                category="error"
            )
            return redirect(redirect_url)

    slot = find_auto_slot_for_player(player, summary)

    if slot is None:
        detail_position = player.get("detail_position")
        fantasy_position_type = player.get("fantasy_position_type")

        if fantasy_position_type == "pitcher":
            used_slots = [
                selected_player["slot"]
                for selected_player in summary["players"]
            ]

            if detail_position == "선발투수" and "P1" in used_slots:
                message = "선발투수 슬롯은 이미 채워져 있습니다."
            elif (
                detail_position == "불펜투수"
                and all(
                    pitcher_slot in used_slots
                    for pitcher_slot in ["P2", "P3", "P4", "P5", "P6"]
                )
            ):
                message = "불펜투수 슬롯이 모두 채워져 있습니다."
            elif detail_position not in ["선발투수", "불펜투수"]:
                message = (
                    f'{player["name"]} 선수는 아직 선발/불펜 역할 정보가 없습니다. '
                    "경기 데이터를 업데이트한 뒤 다시 시도해주세요."
                )
            else:
                message = f'{player["name"]} 선수를 넣을 수 있는 투수 슬롯이 없습니다.'
        else:
            message = f'{player["name"]} 선수를 넣을 수 있는 빈 슬롯이 없습니다.'

        set_team_notice(
            section="search",
            message=message,
            category="error"
        )
        return redirect(redirect_url)

    player_price = round(float(player.get("price") or 0), 1)
    if player_price <= 0:
        set_team_notice(
            section="search",
            message=f'{player["name"]} 선수는 현재 시장가가 없어 영입할 수 없습니다.',
            category="error"
        )
        return redirect(redirect_url)

    available_budget = round(float(summary.get("available_budget") or summary.get("remaining_budget") or 0), 1)
    acquisition_cost_total = round(float(summary.get("acquisition_cost_total") or summary.get("used_budget") or 0), 1)
    budget_limit_number = round(float(team.get("budget_limit") or 100), 1)
    new_acquisition_cost_total = round(acquisition_cost_total + player_price, 1)

    if player_price > available_budget + 1e-9:
        set_team_notice(
            section="search",
            message=(
                f'{player["name"]} 선수의 시장가가 {player_price:.1f}입니다. '
                f'현재 사용가능 예산 {available_budget:.1f}으로는 영입할 수 없습니다.'
            ),
            category="error"
        )
        return redirect(redirect_url)

    latest_price_date = summary.get("latest_price_date") or get_latest_price_date()
    new_cash_balance = round(max(0.0, available_budget - player_price), 1)

    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO fantasy_team_players (
                    team_id,
                    registered_player_id,
                    slot,
                    locked_price_decimal,
                    locked_price_basis_date,
                    locked_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                team["id"],
                player["id"],
                slot,
                player_price,
                latest_price_date,
            ))

            conn.execute("""
                UPDATE fantasy_teams
                SET
                    cash_balance_decimal = ?,
                    is_confirmed = 0,
                    confirmed_at = NULL,
                    confirmed_budget_used = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                new_cash_balance,
                team["id"],
            ))
    except sqlite3.IntegrityError:
        set_team_notice(
            section="search",
            message="이미 선택된 선수이거나 이미 채워진 슬롯입니다.",
            category="error"
        )
        return redirect(redirect_url)

    set_team_notice(
        section="search",
        message=f'{player["name"]} 선수를 {get_slot_label(slot)} 슬롯에 영입하였습니다. 영입가 {player_price:.1f}.',
        category="success"
    )

    return redirect(redirect_url)


@app.route("/team/remove", methods=["POST"])
@login_required
def team_remove():
    current_user = get_current_user()
    team = get_my_team(current_user["id"])
    redirect_url = get_safe_next_url("team_edit", "#roster-section")

    if team is None:
        flash("먼저 팀을 만들어주세요.")
        return redirect(url_for("my_team"))

    locked_response = redirect_if_team_edit_locked()
    if locked_response is not None:
        return locked_response

    slot = request.form.get("slot", "").strip()

    if slot not in get_valid_slot_values():
        set_team_notice(
            section="roster",
            message="올바르지 않은 슬롯입니다.",
            category="error"
        )
        return redirect(redirect_url)

    summary = get_team_summary(
        team_id=team["id"],
        budget_limit=team["budget_limit"]
    )

    deleted_count = 0
    removed_registered_player_id = None
    removed_player_name = None
    sell_price = None
    locked_price = None
    release_values = None
    basis_date = None
    bonus_points = 0.0

    with get_conn() as conn:
        ensure_trade_bonus_tables(conn)

        removed_row = conn.execute("""
            SELECT
                ftp.registered_player_id,
                ftp.slot,
                ftp.locked_price_decimal,
                rp.name,
                rp.team,
                rp.fantasy_position_type
            FROM fantasy_team_players ftp
            JOIN registered_players rp
              ON rp.id = ftp.registered_player_id
            WHERE ftp.team_id = ?
              AND ftp.slot = ?
        """, (
            team["id"],
            slot,
        )).fetchone()

        if removed_row is None:
            set_team_notice(
                section="roster",
                message=f'{get_slot_label(slot)} 슬롯에는 방출할 선수가 없습니다.',
                category="error"
            )
            return redirect(redirect_url)

        removed_registered_player_id = removed_row["registered_player_id"]
        removed_player_name = removed_row["name"]
        locked_price = normalize_market_price_value(removed_row["locked_price_decimal"])

        if locked_price is None or locked_price <= 0:
            set_team_notice(
                section="roster",
                message=(
                    f'{removed_player_name} 선수의 영입가 정보를 확인할 수 없어 방출할 수 없습니다. '
                    '팀 예산 보호를 위해 관리자에게 문의해주세요.'
                ),
                category="error"
            )
            return redirect(redirect_url)

        price_record = fetch_market_price_record(
            conn,
            registered_player_id=removed_registered_player_id,
            player_name=removed_row["name"],
            team=removed_row["team"],
            fantasy_position_type=removed_row["fantasy_position_type"],
        )
        if price_record is not None:
            sell_price = normalize_market_price_value(price_record.get("price_decimal"))
            if sell_price is None:
                sell_price = normalize_market_price_value(price_record.get("price"))
            basis_date = price_record.get("basis_date")

        if sell_price is None or sell_price <= 0:
            set_team_notice(
                section="roster",
                message=f'{removed_player_name} 선수의 현재 시장가를 확인할 수 없어 방출할 수 없습니다.',
                category="error"
            )
            return redirect(redirect_url)

        release_values = calculate_release_trade_values(
            locked_price,
            sell_price,
            roster_market_value_before=summary.get("team_market_value"),
            budget_limit=team.get("budget_limit") or 100,
        )
        if release_values is None:
            set_team_notice(
                section="roster",
                message=f'{removed_player_name} 선수의 방출 정산 금액을 계산할 수 없습니다.',
                category="error"
            )
            return redirect(redirect_url)

        cursor = conn.execute("""
            DELETE FROM fantasy_team_players
            WHERE team_id = ?
              AND slot = ?
        """, (
            team["id"],
            slot,
        ))

        deleted_count = cursor.rowcount or 0

        if deleted_count > 0:
            current_cash = round(float(summary.get("available_budget") or summary.get("cash_balance_decimal") or 0), 1)
            budget_refund = round(float(release_values["budget_refund"] or 0), 1)
            new_cash_balance = round(max(0.0, current_cash + budget_refund), 1)

            bonus_points = float(release_values["bonus_points"] or 0)

            if bonus_points > 0:
                conn.execute("""
                    INSERT INTO fantasy_team_trade_bonus_events (
                        user_id,
                        team_id,
                        registered_player_id,
                        player_name,
                        player_team,
                        position_type,
                        slot,
                        locked_price_decimal,
                        current_market_price,
                        roster_market_value_before,
                        roster_excess_before_decimal,
                        budget_refund_decimal,
                        realized_profit_decimal,
                        profit_units,
                        bonus_points,
                        points_per_unit,
                        basis_source,
                        basis_date,
                        event_date
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    current_user["id"],
                    team["id"],
                    removed_registered_player_id,
                    removed_row["name"],
                    removed_row["team"],
                    removed_row["fantasy_position_type"],
                    removed_row["slot"],
                    locked_price,
                    sell_price,
                    release_values["roster_market_value_before"],
                    release_values["roster_excess_before"],
                    release_values["budget_refund"],
                    release_values["realized_profit"],
                    release_values["profit_units"],
                    bonus_points,
                    TRADE_BONUS_POINTS_PER_PRICE_TENTH,
                    BASIS_SOURCE,
                    basis_date,
                    date.today().isoformat(),
                ))

            conn.execute("""
                UPDATE fantasy_teams
                SET
                    cash_balance_decimal = ?,
                    is_confirmed = 0,
                    confirmed_at = NULL,
                    confirmed_budget_used = NULL,
                    captain_registered_player_id = CASE
                        WHEN captain_registered_player_id = ? THEN NULL
                        ELSE captain_registered_player_id
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                new_cash_balance,
                removed_registered_player_id,
                team["id"],
            ))

    if deleted_count <= 0:
        set_team_notice(
            section="roster",
            message=f'{get_slot_label(slot)} 슬롯에는 방출할 선수가 없습니다.',
            category="error"
        )
        return redirect(redirect_url)

    if bonus_points > 0 and release_values is not None:
        set_team_notice(
            section="roster",
            message=(
                f'{get_slot_label(slot)} 슬롯의 {removed_player_name} 선수를 방출했습니다. '
                f'사용가능 예산 {release_values["budget_refund"]:.1f}이 회복되었고, '
                f'방출 수익 {format_money_from_points(bonus_points)}이 총 자산에 반영되었습니다. '
                f'(초과 수익 {release_values["realized_profit"]:.1f})'
            ),
            category="success"
        )
    elif sell_price is not None and locked_price is not None and sell_price < locked_price:
        set_team_notice(
            section="roster",
            message=(
                f'{get_slot_label(slot)} 슬롯의 {removed_player_name} 선수를 방출했습니다. '
                f'시장가 {release_values["budget_refund"]:.1f}을 사용가능 예산으로 회수했습니다. '
                f'(영입가 {locked_price:.1f})'
            ),
            category="success"
        )
    else:
        set_team_notice(
            section="roster",
            message=(
                f'{get_slot_label(slot)} 슬롯의 {removed_player_name} 선수를 방출했습니다. '
                f'사용가능 예산 {release_values["budget_refund"]:.1f}이 회복되었습니다.'
            ),
            category="success"
        )

    return redirect(redirect_url)


@app.route("/team/captain", methods=["POST"])
@login_required
def team_captain():
    """팀 편집에서 현재 로스터 선수 1명을 C로 지정합니다."""
    current_user = get_current_user()
    team = get_my_team(current_user["id"])
    redirect_url = get_safe_next_url("team_edit", "#roster-section")

    if team is None:
        flash("먼저 팀을 만들어주세요.")
        return redirect(url_for("my_team"))

    locked_response = redirect_if_team_edit_locked()
    if locked_response is not None:
        return locked_response

    registered_player_id = request.form.get("registered_player_id", "").strip()

    if not registered_player_id:
        set_team_notice(
            section="roster",
            message="C로 지정할 선수를 선택해주세요.",
            category="error"
        )
        return redirect(redirect_url)

    try:
        target_player_id = int(registered_player_id)
    except (TypeError, ValueError):
        set_team_notice(
            section="roster",
            message="올바르지 않은 선수입니다.",
            category="error"
        )
        return redirect(redirect_url)

    with get_conn() as conn:
        roster_player = conn.execute("""
            SELECT
                ftp.registered_player_id,
                rp.name,
                rp.team
            FROM fantasy_team_players ftp
            JOIN registered_players rp
              ON rp.id = ftp.registered_player_id
            WHERE ftp.team_id = ?
              AND ftp.registered_player_id = ?
        """, (
            team["id"],
            target_player_id,
        )).fetchone()

        if roster_player is None:
            set_team_notice(
                section="roster",
                message="현재 로스터에 있는 선수만 C로 지정할 수 있습니다.",
                category="error"
            )
            return redirect(redirect_url)

        current_captain_id = team.get("captain_registered_player_id")
        if current_captain_id is not None and int(current_captain_id or 0) == target_player_id:
            set_team_notice(
                section="roster",
                message=f'{roster_player["name"]} 선수는 이미 C로 지정되어 있습니다.',
                category="success"
            )
            return redirect(redirect_url)

        was_confirmed = int(team.get("is_confirmed") or 0) == 1

        conn.execute("""
            UPDATE fantasy_teams
            SET
                captain_registered_player_id = ?,
                is_confirmed = 0,
                confirmed_at = NULL,
                confirmed_budget_used = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            target_player_id,
            team["id"],
        ))

    if was_confirmed:
        set_team_notice(
            section="roster",
            message=f'{roster_player["name"]} 선수를 C로 지정했습니다. 공식 수익에 적용하려면 팀을 다시 확정해주세요.',
            category="warning"
        )
    else:
        set_team_notice(
            section="roster",
            message=f'{roster_player["name"]} 선수를 C로 지정했습니다.',
            category="success"
        )

    return redirect(redirect_url)


@app.route("/team/confirm", methods=["POST"])
@login_required
def team_confirm():
    """
    팀 확정하기 버튼용 라우트입니다.

    새 예산 원칙:
    - 기존 선수의 영입가는 다시 확정해도 시장가로 덮어쓰지 않습니다.
    - 새로 영입된 선수는 /team/add 시점의 시장가가 이미 영입가로 저장됩니다.
    - C 변경은 예산/영입가에 영향을 주지 않고, 다시 확정만 필요합니다.
    """
    current_user = get_current_user()
    team = get_my_team(current_user["id"])

    if team is None:
        flash("먼저 팀을 만들어주세요.")
        return redirect(url_for("my_team"))

    locked_response = redirect_if_team_edit_locked()
    if locked_response is not None:
        return locked_response

    summary = get_team_summary(
        team_id=team["id"],
        budget_limit=team["budget_limit"]
    )

    result = validate_team_roster(
        summary=summary,
        budget_limit=team["budget_limit"]
    )

    if not result["is_complete"]:
        set_team_notice(
            section="confirm",
            message="팀을 확정할 수 없습니다.",
            category="error",
            problems=result["problems"]
        )
        return redirect(url_for("team_edit") + "#confirm-section")

    already_confirmed = int(team.get("is_confirmed") or 0) == 1
    has_complete_locked_prices = all(
        player.get("stored_locked_price_decimal") is not None
        for player in summary["players"]
    )

    if already_confirmed and has_complete_locked_prices:
        set_team_notice(
            section="team",
            message="이미 확정된 팀입니다. 기존 영입가와 예산을 그대로 유지했습니다.",
            category="success"
        )
        return redirect(url_for("my_team") + "#team-status")

    latest_price_date = summary.get("latest_price_date") or get_latest_price_date()
    lock_updates = []
    confirmed_budget_used = 0.0

    for player in summary["players"]:
        locked_price = player.get("stored_locked_price_decimal")

        if locked_price is None:
            locked_price = player.get("current_market_price")
            if locked_price is None:
                locked_price = player.get("price")
            locked_price = round(float(locked_price or 0), 1)

            if locked_price <= 0:
                set_team_notice(
                    section="confirm",
                    message="팀을 확정할 수 없습니다.",
                    category="error",
                    problems=[f'{player["name"]} 선수의 현재 시장가를 확인할 수 없습니다.']
                )
                return redirect(url_for("team_edit") + "#confirm-section")

            lock_updates.append({
                "registered_player_id": player["registered_player_id"],
                "locked_price": locked_price,
            })
        else:
            locked_price = round(float(locked_price or 0), 1)

        confirmed_budget_used = round(confirmed_budget_used + locked_price, 1)

    with get_conn() as conn:
        for item in lock_updates:
            conn.execute("""
                UPDATE fantasy_team_players
                SET
                    locked_price_decimal = ?,
                    locked_price_basis_date = ?,
                    locked_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE team_id = ?
                  AND registered_player_id = ?
                  AND locked_price_decimal IS NULL
            """, (
                item["locked_price"],
                latest_price_date,
                team["id"],
                item["registered_player_id"],
            ))

        conn.execute("""
            UPDATE fantasy_teams
            SET
                is_confirmed = 1,
                confirmed_at = CURRENT_TIMESTAMP,
                confirmed_budget_used = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            confirmed_budget_used,
            team["id"],
        ))

    set_team_notice(
        section="team",
        message="팀이 확정되었습니다. 기존 선수의 영입가와 예산은 그대로 유지되었습니다.",
        category="success"
    )
    return redirect(url_for("my_team") + "#team-status")


@app.route("/team/validate", methods=["POST"])
@login_required
def team_validate():
    current_user = get_current_user()
    team = get_my_team(current_user["id"])

    if team is None:
        flash("먼저 팀을 만들어주세요.")
        return redirect(url_for("my_team"))

    summary = get_team_summary(
        team_id=team["id"],
        budget_limit=team["budget_limit"]
    )

    result = validate_team_roster(
        summary=summary,
        budget_limit=team["budget_limit"]
    )

    if result["is_complete"]:
        set_team_notice(
            section="team",
            message="팀 완성 조건을 모두 만족합니다.",
            category="success"
        )
    else:
        set_team_notice(
            section="team",
            message="아직 팀이 완성되지 않았습니다.",
            category="error",
            problems=result["problems"]
        )

    return redirect(url_for("my_team") + "#team-status")


@app.route("/betting")
def betting():
    """최신 경기 업데이트 이후 가까운 2개 경기일만 보여주는 배팅 메인 페이지입니다."""
    current_user = get_current_user()
    board_data = get_betting_board_data(current_user.get("id") if current_user else None)
    current_wealth = get_user_wealth_points(current_user["id"]) if current_user else 0.0

    return render_template(
        "betting.html",
        page_title="배팅",
        active_tab="betting",
        board_data=board_data,
        current_wealth_points=current_wealth,
        min_stake=BETTING_MIN_STAKE,
        max_stake_per_market=BETTING_MAX_STAKE_PER_MARKET,
        stake_unit=BETTING_STAKE_UNIT,
    )


@app.route("/betting/place", methods=["POST"])
@login_required
def betting_place():
    """배팅 선택을 확정합니다. 클라이언트 값은 믿지 않고 DB의 selection/odds를 기준으로 처리합니다."""
    current_user = get_current_user()
    redirect_url = request.form.get("next_url", "").strip()
    if not (redirect_url.startswith("/") and not redirect_url.startswith("//")):
        redirect_url = url_for("betting")

    try:
        selection_id = int(request.form.get("selection_id", ""))
    except (TypeError, ValueError):
        flash("배팅 선택을 다시 확인해 주세요.")
        return redirect(redirect_url)

    stake, stake_error = parse_stake(request.form.get("stake_points", ""))
    if stake_error:
        flash(stake_error)
        return redirect(redirect_url)

    with get_conn() as conn:
        ensure_betting_tables(conn)
        selected = get_selection_for_bet(conn, selection_id)
        if selected is None:
            flash("배팅 선택지를 찾을 수 없습니다.")
            return redirect(redirect_url)

        if not int(selected["is_active"] or 0):
            flash("현재 선택할 수 없는 배팅입니다.")
            return redirect(redirect_url)

        if selected["market_status"] != "open":
            flash("이미 마감된 배팅 항목입니다.")
            return redirect(redirect_url)

        game_status = selected["game_status"]
        if game_status != "scheduled":
            flash("이미 시작했거나 마감된 경기입니다.")
            return redirect(redirect_url)

        if not is_game_open_for_betting(selected):
            flash("경기 시작 시간이 지나 배팅이 마감되었습니다.")
            return redirect(redirect_url)

        existing = conn.execute("""
            SELECT id
            FROM betting_bets
            WHERE user_id = ?
              AND market_id = ?
            LIMIT 1
        """, (current_user["id"], selected["market_id"])).fetchone()
        if existing is not None:
            flash("같은 경기의 같은 항목에는 한 번만 배팅할 수 있습니다.")
            return redirect(redirect_url)

        available_wealth = get_user_wealth_points_from_conn(conn, current_user["id"])
        if stake > available_wealth:
            flash(f"현재 총 재산보다 큰 금액은 배팅할 수 없습니다. 현재 재산: {format_money_from_points(available_wealth)}")
            return redirect(redirect_url)

        odds = float(selected["odds_decimal"] or 0)
        if odds <= 1:
            flash("배당률이 올바르지 않아 배팅할 수 없습니다.")
            return redirect(redirect_url)

        displayed_odds_raw = request.form.get("displayed_odds", "").strip()
        if displayed_odds_raw:
            try:
                displayed_odds = float(displayed_odds_raw)
            except ValueError:
                displayed_odds = None
            if displayed_odds is not None and abs(displayed_odds - odds) >= 0.001:
                flash(f"배당이 {displayed_odds:.2f}에서 {odds:.2f}로 변경되었습니다. 다시 확인한 뒤 배팅해 주세요.")
                return redirect(redirect_url)

        potential_payout = round(float(stake) * odds, 1)
        cursor = conn.execute("""
            INSERT INTO betting_bets (
                user_id, betting_game_id, market_id, selection_id,
                stake_points, odds_at_bet, potential_payout, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            current_user["id"],
            selected["betting_game_id"],
            selected["market_id"],
            selected["selection_id"],
            stake,
            odds,
            potential_payout,
        ))
        bet_id = cursor.lastrowid

        conn.execute("""
            INSERT INTO betting_ledger (
                user_id, bet_id, event_type, amount_points, note
            )
            VALUES (?, ?, 'stake', ?, ?)
        """, (
            current_user["id"],
            bet_id,
            -float(stake),
            f"{selected['away_team']} vs {selected['home_team']} · {selected['selection_label']}",
        ))

        # 방금 들어온 stake까지 포함해 같은 market의 다음 배당률을 자동 보정합니다.
        # 이미 생성된 이 bet의 odds_at_bet은 그대로 고정됩니다.
        reprice_market_after_bet(conn, int(selected["market_id"]))

    flash(f"{selected['selection_label']}에 {format_money_from_points(stake)} 배팅했습니다. 예상 수령액은 {format_money_from_points(potential_payout)}입니다.")
    return redirect(redirect_url)


@app.route("/betting/history")
@login_required
def betting_history():
    """로그인 유저의 배팅 내역 페이지입니다."""
    current_user = get_current_user()
    history = get_betting_history(current_user["id"], limit=200)

    return render_template(
        "betting_history.html",
        page_title="배팅 내역",
        active_tab="betting",
        history=history,
    )


@app.route("/play-guide")
def play_guide():
    """처음 시작하는 유저를 위한 간단한 플레이 가이드 페이지입니다."""
    return render_template(
        "play_guide.html",
        page_title="플레이 가이드",
        active_tab="",
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("로그아웃되었습니다.")
    return redirect(url_for("index"))



# --- Betting / shared Jinja globals ---
# `_ui.html` macros may be imported without template context, so helpers used
# inside macros must be registered as real Jinja globals.
app.jinja_env.globals["get_team_meta"] = get_team_meta
app.jinja_env.globals["csrf_token"] = get_csrf_token
# --- End Betting / shared Jinja globals ---

if __name__ == "__main__":
    app.run(debug=not IS_PRODUCTION)
