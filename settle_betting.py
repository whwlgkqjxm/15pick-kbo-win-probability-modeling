"""완료된 KBO 경기 결과를 기준으로 MyPick 배팅을 정산합니다.

같은 날짜를 여러 번 실행해도 status='pending'인 배팅만 처리하므로 중복 지급되지 않습니다.
"""

import argparse

from betting import ensure_betting_tables, settle_betting_for_date, update_betting_results_for_date


def main():
    parser = argparse.ArgumentParser(description="MyPick 배팅 결과 정산")
    parser.add_argument("--date", required=True, help="정산할 날짜. 예: 20260522 또는 2026-05-22")
    parser.add_argument("--skip-result-update", action="store_true", help="공식 결과 재조회 없이 DB에 저장된 betting_games 점수로만 정산합니다.")
    args = parser.parse_args()

    ensure_betting_tables()

    if not args.skip_result_update:
        update_result = update_betting_results_for_date(args.date)
        print("배팅 경기 결과 업데이트:", update_result)

    settle_result = settle_betting_for_date(args.date)
    print("배팅 정산 완료:", settle_result)


if __name__ == "__main__":
    main()
