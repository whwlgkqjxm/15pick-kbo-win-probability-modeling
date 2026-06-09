"""
타자와 투수의 판타지 점수를 계산하는 파일입니다.

중요 규칙:

1. 타자는 장타 중복 점수를 주면 안 됩니다.
   예를 들어 2루타는 안타에도 포함되지만,
   안타 점수 + 2루타 점수를 둘 다 주면 안 됩니다.

   그래서 단타를 이렇게 계산합니다.

   단타 = 안타 - 2루타 - 3루타 - 홈런

2. 타점, 득점, 결승타는 장타와 별도 이벤트입니다.
   그래서 안타/2루타/3루타/홈런 점수와 중복으로 더해집니다.

   예:
   홈런 + 타점 + 득점
   홈런 + 타점 + 득점 + 결승타

3. 타자 출전 점수는 타자 기록표에 row가 있으면 +100점을 줍니다.
   타수 0이어도 대주자/대수비/교체 출전으로 row가 있으면 출전으로 봅니다.

4. 투수 출전 점수는 투수 기록표에 row가 있으면 +100점을 줍니다.

5. 투수 이닝은 정수 이닝만 점수화합니다.
   예를 들어 6.2이닝이면 6이닝만 점수로 반영합니다.
   2/3이닝만 던졌으면 0이닝으로 처리합니다.
"""

import re
from decimal import Decimal, ROUND_HALF_UP

from config import (
    # 타자 점수
    BATTER_APPEARANCE_POINT,
    HIT_POINT,
    DOUBLE_POINT,
    TRIPLE_POINT,
    HOME_RUN_POINT,
    RBI_POINT,
    RUN_POINT,
    GAME_WINNING_HIT_POINT,
    HIT_BY_PITCH_POINT,
    WALK_POINT,
    STOLEN_BASE_POINT,
    DOUBLE_PLAY_POINT,
    BATTER_STRIKEOUT_POINT,

    # 투수 점수
    PITCHER_APPEARANCE_POINT,
    WIN_POINT,
    LOSS_POINT,
    HOLD_POINT,
    SAVE_POINT,
    INNING_POINT,
    STRIKEOUT_POINT,
    PITCH_COUNT_POINT,
    HIT_ALLOWED_POINT,
    RUN_ALLOWED_POINT,
    STARTING_PITCHER_SCORE_MULTIPLIER,
    BULLPEN_PITCHER_SCORE_MULTIPLIER,
)


def safe_int(value):
    """
    값을 안전하게 정수로 바꾸는 함수입니다.

    예:
    "3" -> 3
    "" -> 0
    None -> 0
    변환 불가능한 값 -> 0
    """
    try:
        if value is None:
            return 0

        value = str(value).strip()

        if value == "":
            return 0

        return int(value)

    except ValueError:
        return 0


def parse_innings_to_completed(raw_innings):
    """
    투수 이닝 문자열에서 완성된 정수 이닝만 가져옵니다.

    예:
    "6"     -> 6
    "6.2"   -> 6
    "6.1"   -> 6
    "6 2/3" -> 6
    "1 1/3" -> 1
    "2/3"   -> 0
    ""      -> 0
    None    -> 0
    """

    if raw_innings is None:
        return 0

    text = str(raw_innings).strip()

    if text == "":
        return 0

    # "6 2/3" 또는 "1 1/3" 같은 형태 처리
    match = re.match(r"^(\d+)\s+\d+/\d+$", text)
    if match:
        return int(match.group(1))

    # "2/3"처럼 정수 이닝 없이 분수만 있는 경우
    match = re.match(r"^\d+/\d+$", text)
    if match:
        return 0

    # "6.2" 또는 "6.1" 같은 KBO식 이닝 표기 처리
    # 소수점 뒤는 아웃 수이므로 점수 계산에서는 버립니다.
    match = re.match(r"^(\d+)\.\d+$", text)
    if match:
        return int(match.group(1))

    # "6"처럼 그냥 정수인 경우
    match = re.match(r"^\d+$", text)
    if match:
        return int(text)

    # 혹시 앞부분에 숫자가 있는 이상한 형태도 방어적으로 처리
    match = re.match(r"^(\d+)", text)
    if match:
        return int(match.group(1))

    return 0



def round_half_up_to_int_float(value):
    """
    판타지 점수를 정수 단위로 반올림한 뒤 .0 형태의 float로 반환합니다.

    선발투수 1.4배 적용 후 2221.8 같은 값이 나올 수 있으므로
    일반적인 반올림 방식(0.5 이상 올림)을 명시적으로 사용합니다.
    """
    decimal_value = Decimal(str(value or 0))
    return float(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calc_batter_points(stats):
    """
    타자 점수를 계산합니다.

    stats는 이런 형태의 dict입니다.

    {
        "hits": 3,
        "doubles": 1,
        "triples": 0,
        "home_runs": 1,
        "rbi": 2,
        "runs": 1,
        "game_winning_hit": 0,
        "double_play": 1,
        "hit_by_pitch": 1,
        "walks": 1,
        "stolen_bases": 1,
        "strikeouts": 2
    }

    return:
    total_points, detail
    """

    hits = safe_int(stats.get("hits"))
    doubles = safe_int(stats.get("doubles"))
    triples = safe_int(stats.get("triples"))
    home_runs = safe_int(stats.get("home_runs"))
    rbi = safe_int(stats.get("rbi"))
    runs = safe_int(stats.get("runs"))
    game_winning_hit = safe_int(stats.get("game_winning_hit"))
    double_play = safe_int(stats.get("double_play"))

    hit_by_pitch = safe_int(stats.get("hit_by_pitch"))
    walks = safe_int(stats.get("walks"))
    stolen_bases = safe_int(stats.get("stolen_bases"))
    strikeouts = safe_int(stats.get("strikeouts"))

    # 장타 중복 방지
    # 안타에서 2루타, 3루타, 홈런을 빼서 단타만 계산합니다.
    single_hits = hits - doubles - triples - home_runs

    # 혹시 데이터 오류로 음수가 나오면 0으로 막습니다.
    if single_hits < 0:
        single_hits = 0

    detail = {
        # 타자 기록표에 row가 있으면 출전한 것으로 보고 +100점
        "appearance": BATTER_APPEARANCE_POINT,

        # 장타 계열: 서로 중복 계산 금지
        "single_hits": single_hits * HIT_POINT,
        "doubles": doubles * DOUBLE_POINT,
        "triples": triples * TRIPLE_POINT,
        "home_runs": home_runs * HOME_RUN_POINT,

        # 별도 이벤트: 장타/안타와 중복으로 더해짐
        "rbi": rbi * RBI_POINT,
        "runs": runs * RUN_POINT,
        "game_winning_hit": game_winning_hit * GAME_WINNING_HIT_POINT,
        # 볼넷(4구)과 몸에 맞는 볼(사구)은 화면과 점수 detail에서 "출루"로 합쳐 표시합니다.
        # raw_batter_stats에는 검증을 위해 walks/hit_by_pitch를 각각 따로 저장합니다.
        "on_base": (walks * WALK_POINT) + (hit_by_pitch * HIT_BY_PITCH_POINT),
        "stolen_bases": stolen_bases * STOLEN_BASE_POINT,

        # 감점 항목
        "double_play": double_play * DOUBLE_PLAY_POINT,
        "strikeouts": strikeouts * BATTER_STRIKEOUT_POINT,
    }

    total_points = sum(detail.values())

    return total_points, detail


def calc_pitcher_points(stats):
    """
    투수 점수를 계산합니다.

    stats는 이런 형태의 dict입니다.

    {
        "wins": 1,
        "losses": 0,
        "holds": 0,
        "saves": 0,
        "innings_pitched_raw": "6.2",
        "strikeouts": 5,
        "runs_allowed": 2,
        "pitch_count": 87,
        "hits_allowed": 6
    }

    return:
    total_points, detail, completed_innings
    """

    wins = safe_int(stats.get("wins"))
    losses = safe_int(stats.get("losses"))
    holds = safe_int(stats.get("holds"))
    saves = safe_int(stats.get("saves"))
    strikeouts = safe_int(stats.get("strikeouts"))
    runs_allowed = safe_int(stats.get("runs_allowed"))
    pitch_count = safe_int(stats.get("pitch_count"))
    hits_allowed = safe_int(stats.get("hits_allowed"))

    completed_innings = parse_innings_to_completed(
        stats.get("innings_pitched_raw")
    )

    detail = {
        # 투수 기록표에 row가 있으면 출전한 것으로 보고 +100점
        "appearance": PITCHER_APPEARANCE_POINT,

        "wins": wins * WIN_POINT,
        "losses": losses * LOSS_POINT,
        "holds": holds * HOLD_POINT,
        "saves": saves * SAVE_POINT,
        "completed_innings": completed_innings * INNING_POINT,
        "strikeouts": strikeouts * STRIKEOUT_POINT,
        "pitch_count": pitch_count * PITCH_COUNT_POINT,
        "hits_allowed": hits_allowed * HIT_ALLOWED_POINT,
        "runs_allowed": runs_allowed * RUN_ALLOWED_POINT,
    }

    base_total_points = sum(detail.values())

    is_starting_pitcher = safe_int(stats.get("is_starting_pitcher")) == 1

    if is_starting_pitcher:
        multiplied_total = round_half_up_to_int_float(
            base_total_points * STARTING_PITCHER_SCORE_MULTIPLIER
        )
        detail["starting_pitcher_bonus"] = round_half_up_to_int_float(
            multiplied_total - base_total_points
        )
        total_points = multiplied_total
    else:
        multiplied_total = round_half_up_to_int_float(
            base_total_points * BULLPEN_PITCHER_SCORE_MULTIPLIER
        )
        detail["bullpen_pitcher_bonus"] = round_half_up_to_int_float(
            multiplied_total - base_total_points
        )
        total_points = multiplied_total

    return total_points, detail, completed_innings


if __name__ == "__main__":
    # 이 아래는 scoring.py가 제대로 작동하는지 확인하는 테스트입니다.

    print("타자 점수 테스트")

    batter_test = {
        "hits": 3,
        "doubles": 1,
        "triples": 0,
        "home_runs": 1,
        "rbi": 2,
        "runs": 1,
        "game_winning_hit": 0,
        "double_play": 1,
        "hit_by_pitch": 1,
        "walks": 1,
        "stolen_bases": 1,
        "strikeouts": 2,
    }

    batter_total, batter_detail = calc_batter_points(batter_test)

    print("타자 총점:", batter_total)
    print("타자 세부 점수:", batter_detail)

    print()
    print("투수 점수 테스트")

    pitcher_test = {
        "wins": 1,
        "losses": 0,
        "holds": 0,
        "saves": 1,
        "innings_pitched_raw": "6.2",
        "strikeouts": 5,
        "runs_allowed": 2,
        "pitch_count": 87,
        "hits_allowed": 6,
    }

    pitcher_total, pitcher_detail, completed = calc_pitcher_points(pitcher_test)

    print("정수 이닝:", completed)
    print("투수 총점:", pitcher_total)
    print("투수 세부 점수:", pitcher_detail)

    print()
    print("이닝 변환 테스트")
    print("6.2 ->", parse_innings_to_completed("6.2"))
    print("6 2/3 ->", parse_innings_to_completed("6 2/3"))
    print("2/3 ->", parse_innings_to_completed("2/3"))
    print("1 1/3 ->", parse_innings_to_completed("1 1/3"))