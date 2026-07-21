# 15Pick / MyPick KBO RQ1
# V6 Official Performance Income Design Lab — Current Findings

기준일: 2026-07-19 KST  
상태: 실제 전체 공식 데이터 오프라인 진단 완료, 사용자 Mac 재현 대기

## 1. 무엇을 시험했는가

KBO GameCenter에서 직접 수집된 공식 경기 기록만 사용해 6가지 player-game income 체계를 만들었다.
모든 예측 입력은 현재 경기 또는 같은 날짜 결과가 아닌 **역할별 strict-prior 평균수입**이다.

- LEGACY_ROLE_AWARE
- KBO_EMPIRICAL
- KBO_CONSTRAINED
- KBO_CONTEXT
- KBO_RATE_BALANCED
- KBO_TOTAL_VALUE

타자는 공식 타석 결과에서 단타·2루타·3루타·홈런·4구·사구·도루·희생플라이·희생번트·실책출루·야수선택·삼진·병살을 사용했다.
투수는 공식 표의 아웃카운트·탈삼진·피홈런·4사구·피안타·실점/자책·승패·홀드·세이브를 후보별로 다르게 사용했다.

## 2. 2025 rolling temporal 개발 결과

| candidate         |   log_loss |    brier |   roc_auc |   accuracy_050 |
|:------------------|-----------:|---------:|----------:|---------------:|
| KBO_CONSTRAINED   |   0.678712 | 0.242835 |  0.603508 |       0.578797 |
| KBO_RATE_BALANCED |   0.678959 | 0.242954 |  0.603459 |       0.568768 |
| LEGACY_ROLE_AWARE |   0.682203 | 0.244556 |  0.589533 |       0.557307 |
| KBO_TOTAL_VALUE   |   0.6838   | 0.245343 |  0.583068 |       0.554441 |
| KBO_EMPIRICAL     |   0.686207 | 0.246531 |  0.570169 |       0.563037 |
| KBO_CONTEXT       |   0.686983 | 0.246916 |  0.566628 |       0.573066 |
| TEAM_BASELINE     |   0.687049 | 0.246974 |  0.562627 |       0.56447  |

KBO_CONSTRAINED가 가장 좋았다.

- Team baseline log loss: 0.687048586
- Role-aware legacy: 0.682202690
- KBO_CONSTRAINED: 0.678711895
- KBO_CONSTRAINED − legacy: -0.003490795
- 날짜 단위 bootstrap 개선 확률: 95.742%
- CI95: -0.007458 ~ +0.000471

CI가 0을 아주 조금 포함하므로 유망하지만 아직 확정적이라고 부르지 않는다.

## 3. 2026 사후 진단

| candidate         |   log_loss |    brier |   roc_auc |   accuracy_050 |
|:------------------|-----------:|---------:|----------:|---------------:|
| KBO_CONSTRAINED   |   0.672155 | 0.239526 |  0.625359 |       0.608173 |
| KBO_RATE_BALANCED |   0.673577 | 0.240256 |  0.618131 |       0.584135 |
| LEGACY_ROLE_AWARE |   0.674422 | 0.240674 |  0.62237  |       0.596154 |
| KBO_TOTAL_VALUE   |   0.675454 | 0.241163 |  0.617922 |       0.600962 |
| KBO_CONTEXT       |   0.677051 | 0.241955 |  0.612686 |       0.572115 |
| KBO_EMPIRICAL     |   0.677581 | 0.242224 |  0.609258 |       0.579327 |
| TEAM_BASELINE     |   0.683672 | 0.245238 |  0.586971 |       0.560096 |

KBO_CONSTRAINED 단독 체계는 2026에서도 role-aware legacy보다 좋았으나, 기존 V2 Probability 21-feature 모델보다 log loss가 높았다.

## 4. 기존 V2와 결합한 결과

| candidate                      |   log_loss |    brier |   roc_auc |   accuracy_050 |
|:-------------------------------|-----------:|---------:|----------:|---------------:|
| V2_PLUS_KBO_CONSTRAINED        |   0.677207 | 0.242073 |  0.603689 |       0.58596  |
| KBO_CONSTRAINED_LINEUP_STARTER |   0.677581 | 0.242278 |  0.608635 |       0.563037 |
| KBO_CONSTRAINED_STARTER_ONLY   |   0.677648 | 0.242329 |  0.606729 |       0.571633 |
| V2_PROBABILITY_21              |   0.678417 | 0.242678 |  0.600378 |       0.583095 |
| KBO_CONSTRAINED_ALL            |   0.678712 | 0.242835 |  0.603508 |       0.578797 |
| TEAM_BASELINE                  |   0.687049 | 0.246974 |  0.562627 |       0.56447  |
| KBO_CONSTRAINED_LINEUP_ONLY    |   0.687465 | 0.247162 |  0.566924 |       0.551576 |
| KBO_CONSTRAINED_BULLPEN_ONLY   |   0.688016 | 0.247449 |  0.555907 |       0.560172 |

2025에서 기존 V2 21개 feature에 KBO_CONSTRAINED 평균수입 feature를 추가했을 때:

- V2: 0.678417
- V2 + KBO_CONSTRAINED: 0.677207
- 차이: -0.001210
- bootstrap 개선 확률: 72.276%
- CI95: -0.005213 ~ +0.002851

2026 post-hoc에서는:

| candidate                      |   log_loss |    brier |   roc_auc |   accuracy_050 |
|:-------------------------------|-----------:|---------:|----------:|---------------:|
| V2_PLUS_KBO_CONSTRAINED        |   0.670221 | 0.238642 |  0.624317 |       0.591346 |
| V2_PROBABILITY_21              |   0.67061  | 0.238738 |  0.629691 |       0.598558 |
| KBO_CONSTRAINED_ALL            |   0.672155 | 0.239526 |  0.625359 |       0.608173 |
| KBO_CONSTRAINED_LINEUP_STARTER |   0.673092 | 0.239958 |  0.624456 |       0.598558 |
| KBO_CONSTRAINED_STARTER_ONLY   |   0.673555 | 0.240239 |  0.622903 |       0.596154 |
| KBO_CONSTRAINED_LINEUP_ONLY    |   0.682733 | 0.244717 |  0.592762 |       0.569712 |
| KBO_CONSTRAINED_BULLPEN_ONLY   |   0.682877 | 0.244848 |  0.589148 |       0.557692 |
| TEAM_BASELINE                  |   0.683672 | 0.245238 |  0.586971 |       0.560096 |

- V2: 0.670610
- V2 + KBO_CONSTRAINED: 0.670221
- 차이: -0.000390
- bootstrap 개선 확률: 56.790%
- CI95: -0.005058 ~ +0.004301

따라서 새 수입이 기존 최고 모델을 아주 조금 개선하는 방향은 보였지만 통계적으로 결론적이지 않다.

## 5. 어떤 역할이 개선을 만들었는가

2025 개발구간에서 Team baseline 대비 domain ablation:

- KBO_CONSTRAINED starter only: delta log loss -0.009401
- CI95: -0.014817 ~ -0.003986
- 개선 확률: 99.970%
- lineup only: delta +0.000417, 개선 확률 40.468%
- bullpen only: delta +0.000967, 개선 확률 18.618%

즉 현재 발견된 개선은 거의 전부 **선발투수 평균수입을 제대로 재설계한 효과**다.
타격 라인업과 불펜 수입은 아직 최고의 측정 방식이 발견되지 않았다.

## 6. 선수 가치 측정

| role              | diagnostic                         |   KBO_CONSTRAINED |   LEGACY_ROLE_AWARE |
|:------------------|:-----------------------------------|------------------:|--------------------:|
| batter_starter    | 2024_to_2025_stability             |         0.591541  |            0.693926 |
| batter_starter    | 2025_half_to_half_stability        |         0.523364  |            0.564714 |
| batter_starter    | 2025_prior_average_vs_current_game |         0.115465  |            0.159118 |
| batter_substitute | 2024_to_2025_stability             |         0.127462  |            0.208086 |
| batter_substitute | 2025_half_to_half_stability        |         0.159728  |            0.304617 |
| batter_substitute | 2025_prior_average_vs_current_game |         0.0130997 |            0.071267 |
| pitcher_bullpen   | 2024_to_2025_stability             |         0.233556  |            0.405128 |
| pitcher_bullpen   | 2025_half_to_half_stability        |         0.299066  |            0.39311  |
| pitcher_bullpen   | 2025_prior_average_vs_current_game |         0.0873448 |            0.209558 |
| pitcher_starter   | 2024_to_2025_stability             |         0.574638  |            0.451835 |
| pitcher_starter   | 2025_half_to_half_stability        |         0.747735  |            0.698084 |
| pitcher_starter   | 2025_prior_average_vs_current_game |         0.360411  |            0.328656 |

특히 선발투수에서 KBO_CONSTRAINED는 legacy보다:

- 다음 경기 점수 예측 상관: 0.360 vs 0.329
- 2025 전·후반 안정성: 0.748 vs 0.698
- 2024→2025 안정성: 0.575 vs 0.452

으로 더 나았다.
반면 타자와 불펜의 장기 안정성은 legacy보다 낮은 부분이 있어 추가 설계가 필요하다.

## 7. 현재 결정

### 현재 채택 가능한 부분

- 선발투수 player-game income: **KBO_CONSTRAINED starter formula가 현재 최고 후보**
- 평균 방식: starter-only strict-prior mean + recent means + previous-season K=10 shrinkage
- 기존 V2에 challenger feature로 추가할 가치가 있음

### 아직 최종 채택할 수 없는 부분

- 타자 income formula
- 불펜 income formula와 historical active-pool 정의
- 하나의 통합 final income system

2025에서 역할별 개별 winner를 결합한 hybrid는 개발 성능이 더 좋았지만 2026에서 V2보다 나빠져 일반화 안정성이 부족했다.
따라서 2026 결과를 보고 hybrid를 채택하지 않는다.

## 8. 다음 연구

1. 타자 수입을 총기여와 타석당 기여로 분리한다.
2. 타자 공식은 선수의 다음 경기·다음 반기 안정성을 동시에 최적화한다.
3. 불펜은 최근 30일 출전 proxy가 아니라 가능한 경우 official entry/roster snapshot을 확보한다.
4. 평균수입 shrinkage K와 recent window를 2024·2025 안에서만 추가 비교한다.
5. 최종 후보를 V2와 함께 prospective 경기에서 동결 비교한다.
