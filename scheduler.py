"""
KBO 판타지 점수, 유저 팀 점수, 시장 가격, 배팅 정산/일정을 매일 자동 업데이트하는 파일입니다.

최종 자동 실행 순서:
1. KBO 등록 선수 업데이트
2. 경기 동기화
3. 확정 팀 일별 점수 계산
4. market_daily_v3 가격 업데이트
5. 해당 날짜 배팅 결과 업데이트/정산
6. latest_game 다음 실제 경기일 2개 배팅 일정 동기화

중요:
- 팀이 확정되지 않은 유저는 calculate_team_daily_scores.py에서 점수 row가 생성되지 않습니다.
- 경기 없는 날은 팀 점수 계산과 가격 업데이트를 모두 생략합니다.
- DB 삭제 없음, DROP TABLE 없음, 기존 데이터 삭제 없음
"""

import argparse
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from db import get_conn
from sync_db import sync_date
from sync_registered_players import sync_registered_players


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def get_today_korea_date():
    now = datetime.now(KOREA_TIMEZONE)
    return now.strftime("%Y%m%d")


def parse_yyyymmdd(value):
    value = str(value).strip()

    if len(value) != 8 or not value.isdigit():
        raise ValueError("날짜는 YYYYMMDD 형식이어야 합니다. 예: 20260511")

    return datetime.strptime(value, "%Y%m%d")


def yyyymmdd_to_display(value):
    return parse_yyyymmdd(value).strftime("%Y-%m-%d")


def get_latest_synced_game_date():
    with get_conn() as conn:
        row = conn.execute("""
            SELECT MAX(game_date) AS latest_game_date
            FROM fantasy_daily_scores
        """).fetchone()

    if row is None:
        return None

    return row["latest_game_date"]


def run_team_daily_score_update_for_date(target_date, dry_run=False):
    """
    특정 날짜 경기 동기화 후 확정 팀의 일별 점수를 계산합니다.
    """
    target_display_date = yyyymmdd_to_display(target_date)
    latest_game_date = get_latest_synced_game_date()

    print()
    print("=" * 80)
    print("확정 팀 일별 점수 계산 준비")
    print("동기화 대상 경기 날짜:", target_display_date)
    print("DB 최신 경기 날짜:", latest_game_date)
    print("=" * 80)

    if latest_game_date != target_display_date:
        print("확정 팀 일별 점수 계산 생략")
        print("이유: 방금 동기화한 날짜가 DB 최신 경기 날짜가 아닙니다.")
        print("경기가 없었거나, 해당 날짜 데이터 수집에 실패했을 수 있습니다.")
        return False

    command = [
        sys.executable,
        "calculate_team_daily_scores.py",
        target_display_date,
    ]

    if dry_run:
        command.append("--dry-run")

    print("확정 팀 일별 점수 계산 실행 명령:")
    print(" ".join(command))
    print()

    try:
        subprocess.run(command, check=True)
        print("확정 팀 일별 점수 계산 명령 실행 완료")
        return True
    except subprocess.CalledProcessError as error:
        print("확정 팀 일별 점수 계산 명령 실행 실패")
        print("returncode:", error.returncode)
        raise


def run_market_price_update_for_date(target_date, dry_run=False, force=False):
    """
    특정 날짜 경기 동기화 후 시장 가격 업데이트를 실행합니다.
    """
    target_display_date = yyyymmdd_to_display(target_date)
    latest_game_date = get_latest_synced_game_date()

    print()
    print("=" * 80)
    print("시장 가격 자동 업데이트 준비")
    print("동기화 대상 경기 날짜:", target_display_date)
    print("DB 최신 경기 날짜:", latest_game_date)
    print("=" * 80)

    if latest_game_date != target_display_date:
        print("시장 가격 업데이트 생략")
        print("이유: 방금 동기화한 날짜가 DB 최신 경기 날짜가 아닙니다.")
        print("경기가 없었거나, 해당 날짜 데이터 수집에 실패했을 수 있습니다.")
        return False

    command = [
        sys.executable,
        "update_market_prices_v3.py",
        "--basis-date",
        target_display_date,
    ]

    if dry_run:
        command.append("--dry-run")
    else:
        command.append("--apply")

    if force:
        command.append("--force")

    print("시장 가격 업데이트 실행 명령:")
    print(" ".join(command))
    print()

    try:
        subprocess.run(command, check=True)
        print("시장 가격 업데이트 명령 실행 완료")
        return True
    except subprocess.CalledProcessError as error:
        print("시장 가격 업데이트 명령 실행 실패")
        print("returncode:", error.returncode)
        raise





def run_betting_settlement_for_date(target_date):
    """
    특정 경기일의 배팅 결과를 업데이트하고 pending 배팅을 정산합니다.

    settle_betting.py 내부에서 status='pending' 배팅만 처리하므로 같은 날짜를 다시 실행해도
    payout/refund가 중복 지급되지 않습니다.
    """
    target_display_date = yyyymmdd_to_display(target_date)

    print()
    print("=" * 80)
    print("배팅 결과 업데이트/정산 준비")
    print("정산 대상 경기 날짜:", target_display_date)
    print("=" * 80)

    command = [
        sys.executable,
        "settle_betting.py",
        "--date",
        target_display_date,
    ]

    print("배팅 정산 실행 명령:")
    print(" ".join(command))
    print()

    try:
        subprocess.run(command, check=True)
        print("배팅 정산 명령 실행 완료")
        return True
    except subprocess.CalledProcessError as error:
        print("배팅 정산 명령 실행 실패")
        print("returncode:", error.returncode)
        raise


def run_next_betting_schedule_sync(days=2):
    """
    최신 fantasy_daily_scores 날짜 이후 실제 경기일을 기준으로 배팅 일정을 동기화합니다.

    sync_betting_games.py 기본 로직은 DB의 latest_game 다음 실제 경기일만 선택하므로,
    5/22 경기 처리 후에는 5/23 및 그 다음 실제 경기일 배팅이 열려야 합니다.
    """
    print()
    print("=" * 80)
    print("다음 배팅 경기 일정 동기화 준비")
    print("노출 경기일 수:", days)
    print("=" * 80)

    command = [
        sys.executable,
        "sync_betting_games.py",
        "--days",
        str(int(days)),
    ]

    print("배팅 경기 동기화 실행 명령:")
    print(" ".join(command))
    print()

    try:
        subprocess.run(command, check=True)
        print("배팅 경기 동기화 명령 실행 완료")
        return True
    except subprocess.CalledProcessError as error:
        print("배팅 경기 동기화 명령 실행 실패")
        print("returncode:", error.returncode)
        raise

def run_registered_player_update(target_date=None):
    """
    KBO 등록 선수 목록을 먼저 업데이트합니다.

    target_date가 있으면 경기 동기화 대상 날짜와 등록 현황 기준 날짜를 맞추려 시도합니다.
    KBO 페이지가 과거 날짜 조회를 제공하지 않거나 다른 날짜를 반환하면 경고를 남기고,
    가격/화면 로직에서 해당 경기일 출전 선수 fallback을 적용합니다.
    """
    print()
    print("=" * 80)
    print("KBO 등록 선수 목록 업데이트")
    if target_date:
        print("요청 기준 날짜:", yyyymmdd_to_display(target_date) if len(str(target_date)) == 8 else target_date)
    print("=" * 80)

    try:
        target_display_date = yyyymmdd_to_display(target_date) if target_date else None
        sync_registered_players(target_date=target_display_date)
        print("등록 선수 목록 업데이트 완료")
        return True
    except Exception as error:
        print("등록 선수 목록 업데이트 실패")
        print("에러:", error)
        print("기존 registered_players 기준으로 경기 동기화를 계속 진행합니다.")
        return False

def run_sync_team_scores_and_price_update(
    target_date,
    sync_only=False,
    skip_team_scores=False,
    team_score_dry_run=False,
    price_dry_run=False,
    force_price=False,
    skip_betting=False,
    betting_days=2,
):
    """
    특정 날짜 경기 동기화 + 확정 팀 점수 계산 + 가격 업데이트를 실행합니다.
    """
    print("=" * 80)
    print("KBO 판타지 자동 작업 시작")
    print("대상 날짜:", target_date)
    print("=" * 80)

    run_registered_player_update(target_date=target_date)

    sync_date(target_date)

    print("=" * 80)
    print("경기 점수 동기화 완료")
    print("=" * 80)

    if sync_only:
        print("후속 작업 생략: sync_only=True")
        print("팀 점수 계산과 가격 업데이트를 실행하지 않습니다.")
        return

    if skip_team_scores:
        print("확정 팀 일별 점수 계산 생략: skip_team_scores=True")
    else:
        run_team_daily_score_update_for_date(
            target_date=target_date,
            dry_run=team_score_dry_run,
        )

    run_market_price_update_for_date(
        target_date=target_date,
        dry_run=price_dry_run,
        force=force_price,
    )

    if skip_betting:
        print("배팅 정산/일정 동기화 생략: skip_betting=True")
    elif team_score_dry_run or price_dry_run:
        print("배팅 정산/일정 동기화 생략")
        print("이유: dry-run 모드에서는 배팅 status/ledger/일정을 변경하지 않습니다.")
    else:
        run_betting_settlement_for_date(target_date=target_date)
        run_next_betting_schedule_sync(days=betting_days)

    print("=" * 80)
    print("KBO 판타지 자동 작업 완료")
    print("=" * 80)


def run_daily_sync():
    target_date = get_today_korea_date()

    try:
        run_sync_team_scores_and_price_update(
            target_date=target_date,
            sync_only=False,
            skip_team_scores=False,
            team_score_dry_run=False,
            price_dry_run=False,
            force_price=False,
        )
    except Exception as e:
        print("자동 작업 실패")
        print("에러:", e)


def start_scheduler():
    scheduler = BlockingScheduler(timezone=KOREA_TIMEZONE)

    scheduler.add_job(
        run_daily_sync,
        CronTrigger(
            hour=23,
            minute=0,
            timezone=KOREA_TIMEZONE,
        ),
        id="kbo_daily_fantasy_sync_team_scores_and_price_update",
        replace_existing=True,
    )

    print("=" * 80)
    print("KBO 판타지 자동 업데이트 스케줄러 시작")
    print("실행 시간: 매일 밤 11시")
    print("작업 내용: 등록 선수 업데이트 + 경기 점수 동기화 + 팀 점수 + market_daily_v3 가격 + 배팅 정산/일정 동기화")
    print("기준 시간대: Asia/Seoul")
    print("멈추려면 Control + C")
    print("=" * 80)

    scheduler.start()


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="KBO 판타지 자동 점수/팀점수/가격 업데이트 스케줄러"
    )

    parser.add_argument(
        "--date",
        help="특정 날짜를 바로 실행합니다. 예: 20260512",
    )

    parser.add_argument(
        "--run-now",
        action="store_true",
        help="한국 시간 기준 오늘 날짜를 바로 실행합니다.",
    )

    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="경기 데이터 동기화만 하고 팀 점수 계산과 가격 업데이트는 하지 않습니다.",
    )

    parser.add_argument(
        "--skip-team-scores",
        action="store_true",
        help="확정 팀 일별 점수 계산을 생략합니다.",
    )

    parser.add_argument(
        "--team-score-dry-run",
        action="store_true",
        help="확정 팀 일별 점수를 실제 저장하지 않고 dry-run으로만 실행합니다.",
    )

    parser.add_argument(
        "--price-dry-run",
        action="store_true",
        help="가격 업데이트를 실제 적용하지 않고 dry-run으로만 실행합니다.",
    )

    parser.add_argument(
        "--force-price",
        action="store_true",
        help="가격 업데이트 실행 시 --force를 함께 넘깁니다. 수동 재실행 때만 사용하세요.",
    )

    parser.add_argument(
        "--skip-betting",
        action="store_true",
        help="배팅 결과 정산과 다음 배팅 경기 동기화를 생략합니다.",
    )

    parser.add_argument(
        "--betting-days",
        type=int,
        default=2,
        help="latest_game 다음 실제 경기일 몇 개를 배팅에 노출할지 지정합니다. 기본값: 2",
    )

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.date:
        run_sync_team_scores_and_price_update(
            target_date=args.date,
            sync_only=args.sync_only,
            skip_team_scores=args.skip_team_scores,
            team_score_dry_run=args.team_score_dry_run,
            price_dry_run=args.price_dry_run,
            force_price=args.force_price,
            skip_betting=args.skip_betting,
            betting_days=args.betting_days,
        )
    elif args.run_now:
        today = get_today_korea_date()
        run_sync_team_scores_and_price_update(
            target_date=today,
            sync_only=args.sync_only,
            skip_team_scores=args.skip_team_scores,
            team_score_dry_run=args.team_score_dry_run,
            price_dry_run=args.price_dry_run,
            force_price=args.force_price,
            skip_betting=args.skip_betting,
            betting_days=args.betting_days,
        )
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
