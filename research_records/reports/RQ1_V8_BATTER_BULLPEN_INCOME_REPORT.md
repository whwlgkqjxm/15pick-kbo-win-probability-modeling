# RQ1 V8 Batter & Bullpen Income System Lab

## 선택된 타자 수입 시스템
- 경기별 수입: **B_RATE50**
- 선수 평균: **ALL_K10**
- 라인업 집계: **ORDER**
- 2025 OOF log loss: **0.682866464**

## 선택된 불펜 수입 시스템
- 경기별 수입: **P_RUN_PREVENT**
- 선수 평균: **HIER_ALL_K3**
- 경기 전 pool: **W30_H14_NONE**
- 2025 OOF log loss: **0.687444156**

## 평균수입 계산 감사
| check                                        | status   |       value |
|:---------------------------------------------|:---------|------------:|
| lineup_exact_9                               | PASS     | 1           |
| lineup_all_averages_finite                   | PASS     | 1           |
| lineup_same_date_excluded                    | PASS     | 1           |
| lineup_manual_mean_matches_feature           | PASS     | 5.68434e-14 |
| bullpen_same_date_excluded                   | PASS     | 1           |
| starter_excluded_from_pool                   | PASS     | 0           |
| bullpen_all_averages_finite                  | PASS     | 1           |
| bullpen_manual_weighted_mean_matches_feature | PASS     | 0           |
| same_formula_each_side                       | PASS     | 1           |

## 영역별 비교
| candidate        |   log_loss |    brier |   roc_auc |   accuracy |   n |
|:-----------------|-----------:|---------:|----------:|-----------:|----:|
| BATTER_SELECTED  |   0.682866 | 0.244902 |  0.580792 |   0.551576 | 698 |
| BATTER_LEGACY    |   0.68348  | 0.245194 |  0.581523 |   0.553009 | 698 |
| TEAM_BASELINE    |   0.687435 | 0.247153 |  0.565766 |   0.561605 | 698 |
| BULLPEN_SELECTED |   0.687444 | 0.247145 |  0.563823 |   0.561605 | 698 |
| BULLPEN_LEGACY   |   0.687645 | 0.247244 |  0.563354 |   0.567335 | 698 |

## 2025 예측 적용
| method                            |   log_loss |    brier |   roc_auc |   accuracy |
|:----------------------------------|-----------:|---------:|----------:|-----------:|
| LOGIT_STACK_V7_STARTER_C0.1       |   0.669483 | 0.238471 |  0.620432 |   0.583095 |
| LOGIT_STACK_V7_STARTER_C0.3       |   0.669525 | 0.238502 |  0.620202 |   0.577364 |
| LOGIT_STACK_V7_STARTER_C1         |   0.669561 | 0.238523 |  0.620021 |   0.577364 |
| JOINT_V2_ALL_C0.003               |   0.669751 | 0.238441 |  0.625723 |   0.608883 |
| LOGIT_STACK_V7_STARTER_C0.03      |   0.669752 | 0.238568 |  0.62081  |   0.588825 |
| JOINT_V2_ALL_C0.01                |   0.670421 | 0.238698 |  0.623874 |   0.600287 |
| LOGIT_STACK_V7_STARTER_C0.01      |   0.671708 | 0.239457 |  0.621172 |   0.590258 |
| LOGIT_STACK_V7_PLUS_BATTER_C0.01  |   0.673388 | 0.240297 |  0.613917 |   0.578797 |
| LOGIT_STACK_V7_PLUS_BULLPEN_C0.01 |   0.674253 | 0.240715 |  0.612118 |   0.574499 |
| LOGIT_STACK_V7_PLUS_BATTER_C0.03  |   0.674335 | 0.240852 |  0.604272 |   0.557307 |
| LOGIT_STACK_ALL_FOUR_C0.01        |   0.674833 | 0.241005 |  0.608717 |   0.568768 |
| LOGIT_STACK_V7_PLUS_BULLPEN_C0.03 |   0.674857 | 0.241038 |  0.607238 |   0.583095 |
| JOINT_V2_ALL_C0.03                |   0.675036 | 0.240821 |  0.616209 |   0.584527 |
| JOINT_V2_BOTH_C0.003              |   0.676034 | 0.241489 |  0.610861 |   0.578797 |
| LOGIT_STACK_ALL_FOUR_C0.03        |   0.676225 | 0.24172  |  0.60244  |   0.570201 |

## 2026 사후 진단
| method                            |   log_loss |    brier |   roc_auc |   accuracy |
|:----------------------------------|-----------:|---------:|----------:|-----------:|
| LOGIT_STACK_ALL_FOUR_C0.01        |   0.667753 | 0.23726  |  0.640186 |   0.610577 |
| LOGIT_STACK_V7_PLUS_BATTER_C0.01  |   0.667771 | 0.237268 |  0.639677 |   0.612981 |
| LOGIT_STACK_V7_STARTER_C0.1       |   0.667785 | 0.237311 |  0.636364 |   0.596154 |
| LOGIT_STACK_V7_PLUS_BULLPEN_C0.01 |   0.668898 | 0.237891 |  0.637174 |   0.596154 |
| JOINT_V2_ALL_C0.003               |   0.669598 | 0.23833  |  0.631545 |   0.591346 |
| V2_DIRECT                         |   0.67061  | 0.238738 |  0.629691 |   0.598558 |
| LOGIT_STACK_V2_BATTER_C0.01       |   0.671961 | 0.239392 |  0.631939 |   0.600962 |
| LOGIT_STACK_V2_BULLPEN_C0.01      |   0.67328  | 0.240084 |  0.62705  |   0.603365 |
| JOINT_V2_BATTER_C0.003            |   0.673298 | 0.240129 |  0.626471 |   0.591346 |
| JOINT_V2_BULLPEN_C0.003           |   0.674876 | 0.240934 |  0.614053 |   0.603365 |
| JOINT_V2_BOTH_C0.003              |   0.675117 | 0.241055 |  0.612547 |   0.598558 |

## 판정
타자 후보 중에서는 B_RATE50/ALL_K10/ORDER가 기존 타자 수입보다 좋아졌다. 불펜 후보 중에서는 P_RUN_PREVENT/HIER_ALL_K3/W30_H14_NONE이 가장 좋았지만, 팀 baseline을 안정적으로 개선하지 못했다. 2025 최종 적용 비교에서는 타자와 불펜을 V7 starter stack에 추가하는 것보다 기존 V7 starter stack 단독이 가장 좋았다. 2026에서는 all-four stack이 사후 수치상 가장 좋았지만 2026을 보고 선택할 수 없으므로 채택하지 않는다.
