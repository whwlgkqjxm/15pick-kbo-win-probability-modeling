# 데이터 계약과 누수 규칙 — v15

## 공식 원천
- KBO Schedule/GameCenter/BoxScore와 공식 선수 프로필
- official canonical + final numeric identity가 source of truth

## Strict-prior rule
- source date < target date
- 현재 경기 제외
- 같은 날짜 모든 경기 제외
- 더블헤더 1차전도 2차전 history에 미포함
- train-only imputation/scaling/selection/calibration
- random split 금지
- target-game actual reliever 금지

## 2026 해석
2026 예측 자체에는 current/same-date/future leakage가 없다. 그러나 2026 성능은
학습전략과 RECENT_720 선택에 사용됐으므로 development evaluation이다. 최종 untouched
성능으로 표현하지 않는다.

## 역할 분리
- 타자: V11.1 신규 POWER_OBP__RATE100 / S_K5 / lineup MEAN
- 선발: start-only KBO_CONSTRAINED K10
- legacy 타자 수입과 legacy 선발 수입은 현재 V12 모델에 사용하지 않음
- 불펜: player-level income 미사용, team responsibility-run features 사용

## 취소 경기
- 연구 evaluation에서 void/exclude
- 운영 배팅 환불, 가격 유지, DNP penalty 없음 정책과 일치

## 공개 재배포
KBO 원자료의 이용·재배포 조건 확인 전 private repository를 권장한다.
