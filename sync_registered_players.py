# sync_registered_players.py
"""
KBO 등록 선수 전체 목록을 가져와서
registered_players 테이블에 저장하는 파일입니다.

실행 방법:
python sync_registered_players.py

역할:
1. KBO 전체 등록 현황 페이지(RegisterAll.aspx)에서 10개 팀 등록 선수 목록을 가져옵니다.
2. 감독/코치는 제외합니다.
3. 투수는 fantasy_position_type = "pitcher"로 저장합니다.
4. 포수/내야수/외야수는 fantasy_position_type = "batter"로 저장합니다.
5. KBO 선수 조회 페이지(Player/Search.aspx)를 이용해서
   player_id, profile_url, 생년월일, 체격 정보를 보강합니다.
6. KBO 선수 상세 페이지(profile_url)에 접속해서
   투타유형을 보강합니다.
7. registered_players 테이블에 저장하거나 업데이트합니다.

주의:
기존 경기 기록 저장 기능(sync_db.py)은 건드리지 않습니다.
기존 players 테이블도 건드리지 않습니다.
이 파일은 registered_players 테이블만 사용합니다.
"""

import argparse
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs, quote

import requests
from bs4 import BeautifulSoup

from db import get_conn, init_db


KBO_BASE_URL = "https://www.koreabaseball.com"
REGISTER_URL = f"{KBO_BASE_URL}/Player/Register.aspx"
REGISTER_ALL_URL = f"{KBO_BASE_URL}/Player/RegisterAll.aspx"
PLAYER_SEARCH_URL = f"{KBO_BASE_URL}/Player/Search.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.koreabaseball.com/",
}

PLAYER_POSITIONS = ["투수", "포수", "내야수", "외야수"]
STAFF_POSITIONS = ["감독", "코치"]
TEAM_NAMES = ["KT", "LG", "삼성", "SSG", "KIA", "두산", "NC", "한화", "롯데", "키움"]
TEAM_FULL_NAMES = {
    "KT": "KT 위즈",
    "LG": "LG 트윈스",
    "삼성": "삼성 라이온즈",
    "SSG": "SSG 랜더스",
    "KIA": "KIA 타이거즈",
    "두산": "두산 베어스",
    "NC": "NC 다이노스",
    "한화": "한화 이글스",
    "롯데": "롯데 자이언츠",
    "키움": "키움 히어로즈",
}

# KBO 내부/경기 ID에서 자주 쓰이는 팀 코드입니다.
# Register.aspx 팀 탭 전환 방식이 바뀌어도, 후보 URL 검증과 엠블럼 코드 인식에 사용합니다.
TEAM_CODES = {
    "KT": "KT",
    "LG": "LG",
    "삼성": "SS",
    "SSG": "SK",
    "KIA": "HT",
    "두산": "OB",
    "NC": "NC",
    "한화": "HH",
    "롯데": "LT",
    "키움": "WO",
}
CODE_TO_TEAM = {code: team for team, code in TEAM_CODES.items()}
POSITION_ORDER = ["감독", "코치", "투수", "포수", "내야수", "외야수"]

# 같은 이름을 여러 번 검색하지 않기 위한 캐시입니다.
# key: 선수명
# value: Player/Search.aspx 검색 결과 리스트
PLAYER_SEARCH_CACHE = {}

# 선수 상세 페이지를 여러 번 요청하지 않기 위한 캐시입니다.
# key: profile_url
# value: {"roster_position": "...", "throw_bat": "..."}
PLAYER_PROFILE_CACHE = {}


def clean_text(value):
    """
    HTML에서 가져온 문자열의 공백을 정리합니다.
    """
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def fetch_html(url):
    """
    KBO 페이지 HTML을 가져옵니다.
    """
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    # 한글이 깨지는 경우를 줄이기 위해 인코딩을 보정합니다.
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding

    return response.text


def get_soup(html):
    """
    HTML 문자열을 BeautifulSoup 객체로 바꿉니다.
    """
    return BeautifulSoup(html, "html.parser")


def extract_player_id_from_url(url):
    """
    선수 상세 URL에서 playerId 값을 추출합니다.

    예:
    https://www.koreabaseball.com/Record/Player/HitterDetail/Basic.aspx?playerId=65653
    -> 65653
    """
    if not url:
        return None

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    player_ids = query.get("playerId")
    if player_ids:
        return player_ids[0]

    return None


def make_profile_url(href):
    """
    상대 경로로 되어 있는 KBO 선수 상세 링크를 전체 URL로 바꿉니다.
    """
    if not href:
        return None

    return urljoin(KBO_BASE_URL, href)


def get_fantasy_position_type(roster_position):
    """
    KBO 등록 포지션을 판타지 점수용 구분으로 바꿉니다.

    투수 -> pitcher
    포수/내야수/외야수 -> batter
    """
    if roster_position == "투수":
        return "pitcher"

    if roster_position in ["포수", "내야수", "외야수"]:
        return "batter"

    return "staff"


def extract_source_date(soup):
    """
    KBO 등록 현황 페이지에 표시된 기준 날짜를 찾습니다.

    예:
    2026.05.09(토)
    -> 2026-05-09

    날짜를 못 찾으면 오늘 날짜를 사용합니다.
    """
    text = soup.get_text("\n", strip=True)

    match = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"

    return datetime.now().strftime("%Y-%m-%d")


def extract_team_name_from_text(text):
    """
    문장에서 팀명을 찾습니다.
    """
    text = clean_text(text)

    for team in TEAM_NAMES:
        if team in text:
            return team

    return None


def extract_position_from_text(text):
    """
    문장에서 포지션명을 찾습니다.
    """
    text = clean_text(text)

    for position in POSITION_ORDER:
        if position in text:
            return position

    return None


def parse_position_counts(text):
    """
    텍스트에서 포지션별 인원 수를 가져옵니다.

    예:
    감독(1) 코치(10) 투수(13) 포수(3) 내야수(7) 외야수(6)
    """
    counts = {}

    for position in POSITION_ORDER:
        match = re.search(rf"{position}\s*\((\d+)\)", text)
        counts[position] = int(match.group(1)) if match else 0

    return counts


def parse_name_and_back_no(line):
    """
    선수 문자열에서 이름과 등번호를 분리합니다.

    예:
    고영표(1) -> name=고영표, back_no=1
    긴지로(00) -> name=긴지로, back_no=00
    """
    line = clean_text(line)

    # 앞에 붙을 수 있는 기호를 제거합니다.
    line = re.sub(r"^[\*\u2022ㆍ\-]\s*", "", line)

    match = re.match(r"^(.+?)\s*\((.*?)\)$", line)
    if not match:
        return None, None

    name = clean_text(match.group(1))
    back_no = clean_text(match.group(2))

    return name, back_no


def parse_people_from_text(text):
    """
    한 칸 또는 한 블록 안에서 이름(등번호) 형태를 모두 찾습니다.

    예:
    고영표(1) 톨허스트(30)
    -> [("고영표", "1"), ("톨허스트", "30")]
    """
    text = clean_text(text)

    people = []

    # 이름에는 한글, 영어, 숫자, 점, 가운데점 등이 들어올 수 있습니다.
    matches = re.findall(r"([가-힣A-Za-z0-9·.\-]+)\s*\(([^()]*)\)", text)

    for name, back_no in matches:
        name = clean_text(name)
        back_no = clean_text(back_no)

        # 헤더의 투수(13), 코치(10) 같은 값은 제외합니다.
        if name in POSITION_ORDER:
            continue

        # 팀명도 제외합니다.
        if name in TEAM_NAMES:
            continue

        if not name:
            continue

        people.append((name, back_no))

    return people


def make_registered_player(
    name,
    team,
    roster_position,
    back_no=None,
    throw_bat=None,
    birthdate=None,
    height_weight=None,
    profile_url=None,
    player_id=None,
    source_date=None,
):
    """
    DB에 저장할 registered_players 한 명의 dict를 만듭니다.
    """
    return {
        "player_id": player_id,
        "name": name,
        "team": team,
        "team_id": None,
        "roster_position": roster_position,
        "fantasy_position_type": get_fantasy_position_type(roster_position),
        "back_no": back_no,
        "throw_bat": throw_bat,
        "birthdate": birthdate,
        "height_weight": height_weight,
        "profile_url": profile_url,
        "is_active": 1,
        "source_date": source_date,
    }


def parse_register_all_page_by_tables(soup, source_date):
    """
    RegisterAll.aspx를 table 구조 기준으로 파싱합니다.

    현재 성공한 방식입니다.
    전체 10개 팀 290명 정도가 여기서 나옵니다.
    """
    players = []
    excluded_staff_count = 0
    processed_teams = set()

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        header_positions = {}
        header_row_index = None

        # 먼저 헤더 행을 찾습니다.
        for row_index, row in enumerate(rows):
            cells = row.find_all(["th", "td"])
            cell_texts = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]

            if not cell_texts:
                continue

            has_team_header = any("구단" in text for text in cell_texts)
            has_position_header = any(
                any(position in text for position in POSITION_ORDER)
                for text in cell_texts
            )

            if not has_team_header or not has_position_header:
                continue

            for cell_index, text in enumerate(cell_texts):
                position = extract_position_from_text(text)
                if position:
                    header_positions[cell_index] = position

            if header_positions:
                header_row_index = row_index
                break

        if header_row_index is None:
            continue

        # 헤더 아래의 행들을 선수 데이터로 읽습니다.
        for row in rows[header_row_index + 1:]:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            row_text = clean_text(row.get_text(" ", strip=True))
            team = extract_team_name_from_text(row_text)

            if not team:
                continue

            processed_teams.add(team)

            for cell_index, position in header_positions.items():
                if cell_index >= len(cells):
                    continue

                cell = cells[cell_index]
                people = parse_people_from_text(cell.get_text(" ", strip=True))

                for name, back_no in people:
                    if position in STAFF_POSITIONS:
                        excluded_staff_count += 1
                        continue

                    if position not in PLAYER_POSITIONS:
                        continue

                    players.append(
                        make_registered_player(
                            name=name,
                            team=team,
                            roster_position=position,
                            back_no=back_no,
                            source_date=source_date,
                        )
                    )

    return players, excluded_staff_count, processed_teams


def parse_register_all_page_by_joined_text(soup, source_date):
    """
    RegisterAll.aspx를 전체 텍스트 기준으로 파싱합니다.

    table 파싱이 실패할 경우를 대비한 보조 방식입니다.
    """
    text = soup.get_text(" ", strip=True)
    text = clean_text(text)

    # 1군 등록/말소 현황은 전체 등록 선수 명단이 아니므로 잘라냅니다.
    for cut_word in ["1군 등록 현황", "1군등록현황"]:
        cut_index = text.find(cut_word)
        if cut_index != -1:
            text = text[:cut_index]
            break

    players = []
    excluded_staff_count = 0
    processed_teams = set()

    team_pattern = re.compile(
        r"전체\s*등록\s*현황\s*구단\s*"
        r"감독\s*\((\d+)\)\s*"
        r"코치\s*\((\d+)\)\s*"
        r"투수\s*\((\d+)\)\s*"
        r"포수\s*\((\d+)\)\s*"
        r"내야수\s*\((\d+)\)\s*"
        r"외야수\s*\((\d+)\)\s*"
        r"(KT|LG|삼성|SSG|KIA|두산|NC|한화|롯데|키움)\s*"
        r"\d+명\s*"
        r"(.*?)"
        r"(?=전체\s*등록\s*현황\s*구단\s*감독\s*\(|$)"
    )

    for match in team_pattern.finditer(text):
        counts = {
            "감독": int(match.group(1)),
            "코치": int(match.group(2)),
            "투수": int(match.group(3)),
            "포수": int(match.group(4)),
            "내야수": int(match.group(5)),
            "외야수": int(match.group(6)),
        }

        team = match.group(7)
        body = match.group(8)

        processed_teams.add(team)

        people = parse_people_from_text(body)
        person_index = 0

        for position in POSITION_ORDER:
            count = counts.get(position, 0)

            for _ in range(count):
                if person_index >= len(people):
                    break

                name, back_no = people[person_index]
                person_index += 1

                if position in STAFF_POSITIONS:
                    excluded_staff_count += 1
                    continue

                if position not in PLAYER_POSITIONS:
                    continue

                players.append(
                    make_registered_player(
                        name=name,
                        team=team,
                        roster_position=position,
                        back_no=back_no,
                        source_date=source_date,
                    )
                )

    return players, excluded_staff_count, processed_teams


def parse_register_all_page_by_lines(soup, source_date):
    """
    RegisterAll.aspx를 줄 단위 텍스트 기준으로 파싱합니다.

    BeautifulSoup이 텍스트를 여러 줄로 쪼갰을 때를 대비한 방식입니다.
    """
    raw_text = soup.get_text("\n", strip=True)

    lines = []
    for raw_line in raw_text.split("\n"):
        line = clean_text(raw_line)
        if not line:
            continue

        line = re.sub(r"^[\*\u2022ㆍ\-]\s*", "", line)
        lines.append(line)

    players = []
    excluded_staff_count = 0
    processed_teams = set()

    i = 0

    while i < len(lines):
        line = lines[i]

        if "전체등록현황" not in line and "전체 등록 현황" not in line:
            i += 1
            continue

        # 헤더가 여러 줄로 쪼개져 있을 수 있으므로 주변 줄을 합쳐서 인원 수를 찾습니다.
        header_window = " ".join(lines[i:i + 20])
        counts = parse_position_counts(header_window)

        if sum(counts.values()) == 0:
            i += 1
            continue

        team = None
        j = i + 1

        while j < len(lines):
            if lines[j] in TEAM_NAMES:
                team = lines[j]
                break

            if j > i + 1 and ("전체등록현황" in lines[j] or "전체 등록 현황" in lines[j]):
                break

            j += 1

        if not team:
            i += 1
            continue

        processed_teams.add(team)
        j += 1

        while j < len(lines) and re.match(r"^\d+명$", lines[j]):
            j += 1

        total_people_count = sum(counts.values())
        person_lines = []

        while j < len(lines) and len(person_lines) < total_people_count:
            current_line = lines[j]

            if "1군 등록 현황" in current_line or "1군등록현황" in current_line:
                break

            if "전체등록현황" in current_line or "전체 등록 현황" in current_line:
                break

            name, back_no = parse_name_and_back_no(current_line)

            if name:
                person_lines.append(current_line)

            j += 1

        person_index = 0

        for position in POSITION_ORDER:
            count = counts.get(position, 0)

            for _ in range(count):
                if person_index >= len(person_lines):
                    break

                name, back_no = parse_name_and_back_no(person_lines[person_index])
                person_index += 1

                if not name:
                    continue

                if position in STAFF_POSITIONS:
                    excluded_staff_count += 1
                    continue

                if position not in PLAYER_POSITIONS:
                    continue

                players.append(
                    make_registered_player(
                        name=name,
                        team=team,
                        roster_position=position,
                        back_no=back_no,
                        source_date=source_date,
                    )
                )

        i = j

    return players, excluded_staff_count, processed_teams


def dedupe_players(players):
    """
    이름 + 팀 + 등록 포지션 기준으로 중복 선수를 제거합니다.
    """
    result = {}

    for player in players:
        key = (
            player["name"],
            player["team"],
            player["roster_position"],
        )
        result[key] = player

    return list(result.values())


def get_team_counts(players):
    """
    파싱 결과의 팀별 선수 수를 계산합니다.
    """
    counts = {}

    for player in players:
        team = player.get("team")
        if not team:
            continue

        counts[team] = counts.get(team, 0) + 1

    return counts


def score_parse_candidate(players, teams):
    """
    RegisterAll.aspx 파싱 후보의 안전 점수를 계산합니다.

    단순히 선수 수가 많은 후보를 고르면, HTML 구조가 깨졌을 때
    한 팀에 다른 팀 선수들이 몰려 저장되는 문제가 생길 수 있습니다.
    그래서 10개 팀이 균형 있게 잡힌 후보를 우선합니다.
    """
    if not players:
        return -10**9

    counts = get_team_counts(players)
    team_count = len(counts)
    total = len(players)

    min_count = min(counts.values()) if counts else 0
    max_count = max(counts.values()) if counts else 0

    # KBO 1군 등록 선수는 보통 팀당 20~40명대입니다.
    # 너무 적거나 너무 많은 팀이 있으면 잘못 파싱됐을 가능성이 큽니다.
    imbalance_penalty = 0
    for team in TEAM_NAMES:
        count = counts.get(team, 0)
        if count == 0:
            imbalance_penalty += 500
        elif count < 15:
            imbalance_penalty += (15 - count) * 20
        elif count > 45:
            imbalance_penalty += (count - 45) * 20

    # 팀 커버리지를 가장 중요하게 보고, 그 다음 전체 선수 수를 봅니다.
    return team_count * 10000 + total - imbalance_penalty - (max_count - min_count) * 5


def choose_best_parse_candidate(candidates):
    """
    여러 파싱 후보 중 가장 안전한 후보를 고릅니다.
    """
    scored = []

    for name, players, staff_count, teams in candidates:
        deduped_players = dedupe_players(players)
        counts = get_team_counts(deduped_players)
        score = score_parse_candidate(deduped_players, teams)
        scored.append((score, name, deduped_players, staff_count, teams, counts))

    scored.sort(key=lambda item: item[0], reverse=True)

    best_score, best_name, best_players, best_staff_count, best_teams, best_counts = scored[0]

    print("전체 등록 페이지 파싱 후보 점수:")
    for score, name, players, _staff_count, _teams, counts in scored:
        min_count = min(counts.values()) if counts else 0
        max_count = max(counts.values()) if counts else 0
        print(
            f"- {name}: score={score}, 선수 {len(players)}명, "
            f"팀 {len(counts)}개, min={min_count}, max={max_count}"
        )

    suspicious = False
    if len(best_counts) < 10:
        suspicious = True
    if best_counts:
        if min(best_counts.values()) < 15 or max(best_counts.values()) > 45:
            suspicious = True

    if suspicious:
        print("[주의] 선택된 파싱 결과의 팀별 분포가 비정상적일 수 있습니다.")
        print("       저장 전 팀별 선수 수 요약을 반드시 확인하세요.")

    return best_name, best_players, best_staff_count, best_teams


def parse_register_all_page(html):
    """
    RegisterAll.aspx 페이지에서 전체 팀의 등록 선수 목록을 파싱합니다.

    여러 방식으로 파싱을 시도한 뒤,
    가장 많은 선수를 찾은 결과를 사용합니다.
    """
    soup = get_soup(html)
    source_date = extract_source_date(soup)

    table_players, table_staff_count, table_teams = parse_register_all_page_by_tables(
        soup,
        source_date,
    )

    joined_players, joined_staff_count, joined_teams = parse_register_all_page_by_joined_text(
        soup,
        source_date,
    )

    line_players, line_staff_count, line_teams = parse_register_all_page_by_lines(
        soup,
        source_date,
    )

    candidates = [
        ("table", table_players, table_staff_count, table_teams),
        ("joined_text", joined_players, joined_staff_count, joined_teams),
        ("lines", line_players, line_staff_count, line_teams),
    ]

    (
        best_name,
        best_players,
        best_staff_count,
        best_teams,
    ) = choose_best_parse_candidate(candidates)

    print(f"전체 등록 페이지 파싱 방식: {best_name}")
    print(f"전체 등록 페이지 table 파싱 선수 수: {len(table_players)}")
    print(f"전체 등록 페이지 joined_text 파싱 선수 수: {len(joined_players)}")
    print(f"전체 등록 페이지 lines 파싱 선수 수: {len(line_players)}")

    return best_players, best_staff_count, source_date, best_teams



def normalize_transaction_roster_position(value):
    """
    RegisterAll.aspx 하단 1군 등록/말소 현황은 포지션을 투/포/내/외처럼 짧게 줄여서 표시합니다.
    player_register_transactions에는 기존 registered_players와 같은 포지션명으로 저장합니다.
    """
    value = clean_text(value)
    mapping = {
        "투": "투수",
        "투수": "투수",
        "포": "포수",
        "포수": "포수",
        "내": "내야수",
        "내야수": "내야수",
        "외": "외야수",
        "외야수": "외야수",
    }
    return mapping.get(value, value)


def parse_register_all_transactions_from_soup(soup, source_date, source_url=REGISTER_ALL_URL):
    """
    RegisterAll.aspx 하단의 전 구단 1군 등록/말소 현황을 파싱합니다.

    Register.aspx 구단별 탭은 KBO 쪽에서 단순 GET 파라미터를 무시하고 기본 KT 화면을
    반환하는 경우가 있으므로, 전 구단 당일 등록/말소 이력은 RegisterAll.aspx 하단 표를
    1차 기준으로 저장합니다.
    """
    transactions = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        header_cells = [clean_text(cell.get_text(" ", strip=True)) for cell in rows[0].find_all(["th", "td"])]
        header_text = " ".join(header_cells)

        # RegisterAll 하단 transaction table은 보통 선수/포지션/팀 3개 컬럼입니다.
        if not ("선수" in header_text and "포지션" in header_text and "팀" in header_text):
            continue

        previous_texts = []
        for text_node in table.find_all_previous(string=True):
            text = clean_text(text_node)
            if text:
                previous_texts.append(text)
            if len(previous_texts) >= 80:
                break
        previous_blob = " | ".join(previous_texts)

        transaction_type = None
        if "1군 말소 현황" in previous_blob:
            transaction_type = "말소"
        if "1군 등록 현황" in previous_blob and (transaction_type is None or previous_blob.find("1군 등록 현황") < previous_blob.find("1군 말소 현황")):
            # find_all_previous는 가까운 노드부터 역순으로 나오므로, 표 바로 위의 가장 가까운 제목이 우선입니다.
            # 위 조건은 등록 표와 말소 표가 가까이 있을 때 등록 표를 보수적으로 잡기 위한 처리입니다.
            transaction_type = "등록"

        # 더 안전하게 가까운 heading/text부터 순서대로 확인합니다.
        for text in previous_texts:
            if "1군 말소 현황" in text:
                transaction_type = "말소"
                break
            if "1군 등록 현황" in text:
                transaction_type = "등록"
                break

        if transaction_type not in ["등록", "말소"]:
            continue

        for row in rows[1:]:
            cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
            row_text = clean_text(row.get_text(" ", strip=True))
            if not row_text:
                continue
            if "당일" in row_text and ("없습니다" in row_text or "선수가 없습니다" in row_text):
                continue
            if len(cells) < 3:
                continue

            name, roster_position_raw, team_raw = cells[:3]
            team = normalize_team_name_from_text(team_raw)
            roster_position = normalize_transaction_roster_position(roster_position_raw)

            if not name or name == "선수":
                continue
            if team not in TEAM_NAMES:
                continue
            if roster_position not in PLAYER_POSITIONS:
                continue

            transactions.append({
                "source_date": source_date,
                "team": team,
                "transaction_type": transaction_type,
                "player_name": name,
                "roster_position": roster_position,
                "back_no": "",
                "throw_bat": "",
                "birthdate": "",
                "height_weight": "",
                "source_url": source_url,
                "raw_section": f"RegisterAll direct: {row_text}",
            })

    return transactions





def normalize_team_name_from_text(text):
    """
    KBO 페이지의 팀 약칭/풀네임/내부 코드/엠블럼 파일명을 내부 팀명으로 정규화합니다.
    """
    text = clean_text(text)
    if not text:
        return None

    for team, full_name in TEAM_FULL_NAMES.items():
        if full_name in text:
            return team

    upper_text = text.upper()
    for team, code in TEAM_CODES.items():
        code_patterns = [
            rf"emblem[_-]{re.escape(code)}(?:\.|_|-|\?|$)",
            rf"team[_-]?code[=:_-]?{re.escape(code)}(?:\W|$)",
            rf"team[_-]?id[=:_-]?{re.escape(code)}(?:\W|$)",
            rf"club[_-]?id[=:_-]?{re.escape(code)}(?:\W|$)",
        ]
        if any(re.search(pattern, upper_text, re.IGNORECASE) for pattern in code_patterns):
            return team

    # 짧은 팀명은 다른 단어에 섞일 수 있으므로 긴 이름/코드 확인 뒤 fallback으로만 사용합니다.
    for team in TEAM_NAMES:
        if re.search(rf"(^|\s|[^가-힣A-Za-z0-9]){re.escape(team)}($|\s|[^가-힣A-Za-z0-9])", text):
            return team

    return None


def extract_detailed_register_team(soup):
    """
    Register.aspx 구단별 페이지에서 실제로 선택된 팀을 찾습니다.
    메뉴에 10개 팀명이 모두 있기 때문에, 전체 텍스트 첫 팀명을 쓰면 안 됩니다.
    """
    for text_node in soup.find_all(string=True):
        text = clean_text(text_node)
        if "선수등록명단" not in text:
            continue
        team = normalize_team_name_from_text(text)
        if team:
            return team

    text = soup.get_text(" ", strip=True)
    match = re.search(r"([가-힣A-Za-z0-9\s]+?)\s*선수등록명단", text)
    if match:
        return normalize_team_name_from_text(match.group(1))

    return None


def parse_register_transactions_from_soup(soup, team, source_date, source_url):
    """
    Register.aspx의 당일 등/말소 현황을 파싱합니다.

    이 정보는 active 여부를 직접 결정하는 기준이 아니라,
    KBO 공식 페이지에 표시된 당일 transaction을 검증/표시하기 위한 참고 데이터입니다.
    현재 active 여부는 RegisterAll.aspx 전체 등록 현황을 기준으로 합니다.
    """
    transactions = []
    if not team:
        return transactions

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        header_text = clean_text(rows[0].get_text(" ", strip=True))
        if "선수명" not in header_text or "포지션" not in header_text:
            continue

        transaction_type = None
        for text_node in table.find_all_previous(string=True):
            text = clean_text(text_node)
            if text in ["등록", "말소"]:
                transaction_type = text
                break
            if "선수등록명단" in text:
                break

        if transaction_type not in ["등록", "말소"]:
            continue

        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            cell_texts = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            row_text = clean_text(row.get_text(" ", strip=True))

            if not row_text:
                continue
            if "당일" in row_text and ("없습니다" in row_text or "선수가 없습니다" in row_text):
                continue
            if len(cell_texts) < 6:
                continue

            back_no, name, roster_position, throw_bat, birthdate, height_weight = cell_texts[:6]
            if not name or name == "선수명":
                continue
            if roster_position not in PLAYER_POSITIONS:
                continue

            transactions.append({
                "source_date": source_date,
                "team": team,
                "transaction_type": transaction_type,
                "player_name": name,
                "roster_position": roster_position,
                "back_no": back_no,
                "throw_bat": throw_bat,
                "birthdate": birthdate,
                "height_weight": height_weight,
                "source_url": source_url,
                "raw_section": row_text,
            })

    return transactions


def parse_register_postback_targets(html):
    """
    KBO Register.aspx가 ASP.NET postback으로 팀 탭을 전환하는 경우를 대비해
    팀별 __doPostBack target을 찾습니다.

    tag href/onclick만 보는 방식은 팀 탭을 놓칠 수 있어서,
    tag 전체 HTML, 엠블럼 코드, 주변 텍스트까지 같이 봅니다.
    """
    soup = get_soup(html)
    targets = {}

    for tag in soup.find_all(["a", "button", "input", "img", "li", "span", "div"]):
        attr_text = " ".join(
            clean_text(tag.get(attr) or "")
            for attr in [
                "alt", "title", "value", "href", "onclick", "src", "class",
                "id", "name", "data-team", "data-id", "data-code"
            ]
        )
        visible_text = clean_text(tag.get_text(" ", strip=True))
        raw_tag_text = clean_text(str(tag))
        parent_text = clean_text(tag.parent.get_text(" ", strip=True)) if tag.parent else ""
        combined = f"{visible_text} {attr_text} {raw_tag_text} {parent_text}"
        team = normalize_team_name_from_text(combined)
        if not team:
            continue

        m = re.search(r"__doPostBack\(['\"]([^'\"]*)['\"]\s*,\s*['\"]([^'\"]*)['\"]\)", combined)
        if m and team not in targets:
            targets[team] = (m.group(1), m.group(2))

    return targets


def postback_register_page(session, base_html, event_target, event_argument):
    soup = get_soup(base_html)
    data = {}
    for input_tag in soup.find_all("input"):
        name = input_tag.get("name")
        if not name:
            continue
        data[name] = input_tag.get("value", "")
    data["__EVENTTARGET"] = event_target
    data["__EVENTARGUMENT"] = event_argument or ""

    response = session.post(REGISTER_URL, data=data, headers=HEADERS, timeout=15)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


def iter_candidate_register_urls(team):
    """
    Register.aspx 팀 탭 전환 방식이 바뀌었거나 postback target 파싱이 실패할 때를 위한
    보수적 후보 URL 목록입니다. 실제 사용 여부는 parsed_team == team 검증으로만 결정합니다.
    """
    code = TEAM_CODES.get(team, team)
    encoded_team = quote(team)
    candidates = []
    for key in ["teamId", "teamCode", "clubId", "clubCode", "team", "searchTeam", "selectTeam"]:
        candidates.append(f"{REGISTER_URL}?{key}={code}")
        candidates.append(f"{REGISTER_URL}?{key}={encoded_team}")

    lower_url = REGISTER_URL.replace("/Player/", "/player/")
    for key in ["teamId", "teamCode", "clubId", "clubCode", "team", "searchTeam", "selectTeam"]:
        candidates.append(f"{lower_url}?{key}={code}")
        candidates.append(f"{lower_url}?{key}={encoded_team}")

    seen = set()
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        yield url


def try_fetch_register_page_for_team(session, team):
    """
    팀별 상세 페이지 직접 URL 후보를 검증하면서 가져옵니다.
    잘못된 후보는 대부분 기본 팀 페이지를 반환하므로 parsed_team 검증을 반드시 거칩니다.
    """
    failures = []
    for url in iter_candidate_register_urls(team):
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding
            html = response.text
            parsed_team = extract_detailed_register_team(get_soup(html))
            if parsed_team == team:
                return html, url, failures
            failures.append(f"{team}: 후보 URL 팀 불일치({url} -> {parsed_team})")
        except Exception as e:
            failures.append(f"{team}: 후보 URL 실패({url}): {e}")
        time.sleep(0.03)
    return None, None, failures


def collect_detailed_register_pages():
    """
    구단별 Register.aspx 상세 페이지를 가능한 범위에서 수집합니다.

    active 여부의 최종 기준은 RegisterAll.aspx이며,
    이 함수는 상세 정보/당일 등말소 transaction 보강을 위한 보조 수집입니다.

    수집 우선순위:
    1. 기본 GET 페이지
    2. HTML 내 ASP.NET __doPostBack 팀 탭
    3. 팀 코드 후보 URL 검증
    실패하더라도 RegisterAll 기준 active 업데이트는 계속 진행합니다.
    """
    pages = {}
    failed = []
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        response = session.get(REGISTER_URL, timeout=15)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        base_html = response.text
    except Exception as e:
        failed.append(f"Register.aspx 기본 GET: {e}")
        return pages, failed

    base_soup = get_soup(base_html)
    base_team = extract_detailed_register_team(base_soup)
    if base_team:
        pages[base_team] = (base_html, REGISTER_URL)

    targets = parse_register_postback_targets(base_html)
    for team, (event_target, event_argument) in targets.items():
        if team in pages:
            continue
        try:
            html = postback_register_page(session, base_html, event_target, event_argument)
            parsed_team = extract_detailed_register_team(get_soup(html))
            if parsed_team == team:
                pages[team] = (html, f"{REGISTER_URL}#__postback__{team}")
            else:
                failed.append(f"{team}: postback 결과 팀 불일치({parsed_team})")
            time.sleep(0.05)
        except Exception as e:
            failed.append(f"{team}: postback 실패: {e}")

    for team in TEAM_NAMES:
        if team in pages:
            continue
        html, url, url_failures = try_fetch_register_page_for_team(session, team)
        if html and url:
            pages[team] = (html, url)
        elif url_failures:
            failed.append(url_failures[-1])

    missing = [team for team in TEAM_NAMES if team not in pages]
    if missing:
        failed.append(
            "구단별 상세 페이지 미수집 팀: " + ", ".join(missing)
            + " / active 여부는 RegisterAll.aspx 기준으로 계속 처리"
        )
    return pages, failed


def get_previous_active_registered_snapshot(conn):
    """
    RegisterAll 동기화 전 현재 active 선수 스냅샷을 가져옵니다.
    Register.aspx 팀 탭 수집이 불완전해도 RegisterAll 변경분으로 전 구단 등록/말소 transaction을 보강합니다.
    """
    rows = conn.execute("""
        SELECT
            id,
            name,
            team,
            roster_position,
            fantasy_position_type,
            back_no,
            throw_bat,
            birthdate,
            height_weight,
            source_date
        FROM registered_players
        WHERE is_active = 1
    """).fetchall()

    snapshot = {}
    for row in rows:
        key = (row["name"], row["team"], row["roster_position"])
        snapshot[key] = dict(row)
    return snapshot


def build_register_transactions_from_active_diff(previous_active_snapshot, current_players, source_date):
    """
    RegisterAll 전체 등록 현황의 active set 변화를 transaction 참고 데이터로 보강합니다.
    """
    current_map = {}
    for player in current_players:
        if player.get("fantasy_position_type") not in ["batter", "pitcher"]:
            continue
        key = (player.get("name"), player.get("team"), player.get("roster_position"))
        current_map[key] = player

    transactions = []

    for key, player in current_map.items():
        if key in previous_active_snapshot:
            continue
        transactions.append({
            "source_date": source_date,
            "team": player.get("team"),
            "transaction_type": "등록",
            "player_name": player.get("name"),
            "roster_position": player.get("roster_position"),
            "back_no": player.get("back_no"),
            "throw_bat": player.get("throw_bat"),
            "birthdate": player.get("birthdate"),
            "height_weight": player.get("height_weight"),
            "source_url": REGISTER_ALL_URL,
            "raw_section": "RegisterAll active diff: previous inactive/missing -> current active",
        })

    for key, old in previous_active_snapshot.items():
        if key in current_map:
            continue
        transactions.append({
            "source_date": source_date,
            "team": old.get("team"),
            "transaction_type": "말소",
            "player_name": old.get("name"),
            "roster_position": old.get("roster_position"),
            "back_no": old.get("back_no"),
            "throw_bat": old.get("throw_bat"),
            "birthdate": old.get("birthdate"),
            "height_weight": old.get("height_weight"),
            "source_url": REGISTER_ALL_URL,
            "raw_section": "RegisterAll active diff: previous active -> current inactive/missing",
        })

    return transactions


def get_transaction_source_priority(item):
    """transaction 중복이 있을 때 어떤 소스를 우선할지 정합니다.

    Register.aspx direct는 등번호/생년월일/체격까지 가장 자세하고,
    RegisterAll direct는 10개 팀 전체 당일 등록/말소를 가장 안정적으로 제공합니다.
    RegisterAll active diff는 direct 표가 없을 때만 쓰는 보조 추정입니다.
    """
    raw = item.get("raw_section") or ""
    url = item.get("source_url") or ""
    if "RegisterAll active diff" in raw:
        return 10
    if "RegisterAll direct" in raw:
        return 80
    if "Register.aspx" in url:
        return 100
    return 50


def merge_register_transactions(*transaction_lists):
    """
    같은 선수/팀/유형 transaction 중복을 제거합니다.

    UNIQUE 제약에는 back_no가 포함되어 있지만, RegisterAll 하단 전 구단 transaction 표에는
    등번호가 없습니다. 따라서 merge 단계에서는 back_no를 제외하고 같은 transaction으로
    판단해야 KT처럼 Register.aspx direct와 RegisterAll direct가 동시에 들어올 때 중복 저장을
    막을 수 있습니다.
    """
    merged = {}
    for transactions in transaction_lists:
        for item in transactions or []:
            key = (
                item.get("source_date"),
                item.get("team"),
                item.get("transaction_type"),
                item.get("player_name"),
                item.get("roster_position"),
            )
            if not all(key[:4]):
                continue
            if key not in merged:
                merged[key] = item
                continue
            if get_transaction_source_priority(item) > get_transaction_source_priority(merged[key]):
                merged[key] = item
    return list(merged.values())

def save_register_transactions(transactions):
    if not transactions:
        print("구단별 등/말소 transaction 저장: 0건")
        return 0

    saved_count = 0
    with get_conn() as conn:
        for item in transactions:
            # back_no가 없는 RegisterAll direct와 back_no가 있는 Register.aspx direct가
            # 같은 transaction으로 중복 저장되지 않도록 논리 key 기준으로 기존 row를 정리합니다.
            conn.execute("""
                DELETE FROM player_register_transactions
                WHERE source_date = ?
                  AND team = ?
                  AND transaction_type = ?
                  AND player_name = ?
                  AND roster_position = ?
            """, (
                item.get("source_date"), item.get("team"), item.get("transaction_type"),
                item.get("player_name"), item.get("roster_position"),
            ))

            conn.execute("""
                INSERT INTO player_register_transactions (
                    source_date, team, transaction_type, player_name, roster_position,
                    back_no, throw_bat, birthdate, height_weight, source_url, raw_section,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(source_date, team, transaction_type, player_name, roster_position, back_no)
                DO UPDATE SET
                    throw_bat = excluded.throw_bat,
                    birthdate = excluded.birthdate,
                    height_weight = excluded.height_weight,
                    source_url = excluded.source_url,
                    raw_section = excluded.raw_section,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                item.get("source_date"), item.get("team"), item.get("transaction_type"),
                item.get("player_name"), item.get("roster_position"), item.get("back_no"),
                item.get("throw_bat"), item.get("birthdate"), item.get("height_weight"),
                item.get("source_url"), item.get("raw_section"),
            ))
            saved_count += 1
    print(f"구단별 등/말소 transaction 저장: {saved_count}건")
    return saved_count

def parse_detailed_register_page(html):
    """
    Register.aspx 페이지에서 상세 선수 정보를 파싱합니다.

    현재 기본 페이지는 KT 한 팀만 잘 보이는 상태입니다.
    그래서 이 함수는 KT 상세 정보 보강용으로만 사용합니다.
    """
    soup = get_soup(html)
    source_date = extract_source_date(soup)

    page_text = soup.get_text("\n", strip=True)
    team = extract_detailed_register_team(soup) or extract_team_name_from_text(page_text)

    players = []
    excluded_staff_count = 0

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        current_position = None

        for row in rows:
            cells = row.find_all(["th", "td"])
            cell_texts = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]

            if not cell_texts:
                continue

            # 헤더 행 예시:
            # 등번호 투수 투타유형 생년월일 체격
            if "등번호" in cell_texts:
                for pos in POSITION_ORDER:
                    if pos in cell_texts:
                        current_position = pos
                        break
                continue

            if current_position is None:
                continue

            if current_position in STAFF_POSITIONS:
                if len(cell_texts) >= 2 and cell_texts[0] != "등번호":
                    excluded_staff_count += 1
                continue

            if current_position not in PLAYER_POSITIONS:
                continue

            # 선수 행은 보통 다음 구조입니다.
            # 등번호 / 선수명 / 투타유형 / 생년월일 / 체격
            if len(cell_texts) < 5:
                continue

            back_no = cell_texts[0]
            name = cell_texts[1]
            throw_bat = cell_texts[2]
            birthdate = cell_texts[3]
            height_weight = cell_texts[4]

            name_cell = cells[1]
            link = name_cell.find("a")
            href = link.get("href") if link else None

            profile_url = make_profile_url(href)
            player_id = extract_player_id_from_url(profile_url)

            if not name or name in ["선수명", current_position]:
                continue

            players.append(
                make_registered_player(
                    name=name,
                    team=team,
                    roster_position=current_position,
                    back_no=back_no,
                    throw_bat=throw_bat,
                    birthdate=birthdate,
                    height_weight=height_weight,
                    profile_url=profile_url,
                    player_id=player_id,
                    source_date=source_date,
                )
            )

    return players, excluded_staff_count, source_date


def search_player_by_name(name):
    """
    KBO 선수 조회 페이지에서 선수 이름으로 검색합니다.

    반환값:
    검색 결과 선수 dict 리스트

    이 함수는 DB를 수정하지 않고, 검색 결과만 반환합니다.
    """
    if name in PLAYER_SEARCH_CACHE:
        return PLAYER_SEARCH_CACHE[name]

    encoded_name = quote(name)
    url = f"{PLAYER_SEARCH_URL}?searchWord={encoded_name}"

    html = fetch_html(url)
    soup = get_soup(html)

    results = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all(["th", "td"])

            # 선수 조회 결과는 보통 7칸입니다.
            # 등번호 / 선수명 / 팀명 / 포지션 / 생년월일 / 체격 / 출신교
            if len(cells) < 7:
                continue

            cell_texts = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]

            # 헤더 행이면 건너뜁니다.
            if "선수명" in cell_texts:
                continue

            back_no = cell_texts[0]
            player_name = cell_texts[1]
            team = cell_texts[2]
            position = cell_texts[3]
            birthdate = cell_texts[4]
            height_weight = cell_texts[5]
            school = cell_texts[6]

            name_cell = cells[1]
            link = name_cell.find("a")
            href = link.get("href") if link else None

            profile_url = make_profile_url(href)
            player_id = extract_player_id_from_url(profile_url)

            if not player_name or player_name == "선수명":
                continue

            results.append({
                "player_id": player_id,
                "name": player_name,
                "team": team,
                "position": position,
                "back_no": back_no,
                "birthdate": birthdate,
                "height_weight": height_weight,
                "school": school,
                "profile_url": profile_url,
            })

    PLAYER_SEARCH_CACHE[name] = results

    # KBO 서버에 너무 빠르게 요청하지 않도록 아주 짧게 쉽니다.
    time.sleep(0.1)

    return results


def find_matching_search_result(player, search_results):
    """
    registered_players의 선수 1명과
    Player/Search.aspx 검색 결과 중 맞는 선수를 연결합니다.

    우선순위:
    1. 이름 + 팀 + 포지션이 모두 같은 결과
    2. 이름 + 팀이 같은 결과
    """
    name = player["name"]
    team = player["team"]
    roster_position = player["roster_position"]

    # 1순위: 이름 + 팀 + 포지션이 모두 같은 경우
    for result in search_results:
        if (
            result["name"] == name
            and result["team"] == team
            and result["position"] == roster_position
        ):
            return result

    # 2순위: 이름 + 팀이 같은 경우
    for result in search_results:
        if (
            result["name"] == name
            and result["team"] == team
        ):
            return result

    return None


def find_unique_same_name_result(player, search_results):
    """
    RegisterAll 파싱에서 팀이 잘못 잡혔을 가능성이 있을 때,
    KBO 선수 검색 결과를 이용해 보수적으로 팀을 보정할 후보를 찾습니다.

    조건:
    - 이름이 정확히 같아야 함
    - 검색 결과가 KBO 10개 팀 중 하나여야 함
    - 타자/투수 fantasy 구분이 같아야 함
    - 후보가 정확히 1명이어야 함

    후보가 여러 명이면 자동 보정하지 않습니다.
    """
    name = player["name"]
    expected_type = player["fantasy_position_type"]

    candidates = []

    for result in search_results:
        if result.get("name") != name:
            continue

        result_team = result.get("team")
        result_position = result.get("position")

        if result_team not in TEAM_NAMES:
            continue

        if result_position not in PLAYER_POSITIONS:
            continue

        if get_fantasy_position_type(result_position) != expected_type:
            continue

        candidates.append(result)

    if len(candidates) == 1:
        return candidates[0]

    return None


def apply_search_result_to_player(player, matched, *, correct_team=False):
    """
    검색 결과 정보를 registered player dict에 반영합니다.
    """
    if correct_team and matched.get("team") in TEAM_NAMES:
        old_team = player.get("team")
        new_team = matched.get("team")

        if old_team != new_team:
            print(
                f"[팀 보정] {player['name']} {player['fantasy_position_type']}: "
                f"{old_team} -> {new_team}"
            )
            player["team"] = new_team

    if matched.get("position") in PLAYER_POSITIONS:
        player["roster_position"] = matched["position"]
        player["fantasy_position_type"] = get_fantasy_position_type(matched["position"])

    if matched.get("player_id"):
        player["player_id"] = matched["player_id"]

    if matched.get("profile_url"):
        player["profile_url"] = matched["profile_url"]

    if matched.get("birthdate"):
        player["birthdate"] = matched["birthdate"]

    if matched.get("height_weight"):
        player["height_weight"] = matched["height_weight"]

    if matched.get("back_no"):
        player["back_no"] = matched["back_no"]

    return player


def enrich_players_from_search(players):
    """
    RegisterAll.aspx에서 가져온 선수 목록을
    Player/Search.aspx 검색 결과로 보강합니다.

    보강하는 값:
    - player_id
    - profile_url
    - birthdate
    - height_weight
    - back_no
    """
    print("선수 조회 페이지 정보 보강 시작")

    enriched_players = []

    success_count = 0
    fail_count = 0

    for index, player in enumerate(players, start=1):
        try:
            search_results = search_player_by_name(player["name"])
            matched = find_matching_search_result(player, search_results)

            if matched:
                # 검색 결과에서 더 정확한 정보가 있으면 채웁니다.
                player = apply_search_result_to_player(player, matched, correct_team=False)
                success_count += 1
            else:
                # RegisterAll 파싱에서 팀이 잘못 잡힌 경우를 보수적으로 보정합니다.
                # 예: 삼성 선수들이 KT로 저장되는 문제 방지.
                unique_match = find_unique_same_name_result(player, search_results)

                if unique_match:
                    player = apply_search_result_to_player(player, unique_match, correct_team=True)
                    success_count += 1
                else:
                    fail_count += 1

            enriched_players.append(player)

        except Exception as e:
            fail_count += 1
            enriched_players.append(player)
            print(f"[검색 보강 실패] {player['team']} {player['name']} {player['roster_position']}: {e}")

        # 너무 많은 로그가 찍히지 않게 50명마다 진행 상황을 출력합니다.
        if index % 50 == 0:
            print(f"검색 보강 진행 중: {index}/{len(players)}명 처리")

    print(f"선수 조회 페이지 정보 보강 성공 수: {success_count}")
    print(f"선수 조회 페이지 정보 보강 실패 수: {fail_count}")

    return enriched_players, success_count, fail_count


def parse_throw_bat_from_profile(profile_url):
    """
    KBO 선수 상세 페이지에서 투타유형을 가져옵니다.

    예:
    포지션: 외야수(우투우타)
    포지션: 투수(좌투좌타)

    여기서 괄호 안의 값을 throw_bat으로 저장합니다.
    """
    if not profile_url:
        return {
            "roster_position": None,
            "throw_bat": None,
        }

    if profile_url in PLAYER_PROFILE_CACHE:
        return PLAYER_PROFILE_CACHE[profile_url]

    html = fetch_html(profile_url)
    soup = get_soup(html)

    # 줄 단위가 아니라 전체 텍스트를 한 줄처럼 합쳐서 찾습니다.
    text = soup.get_text(" ", strip=True)
    text = clean_text(text)

    roster_position = None
    throw_bat = None

    match = re.search(
        r"포지션\s*:\s*([가-힣]+)\s*\(([^()]*)\)",
        text
    )

    if match:
        roster_position = match.group(1)
        throw_bat = match.group(2)

    result = {
        "roster_position": roster_position,
        "throw_bat": throw_bat,
    }

    PLAYER_PROFILE_CACHE[profile_url] = result

    # KBO 서버에 너무 빠르게 요청하지 않도록 짧게 쉽니다.
    time.sleep(0.1)

    return result


def enrich_players_throw_bat(players):
    """
    선수 상세 페이지 profile_url에 접속해서
    전 구단 선수의 투타유형을 보강합니다.

    보강하는 값:
    - throw_bat

    예:
    우투우타
    좌투좌타
    우투좌타
    좌투우타
    """
    print("선수 상세 페이지 투타유형 보강 시작")

    enriched_players = []

    success_count = 0
    fail_count = 0
    already_count = 0
    failure_details = []

    def remember_failure(player, reason, profile_url=None, parsed_position=None):
        """투타유형 보강 실패자를 로그에 남기기 위한 내부 helper입니다."""
        failure_details.append({
            "team": player.get("team") or "-",
            "name": player.get("name") or "-",
            "roster_position": player.get("roster_position") or "-",
            "fantasy_position_type": player.get("fantasy_position_type") or "-",
            "back_no": player.get("back_no") or "-",
            "player_id": player.get("player_id") or "-",
            "profile_url": profile_url or player.get("profile_url") or "-",
            "parsed_position": parsed_position or "-",
            "reason": reason,
        })

    for index, player in enumerate(players, start=1):
        # 이미 투타유형이 있으면 다시 요청하지 않습니다.
        # 예: KT 선수들은 Register.aspx에서 이미 들어와 있을 수 있습니다.
        if player.get("throw_bat"):
            already_count += 1
            enriched_players.append(player)
            continue

        profile_url = player.get("profile_url")

        if not profile_url:
            fail_count += 1
            remember_failure(player, "profile_url 없음", profile_url=profile_url)
            enriched_players.append(player)
            continue

        try:
            result = parse_throw_bat_from_profile(profile_url)

            if result.get("throw_bat"):
                player["throw_bat"] = result["throw_bat"]
                success_count += 1
            else:
                fail_count += 1
                remember_failure(
                    player,
                    "상세 페이지에서 투타유형 패턴을 찾지 못함",
                    profile_url=profile_url,
                    parsed_position=result.get("roster_position") if result else None,
                )

            enriched_players.append(player)

        except Exception as e:
            fail_count += 1
            enriched_players.append(player)
            remember_failure(player, f"상세 페이지 요청/파싱 예외: {e}", profile_url=profile_url)
            print(f"[투타유형 보강 실패] {player.get('team')} {player.get('name')}: {e}")

        if index % 50 == 0:
            print(f"투타유형 보강 진행 중: {index}/{len(players)}명 처리")

    print(f"투타유형 이미 존재한 선수 수: {already_count}")
    print(f"투타유형 보강 성공 수: {success_count}")
    print(f"투타유형 보강 실패 수: {fail_count}")

    if failure_details:
        print("투타유형 보강 실패 상세:")
        for item in failure_details:
            print(
                "- "
                f"{item['team']} {item['name']} "
                f"(등록포지션={item['roster_position']}, "
                f"fantasy={item['fantasy_position_type']}, "
                f"등번호={item['back_no']}, "
                f"player_id={item['player_id']}) "
                f"reason={item['reason']} "
                f"parsed_position={item['parsed_position']} "
                f"profile_url={item['profile_url']}"
            )

    return enriched_players, success_count, fail_count, already_count


def merge_players(summary_players, detailed_players):
    """
    전체 등록 현황에서 가져온 선수 목록과
    상세 등록 현황에서 가져온 선수 정보를 합칩니다.

    기준:
    이름 + 팀 + 등록 포지션

    summary_players:
    - 전체 10개 팀 기준
    - RegisterAll.aspx에서 가져온 목록

    detailed_players:
    - 현재는 기본 Register.aspx에서 보이는 KT 상세 정보
    """
    merged = {}

    for player in summary_players:
        key = (
            player["name"],
            player["team"],
            player["roster_position"],
        )
        merged[key] = player

    for player in detailed_players:
        if not player.get("team"):
            continue

        key = (
            player["name"],
            player["team"],
            player["roster_position"],
        )

        if key in merged:
            old = merged[key]

            # 상세 페이지에서 얻은 값이 있으면 기존 값을 채웁니다.
            for field in [
                "player_id",
                "throw_bat",
                "birthdate",
                "height_weight",
                "profile_url",
                "source_date",
            ]:
                if player.get(field):
                    old[field] = player[field]

            if player.get("back_no"):
                old["back_no"] = player["back_no"]

            merged[key] = old
        else:
            # Register.aspx 기본 상세 페이지는 특정 구단 탭/기본 선택 상태의 영향으로
            # 다른 팀 선수를 잘못된 팀으로 섞어 가져오는 경우가 있습니다.
            # 이 detailed-only row를 새 선수로 추가하면 기존 올바른 RegisterAll 선수 row가
            # 나중에 player_id 기준 업데이트로 다시 잘못된 팀으로 이동할 수 있습니다.
            # 따라서 상세 페이지 정보는 RegisterAll에서 이미 확인된 같은 팀+이름+포지션 row에만
            # 보강하고, detailed-only row는 저장 대상에서 제외합니다.
            continue

    return list(merged.values())


def upsert_registered_player(conn, player):
    """
    registered_players 테이블에 선수를 저장하거나 업데이트합니다.

    player_id가 있으면 player_id 기준으로 먼저 찾고,
    player_id가 없으면 이름 + 팀 + 등록 포지션 기준으로 찾습니다.
    """
    c = conn.cursor()

    existing = None

    if player.get("player_id"):
        existing = c.execute("""
            SELECT id
            FROM registered_players
            WHERE player_id = ?
        """, (player["player_id"],)).fetchone()

    if existing is None:
        existing = c.execute("""
            SELECT id
            FROM registered_players
            WHERE name = ?
              AND team = ?
              AND roster_position = ?
        """, (
            player["name"],
            player["team"],
            player["roster_position"],
        )).fetchone()

    # 가격 계산 중 경기 기록에는 등장했지만 KBO 등록 선수 목록에는 아직 없던 선수를
    # score_auto_registered 방식으로 임시 등록했을 수 있습니다.
    # 이후 KBO 등록 동기화에서 같은 이름/팀/판타지 구분 선수가 들어오면
    # 새 row를 중복 생성하지 말고 기존 임시 row를 공식 등록 정보로 갱신합니다.
    if existing is None:
        existing = c.execute("""
            SELECT id
            FROM registered_players
            WHERE name = ?
              AND team = ?
              AND fantasy_position_type = ?
            ORDER BY
              CASE WHEN detail_position_source = 'score_auto_registered' THEN 0 ELSE 1 END,
              id ASC
            LIMIT 1
        """, (
            player["name"],
            player["team"],
            player["fantasy_position_type"],
        )).fetchone()

    # 이전 파싱 오류로 같은 선수가 잘못된 팀에 저장되어 있을 수 있습니다.
    # 정확한 팀 row가 아직 없고, 같은 이름+fantasy 구분의 다른 팀 row가 딱 1개라면
    # 새 row를 만들지 않고 그 row를 공식 팀으로 이동시켜 중복/말소 오표시를 줄입니다.
    if existing is None:
        params = [player["name"], player["fantasy_position_type"], player["team"]]
        player_id_condition = ""

        if player.get("player_id"):
            player_id_condition = "AND (player_id IS NULL OR player_id = ?)"
            params.append(player["player_id"])

        wrong_team_rows = c.execute(f"""
            SELECT id, team, player_id
            FROM registered_players
            WHERE name = ?
              AND fantasy_position_type = ?
              AND team <> ?
              {player_id_condition}
            ORDER BY is_active DESC, id ASC
        """, params).fetchall()

        if len(wrong_team_rows) == 1:
            wrong_row = wrong_team_rows[0]
            print(
                f"[기존 row 팀 이동] {player['name']} {player['fantasy_position_type']}: "
                f"{wrong_row['team']} -> {player['team']} (id={wrong_row['id']})"
            )
            existing = wrong_row

    if existing:
        c.execute("""
            UPDATE registered_players
            SET
                player_id = COALESCE(?, player_id),
                name = ?,
                team = ?,
                team_id = ?,
                roster_position = ?,
                fantasy_position_type = ?,
                back_no = ?,
                throw_bat = COALESCE(?, throw_bat),
                birthdate = COALESCE(?, birthdate),
                height_weight = COALESCE(?, height_weight),
                profile_url = COALESCE(?, profile_url),
                is_active = ?,
                source_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            player.get("player_id"),
            player["name"],
            player["team"],
            player.get("team_id"),
            player["roster_position"],
            player["fantasy_position_type"],
            player.get("back_no"),
            player.get("throw_bat"),
            player.get("birthdate"),
            player.get("height_weight"),
            player.get("profile_url"),
            player.get("is_active", 1),
            player.get("source_date"),
            existing["id"],
        ))

        return "updated"

    c.execute("""
        INSERT INTO registered_players (
            player_id,
            name,
            team,
            team_id,
            roster_position,
            fantasy_position_type,
            back_no,
            throw_bat,
            birthdate,
            height_weight,
            profile_url,
            is_active,
            source_date,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        player.get("player_id"),
        player["name"],
        player["team"],
        player.get("team_id"),
        player["roster_position"],
        player["fantasy_position_type"],
        player.get("back_no"),
        player.get("throw_bat"),
        player.get("birthdate"),
        player.get("height_weight"),
        player.get("profile_url"),
        player.get("is_active", 1),
        player.get("source_date"),
    ))

    return "inserted"


def save_registered_players(players):
    """
    파싱한 선수 목록을 DB에 저장합니다.

    1. 가져온 선수가 1명 이상인지 확인합니다.
    2. 기존 registered_players를 전부 is_active = 0으로 바꿉니다.
    3. 이번에 가져온 선수들을 저장하면서 is_active = 1로 바꿉니다.
    """
    inserted_count = 0
    updated_count = 0

    if not players:
        print("가져온 선수가 0명이라 DB를 수정하지 않습니다.")
        return inserted_count, updated_count

    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
            UPDATE registered_players
            SET is_active = 0,
                updated_at = CURRENT_TIMESTAMP
        """)

        for player in players:
            result = upsert_registered_player(conn, player)

            if result == "inserted":
                inserted_count += 1
            else:
                updated_count += 1

    return inserted_count, updated_count


def infer_fallback_detail_position(conn, player_name, team, fantasy_position_type, latest_game_date):
    """
    KBO 등록 명단에는 없지만 fantasy_daily_scores에는 존재하는 선수의
    최소 상세 포지션을 안전하게 추정합니다.

    - 타자는 팀 편집에 바로 사용되지 않도록 detail_position을 '미등록'으로 둡니다.
    - 투수는 raw_pitcher_stats의 실제 선발 기록이 있으면 선발투수, 아니면 불펜투수로 둡니다.
    """
    if fantasy_position_type != "pitcher":
        return "미등록"

    row = conn.execute("""
        SELECT COUNT(*) AS start_count
        FROM raw_pitcher_stats
        WHERE player_name = ?
          AND team = ?
          AND game_date <= ?
          AND is_starting_pitcher = 1
    """, (player_name, team, latest_game_date)).fetchone()

    if int(row["start_count"] or 0) > 0:
        return "선발투수"

    return "불펜투수"


def insert_score_fallback_registered_players(season_start_date="2026-03-28"):
    """
    공식 registered_players에는 없지만 실제 경기 점수에는 존재하는 선수를
    말소/비활성 fallback row로 보강합니다.

    원칙:
    - 같은 이름+팀의 registered_players row가 하나라도 있으면 새 row를 만들지 않습니다.
      예: 투수가 대타/대주자처럼 batter 100점 row를 가진 경우 중복 batter row 생성 방지.
    - 새 row는 is_active=0으로 저장합니다.
    - 기존 official row, 가격 row, 유저 팀 row는 삭제/변경하지 않습니다.
    """
    inserted_count = 0

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                fds.player_name,
                fds.team,
                fds.position_type,
                COUNT(DISTINCT fds.game_id) AS game_count,
                MAX(fds.game_date) AS latest_game_date,
                SUM(fds.points) AS total_points
            FROM fantasy_daily_scores fds
            LEFT JOIN registered_players rp_exact
              ON rp_exact.name = fds.player_name
             AND rp_exact.team = fds.team
             AND rp_exact.fantasy_position_type = fds.position_type
            WHERE fds.game_date >= ?
              AND rp_exact.id IS NULL
              AND NOT EXISTS (
                    SELECT 1
                    FROM registered_players rp_any
                    WHERE rp_any.name = fds.player_name
                      AND rp_any.team = fds.team
              )
            GROUP BY fds.player_name, fds.team, fds.position_type
            ORDER BY total_points DESC, latest_game_date DESC, fds.team, fds.player_name
        """, (season_start_date,)).fetchall()

        skipped_same_name_team_count = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM (
                SELECT fds.player_name, fds.team, fds.position_type
                FROM fantasy_daily_scores fds
                LEFT JOIN registered_players rp_exact
                  ON rp_exact.name = fds.player_name
                 AND rp_exact.team = fds.team
                 AND rp_exact.fantasy_position_type = fds.position_type
                WHERE fds.game_date >= ?
                  AND rp_exact.id IS NULL
                  AND EXISTS (
                        SELECT 1
                        FROM registered_players rp_any
                        WHERE rp_any.name = fds.player_name
                          AND rp_any.team = fds.team
                  )
                GROUP BY fds.player_name, fds.team, fds.position_type
            )
        """, (season_start_date,)).fetchone()["cnt"]

        if not rows:
            print("경기 기록 기반 fallback 등록 선수 추가: 0명")
            if skipped_same_name_team_count:
                print(f"동일 이름+팀 기존 row가 있어 fallback 생성을 건너뛴 기록: {skipped_same_name_team_count}건")
            return 0

        print("경기 기록 기반 fallback 등록 선수 추가 시작")

        for row in rows:
            player_name = row["player_name"]
            team = row["team"]
            fantasy_position_type = row["position_type"]
            latest_game_date = row["latest_game_date"]

            roster_position = "투수" if fantasy_position_type == "pitcher" else "미등록"
            detail_position = infer_fallback_detail_position(
                conn,
                player_name,
                team,
                fantasy_position_type,
                latest_game_date,
            )

            conn.execute("""
                INSERT INTO registered_players (
                    player_id,
                    name,
                    team,
                    team_id,
                    roster_position,
                    fantasy_position_type,
                    back_no,
                    throw_bat,
                    birthdate,
                    height_weight,
                    profile_url,
                    is_active,
                    source_date,
                    detail_position,
                    detail_position_source,
                    detail_position_updated_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    NULL, ?, ?, NULL, ?, ?, NULL, NULL, NULL, NULL, NULL,
                    0, ?, ?, 'fantasy_daily_scores_fallback', CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """, (
                player_name,
                team,
                roster_position,
                fantasy_position_type,
                latest_game_date,
                detail_position,
            ))

            inserted_count += 1

            if inserted_count <= 20:
                print(
                    f"[fallback 등록] {player_name} / {team} / {fantasy_position_type} "
                    f"최근경기={latest_game_date} 합계={float(row['total_points'] or 0):.1f}"
                )

        if inserted_count > 20:
            print(f"... 외 {inserted_count - 20}명 fallback 등록")

        if skipped_same_name_team_count:
            print(f"동일 이름+팀 기존 row가 있어 fallback 생성을 건너뛴 기록: {skipped_same_name_team_count}건")

    print(f"경기 기록 기반 fallback 등록 선수 추가 완료: {inserted_count}명")
    return inserted_count


def print_position_summary(players):
    """
    팀별/포지션별 인원 수를 출력합니다.
    """
    summary = {}

    for player in players:
        team = player["team"]
        position = player["roster_position"]

        if team not in summary:
            summary[team] = {}

        if position not in summary[team]:
            summary[team][position] = 0

        summary[team][position] += 1

    print("팀별 선수 수 요약:")

    for team in TEAM_NAMES:
        if team not in summary:
            continue

        pitcher_count = summary[team].get("투수", 0)
        catcher_count = summary[team].get("포수", 0)
        infielder_count = summary[team].get("내야수", 0)
        outfielder_count = summary[team].get("외야수", 0)

        total = pitcher_count + catcher_count + infielder_count + outfielder_count

        print(
            f"- {team}: 총 {total}명 "
            f"(투수 {pitcher_count}, 포수 {catcher_count}, "
            f"내야수 {infielder_count}, 외야수 {outfielder_count})"
        )




def normalize_target_date(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    m = re.match(r"^(\d{4})[.-](\d{2})[.-](\d{2})$", text)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{mo}-{d}"
    raise ValueError("target_date는 YYYYMMDD 또는 YYYY-MM-DD 형식이어야 합니다.")


def iter_register_all_urls_for_target_date(target_date):
    """
    KBO RegisterAll.aspx가 날짜 파라미터를 지원할 가능성에 대비한 후보 URL 목록입니다.
    실제 사용 여부는 페이지 안 source_date가 target_date와 일치하는지로만 검증합니다.
    """
    if not target_date:
        yield REGISTER_ALL_URL
        return

    compact = target_date.replace("-", "")
    dotted = target_date.replace("-", ".")
    candidates = [
        f"{REGISTER_ALL_URL}?searchDate={compact}",
        f"{REGISTER_ALL_URL}?searchDate={target_date}",
        f"{REGISTER_ALL_URL}?date={compact}",
        f"{REGISTER_ALL_URL}?date={target_date}",
        f"{REGISTER_ALL_URL}?gameDate={compact}",
        f"{REGISTER_ALL_URL}?gameDate={target_date}",
        f"{REGISTER_ALL_URL}?selectDate={dotted}",
        REGISTER_ALL_URL,
    ]
    seen = set()
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        yield url


def fetch_register_all_html_for_target_date(target_date, failed_sources):
    best_html = None
    best_url = REGISTER_ALL_URL
    best_source_date = None

    for url in iter_register_all_urls_for_target_date(target_date):
        try:
            html = fetch_html(url)
            source_date = extract_source_date(get_soup(html))
            if best_html is None:
                best_html = html
                best_url = url
                best_source_date = source_date
            if target_date and source_date == target_date:
                return html, url, source_date
        except Exception as exc:
            failed_sources.append(f"RegisterAll 날짜 후보 실패({url}): {exc}")

    if target_date and best_source_date != target_date:
        failed_sources.append(
            f"RegisterAll 기준 날짜 불일치: 요청={target_date}, 반환={best_source_date}. "
            "가격/화면 로직은 해당 경기일 실제 출전 선수 fallback을 적용합니다."
        )

    if best_html is None:
        raise RuntimeError("RegisterAll.aspx를 가져오지 못했습니다.")

    return best_html, best_url, best_source_date

def sync_registered_players(target_date=None):
    """
    등록 선수 동기화 전체 흐름입니다.
    """
    print("등록 선수 동기화 시작")
    target_date = normalize_target_date(target_date)
    if target_date:
        print(f"요청 기준 날짜: {target_date}")

    init_db()

    failed_sources = []

    summary_players = []
    detailed_players = []

    summary_excluded_staff_count = 0
    detailed_excluded_staff_count = 0

    search_enrich_success_count = 0
    search_enrich_fail_count = 0

    throw_bat_enrich_success_count = 0
    throw_bat_enrich_fail_count = 0
    throw_bat_already_count = 0

    source_date = datetime.now().strftime("%Y-%m-%d")
    processed_teams = set()
    register_all_direct_transactions = []

    # 1. 전체 등록 현황 페이지에서 전체 팀 선수 목록과 전 구단 당일 등/말소 현황을 가져옵니다.
    try:
        all_html, register_all_source_url, register_all_source_date = fetch_register_all_html_for_target_date(
            target_date,
            failed_sources,
        )
        all_soup = get_soup(all_html)
        (
            summary_players,
            summary_excluded_staff_count,
            source_date,
            processed_teams,
        ) = parse_register_all_page(all_html)
        if register_all_source_date and register_all_source_date != source_date:
            source_date = register_all_source_date
        register_all_direct_transactions = parse_register_all_transactions_from_soup(
            all_soup,
            source_date,
            register_all_source_url,
        )
        if register_all_direct_transactions:
            print(f"RegisterAll 전 구단 직접 등/말소 transaction 파싱: {len(register_all_direct_transactions)}건")
    except Exception as e:
        failed_sources.append(f"RegisterAll.aspx: {e}")

    # 2. 선수 조회 페이지에서 player_id, 생년월일, 체격, profile_url을 보강합니다.
    if summary_players:
        (
            summary_players,
            search_enrich_success_count,
            search_enrich_fail_count,
        ) = enrich_players_from_search(summary_players)

    # 3. 선수 상세 페이지에서 투타유형을 보강합니다.
    if summary_players:
        (
            summary_players,
            throw_bat_enrich_success_count,
            throw_bat_enrich_fail_count,
            throw_bat_already_count,
        ) = enrich_players_throw_bat(summary_players)

    # 4. 구단별 등록 현황 페이지에서 가져올 수 있는 상세 정보와 당일 등/말소 transaction을 보조로 가져옵니다.
    # active 여부의 최종 기준은 RegisterAll.aspx 전체 등록 현황입니다.
    detailed_pages = {}
    register_transactions = []
    try:
        detailed_pages, detail_failures = collect_detailed_register_pages()
        failed_sources.extend(detail_failures)
        for detail_team, (detail_html, detail_url) in detailed_pages.items():
            (
                team_detailed_players,
                team_excluded_staff_count,
                detail_source_date,
            ) = parse_detailed_register_page(detail_html)
            detailed_players.extend(team_detailed_players)
            detailed_excluded_staff_count += team_excluded_staff_count
            if detail_source_date:
                source_date = detail_source_date
            register_transactions.extend(
                parse_register_transactions_from_soup(
                    get_soup(detail_html),
                    detail_team,
                    detail_source_date or source_date,
                    detail_url,
                )
            )
    except Exception as e:
        failed_sources.append(f"Register.aspx 구단별 상세 수집: {e}")

    # 5. 전체 목록과 상세 정보를 합칩니다.
    players = merge_players(summary_players, detailed_players)

    # RegisterAll.aspx 하단의 전 구단 1군 등록/말소 현황을 먼저 반영합니다.
    # Register.aspx 구단별 탭 직접 수집이 KT만 열리는 경우에도, 이 표가 전 구단 transaction의 1차 기준입니다.
    register_transactions = merge_register_transactions(register_transactions, register_all_direct_transactions)

    # 6. RegisterAll 기준 active 변화분을 transaction 참고 데이터로 보강합니다.
    # Register.aspx 팀 탭이 KT만 수집되는 경우에도 전 구단 active 변화는 놓치지 않기 위함입니다.
    try:
        with get_conn() as conn:
            previous_active_snapshot = get_previous_active_registered_snapshot(conn)
        inferred_transactions = build_register_transactions_from_active_diff(
            previous_active_snapshot,
            players,
            source_date,
        )
        if inferred_transactions:
            print(f"RegisterAll active diff transaction 보강: {len(inferred_transactions)}건")
        register_transactions = merge_register_transactions(register_transactions, inferred_transactions)
    except Exception as e:
        failed_sources.append(f"RegisterAll active diff transaction 보강 실패: {e}")

    # 7. DB에 저장합니다.
    inserted_count, updated_count = save_registered_players(players)
    saved_transaction_count = save_register_transactions(register_transactions)

    # 중요:
    # 과거 fantasy_daily_scores에만 존재하는 선수를 등록 선수로 대량 보강하면
    # 가격 계산 대상과 percentile 시장이 비정상적으로 커질 수 있습니다.
    # 따라서 자동 fallback 등록은 더 이상 기본 동기화에서 실행하지 않습니다.
    # 공식 RegisterAll.aspx 기반 등록/말소 상태만 이 스크립트가 갱신합니다.
    fallback_inserted_count = 0

    total_saved_count = inserted_count + updated_count
    total_excluded_staff_count = summary_excluded_staff_count + detailed_excluded_staff_count

    print(f"기준 날짜: {source_date}")
    if target_date and source_date != target_date:
        print(f"주의: 요청 기준 날짜({target_date})와 KBO 등록 현황 기준 날짜({source_date})가 다릅니다.")
    print(f"처리한 팀 수: {len(processed_teams)}")
    print(f"전체 등록 페이지에서 파싱한 선수 수: {len(summary_players)}")
    print(f"상세 등록 페이지에서 파싱한 선수 수: {len(detailed_players)}")
    print(f"구단별 상세 페이지 수집 팀 수: {len(detailed_pages) if 'detailed_pages' in locals() else 0}/10")
    print(f"RegisterAll 직접 등/말소 transaction 수: {len(register_all_direct_transactions) if 'register_all_direct_transactions' in locals() else 0}")
    print(f"구단별/전체 등/말소 transaction 저장 수: {saved_transaction_count if 'saved_transaction_count' in locals() else 0}")
    print(f"선수 조회 페이지 보강 성공 수: {search_enrich_success_count}")
    print(f"선수 조회 페이지 보강 실패 수: {search_enrich_fail_count}")
    print(f"투타유형 이미 존재한 선수 수: {throw_bat_already_count}")
    print(f"투타유형 보강 성공 수: {throw_bat_enrich_success_count}")
    print(f"투타유형 보강 실패 수: {throw_bat_enrich_fail_count}")
    print(f"최종 합친 선수 수: {len(players)}")
    print(f"새로 저장한 선수 수: {inserted_count}")
    print(f"업데이트한 선수 수: {updated_count}")
    print("fallback 비활성 자동 등록: 비활성화됨")
    print(f"저장/업데이트한 선수 수: {total_saved_count}")
    print(f"제외한 감독/코치 수: {total_excluded_staff_count}")
    print(f"실패한 소스 목록: {failed_sources}")

    print_position_summary(players)

    print("등록 선수 동기화 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", dest="target_date", default=None, help="KBO 등록 현황 기준 날짜. YYYYMMDD 또는 YYYY-MM-DD")
    args = parser.parse_args()
    sync_registered_players(target_date=args.target_date)