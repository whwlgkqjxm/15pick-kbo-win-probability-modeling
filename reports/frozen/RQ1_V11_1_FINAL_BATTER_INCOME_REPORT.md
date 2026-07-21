# RQ1 V11.1 완전 신규 타격 수입 시스템 결과

## 최종 개발 후보
- 경기 점수: **POWER_OBP__RATE100**
- 선수 평균: **S_K5** (현재 시즌 과거 평균을 K=5로 전년도 평균에 수축)
- 라인업 적용: **MEAN**
- 승부예측: 팀 전력 5개 + 깨끗한 선발/포스트선발 5개 + 신규 타자 block, L2 Logistic C=0.01
- 기존 fantasy 타격 수입 사용: **0**

## 검증 결과

| model_id                 |   log_loss |    brier |   roc_auc |   accuracy |   n |
|:-------------------------|-----------:|---------:|----------:|-----------:|----:|
| V11_1_NEW_BATTER         |   0.66502  | 0.236312 |  0.632608 |   0.594556 | 698 |
| V9_STYLE_CURRENT_PRIMARY |   0.667336 | 0.237412 |  0.628557 |   0.583095 | 698 |
| CLEAN_NO_BATTER          |   0.668954 | 0.23827  |  0.619939 |   0.574499 | 698 |
| TEAM_BASELINE            |   0.688182 | 0.247525 |  0.564213 |   0.558739 | 698 |

신규 타자 후보는 2025 검증에서 clean no-batter 모델의 Log loss를 **0.668953644 → 0.665019783**로 낮췄고, AUC는 **0.619939 → 0.632608**로 높였다. 현재 V9_STYLE 동일 경기 Log loss는 0.667335696이다.

## Bootstrap

| new_model          | reference_model   |   delta_log_loss |      ci_low |     ci_high |   improvement_probability |   reps |
|:-------------------|:------------------|-----------------:|------------:|------------:|--------------------------:|-------:|
| p_v11_1_new_batter | p_clean_no_batter |      -0.00393386 | -0.0105849  |  0.00292491 |                    0.8784 |  10000 |
| p_v11_1_new_batter | p_v9_style        |      -0.00231591 | -0.00911779 |  0.00471667 |                    0.7461 |  10000 |
| p_v11_1_new_batter | p_team_baseline   |      -0.0231619  | -0.0372823  | -0.00924551 |                    0.9993 |  10000 |

## 과학적 상태
첫 2024-only champion을 2025에서 확인한 뒤 평균 구조를 재검토했으므로, 이 V11.1 후보에서 2025는 더 이상 untouched test가 아니라 validation이다. 위 결과는 개발 증거이며 최종 일반화 증거는 아니다. 2026은 선택·학습에 사용하지 않았고, 2024+2025 refit 모델은 prospective 검증용이다.

## 탐색 범위
- 공식 타격 이벤트에서 독립 신규 점수 후보 215개 생성
- 30개 full temporal score search
- 상위 점수 18개에 평균법 20개
- 라인업 block 6개
- L2, Elastic Net, gradient boosting, histogram boosting, random forest, extra trees
- clean baseline 직접 결합, stacking, logit blend, ensemble

## 계산 계약
- 공식 선발타자 정확히 9명
- player ID 결측 0
- 같은 날짜의 모든 경기 결과를 history 업데이트 전에 묶어 제외
- 더블헤더 1차전 결과를 2차전에 사용하지 않음
- 2026 튜닝 금지
