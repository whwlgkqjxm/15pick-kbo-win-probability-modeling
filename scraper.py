# scraper.py
"""
KBO 사이트에서 경기 일정, 타자 기록, 투수 기록을 가져오는 파일입니다.

현재 이 파일이 하는 일:

1. 날짜별 KBO 경기 목록 가져오기
2. 각 경기의 game_id, 리뷰 URL, 팀명, 점수 가져오기
3. GetBoxScore API로 타자/투수 기록 가져오기
4. 타자 기록 파싱
5. 투수 기록 파싱
6. 홈 투수 이름이 숫자 ID로 나오는 경우 실제 선수명으로 변환
7. 투수 기록표 순서를 기준으로 선발투수 여부와 투수 등판 순서 저장

아직 DB 저장은 하지 않습니다.
DB 저장은 다음 단계에서 sync_db.py에서 처리합니다.
"""

import json
import re
import sys
import time
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

from config import KBO_BASE, SCHEDULE_URL, REQUEST_HEADERS, REQUEST_TIMEOUT


# ==========================================================
# KBO API 주소
# ==========================================================

SCHEDULE_LIST_API = f"{KBO_BASE}/ws/Schedule.asmx/GetScheduleList"
BOX_SCORE_API = f"{KBO_BASE}/ws/Schedule.asmx/GetBoxScore"


# KBO game_id에 쓰이는 구단 코드입니다.
# 예: 20260519SKWO0 -> SSG 원정 / 키움 홈
KBO_TEAM_CODE_TO_NAME = {
    "KT": "KT",
    "LG": "LG",
    "SK": "SSG",
    "HT": "KIA",
    "OB": "두산",
    "NC": "NC",
    "HH": "한화",
    "LT": "롯데",
    "SS": "삼성",
    "WO": "키움",
}

KBO_TEAM_CODES = list(KBO_TEAM_CODE_TO_NAME.keys())

# KBO 영문 스코어보드 fallback에서 쓰는 팀명 매핑입니다.
KBO_TEAM_NAME_TO_CODE = {name: code for code, name in KBO_TEAM_CODE_TO_NAME.items()}
KBO_ENGLISH_TEAM_TO_CODE = {
    "KT": "KT",
    "KT WIZ": "KT",
    "LG": "LG",
    "LG TWINS": "LG",
    "SSG": "SK",
    "SSG LANDERS": "SK",
    "KIA": "HT",
    "KIA TIGERS": "HT",
    "DOOSAN": "OB",
    "DOOSAN BEARS": "OB",
    "NC": "NC",
    "NC DINOS": "NC",
    "HANWHA": "HH",
    "HANWHA EAGLES": "HH",
    "LOTTE": "LT",
    "LOTTE GIANTS": "LT",
    "SAMSUNG": "SS",
    "SAMSUNG LIONS": "SS",
    "KIWOOM": "WO",
    "KIWOOM HEROES": "WO",
}

KBO_ENGLISH_SCOREBOARD_URL = "https://eng.koreabaseball.com/Schedule/Scoreboard.aspx"


# 숫자 선수 ID를 실제 선수명으로 바꿀 때 캐시로 저장합니다.
# 같은 선수를 여러 번 요청하지 않게 하기 위해서입니다.
PLAYER_NAME_CACHE = {}


# ==========================================================
# 기본 유틸 함수
# ==========================================================

def clean_html_text(html_text):
    """
    HTML 태그가 섞인 문자열에서 실제 글자만 뽑습니다.

    예:
    '<b>17:00</b>' -> '17:00'
    '&nbsp;' -> ''
    """
    if html_text is None:
        return ""

    soup = BeautifulSoup(str(html_text), "html.parser")
    text = soup.get_text(" ", strip=True)

    # &nbsp;가 변환되면 보통 \xa0가 됩니다.
    text = text.replace("\xa0", " ").strip()

    if text == "&nbsp;":
        return ""

    return text


def cell_text(cell):
    """
    KBO JSON cell에서 Text 값을 안전하게 꺼냅니다.
    """
    if not isinstance(cell, dict):
        return ""

    return clean_html_text(cell.get("Text", ""))


def safe_int(value):
    """
    값을 안전하게 정수로 바꿉니다.

    예:
    '3' -> 3
    '' -> 0
    '&nbsp;' -> 0
    '-' -> 0
    """
    try:
        text = clean_html_text(value)

        if text == "" or text == "-":
            return 0

        return int(text)

    except Exception:
        return 0


def normalize_date_to_yyyymmdd(date_text):
    """
    여러 날짜 형태를 YYYYMMDD 형태로 통일합니다.

    예:
    2026-05-01 -> 20260501
    20260501 -> 20260501
    """
    if date_text is None:
        return ""

    only_digits = re.sub(r"[^0-9]", "", str(date_text))

    if len(only_digits) >= 8:
        return only_digits[:8]

    return only_digits


def convert_yyyymmdd_to_dash(date_raw):
    """
    YYYYMMDD 형식을 YYYY-MM-DD 형식으로 바꿉니다.

    예:
    20260501 -> 2026-05-01
    """
    date_raw = normalize_date_to_yyyymmdd(date_raw)

    if len(date_raw) != 8:
        return ""

    return f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"


def get_header_map(table):
    """
    KBO 테이블의 header를 읽어서
    컬럼 이름이 몇 번째 위치인지 dict로 만듭니다.

    예:
    {
        "선수명": 2,
        "안타": 16,
        "타점": 17,
        "득점": 18
    }
    """
    headers = table.get("headers", [])

    if not headers:
        return {}

    first_header_row = headers[0].get("row", [])
    header_map = {}

    for index, cell in enumerate(first_header_row):
        text = cell_text(cell)

        if text and text not in header_map:
            header_map[text] = index

    return header_map


def row_to_texts(row_obj):
    """
    KBO row 객체를 글자 리스트로 바꿉니다.
    """
    cells = row_obj.get("row", [])
    return [cell_text(cell) for cell in cells]


def get_batter_inning_indices(header_map):
    """
    타자 테이블에서 1회~12회 타석 결과 칸의 인덱스만 가져옵니다.

    KBO 타자 테이블 header는 보통 아래처럼 생겼습니다.

    선수명, 1, 2, 3, ... 12, 타수, 안타, 타점, 득점, 타율

    사구와 삼진은 별도 컬럼이 아니라
    1~12회 타석 결과 칸 안에 "사구", "삼진"처럼 들어갑니다.
    """
    inning_indices = []

    for key, value in header_map.items():
        if str(key).isdigit():
            inning_indices.append(value)

    inning_indices.sort()
    return inning_indices


def normalize_record_text(value):
    """
    KBO 기록 텍스트 비교용 정규화입니다.

    HTML 정리 후 공백과 일부 구분 기호를 제거해서
    "몸에 맞는 볼" / "몸에맞는볼"처럼 표기가 달라도
    같은 이벤트로 인식할 수 있게 합니다.
    """
    text = clean_html_text(value)
    text = re.sub(r"\s+", "", text)
    text = text.replace("ㆍ", "·")
    return text


def count_alias_occurrences(text, aliases):
    """
    하나의 문자열에서 여러 alias 중 가장 안정적인 이벤트 개수를 계산합니다.

    같은 이벤트를 나타내는 긴 alias와 짧은 alias가 같이 있을 수 있어
    단순 합산하지 않고 alias별 count의 최댓값을 사용합니다.
    예: "몸에맞는볼" 안에 "사구"가 같이 있지는 않지만, 방어적으로 처리합니다.
    """
    normalized_text = normalize_record_text(text)

    if not normalized_text:
        return 0

    counts = []

    for alias in aliases:
        normalized_alias = normalize_record_text(alias)
        if not normalized_alias:
            continue
        counts.append(normalized_text.count(normalized_alias))

    return max(counts) if counts else 0


def count_event_in_inning_cells(texts, inning_indices, event_aliases):
    """
    타자 row의 1회~12회 타석 결과 칸에서 특정 이벤트 개수를 셉니다.

    event_aliases는 문자열 하나 또는 문자열 리스트를 받을 수 있습니다.
    사구처럼 KBO 표기가 여러 방식으로 들어올 수 있는 이벤트를
    특정 문자열 하나에만 의존하지 않기 위해 alias 기반으로 계산합니다.
    """
    if isinstance(event_aliases, str):
        aliases = [event_aliases]
    else:
        aliases = list(event_aliases or [])

    count = 0

    for idx in inning_indices:
        if len(texts) <= idx:
            continue

        text = texts[idx].strip()

        if not text:
            continue

        count += count_alias_occurrences(text, aliases)

    return count


def merge_record_counts_by_max(*count_maps):
    """
    여러 출처의 선수별 이벤트 count를 합칩니다.

    타석 결과 칸과 상세 기록표에 같은 이벤트가 중복으로 나타날 수 있으므로
    합산이 아니라 선수별 최댓값을 사용합니다.
    """
    result = defaultdict(int)

    for count_map in count_maps:
        for name, count in (count_map or {}).items():
            if not name:
                continue
            result[name] = max(result[name], int(count or 0))

    return dict(result)


def normalize_special_record_label(label):
    """상세 기록표 label을 비교하기 쉽게 정규화합니다."""
    return normalize_record_text(label)


# ==========================================================
# 일정 리스트 가져오기
# ==========================================================

def make_kbo_ajax_headers(referer=None):
    """KBO 내부 AJAX API 호출에 필요한 헤더를 만듭니다."""
    headers = dict(REQUEST_HEADERS)
    headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": KBO_BASE,
    })
    headers["Referer"] = referer or SCHEDULE_URL
    return headers


def fetch_schedule_list(year, month):
    """
    KBO 월별 경기 일정 JSON을 가져옵니다.

    1차로 Schedule.aspx에 먼저 접속해 세션 쿠키를 받은 뒤 내부 API를 호출합니다.
    KBO가 JSON 대신 HTML을 반환하면 scheduler가 죽지 않도록 실패 정보를 담아 반환하고,
    get_games_for_date()에서 HTML/BoxScore fallback으로 한 번 더 복구합니다.
    """

    data = {
        "leId": "1",
        "srIdList": "0,9,6",
        "seasonId": str(year),
        "gameMonth": str(month).zfill(2),
        "teamId": "",
    }

    last_error = None
    last_status = None
    last_content_type = ""
    last_preview = ""
    last_text = ""

    session = requests.Session()

    try:
        # 일부 시점에는 세션 쿠키/Referer 없이 내부 API를 바로 때리면
        # JSON 대신 Schedule.aspx HTML이 내려옵니다.
        session.get(
            SCHEDULE_URL,
            headers=dict(REQUEST_HEADERS),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        # 쿠키 준비 실패만으로 바로 중단하지는 않습니다.
        print(f"KBO 일정 페이지 사전 접속 실패: {error}")

    for attempt in range(1, 4):
        try:
            response = session.post(
                SCHEDULE_LIST_API,
                headers=make_kbo_ajax_headers(SCHEDULE_URL),
                data=data,
                timeout=REQUEST_TIMEOUT,
            )
            last_status = response.status_code
            last_content_type = response.headers.get("Content-Type", "")
            last_text = response.text or ""
            last_preview = last_text[:300].replace("\n", " ").strip()

            response.raise_for_status()

            try:
                return response.json()
            except (ValueError, json.JSONDecodeError) as error:
                last_error = error
                print(
                    f"KBO 일정 API JSON 파싱 실패 "
                    f"({attempt}/3): status={last_status}, content_type={last_content_type}"
                )
                if last_preview:
                    print("응답 앞부분:", last_preview)

        except requests.RequestException as error:
            last_error = error
            print(f"KBO 일정 API 요청 실패 ({attempt}/3): {error}")

        if attempt < 3:
            time.sleep(1.0 * attempt)

    print("KBO 일정 API 응답을 JSON으로 읽지 못했습니다.")
    print("HTML/BoxScore fallback으로 경기 목록 복구를 시도합니다.")
    print(f"마지막 상태: status={last_status}, content_type={last_content_type}")
    if last_preview:
        print("마지막 응답 앞부분:", last_preview)
    if last_error:
        print("마지막 에러:", last_error)

    return {
        "rows": [],
        "_schedule_fetch_failed": True,
        "_status_code": last_status,
        "_content_type": last_content_type,
        "_preview": last_preview,
        "_html_text": last_text,
    }

def parse_review_link(html_text):
    """
    리뷰 버튼 HTML에서 gameDate, gameId, review_url을 추출합니다.
    """

    if html_text is None:
        return None

    raw_text = str(html_text)

    if "gameDate=" not in raw_text or "gameId=" not in raw_text:
        return None

    if "section=REVIEW" not in raw_text and "section=review" not in raw_text:
        return None

    game_date_match = re.search(r"gameDate=(\d{8})", raw_text)
    game_id_match = re.search(r"gameId=([A-Za-z0-9]+)", raw_text)

    if game_date_match is None or game_id_match is None:
        return None

    game_date_raw = game_date_match.group(1)
    game_id = game_id_match.group(1)

    href_match = re.search(r"href=['\"]([^'\"]+)['\"]", raw_text)

    if href_match:
        href = href_match.group(1)

        if href.startswith("http"):
            review_url = href
        else:
            review_url = KBO_BASE + href
    else:
        review_url = (
            f"{KBO_BASE}/Schedule/GameCenter/Main.aspx"
            f"?gameDate={game_date_raw}&gameId={game_id}&section=REVIEW"
        )

    return {
        "game_date_raw": game_date_raw,
        "game_date": convert_yyyymmdd_to_dash(game_date_raw),
        "game_id": game_id,
        "review_url": review_url,
    }


def parse_play_cell(html_text):
    """
    경기 칸에서 팀명과 점수를 추출합니다.

    예:
    NC 1 vs 5 LG
    """

    if html_text is None:
        return None

    soup = BeautifulSoup(str(html_text), "html.parser")

    span_texts = []

    for span in soup.find_all("span"):
        text = span.get_text(strip=True)

        if text != "":
            span_texts.append(text)

    if len(span_texts) < 5:
        return None

    if "vs" not in span_texts:
        return None

    try:
        vs_index = span_texts.index("vs")

        away_team = span_texts[0]
        away_score = int(span_texts[vs_index - 1])
        home_score = int(span_texts[vs_index + 1])
        home_team = span_texts[-1]

    except Exception:
        return None

    return {
        "away_team": away_team,
        "away_score": away_score,
        "home_score": home_score,
        "home_team": home_team,
    }


def find_review_info_from_cells(cells):
    """
    한 경기 row의 cell들 중에서 리뷰 링크를 찾습니다.
    """

    for cell in cells:
        review_info = parse_review_link(cell.get("Text", ""))

        if review_info is not None:
            return review_info

    return None


def find_play_info_from_cells(cells):
    """
    한 경기 row의 cell들 중에서 경기 정보 cell을 찾습니다.
    """

    for cell in cells:
        cell_class = str(cell.get("Class", ""))

        if "play" in cell_class:
            play_info = parse_play_cell(cell.get("Text", ""))

            if play_info is not None:
                return play_info

    for cell in cells:
        html_text = str(cell.get("Text", ""))

        if "vs" in html_text:
            play_info = parse_play_cell(html_text)

            if play_info is not None:
                return play_info

    return None


def find_stadium_from_cells(cells):
    """
    한 경기 row에서 구장 정보를 찾습니다.

    보통 뒤에서 두 번째 cell이 구장입니다.
    """

    if len(cells) < 2:
        return ""

    return clean_html_text(cells[-2].get("Text", ""))




def infer_game_from_game_id(game_id, target_date_raw, away_score=0, home_score=0, stadium=""):
    """game_id 코드로 원정/홈 팀을 추정해 game dict를 만듭니다."""
    game_id = str(game_id).strip()
    if len(game_id) < 13:
        return None

    game_date_raw = normalize_date_to_yyyymmdd(game_id[:8])
    if game_date_raw != normalize_date_to_yyyymmdd(target_date_raw):
        return None

    away_code = game_id[8:10]
    home_code = game_id[10:12]

    away_team = KBO_TEAM_CODE_TO_NAME.get(away_code)
    home_team = KBO_TEAM_CODE_TO_NAME.get(home_code)

    if away_team is None or home_team is None:
        return None

    return {
        "game_date": convert_yyyymmdd_to_dash(game_date_raw),
        "game_date_raw": game_date_raw,
        "game_id": game_id,
        "review_url": (
            f"{KBO_BASE}/Schedule/GameCenter/Main.aspx"
            f"?gameDate={game_date_raw}&gameId={game_id}&section=REVIEW"
        ),
        "away_team": away_team,
        "home_team": home_team,
        "away_score": int(away_score or 0),
        "home_score": int(home_score or 0),
        "stadium": stadium or "",
        "finished": True,
    }


def normalize_team_lookup_key(value):
    """팀명 비교용 문자열을 보수적으로 정규화합니다."""
    if value is None:
        return ""
    text = clean_html_text(value).upper()
    text = re.sub(r"[^A-Z0-9가-힣]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_team_code(team_name):
    """한글/영문 팀명을 KBO game_id 팀 코드로 변환합니다."""
    if team_name is None:
        return None

    raw = clean_html_text(team_name).strip()
    if raw in KBO_TEAM_NAME_TO_CODE:
        return KBO_TEAM_NAME_TO_CODE[raw]
    if raw in KBO_TEAM_CODE_TO_NAME:
        return raw

    key = normalize_team_lookup_key(raw)
    if key in KBO_ENGLISH_TEAM_TO_CODE:
        return KBO_ENGLISH_TEAM_TO_CODE[key]

    # 페이지에 "Samsung Lions", "Kiwoom Heroes"처럼 일부 이름이 섞여도 처리합니다.
    for alias, code in KBO_ENGLISH_TEAM_TO_CODE.items():
        if key == alias or key.startswith(alias + " ") or (" " + alias + " ") in (" " + key + " "):
            return code

    return None


def infer_game_from_team_names(target_date_raw, away_team_name, home_team_name, away_score=0, home_score=0, stadium="", source="team_name_fallback"):
    """팀명과 날짜로 game_id를 구성해 game dict를 만듭니다."""
    target_date_raw = normalize_date_to_yyyymmdd(target_date_raw)
    away_code = resolve_team_code(away_team_name)
    home_code = resolve_team_code(home_team_name)

    if away_code is None or home_code is None or away_code == home_code:
        return None

    game_id = f"{target_date_raw}{away_code}{home_code}0"
    game = infer_game_from_game_id(game_id, target_date_raw, away_score, home_score, stadium)
    if game is not None:
        game["source"] = source
    return game


def extract_stadium_from_text(text):
    """일정 HTML row 텍스트에서 구장명을 보수적으로 추출합니다."""
    text = clean_html_text(text)
    stadiums = [
        "잠실", "고척", "문학", "수원", "대전", "대구", "광주", "사직", "창원",
        "울산", "포항", "청주", "군산", "마산", "목동",
    ]
    for stadium in stadiums:
        if stadium in text:
            return stadium
    return ""


def parse_score_from_schedule_text(text, away_team, home_team):
    """일정 HTML row 텍스트에서 점수를 찾습니다. 실패하면 0, 0을 반환합니다."""
    text = clean_html_text(text)
    if not text:
        return 0, 0

    # 예: SSG vs 키움 (6 : 7)
    match = re.search(r"\((\d+)\s*[:：]\s*(\d+)\)", text)
    if match:
        return int(match.group(1)), int(match.group(2))

    # 예: SSG 6 vs 7 키움
    if away_team and home_team:
        pattern = (
            re.escape(away_team) + r"\s*(\d+)\s*(?:vs|VS|:|-)\s*(\d+)\s*" +
            re.escape(home_team)
        )
        match = re.search(pattern, text)
        if match:
            return int(match.group(1)), int(match.group(2))

    return 0, 0


def parse_schedule_html_games(html_text, target_date):
    """Schedule.aspx HTML 안에 gameId 링크가 있을 때 직접 경기 목록을 복구합니다."""
    if not html_text:
        return []

    target_date_raw = normalize_date_to_yyyymmdd(target_date)
    soup = BeautifulSoup(html_text, "html.parser")
    games = []
    seen = set()

    # 우선 tr 단위로 파싱해 구장/점수까지 최대한 살립니다.
    for tr in soup.find_all("tr"):
        row_html = str(tr)
        row_text = tr.get_text(" ", strip=True)
        if "gameId" not in row_html:
            continue

        game_ids = re.findall(r"gameId=([0-9]{8}[A-Z]{4}\d)", row_html)
        if not game_ids:
            continue

        date_matches = re.findall(r"gameDate=(\d{8})", row_html)

        for game_id in game_ids:
            if game_id in seen:
                continue

            game_date_raw = normalize_date_to_yyyymmdd(game_id[:8])
            if date_matches:
                game_date_raw = normalize_date_to_yyyymmdd(date_matches[0])

            if game_date_raw != target_date_raw:
                continue

            base_game = infer_game_from_game_id(game_id, target_date_raw)
            if base_game is None:
                continue

            away_score, home_score = parse_score_from_schedule_text(
                row_text,
                base_game["away_team"],
                base_game["home_team"],
            )
            base_game["away_score"] = away_score
            base_game["home_score"] = home_score
            base_game["stadium"] = extract_stadium_from_text(row_text)
            base_game["source"] = "schedule_html"

            games.append(base_game)
            seen.add(game_id)

    # tr 구조 밖에 gameId가 있는 경우도 대비합니다.
    if not games:
        for game_id in re.findall(r"([0-9]{8}[A-Z]{4}\d)", html_text):
            if game_id in seen:
                continue
            game = infer_game_from_game_id(game_id, target_date_raw)
            if game is None:
                continue
            game["source"] = "schedule_html_regex"
            games.append(game)
            seen.add(game_id)

    return games


def fetch_schedule_page_html(year, month):
    """KBO 일정 페이지 HTML을 가져옵니다."""
    headers = dict(REQUEST_HEADERS)
    headers["Referer"] = SCHEDULE_URL

    try:
        response = requests.get(
            SCHEDULE_URL,
            headers=headers,
            params={
                "year": str(year),
                "month": str(month).zfill(2),
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.text or ""
    except requests.RequestException as error:
        print(f"KBO 일정 HTML fallback 요청 실패: {error}")
        return ""


def fetch_english_scoreboard_html(target_date):
    """KBO 영문 Scoreboard 페이지 HTML을 가져옵니다. 일정 API가 막힐 때 공식 fallback으로 사용합니다."""
    target_date_raw = normalize_date_to_yyyymmdd(target_date)
    if len(target_date_raw) != 8:
        return ""

    search_date = convert_yyyymmdd_to_dash(target_date_raw)
    headers = dict(REQUEST_HEADERS)
    headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": f"{KBO_BASE}/Schedule/Scoreboard.aspx",
    })

    try:
        response = requests.get(
            KBO_ENGLISH_SCOREBOARD_URL,
            headers=headers,
            params={"searchDate": search_date},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.text or ""
    except requests.RequestException as error:
        print(f"KBO 영문 스코어보드 fallback 요청 실패: {error}")
        return ""


def parse_english_scoreboard_games(html_text, target_date):
    """KBO 영문 Scoreboard HTML에서 완료 경기 목록을 복구합니다."""
    if not html_text:
        return []

    target_date_raw = normalize_date_to_yyyymmdd(target_date)
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    team_pattern = r"KT|LG|SSG|KIA|DOOSAN|NC|HANWHA|LOTTE|SAMSUNG|KIWOOM"
    score_pattern = re.compile(
        rf"\b(?P<away>{team_pattern})\s+(?P<away_score>\d{{1,2}})\s+(?:FINAL|Final|final)\s+(?P<home_score>\d{{1,2}})\s+(?P<home>{team_pattern})\b"
    )

    games = []
    seen = set()

    for match in score_pattern.finditer(text):
        game = infer_game_from_team_names(
            target_date_raw,
            match.group("away"),
            match.group("home"),
            int(match.group("away_score")),
            int(match.group("home_score")),
            source="english_scoreboard",
        )
        if game is None:
            continue
        if game["game_id"] in seen:
            continue
        games.append(game)
        seen.add(game["game_id"])

    # 텍스트 구조가 바뀌어도 최소한 팀명 순서만 복구할 수 있게 보조 정규식도 둡니다.
    if not games:
        compact = re.sub(r"[^A-Z0-9]+", " ", text.upper())
        for match in score_pattern.finditer(compact):
            game = infer_game_from_team_names(
                target_date_raw,
                match.group("away"),
                match.group("home"),
                int(match.group("away_score")),
                int(match.group("home_score")),
                source="english_scoreboard_compact",
            )
            if game is None or game["game_id"] in seen:
                continue
            games.append(game)
            seen.add(game["game_id"])

    return games


def safe_fetch_boxscore_for_probe(game_id, season_id):
    """BoxScore probe용 안전 호출. 실패해도 예외를 밖으로 던지지 않습니다."""
    game_id = str(game_id).strip()
    data_template = {
        "leId": "1",
        "seasonId": str(season_id),
        "gameId": game_id,
    }
    referer = f"{KBO_BASE}/Schedule/GameCenter/Main.aspx?gameDate={game_id[:8]}&gameId={game_id}&section=REVIEW"

    session = requests.Session()
    try:
        # GameCenter 페이지를 먼저 열어 쿠키/세션을 받은 뒤 BoxScore API를 호출합니다.
        session.get(referer, headers=dict(REQUEST_HEADERS), timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        pass

    for sr_id in ["0", "9", "6"]:
        data = dict(data_template)
        data["srId"] = sr_id
        try:
            response = session.post(
                BOX_SCORE_API,
                headers=make_kbo_ajax_headers(referer),
                data=data,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            continue

    return None


def boxscore_has_game_records(boxscore):
    """BoxScore JSON이 실제 경기 기록을 담고 있는지 보수적으로 확인합니다."""
    if not isinstance(boxscore, dict):
        return False

    tables = boxscore.get("tables", [])
    if not isinstance(tables, list) or len(tables) < 5:
        return False

    # 타자/투수 테이블 중 하나라도 실제 row가 있으면 유효한 경기로 봅니다.
    for table_index in [1, 2, 3, 4]:
        table = tables[table_index] or {}
        rows = table.get("rows", [])
        if not rows:
            continue
        for row_obj in rows:
            texts = row_to_texts(row_obj)
            joined = " ".join(texts).strip()
            if joined and joined not in {"합계", "팀 합계"}:
                return True

    return False


def discover_games_by_boxscore_probe(target_date, candidate_games=None):
    """
    일정 API/HTML/영문 스코어보드 fallback이 모두 실패했을 때 game_id 규칙으로 BoxScore를 탐색합니다.

    candidate_games가 있으면 해당 match-up을 먼저 검증하고, 없으면 전체 팀 조합을 탐색합니다.
    """
    target_date_raw = normalize_date_to_yyyymmdd(target_date)
    if len(target_date_raw) != 8:
        return []

    print("KBO 일정 fallback: BoxScore game_id 탐색을 시작합니다.")

    candidate_ids = []
    seen_candidates = set()

    if candidate_games:
        for game in candidate_games:
            base_id = str(game.get("game_id", "")).strip()
            if len(base_id) >= 13:
                prefixes = [base_id[:12]]
            else:
                away_code = resolve_team_code(game.get("away_team"))
                home_code = resolve_team_code(game.get("home_team"))
                prefixes = [f"{target_date_raw}{away_code}{home_code}"] if away_code and home_code else []
            for prefix in prefixes:
                for suffix in ["0", "1", "2"]:
                    gid = prefix + suffix
                    if gid not in seen_candidates:
                        candidate_ids.append(gid)
                        seen_candidates.add(gid)

    if not candidate_ids:
        for away_code in KBO_TEAM_CODES:
            for home_code in KBO_TEAM_CODES:
                if away_code == home_code:
                    continue
                for suffix in ["0", "1", "2"]:
                    gid = f"{target_date_raw}{away_code}{home_code}{suffix}"
                    candidate_ids.append(gid)

    games = []
    seen_games = set()

    for idx, game_id in enumerate(candidate_ids, start=1):
        boxscore = safe_fetch_boxscore_for_probe(game_id, target_date_raw[:4])

        if not boxscore_has_game_records(boxscore):
            continue

        game = infer_game_from_game_id(game_id, target_date_raw)
        if game is None or game["game_id"] in seen_games:
            continue
        game["source"] = "boxscore_probe"
        games.append(game)
        seen_games.add(game["game_id"])
        print("BoxScore fallback 경기 발견:", game_id, game["away_team"], "vs", game["home_team"])

        if len(games) >= 5:
            print("BoxScore fallback 경기 5개 발견. 탐색을 종료합니다.")
            return games

        time.sleep(0.05)

    print(f"BoxScore fallback 후보 검사 수: {len(candidate_ids)}")
    print(f"BoxScore fallback 발견 경기 수: {len(games)}")
    return games

def parse_schedule_rows(schedule_json, target_date):
    """
    KBO 일정 JSON에서 특정 날짜의 경기만 추출합니다.
    """

    target_date_raw = normalize_date_to_yyyymmdd(target_date)
    target_date_dash = convert_yyyymmdd_to_dash(target_date_raw)

    rows = schedule_json.get("rows", [])
    games = []

    for item in rows:
        cells = item.get("row", [])

        if not cells:
            continue

        review_info = find_review_info_from_cells(cells)

        if review_info is None:
            continue

        review_game_date_raw = normalize_date_to_yyyymmdd(
            review_info["game_date_raw"]
        )

        if review_game_date_raw != target_date_raw:
            continue

        play_info = find_play_info_from_cells(cells)

        if play_info is None:
            continue

        stadium = find_stadium_from_cells(cells)

        games.append({
            "game_date": target_date_dash,
            "game_date_raw": review_info["game_date_raw"],
            "game_id": review_info["game_id"],
            "review_url": review_info["review_url"],
            "away_team": play_info["away_team"],
            "home_team": play_info["home_team"],
            "away_score": play_info["away_score"],
            "home_score": play_info["home_score"],
            "stadium": stadium,
            "finished": True,
        })

    return games


def get_games_for_date(target_date):
    """
    특정 날짜의 KBO 경기 목록을 가져옵니다.

    target_date:
        "2026-05-01" 또는 "20260501"
    """

    target_date_raw = normalize_date_to_yyyymmdd(target_date)

    if len(target_date_raw) != 8:
        raise ValueError("날짜 형식이 잘못되었습니다. 예: 2026-05-01 또는 20260501")

    year = target_date_raw[0:4]
    month = target_date_raw[4:6]

    schedule_json = fetch_schedule_list(year, month)
    games = parse_schedule_rows(schedule_json, target_date_raw)

    if games:
        return games

    if isinstance(schedule_json, dict) and schedule_json.get("_schedule_fetch_failed"):
        print("경기 일정 수집 실패: KBO 일정 API가 JSON이 아닌 응답을 반환했습니다.")
        print("HTML/BoxScore fallback으로 경기 목록 복구를 시도합니다.")

        html_text = schedule_json.get("_html_text") or ""
        html_games = parse_schedule_html_games(html_text, target_date_raw)

        if not html_games:
            page_html = fetch_schedule_page_html(year, month)
            html_games = parse_schedule_html_games(page_html, target_date_raw)

        if html_games:
            print(f"KBO 일정 HTML fallback 경기 수: {len(html_games)}")
            return html_games

        print("KBO 영문 스코어보드 fallback을 시도합니다.")
        english_html = fetch_english_scoreboard_html(target_date_raw)
        english_games = parse_english_scoreboard_games(english_html, target_date_raw)
        if english_games:
            print(f"KBO 영문 스코어보드 fallback 경기 수: {len(english_games)}")
            return english_games

        probe_games = discover_games_by_boxscore_probe(target_date_raw, candidate_games=html_games or english_games)
        if probe_games:
            print(f"KBO BoxScore fallback 경기 수: {len(probe_games)}")
            return probe_games

        print("모든 일정 fallback이 실패했습니다.")
        print("이 날짜의 경기/팀 점수/가격 업데이트는 후속 단계에서 안전하게 생략됩니다.")

    return games


# ==========================================================
# BoxScore 가져오기
# ==========================================================

def fetch_boxscore(game_id, le_id="1", sr_id="0", season_id=None):
    """
    KBO GetBoxScore API를 호출합니다.

    이 API에서 실제 타자/투수 기록이 나옵니다.
    """

    if season_id is None:
        season_id = str(game_id)[0:4]

    data = {
        "leId": str(le_id),
        "srId": str(sr_id),
        "seasonId": str(season_id),
        "gameId": str(game_id),
    }

    response = requests.post(
        BOX_SCORE_API,
        headers=make_kbo_ajax_headers(
            f"{KBO_BASE}/Schedule/GameCenter/Main.aspx?gameDate={str(game_id)[:8]}&gameId={game_id}"
        ),
        data=data,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError) as error:
        preview = (response.text or "")[:300].replace("\n", " ").strip()
        raise ValueError(
            f"KBO BoxScore API JSON 파싱 실패: game_id={game_id}, "
            f"status={response.status_code}, "
            f"content_type={response.headers.get('Content-Type', '')}, "
            f"preview={preview}"
        ) from error


# ==========================================================
# 선수 ID를 선수명으로 바꾸기
# ==========================================================

def resolve_player_id_to_name(player_id, position_type="pitcher"):
    """
    선수명이 숫자 ID로 나온 경우 실제 선수명으로 바꿉니다.

    예:
    55130 -> 톨허스트
    75867 -> 김진성

    position_type:
        pitcher 또는 hitter
    """

    player_id = str(player_id).strip()

    if not player_id.isdigit():
        return player_id

    cache_key = f"{position_type}:{player_id}"

    if cache_key in PLAYER_NAME_CACHE:
        return PLAYER_NAME_CACHE[cache_key]

    if position_type == "pitcher":
        url = f"{KBO_BASE}/Record/Player/PitcherDetail/Basic.aspx?playerId={player_id}"
    else:
        url = f"{KBO_BASE}/Record/Player/HitterDetail/Basic.aspx?playerId={player_id}"

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # 가장 정확한 위치입니다.
        name_span = soup.find(
            "span",
            id=re.compile(r"playerProfile_lblName$")
        )

        if name_span is not None:
            name = name_span.get_text(strip=True)

            if name:
                PLAYER_NAME_CACHE[cache_key] = name
                return name

        # 혹시 span을 못 찾으면 선수 사진 alt에서 한 번 더 찾습니다.
        profile_img = soup.find(
            "img",
            id=re.compile(r"playerProfile_img")
        )

        if profile_img is not None:
            alt_name = profile_img.get("alt", "").strip()

            if alt_name:
                PLAYER_NAME_CACHE[cache_key] = alt_name
                return alt_name

    except Exception as e:
        print("선수 ID 이름 변환 실패:", player_id, e)

    # 실패하면 일단 숫자를 그대로 반환합니다.
    PLAYER_NAME_CACHE[cache_key] = player_id
    return player_id


# ==========================================================
# 경기 상세 기록표 파싱
# ==========================================================

def count_event_mentions_in_parentheses(parenthetical_text):
    """
    상세 기록 괄호 안에서 같은 선수의 이벤트가 몇 번인지 계산합니다.

    KBO 상세기록은 같은 선수가 한 항목을 여러 번 기록하면 아래처럼
    회차를 압축해서 적는 경우가 있습니다.

    예:
    "7회" -> 1
    "7회 8회" -> 2
    "1회 3회" -> 2
    "1 3회" -> 2
    "1,3회" -> 2
    "2회2점 7회1점 황동하" -> 2

    기존 구현은 "1 3회"를 "3회" 한 번으로만 세어서
    도루/2루타/병살타 같은 반복 기록이 1개만 저장될 수 있었습니다.
    """
    text = clean_html_text(parenthetical_text)

    if not text or text == "-":
        return 1

    count = 0

    # "1 3회", "1,3회", "1·3회"처럼 마지막 숫자에만 '회'가 붙는
    # 압축 표기도 한 묶음 안의 숫자 개수만큼 이벤트로 봅니다.
    for match in re.finditer(r"((?:\d+\s*(?:[,·ㆍ/]|\s)*)+)회", text):
        number_group = match.group(1) or ""
        numbers = re.findall(r"\d+", number_group)
        count += max(1, len(numbers))

    if count > 0:
        return count

    return 1


def extract_special_record_counts(detail_text, record_type=None):
    """
    경기 상세 기록표 한 줄에서 선수별 개수를 추출합니다.

    홈런 예:
    양의지3호4호(2회2점 7회1점 황동하)
    -> {"양의지": 2}

    2루타/3루타/도루/병살타 예:
    김정민(7회 8회)
    -> {"김정민": 2}

    결승타는 회차가 여러 개처럼 보일 수 있어도 1개 이벤트로 처리합니다.
    """
    text = clean_html_text(detail_text)

    if not text or text == "-":
        return {}

    result = defaultdict(int)

    # 이름 + 선택적 홈런 호수들 + 선택적 일반 숫자 + 괄호 내용
    #
    # 비홈런 기록에서도 KBO가 "정수빈2(1 3회)", "박지훈2(1 5회)"처럼
    # 이름 뒤에 숫자를 붙이는 경우가 있습니다. 기존 정규식은 이 숫자 때문에
    # 전체 괄호 패턴 매칭에 실패했고, fallback에서 선수명 1개만 세었습니다.
    # 일반 숫자는 선수명에서 분리하되, 실제 개수는 괄호 안 회차 계산을 우선합니다.
    pattern = r"([가-힣A-Za-z.\-·]+)((?:\d+호)*)(\d*)\s*\(([^)]*)\)"

    matched_spans = []

    for match in re.finditer(pattern, text):
        matched_spans.append(match.span())
        name = match.group(1).strip()
        homer_numbers = match.group(2) or ""
        plain_number_suffix = match.group(3) or ""
        parenthetical = match.group(4) or ""

        if not name or name in ["없음"]:
            continue

        if record_type == "home_runs":
            homer_count = len(re.findall(r"\d+호", homer_numbers))
            count = homer_count if homer_count > 0 else 1
        elif record_type == "game_winning_hit":
            count = 1
        else:
            count = count_event_mentions_in_parentheses(parenthetical)

            # 괄호 안에 회차 정보가 전혀 없고, 이름 뒤에 2~6 정도의 작은
            # 일반 숫자가 붙은 예외 형태가 들어오면 보조 신호로만 사용합니다.
            # 정상 KBO 표기에서는 "1 3회" 같은 괄호 정보가 더 신뢰도 높습니다.
            if count <= 1 and plain_number_suffix:
                try:
                    suffix_count = int(plain_number_suffix)
                except ValueError:
                    suffix_count = 0
                if 2 <= suffix_count <= 6 and "회" not in parenthetical:
                    count = suffix_count

        result[name] += count

    # 일부 상세 기록은 "정수빈"처럼 괄호 없이 이름만 들어오는 경우가 있어
    # 괄호 패턴으로 잡히지 않은 텍스트 조각에서 선수명 후보를 보강합니다.
    if matched_spans:
        remaining_parts = []
        cursor = 0
        for start, end in matched_spans:
            remaining_parts.append(text[cursor:start])
            cursor = end
        remaining_parts.append(text[cursor:])
        remaining_text = " ".join(remaining_parts)
    else:
        remaining_text = text

    remaining_text = re.sub(r"\([^)]*\)", " ", remaining_text)
    remaining_text = re.sub(r"\d+호", " ", remaining_text)
    remaining_text = re.sub(r"\d+회", " ", remaining_text)
    remaining_text = re.sub(r"\d+점", " ", remaining_text)
    remaining_text = re.sub(r"[,:;/·ㆍ]+", " ", remaining_text)

    for token in re.findall(r"[가-힣A-Za-z.\-·]{2,}", remaining_text):
        name = token.strip()
        if not name or name in {"없음", "무", "해당없음"}:
            continue
        # 상세 기록 괄호 안 투수명 등이 남는 것을 완전히 배제할 수는 없지만,
        # 괄호 내용은 위에서 제거했으므로 보강 후보로 안전하게 1개만 반영합니다.
        result[name] += 1

    return dict(result)


def extract_names_from_detail(detail_text):
    """
    경기 상세 기록표에서 선수 이름을 뽑습니다.

    기존 호환용 함수입니다. 실제 개수 계산은
    extract_special_record_counts()를 사용합니다.
    """
    counts = extract_special_record_counts(detail_text)
    names = []

    for name, count in counts.items():
        names.extend([name] * count)

    return names


def make_name_count(names):
    """
    이름 리스트를 선수별 개수 dict로 바꿉니다.

    예:
    ["오스틴", "오스틴", "송찬의"]
    -> {"오스틴": 2, "송찬의": 1}
    """

    result = defaultdict(int)

    for name in names:
        result[name] += 1

    return dict(result)


def parse_game_special_records(detail_table):
    """
    tables[0] 경기기록 상세기록표를 파싱합니다.

    필요한 항목:
    결승타
    홈런
    3루타
    2루타
    병살타
    도루

    주의:
    사구와 삼진은 tables[0]이 아니라
    타자 row의 1~12회 타석 결과 칸에서 계산합니다.
    """

    special = {
        "game_winning_hit": {},
        "home_runs": {},
        "triples": {},
        "doubles": {},
        "double_play": {},
        "stolen_bases": {},
        "hit_by_pitch": {},
        "walks": {},
        "strikeouts": {},
    }

    rows = detail_table.get("rows", [])

    for row_obj in rows:
        texts = row_to_texts(row_obj)

        if len(texts) < 2:
            continue

        label = texts[0]
        detail = texts[1]
        normalized_label = normalize_special_record_label(label)

        if normalized_label == "결승타":
            special["game_winning_hit"] = extract_special_record_counts(
                detail,
                record_type="game_winning_hit",
            )
        elif normalized_label == "홈런":
            special["home_runs"] = extract_special_record_counts(
                detail,
                record_type="home_runs",
            )
        elif normalized_label == "3루타":
            special["triples"] = extract_special_record_counts(
                detail,
                record_type="triples",
            )
        elif normalized_label == "2루타":
            special["doubles"] = extract_special_record_counts(
                detail,
                record_type="doubles",
            )
        elif normalized_label == "병살타":
            special["double_play"] = extract_special_record_counts(
                detail,
                record_type="double_play",
            )
        elif normalized_label == "도루":
            special["stolen_bases"] = extract_special_record_counts(
                detail,
                record_type="stolen_bases",
            )
        elif normalized_label in {"사구", "몸에맞는볼", "몸맞는볼", "몸에맞는공"}:
            special["hit_by_pitch"] = extract_special_record_counts(
                detail,
                record_type="hit_by_pitch",
            )
        elif normalized_label in {"4구", "볼넷", "고의4구", "고4", "베이스온볼스"}:
            special["walks"] = extract_special_record_counts(
                detail,
                record_type="walks",
            )
        elif normalized_label in {"삼진", "탈삼진"}:
            special["strikeouts"] = extract_special_record_counts(
                detail,
                record_type="strikeouts",
            )

    return special



DETAIL_BATTER_POSITIONS = {
    "포수", "1루수", "2루수", "3루수", "유격수", "좌익수", "중견수", "우익수"
}
DH_BATTER_POSITIONS = {"지명타자"}
NON_POSITION_BATTER_ROLES = {"지명타자", "DH", "대타", "대주자"}


def first_header_index(header_map, aliases):
    for alias in aliases:
        if alias in header_map:
            return header_map[alias]
    return None


def normalize_batter_defense_position(value):
    text = clean_html_text(value).strip()
    text = text.replace(" ", "")

    aliases = {
        "포": "포수",
        "포수": "포수",
        "1루": "1루수",
        "1루수": "1루수",
        "일루수": "1루수",
        "2루": "2루수",
        "2루수": "2루수",
        "이루수": "2루수",
        "3루": "3루수",
        "3루수": "3루수",
        "삼루수": "3루수",
        "유격": "유격수",
        "유격수": "유격수",
        "좌익": "좌익수",
        "좌익수": "좌익수",
        "중견": "중견수",
        "중견수": "중견수",
        "우익": "우익수",
        "우익수": "우익수",
        "지명타자": "지명타자",
        "지명": "지명타자",
        "DH": "지명타자",
        "D/H": "지명타자",
        "대타": "대타",
        "대주자": "대주자",
    }
    return aliases.get(text, text)


def safe_batting_order(value):
    text = clean_html_text(value).strip()
    match = re.search(r"\d+", text)
    return safe_int(match.group(0)) if match else None

# ==========================================================
# 타자 기록 파싱
# ==========================================================

def parse_batter_table(table, team, special_records):
    """
    타자 기록 테이블을 파싱합니다.

    직접 가져오는 항목:
    선수명
    안타
    타점
    득점

    tables[0] 경기 상세 기록표에서 가져오는 항목:
    결승타
    2루타
    3루타
    홈런
    병살타
    도루

    타자 row의 1~12회 타석 결과 칸에서 세는 항목:
    사구
    삼진

    중요:
    2루타, 3루타, 홈런은 안타에도 포함됩니다.
    하지만 점수 계산에서는 중복 점수를 주지 않기 위해
    scoring.py에서 단타 = 안타 - 2루타 - 3루타 - 홈런 방식으로 처리합니다.
    """

    header_map = get_header_map(table)

    player_idx = header_map.get("선수명")
    hits_idx = header_map.get("안타")
    rbi_idx = header_map.get("타점")
    runs_idx = header_map.get("득점")

    # KBO boxscore 응답에 선발 라인업 수비 위치/타순 컬럼이 포함되는 경우만 사용합니다.
    # 컬럼이 없으면 절대 추측하지 않고 NULL로 둡니다.
    batting_order_idx = first_header_index(header_map, ["타순", "순번", "순", "타격순서"])
    defense_position_idx = first_header_index(header_map, ["포지션", "수비", "위치", "수비위치"])

    # 1회~12회 타석 결과 칸 인덱스입니다.
    # 사구/삼진은 이 칸들 안에 들어 있습니다.
    inning_indices = get_batter_inning_indices(header_map)

    if player_idx is None:
        print("타자 테이블에서 선수명 컬럼을 찾지 못했습니다.")
        return []

    batter_records = []
    seen_starting_orders = set()

    for row_obj in table.get("rows", []):
        texts = row_to_texts(row_obj)

        if len(texts) <= player_idx:
            continue

        player_name = texts[player_idx].strip()

        if not player_name:
            continue

        player_name = resolve_player_id_to_name(player_name, "hitter")

        hits = safe_int(texts[hits_idx]) if hits_idx is not None and len(texts) > hits_idx else 0
        rbi = safe_int(texts[rbi_idx]) if rbi_idx is not None and len(texts) > rbi_idx else 0
        runs = safe_int(texts[runs_idx]) if runs_idx is not None and len(texts) > runs_idx else 0

        doubles = special_records["doubles"].get(player_name, 0)
        triples = special_records["triples"].get(player_name, 0)
        home_runs = special_records["home_runs"].get(player_name, 0)
        game_winning_hit = special_records["game_winning_hit"].get(player_name, 0)
        double_play = special_records["double_play"].get(player_name, 0)
        stolen_bases = special_records["stolen_bases"].get(player_name, 0)

        inning_hit_by_pitch = count_event_in_inning_cells(
            texts,
            inning_indices,
            ["사구", "몸에 맞는 볼", "몸에맞는볼", "몸맞는볼", "몸에 맞는 공"]
        )
        detail_hit_by_pitch = special_records.get("hit_by_pitch", {}).get(player_name, 0)
        hit_by_pitch = max(inning_hit_by_pitch, detail_hit_by_pitch)

        inning_walks = count_event_in_inning_cells(
            texts,
            inning_indices,
            ["4구", "볼넷", "고4", "고의4구", "고의 4구", "baseonballs"]
        )
        detail_walks = special_records.get("walks", {}).get(player_name, 0)
        walks = max(inning_walks, detail_walks)

        inning_strikeouts = count_event_in_inning_cells(
            texts,
            inning_indices,
            ["삼진", "헛스윙삼진", "루킹삼진"]
        )
        detail_strikeouts = special_records.get("strikeouts", {}).get(player_name, 0)
        strikeouts = max(inning_strikeouts, detail_strikeouts)

        batting_order = None
        if batting_order_idx is not None and len(texts) > batting_order_idx:
            batting_order = safe_batting_order(texts[batting_order_idx])

        defense_position = None
        if defense_position_idx is not None and len(texts) > defense_position_idx:
            defense_position = normalize_batter_defense_position(texts[defense_position_idx])

        # 교체 기록은 제외합니다. 타순이 확인되고, 같은 타순의 첫 번째 선발 row만
        # 선발 포지션 근거로 저장합니다. 실제 수비 포지션은 상세 포지션 업데이트 근거가 되고,
        # 지명타자는 수비 포지션이 전혀 없는 DH-only 선수 판정 근거로만 사용합니다.
        # 대타/대주자/내야수/외야수 같은 값은 근거로 쓰지 않습니다.
        is_starting_batter = 0
        starting_detail_position = None
        lineup_position_source = None
        if (
            batting_order is not None
            and batting_order not in seen_starting_orders
            and (defense_position in DETAIL_BATTER_POSITIONS or defense_position in DH_BATTER_POSITIONS)
        ):
            is_starting_batter = 1
            starting_detail_position = defense_position
            lineup_position_source = "boxscore_starting_lineup"
            seen_starting_orders.add(batting_order)

        batter_records.append({
            "player_name": player_name,
            "team": team,
            "hits": hits,
            "doubles": doubles,
            "triples": triples,
            "home_runs": home_runs,
            "rbi": rbi,
            "runs": runs,
            "game_winning_hit": game_winning_hit,
            "double_play": double_play,
            "hit_by_pitch": hit_by_pitch,
            "walks": walks,
            "stolen_bases": stolen_bases,
            "strikeouts": strikeouts,
            "batting_order": batting_order,
            "starting_detail_position": starting_detail_position,
            "is_starting_batter": is_starting_batter,
            "lineup_position_source": lineup_position_source,
        })

    return batter_records


# ==========================================================
# 투수 기록 파싱
# ==========================================================

def parse_pitcher_table(table, team):
    """
    투수 기록 테이블을 파싱합니다.

    필요한 항목:
    선수명
    결과
    이닝
    삼진
    실점

    새 점수 규칙에서 추가된 항목:
    세이브
    투구수
    피안타

    선발/불펜 분류용 항목:
    is_starting_pitcher
        - 해당 팀 투수 기록표에서 첫 번째 실제 투수이면 1
        - 나머지 투수이면 0

    pitching_order
        - 해당 팀 투수 기록표에서 몇 번째 투수인지 저장합니다.
        - 선발투수는 1입니다.

    중요:
    선발 여부는 승/패/홀드/세이브 결과로 판단하지 않습니다.
    KBO 투수 기록표에 등장하는 순서로 판단합니다.
    """

    header_map = get_header_map(table)

    player_idx = header_map.get("선수명")
    result_idx = header_map.get("결과")
    innings_idx = header_map.get("이닝")
    strikeouts_idx = header_map.get("삼진")
    runs_allowed_idx = header_map.get("실점")

    # 새 점수 규칙용 컬럼입니다.
    pitch_count_idx = header_map.get("투구수")
    hits_allowed_idx = header_map.get("피안타")

    if player_idx is None:
        print("투수 테이블에서 선수명 컬럼을 찾지 못했습니다.")
        return []

    pitcher_records = []

    # 이 값은 "실제 투수 row"를 만났을 때만 1씩 증가합니다.
    # 빈 row나 합계 row가 있더라도 선발투수 순서가 밀리지 않게 하기 위해서입니다.
    pitching_order = 0

    for row_obj in table.get("rows", []):
        texts = row_to_texts(row_obj)

        if len(texts) <= player_idx:
            continue

        player_name = texts[player_idx].strip()

        if not player_name:
            continue

        # 혹시 KBO 테이블에 합계 row가 들어오는 경우를 방지합니다.
        # 기존에는 이런 row가 없었을 가능성이 높지만,
        # 선발투수 판정에서는 첫 번째 row가 중요하므로 안전하게 제외합니다.
        if player_name in ["합계", "총계", "TOTAL", "Total"]:
            continue

        # 홈 투수 쪽에서 55130처럼 숫자로 나오는 경우가 있어서 이름으로 변환합니다.
        player_name = resolve_player_id_to_name(player_name, "pitcher")

        # 이름 변환 후에도 이상한 값이면 제외합니다.
        if not player_name or player_name in ["합계", "총계", "TOTAL", "Total"]:
            continue

        # 여기까지 통과한 row를 "실제 투수 row"로 봅니다.
        pitching_order += 1

        result_text = ""
        if result_idx is not None and len(texts) > result_idx:
            result_text = texts[result_idx].strip()

        wins = 1 if result_text == "승" else 0
        losses = 1 if result_text == "패" else 0
        holds = 1 if "홀드" in result_text else 0

        # 세이브는 승/패/홀드처럼 "결과" 칸을 기준으로 판단합니다.
        # 투수 header에는 "세" 컬럼도 있지만, 이 컬럼은 누적 기록일 수 있으므로
        # 경기별 세이브 여부는 결과 칸의 "세" 또는 "세이브"를 우선 사용합니다.
        saves = 1 if result_text == "세" or "세이브" in result_text else 0

        innings_raw = ""
        if innings_idx is not None and len(texts) > innings_idx:
            innings_raw = texts[innings_idx]

        strikeouts = 0
        if strikeouts_idx is not None and len(texts) > strikeouts_idx:
            strikeouts = safe_int(texts[strikeouts_idx])

        runs_allowed = 0
        if runs_allowed_idx is not None and len(texts) > runs_allowed_idx:
            runs_allowed = safe_int(texts[runs_allowed_idx])

        pitch_count = 0
        if pitch_count_idx is not None and len(texts) > pitch_count_idx:
            pitch_count = safe_int(texts[pitch_count_idx])

        hits_allowed = 0
        if hits_allowed_idx is not None and len(texts) > hits_allowed_idx:
            hits_allowed = safe_int(texts[hits_allowed_idx])

        # 각 팀 투수 기록표에서 첫 번째 실제 투수를 선발투수로 판단합니다.
        is_starting_pitcher = 1 if pitching_order == 1 else 0

        pitcher_records.append({
            "player_name": player_name,
            "team": team,
            "wins": wins,
            "losses": losses,
            "holds": holds,
            "saves": saves,
            "innings_pitched_raw": innings_raw,
            "strikeouts": strikeouts,
            "runs_allowed": runs_allowed,
            "pitch_count": pitch_count,
            "hits_allowed": hits_allowed,
            "is_starting_pitcher": is_starting_pitcher,
            "pitching_order": pitching_order,
        })

    return pitcher_records


# ==========================================================
# 한 경기 전체 기록 가져오기
# ==========================================================

def get_game_boxscore_stats(game):
    """
    한 경기의 타자/투수 기록을 모두 가져옵니다.

    game:
        get_games_for_date에서 나온 경기 dict 하나
    """

    game_id = game["game_id"]
    season_id = game["game_date_raw"][0:4]

    boxscore = fetch_boxscore(
        game_id=game_id,
        le_id="1",
        sr_id="0",
        season_id=season_id,
    )

    tables = boxscore.get("tables", [])

    if len(tables) < 5:
        raise ValueError(f"BoxScore tables 개수가 부족합니다. game_id={game_id}")

    detail_table = tables[0]
    away_batter_table = tables[1]
    home_batter_table = tables[2]
    away_pitcher_table = tables[3]
    home_pitcher_table = tables[4]

    special_records = parse_game_special_records(detail_table)

    batters = []
    pitchers = []

    batters.extend(
        parse_batter_table(
            away_batter_table,
            game["away_team"],
            special_records,
        )
    )

    batters.extend(
        parse_batter_table(
            home_batter_table,
            game["home_team"],
            special_records,
        )
    )

    pitchers.extend(
        parse_pitcher_table(
            away_pitcher_table,
            game["away_team"],
        )
    )

    pitchers.extend(
        parse_pitcher_table(
            home_pitcher_table,
            game["home_team"],
        )
    )

    return {
        "game": game,
        "special_records": special_records,
        "batters": batters,
        "pitchers": pitchers,
    }


# ==========================================================
# 단독 실행 테스트
# ==========================================================

if __name__ == "__main__":
    """
    실행 예시:

    python scraper.py 20260501

    또는 특정 경기만 보고 싶으면:

    python scraper.py 20260501 20260501NCLG0
    """

    if len(sys.argv) >= 2:
        test_date = sys.argv[1]
    else:
        test_date = "20260501"

    target_game_id = None

    if len(sys.argv) >= 3:
        target_game_id = sys.argv[2]

    games = get_games_for_date(test_date)

    print("테스트 날짜:", convert_yyyymmdd_to_dash(test_date))
    print("찾은 경기 수:", len(games))
    print()

    for game in games:
        print(
            game["game_date"],
            game["game_id"],
            game["away_team"],
            game["away_score"],
            "vs",
            game["home_score"],
            game["home_team"],
            game["stadium"],
        )

    print()

    if not games:
        print("경기가 없어서 종료합니다.")
        sys.exit(0)

    selected_game = None

    if target_game_id:
        for game in games:
            if game["game_id"] == target_game_id:
                selected_game = game
                break

        if selected_game is None:
            print("입력한 game_id를 찾지 못했습니다:", target_game_id)
            sys.exit(1)
    else:
        selected_game = games[0]

    print("=" * 80)
    print("BoxScore 테스트 경기")
    print("=" * 80)
    print("game_id:", selected_game["game_id"])
    print(
        selected_game["away_team"],
        selected_game["away_score"],
        "vs",
        selected_game["home_score"],
        selected_game["home_team"],
    )
    print()

    result = get_game_boxscore_stats(selected_game)

    print("특수 기록:")
    print(result["special_records"])
    print()

    print("타자 기록 수:", len(result["batters"]))
    print("투수 기록 수:", len(result["pitchers"]))
    print()

    print("=" * 80)
    print("타자 기록")
    print("=" * 80)

    for batter in result["batters"]:
        print(
            batter["player_name"],
            batter["team"],
            "hits=" + str(batter["hits"]),
            "2B=" + str(batter["doubles"]),
            "3B=" + str(batter["triples"]),
            "HR=" + str(batter["home_runs"]),
            "RBI=" + str(batter["rbi"]),
            "R=" + str(batter["runs"]),
            "GWH=" + str(batter["game_winning_hit"]),
            "GDP=" + str(batter["double_play"]),
            "HBP=" + str(batter["hit_by_pitch"]),
            "BB=" + str(batter.get("walks", 0)),
            "SB=" + str(batter["stolen_bases"]),
            "K=" + str(batter["strikeouts"]),
        )

    print()
    print("=" * 80)
    print("투수 기록")
    print("=" * 80)

    for pitcher in result["pitchers"]:
        print(
            pitcher["player_name"],
            pitcher["team"],
            "ORDER=" + str(pitcher["pitching_order"]),
            "START=" + str(pitcher["is_starting_pitcher"]),
            "W=" + str(pitcher["wins"]),
            "L=" + str(pitcher["losses"]),
            "HLD=" + str(pitcher["holds"]),
            "SV=" + str(pitcher["saves"]),
            "IP=" + str(pitcher["innings_pitched_raw"]),
            "SO=" + str(pitcher["strikeouts"]),
            "R=" + str(pitcher["runs_allowed"]),
            "PC=" + str(pitcher["pitch_count"]),
            "HA=" + str(pitcher["hits_allowed"]),
        )