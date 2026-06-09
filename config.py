"""
KBO 판타지 프로젝트의 기본 설정 파일입니다.

여기서는 크게 3가지를 관리합니다.

1. 데이터베이스 파일 위치
2. 판타지 점수 규칙
3. KBO 사이트 주소와 요청 설정

나중에 점수 규칙을 바꾸고 싶으면
다른 파일을 고치지 말고 이 파일만 수정하면 됩니다.
"""

import os


# 현재 프로젝트 폴더의 절대 경로를 구합니다.
# 예: /Users/jihochoi/Desktop/kbo_fantasy_real
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# SQLite 데이터베이스 파일 이름입니다.
# 프로젝트 폴더 안에 kbo_fantasy.db 파일이 만들어집니다.
DB_PATH = os.environ.get("MYPICK_DB_PATH") or os.path.join(BASE_DIR, "kbo_fantasy.db")


# ==========================================================
# 타자 점수 설정
# ==========================================================

# 타자 출전 점수입니다.
# 타자 기록표에 row가 있으면 출전한 것으로 보고 +100점을 줍니다.
BATTER_APPEARANCE_POINT = 100

# 단타 점수입니다.
# 주의: 2루타, 3루타, 홈런은 안타에도 포함되지만
# 중복 점수를 주면 안 되기 때문에 단타만 따로 계산합니다.
HIT_POINT = 120

# 2루타 점수
DOUBLE_POINT = 200

# 3루타 점수
TRIPLE_POINT = 300

# 홈런 점수
HOME_RUN_POINT = 500

# 타점 점수
RBI_POINT = 200

# 득점 점수
RUN_POINT = 150

# 결승타 점수
GAME_WINNING_HIT_POINT = 500

# 사구 점수
HIT_BY_PITCH_POINT = 100

# 볼넷 점수
WALK_POINT = 100

# 도루 점수
STOLEN_BASE_POINT = 100

# 병살타 점수입니다.
# 점수를 깎아야 하므로 음수로 둡니다.
DOUBLE_PLAY_POINT = -300

# 타자 삼진 점수입니다.
# 점수를 깎아야 하므로 음수로 둡니다.
BATTER_STRIKEOUT_POINT = -200


# ==========================================================
# 투수 점수 설정
# ==========================================================

# 투수 출전 점수입니다.
# 투수 기록표에 row가 있으면 출전한 것으로 보고 +100점을 줍니다.
PITCHER_APPEARANCE_POINT = 100

# 승리 점수
WIN_POINT = 500

# 패배 점수입니다.
# 점수를 깎아야 하므로 음수로 둡니다.
LOSS_POINT = -200

# 홀드 점수
HOLD_POINT = 300

# 세이브 점수
SAVE_POINT = 300

# 정수 이닝 1이닝당 점수입니다.
# 예: 6과 2/3이닝이면 6이닝만 반영합니다.
INNING_POINT = 100

# 투수 삼진 1개당 점수
STRIKEOUT_POINT = 100

# 투구수 1개당 점수입니다.
# 예: 투구수 87개면 +87점입니다.
PITCH_COUNT_POINT = 1

# 피안타 1개당 감점
HIT_ALLOWED_POINT = -50

# 실점 1점당 감점
RUN_ALLOWED_POINT = -100



# 실제 경기에서 선발 등판한 투수의 경기 점수 배율입니다.
# 팀 슬롯이 아니라 raw_pitcher_stats.is_starting_pitcher = 1인 경기만 적용합니다.
# 예: 기본 투수 점수 1587점 -> 1587 * 2.0 = 3174.0점 저장
STARTING_PITCHER_SCORE_MULTIPLIER = 2.0

# 실제 경기에서 불펜 등판한 투수의 경기 점수 배율입니다.
# raw_pitcher_stats에 투수 기록 row가 있고 is_starting_pitcher != 1인 경기만 적용합니다.
# 예: 기본 투수 점수 350점 -> 350 * 1.4 = 490.0점 저장
BULLPEN_PITCHER_SCORE_MULTIPLIER = 1.4

# ==========================================================
# KBO 사이트 주소 설정
# ==========================================================

# KBO 공식 사이트 기본 주소
KBO_BASE = "https://www.koreabaseball.com"

# 일정/결과 페이지 주소
SCHEDULE_URL = f"{KBO_BASE}/Schedule/Schedule.aspx"

# 게임센터 기본 주소
GAMECENTER_BASE = f"{KBO_BASE}/Schedule/GameCenter/Main.aspx"

# 게임센터 리뷰 페이지 주소 형식입니다.
# 실제 사용할 때 date와 game_id를 넣어서 완성합니다.
REVIEW_URL_TEMPLATE = (
    f"{KBO_BASE}/Schedule/GameCenter/Main.aspx"
    "?gameDate={date}&gameId={game_id}&section=REVIEW"
)


# ==========================================================
# 웹 요청 설정
# ==========================================================

# KBO 사이트에 요청을 보낼 때 사용할 기본 헤더입니다.
# 브라우저에서 접속하는 것처럼 보이게 하기 위해 User-Agent를 넣습니다.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 요청이 너무 오래 걸리면 멈추도록 제한하는 시간입니다.
# 단위는 초입니다.
REQUEST_TIMEOUT = 15