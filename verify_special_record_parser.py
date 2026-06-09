"""
KBO 상세기록 반복 이벤트 파서 검증 스크립트.

목적:
- 도루/2루타/3루타/병살타처럼 한 선수가 같은 기록을 2번 이상 했을 때
  KBO 표기 "정수빈2(1 3회)" 같은 압축 회차를 정확히 2개로 세는지 확인합니다.
- 홈런 다중 호수, 결승타 1회 고정, 사구/볼넷/삼진 타석칸 반복 카운트도 같이 확인합니다.

실행:
    ./venv/bin/python verify_special_record_parser.py
"""

from scraper import (
    count_event_in_inning_cells,
    count_event_mentions_in_parentheses,
    extract_special_record_counts,
    parse_game_special_records,
)


def assert_equal(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"{label}\n  actual:   {actual}\n  expected: {expected}")
    print(f"OK - {label}: {actual}")


def make_row(label, detail):
    return {
        "row": [
            {"Text": label},
            {"Text": detail},
        ]
    }


def main():
    # 괄호 안 회차 개수 계산: 기존에 문제가 났던 "1 3회" 압축 표기 포함.
    assert_equal("parentheses 7회", count_event_mentions_in_parentheses("7회"), 1)
    assert_equal("parentheses 1회 3회", count_event_mentions_in_parentheses("1회 3회"), 2)
    assert_equal("parentheses 1 3회", count_event_mentions_in_parentheses("1 3회"), 2)
    assert_equal("parentheses 1,3회", count_event_mentions_in_parentheses("1,3회"), 2)
    assert_equal("parentheses 1·3회", count_event_mentions_in_parentheses("1·3회"), 2)
    assert_equal("parentheses HR 2회2점 7회1점", count_event_mentions_in_parentheses("2회2점 7회1점 황동하"), 2)

    # 상세기록표 선수별 count.
    assert_equal(
        "stolen bases compressed suffix",
        extract_special_record_counts("정수빈2(1 3회)", "stolen_bases"),
        {"정수빈": 2},
    )
    assert_equal(
        "doubles compressed suffix",
        extract_special_record_counts("박지훈2(1 5회)", "doubles"),
        {"박지훈": 2},
    )
    assert_equal(
        "triples normal",
        extract_special_record_counts("김도영(4회)", "triples"),
        {"김도영": 1},
    )
    assert_equal(
        "double plays multiple players",
        extract_special_record_counts("이유찬(5회) 최준호(8회)", "double_play"),
        {"이유찬": 1, "최준호": 1},
    )
    assert_equal(
        "home runs multi-ho",
        extract_special_record_counts("양의지3호4호(2회2점 7회1점 황동하)", "home_runs"),
        {"양의지": 2},
    )
    assert_equal(
        "home runs single-ho",
        extract_special_record_counts("김민석3호(8회1점 홍민기)", "home_runs"),
        {"김민석": 1},
    )
    assert_equal(
        "game winning hit fixed one",
        extract_special_record_counts("김상수(7회 1사 1,3루서 우익수 땅볼)", "game_winning_hit"),
        {"김상수": 1},
    )
    assert_equal(
        "walks detail repeated",
        extract_special_record_counts("홍창기2(1 4회)", "walks"),
        {"홍창기": 2},
    )
    assert_equal(
        "hit by pitch detail repeated",
        extract_special_record_counts("최정2(2 7회)", "hit_by_pitch"),
        {"최정": 2},
    )
    assert_equal(
        "strikeouts detail repeated",
        extract_special_record_counts("박병호2(3 6회)", "strikeouts"),
        {"박병호": 2},
    )

    # 타석 결과 칸 반복 카운트. 상세기록표가 아니라 타자 row 1~12회 칸에서 세는 항목 검증.
    texts = ["", "삼진 삼진", "4구", "사구 사구", "볼넷", "헛스윙삼진"]
    inning_indices = [1, 2, 3, 4, 5]
    assert_equal(
        "inning strikeouts repeated",
        count_event_in_inning_cells(texts, inning_indices, ["삼진", "헛스윙삼진", "루킹삼진"]),
        3,
    )
    assert_equal(
        "inning walks repeated",
        count_event_in_inning_cells(texts, inning_indices, ["4구", "볼넷", "고4", "고의4구"]),
        2,
    )
    assert_equal(
        "inning HBP repeated",
        count_event_in_inning_cells(texts, inning_indices, ["사구", "몸에 맞는 볼", "몸에맞는볼"]),
        2,
    )

    # parse_game_special_records 전체 흐름 검증.
    fake_detail_table = {
        "rows": [
            make_row("도루", "정수빈2(1 3회)"),
            make_row("2루타", "박지훈2(1 5회)"),
            make_row("3루타", "김도영(4회)"),
            make_row("홈런", "양의지3호4호(2회2점 7회1점 황동하)"),
            make_row("병살타", "이유찬(5회) 최준호(8회)"),
            make_row("결승타", "김상수(7회 1사 1,3루서 우익수 땅볼)"),
            make_row("사구", "최정2(2 7회)"),
            make_row("4구", "홍창기2(1 4회)"),
            make_row("삼진", "박병호2(3 6회)"),
        ]
    }
    special = parse_game_special_records(fake_detail_table)
    assert_equal("parse table stolen_bases", special["stolen_bases"], {"정수빈": 2})
    assert_equal("parse table doubles", special["doubles"], {"박지훈": 2})
    assert_equal("parse table triples", special["triples"], {"김도영": 1})
    assert_equal("parse table home_runs", special["home_runs"], {"양의지": 2})
    assert_equal("parse table double_play", special["double_play"], {"이유찬": 1, "최준호": 1})
    assert_equal("parse table game_winning_hit", special["game_winning_hit"], {"김상수": 1})
    assert_equal("parse table hit_by_pitch", special["hit_by_pitch"], {"최정": 2})
    assert_equal("parse table walks", special["walks"], {"홍창기": 2})
    assert_equal("parse table strikeouts", special["strikeouts"], {"박병호": 2})

    print("\nALL SPECIAL RECORD PARSER TESTS PASSED")


if __name__ == "__main__":
    main()
