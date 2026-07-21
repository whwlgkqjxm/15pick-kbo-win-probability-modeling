# RQ1 Role-Aware Fantasy-Income Audit v1

## 결론

사용자의 지적이 맞다.

원시 player-game fantasy income 65,554행은 수집·identity·scoring 검증이 완료되어 있다.
그러나 strict-prior history의 scope가 `season + player_id + position_type`으로만 구성되어
`role`을 분리하지 않았다.

그 결과:

1. 공식 선발 라인업 선수의 평균에 과거 대타·대수비 등 substitute 경기 수입이 포함됐다.
2. 선발투수 평균에 과거 구원 등판 수입이 포함됐다.
3. 불펜은 선수별 fantasy-income 평균을 비교하지 않았고, 팀의 과거 구원 실점/경기만 사용했다.
4. V3도 불펜 투구 수·아웃·등판 수·최근 사용량은 추가했지만 relief-only income 비교를 완성하지 않았다.

따라서 V5의 “현재 feature set의 실용적 상한” 판정은 기존 feature 구현에만 해당한다.
RQ1 전체의 최종 상한 판정으로 사용해서는 안 되며, role-aware foundation 재구축 전까지 보류한다.

## 원시 데이터 상태

- 전체 player-game income: 65,554행
- 타자 선발: 33,552행
- 타자 substitute: 13,801행
- 투수 선발: 3,728행
- 투수 bullpen: 14,473행
- 공식 선발 라인업: 매 경기-팀 정확히 9명
- 공식 선발투수: 매 경기-팀 정확히 1명
- lineup/starter history join failure: 0

즉 문제는 수입 행의 누락이 아니라 평균 집계 scope다.

## 역할별 수입 규모 차이

| 구분 | 평균 | 중앙값 |
|---|---:|---:|
| 타자 선발 | 337.52 | 220 |
| 타자 substitute | 147.89 | 100 |
| 투수 선발 | 1,310.23 | 1,252 |
| 투수 bullpen | 339.03 | 308 |

역할별 기회와 scoring multiplier가 크게 다르므로 같은 평균에 섞으면 의미가 달라진다.

## 오염 규모

### 타격 라인업

- prior history가 있는 선발타자 occurrence: 33,121
- 그중 과거 substitute 기록이 포함된 occurrence: 25,870
- 비율: 78.11%
- starter-only history도 존재하는 오염 행에서:
  - all-role vs starter-only 평균 절대차 중앙값: 18.72점
  - 평균 절대차: 38.32점

### 선발투수

- prior history가 있는 선발투수 occurrence: 3,496
- 그중 과거 bullpen 기록이 포함된 occurrence: 726
- 비율: 20.77%
- prior starts와 prior bullpen 기록이 모두 있는 614행에서:
  - all-role vs start-only 평균 절대차 중앙값: 149.14점
  - 평균 절대차: 294.11점

선발투수는 starter ×2.0, bullpen ×1.4 multiplier와 이닝 차이 때문에 역할 혼합 문제가 특히 크다.

## 불펜

V1/V2의 `bullpen_strength_diff`는 다음이다.

- 각 팀의 이전 경기들에서 구원투수들이 허용한 총 실점
- 이를 이전 팀 경기 수로 나눈 값
- 홈·원정 차이

이는 선수별 불펜 fantasy-income 평균이 아니다.

올바른 불펜 비교에는 경기 전에 실제로 가용할 가능성이 있는 relief pool을 구성하고,
각 투수의 relief-only strict-prior income, 최근 투구량, 연투, 휴식일을 결합해야 한다.
당일 실제 등판자를 사용하면 leakage이므로 사용할 수 없다.

## 진단용 사후 실험

role-specific feature를 급히 다시 계산해 사후 비교했지만 V2를 넘지 못했다.
이 결과는 다음 두 이유로 최종 선택 증거가 아니다.

1. 2026 결과는 이미 반복 관찰됐다.
2. 완전한 official pregame bullpen roster/availability가 아니라 과거 team/pool proxy만 사용했다.

따라서 role-aware 수정이 성능을 보장하지는 않지만, 의미가 틀린 평균을 그대로 유지할 이유도 없다.
all-role 평균은 별도 general-usage feature로 보존하고 role-specific 평균과 동시에 비교해야 한다.

## 필수 재구축

1. Income Foundation V2 Role-Aware 생성
2. 다음 history를 병렬 보존
   - batter all / starter / substitute
   - pitcher all / starter / bullpen
3. 라인업 9명:
   - starter-only prior mean
   - all-appearance prior mean
   - recent mean
   - previous-season role-specific mean
   - cold-start league/position shrinkage
4. 선발투수:
   - start-only prior starts와 income
   - all-pitcher history는 별도 보조 feature
5. 불펜:
   - relief-only player history
   - 최근 14/30일 active pool
   - 최근 1/2/3일 pitches, 연투, 휴식
   - official roster/entry가 확보되면 이를 우선 사용
6. 2024·2025 temporal selection
7. 2026은 진단용 post-hoc로만 표시
8. 최종 판정은 prospective 경기로 수행

## 상태 변경

- 기존 V2: historical observed champion, semantic role-mixing limitation 명시
- V5 ceiling audit: suspended as final ceiling decision
- 다음 단계: Role-Aware Income Foundation V2 및 V6 Role-Aware Comparison Lab
