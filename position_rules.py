"""MyPick roster slot / player detail-position eligibility rules.

This module is deliberately small and dependency-free so app.py,
team score recalculation scripts, sync scripts, and reports all use the
same slot rules.
"""

BATTER_SLOT_DETAIL_MAP = {
    "C": "포수",
    "1B": "1루수",
    "2B": "2루수",
    "3B": "3루수",
    "SS": "유격수",
    "LF": "좌익수",
    "CF": "중견수",
    "RF": "우익수",
}

PITCHER_SLOT_DETAIL_MAP = {
    "P1": "선발투수",
    "P2": "불펜투수",
    "P3": "불펜투수",
    "P4": "불펜투수",
    "P5": "불펜투수",
    "P6": "불펜투수",
}

INFIELD_DETAIL_POSITIONS = {"1루수", "2루수", "3루수", "유격수"}
OUTFIELD_DETAIL_POSITIONS = {"좌익수", "중견수", "우익수"}
EXACT_BATTER_DETAIL_POSITIONS = {"포수"} | INFIELD_DETAIL_POSITIONS | OUTFIELD_DETAIL_POSITIONS
WIDE_BATTER_DETAIL_POSITIONS = {"내야수", "외야수"}
DH_ONLY_DETAIL_POSITIONS = {"지명타자", "DH", "타자"}
NON_DEFENSIVE_BATTER_POSITIONS = DH_ONLY_DETAIL_POSITIONS | {"대타", "대주자"}

DETAIL_TO_PRIMARY_SLOT = {v: k for k, v in BATTER_SLOT_DETAIL_MAP.items()}

INFIELD_SLOTS = ["1B", "2B", "3B", "SS"]
OUTFIELD_SLOTS = ["LF", "CF", "RF"]
BULLPEN_SLOTS = ["P2", "P3", "P4", "P5", "P6"]


def clean_position(value):
    return (value or "").strip()


def slot_label(slot):
    labels = {
        "C": "포수",
        "1B": "1루수",
        "2B": "2루수",
        "3B": "3루수",
        "SS": "유격수",
        "LF": "좌익수",
        "CF": "중견수",
        "RF": "우익수",
        "UTIL": "지명타자/UTIL",
        "P1": "SP",
        "P2": "P1",
        "P3": "P2",
        "P4": "P3",
        "P5": "P4",
        "P6": "P5",
    }
    return labels.get(slot, slot)


def get_slot_requirement(slot):
    if slot in BATTER_SLOT_DETAIL_MAP:
        return {
            "position_type": "batter",
            "detail_position": BATTER_SLOT_DETAIL_MAP[slot],
            "allows_any_batter": False,
        }
    if slot == "UTIL":
        return {
            "position_type": "batter",
            "detail_position": None,
            "allows_any_batter": True,
        }
    if slot in PITCHER_SLOT_DETAIL_MAP:
        return {
            "position_type": "pitcher",
            "detail_position": PITCHER_SLOT_DETAIL_MAP[slot],
            "allows_any_batter": False,
        }
    return {
        "position_type": None,
        "detail_position": None,
        "allows_any_batter": False,
    }


def is_wide_detail_eligible_for_exact_detail(player_detail, expected_detail):
    player_detail = clean_position(player_detail)
    expected_detail = clean_position(expected_detail)
    if player_detail == expected_detail:
        return True
    if player_detail == "내야수" and expected_detail in INFIELD_DETAIL_POSITIONS:
        return True
    if player_detail == "외야수" and expected_detail in OUTFIELD_DETAIL_POSITIONS:
        return True
    return False


def get_slot_position_mismatch_reason(player_type, player_detail, slot):
    requirement = get_slot_requirement(slot)
    expected_type = requirement.get("position_type")
    expected_detail = requirement.get("detail_position")
    player_type = clean_position(player_type)
    player_detail = clean_position(player_detail)

    if expected_type is None:
        return "알 수 없는 로스터 슬롯입니다."

    if player_type != expected_type:
        expected_label = "타자" if expected_type == "batter" else "투수"
        return f"{slot_label(slot)} 슬롯에는 {expected_label}만 들어갈 수 있습니다."

    # 지명타자/UTIL 슬롯은 모든 타자, 즉 수비 포지션 타자와 DH-only 타자 모두 허용합니다.
    if slot == "UTIL":
        return None

    if expected_detail and not is_wide_detail_eligible_for_exact_detail(player_detail, expected_detail):
        return (
            f"{slot_label(slot)} 슬롯 요구 포지션은 {expected_detail}이지만 "
            f"계산일 기준 선수 포지션은 {player_detail or '미등록'}입니다."
        )

    return None


def is_player_eligible_for_slot(player_type, player_detail, slot):
    return get_slot_position_mismatch_reason(player_type, player_detail, slot) is None


def candidate_slots_for_detail(fantasy_position_type, detail_position):
    """Return preferred slots for auto-add, ordered from strict to broad to UTIL.

    Rules:
    - Exact defensive batter positions prefer their exact slot, then UTIL.
    - 내야수 is a broad infield wildcard: 1B/2B/3B/SS, then UTIL.
    - 외야수 is a broad outfield wildcard: LF/CF/RF, then UTIL.
    - 지명타자 means DH-only batter: UTIL only.
    - UTIL itself accepts every batter.
    """
    fantasy_position_type = clean_position(fantasy_position_type)
    detail_position = clean_position(detail_position)

    if fantasy_position_type == "pitcher":
        if detail_position == "선발투수":
            return ["P1"]
        if detail_position == "불펜투수":
            return list(BULLPEN_SLOTS)
        return []

    if fantasy_position_type != "batter":
        return []

    if detail_position in DETAIL_TO_PRIMARY_SLOT:
        slots = [DETAIL_TO_PRIMARY_SLOT[detail_position]]
    elif detail_position == "내야수":
        slots = list(INFIELD_SLOTS)
    elif detail_position == "외야수":
        slots = list(OUTFIELD_SLOTS)
    elif detail_position in DH_ONLY_DETAIL_POSITIONS:
        slots = []
    else:
        slots = []

    slots.append("UTIL")
    return slots


def detail_positions_for_filter(detail_position):
    """Expand a UI detail-position filter so broad positions are included.

    Example: 중견수 filter returns 중견수 + 외야수.
    Example: 1루수 filter returns 1루수 + 내야수.
    지명타자 filter returns only DH-only players.
    """
    detail_position = clean_position(detail_position)
    if not detail_position:
        return []
    if detail_position in INFIELD_DETAIL_POSITIONS:
        return [detail_position, "내야수"]
    if detail_position in OUTFIELD_DETAIL_POSITIONS:
        return [detail_position, "외야수"]
    if detail_position in DH_ONLY_DETAIL_POSITIONS:
        return ["지명타자", "DH", "타자"]
    return [detail_position]


def normalize_batter_start_position_for_storage(detail_position):
    """Normalize parsed starting lineup position for raw_batter_stats.

    Exact defensive positions and 지명타자 are stored as starting lineup evidence.
    Pinch roles, broad positions, and empty values are not accepted as update evidence.
    """
    detail_position = clean_position(detail_position)
    if detail_position in EXACT_BATTER_DETAIL_POSITIONS:
        return detail_position
    if detail_position in DH_ONLY_DETAIL_POSITIONS:
        return "지명타자"
    return None


def is_starting_batter_defensive_position(detail_position):
    """Positions that can safely update a batter's detail_position from a start.

    DH, pinch-hit, pinch-run, broad infielder/outfielder, and empty values are not
    accepted as defensive evidence for narrowing a player's fielding slot.
    """
    detail_position = clean_position(detail_position)
    return detail_position in EXACT_BATTER_DETAIL_POSITIONS


def is_dh_only_position(detail_position):
    detail_position = clean_position(detail_position)
    return detail_position in DH_ONLY_DETAIL_POSITIONS
