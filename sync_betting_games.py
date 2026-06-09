"""KBO 공식 일정에서 MyPick 배팅용 경기/시장/선택지를 생성합니다.

기본 실행은 DB의 최신 fantasy_daily_scores 날짜 다음 실제 경기일 2개만 저장합니다.
기존 데이터 삭제, 기존 가격/선수/팀 데이터 변경은 하지 않습니다.
"""

import argparse

from betting import ensure_betting_tables, sync_betting_games_for_dates, sync_next_betting_game_dates


def main():
    parser = argparse.ArgumentParser(description="MyPick 배팅 경기 동기화")
    parser.add_argument("--date", action="append", help="특정 날짜만 동기화합니다. 예: 20260522")
    parser.add_argument("--days", type=int, default=2, help="최신 경기일 이후 실제 경기일 몇 개를 가져올지 지정합니다.")
    args = parser.parse_args()

    ensure_betting_tables()

    if args.date:
        result = sync_betting_games_for_dates(args.date)
    else:
        result = sync_next_betting_game_dates(limit=args.days)

    print("배팅 경기 동기화 완료")
    print(result)


if __name__ == "__main__":
    main()
