# RQ1 V12 신규 타자 수입 학습전략 및 머신러닝 비교

## 목적
V11.1에서 고정한 완전 신규 타자 수입 구조를 변경하지 않고, 학습 데이터 사용법·시간 가중·재학습 방식·모델 계열·확률 보정을 비교했다. 기존 기본 타격 수입은 사용하지 않았다.

## 평가 계약
- 2024–2025: expanding temporal cross-validation으로 모델 계열과 하이퍼파라미터 선택
- 2026: 2024–2025 학습 또는 날짜별 과거 데이터만 이용한 개발 평가
- 같은 날짜 결과는 그 날짜의 모든 예측이 끝난 뒤에만 adaptive 학습에 추가
- 2026 결과는 이미 관찰된 개발 비교이므로 최종 untouched test라고 부르지 않음

## 2024–2025 시간순 CV 상위 모델

| model_id          | family      |   log_loss |    brier |   roc_auc |   accuracy |   fold_log_loss_sd |   selection_score |
|:------------------|:------------|-----------:|---------:|----------:|-----------:|-------------------:|------------------:|
| L2_C0.03          | L2_LOGISTIC |   0.668643 | 0.237899 |  0.628609 |   0.590447 |         0.0128026  |          0.669283 |
| L2_C0.01          | L2_LOGISTIC |   0.668908 | 0.238117 |  0.627494 |   0.59248  |         0.011881   |          0.669502 |
| ENET_C0.1_L10.25  | ELASTIC_NET |   0.669683 | 0.238379 |  0.62649  |   0.590447 |         0.0132948  |          0.670348 |
| ENET_C0.1_L10.5   | ELASTIC_NET |   0.670085 | 0.238643 |  0.624693 |   0.593496 |         0.0132543  |          0.670748 |
| ENET_C0.3_L10.75  | ELASTIC_NET |   0.670158 | 0.238555 |  0.626325 |   0.594512 |         0.0134053  |          0.670829 |
| ENET_C0.3_L10.5   | ELASTIC_NET |   0.670304 | 0.238576 |  0.62682  |   0.588415 |         0.0133472  |          0.670971 |
| L2_C0.1           | L2_LOGISTIC |   0.670341 | 0.23854  |  0.62713  |   0.586382 |         0.0129305  |          0.670988 |
| ENET_C0.1_L10.75  | ELASTIC_NET |   0.67081  | 0.239015 |  0.622119 |   0.591463 |         0.0131564  |          0.671467 |
| ENET_C0.03_L10.25 | ELASTIC_NET |   0.670923 | 0.239105 |  0.621743 |   0.59248  |         0.0123679  |          0.671541 |
| ENET_C0.3_L10.25  | ELASTIC_NET |   0.67089  | 0.238785 |  0.626399 |   0.587398 |         0.0131452  |          0.671547 |
| L2_C0.3           | L2_LOGISTIC |   0.672314 | 0.239341 |  0.62468  |   0.594512 |         0.0132905  |          0.672979 |
| L2_C0.003         | L2_LOGISTIC |   0.672975 | 0.240069 |  0.622131 |   0.580285 |         0.00942282 |          0.673446 |

## 2026 정적 학습전략 상위 결과

| model_id         | family      | training_strategy    |   n_train |   log_loss |    brier |   roc_auc |   accuracy |
|:-----------------|:------------|:---------------------|----------:|-----------:|---------:|----------:|-----------:|
| L2_C0.1          | L2_LOGISTIC | RECENT_720           |       720 |   0.666135 | 0.236498 |  0.635275 |   0.596154 |
| L2_C0.03         | L2_LOGISTIC | RECENT_720           |       720 |   0.666387 | 0.236612 |  0.639097 |   0.59375  |
| ENET_C0.3_L10.5  | ELASTIC_NET | RECENT_720           |       720 |   0.666698 | 0.236804 |  0.635553 |   0.588942 |
| L2_C0.01         | L2_LOGISTIC | SEASON_WEIGHT_2025X2 |      1408 |   0.666854 | 0.236807 |  0.635738 |   0.596154 |
| L2_C0.01         | L2_LOGISTIC | ALL_EQUAL            |      1408 |   0.666894 | 0.236835 |  0.637545 |   0.59375  |
| L2_C0.01         | L2_LOGISTIC | SEASON_WEIGHT_2025X4 |      1408 |   0.666999 | 0.236884 |  0.633723 |   0.603365 |
| ENET_C0.3_L10.5  | ELASTIC_NET | SEASON_WEIGHT_2025X4 |      1408 |   0.667015 | 0.236917 |  0.632495 |   0.608173 |
| L2_C0.01         | L2_LOGISTIC | DECAY_HL480D         |      1408 |   0.667024 | 0.236897 |  0.63736  |   0.59375  |
| L2_C0.03         | L2_LOGISTIC | SEASON_WEIGHT_2025X4 |      1408 |   0.667064 | 0.236921 |  0.633282 |   0.610577 |
| ENET_C0.3_L10.75 | ELASTIC_NET | SEASON_WEIGHT_2025X4 |      1408 |   0.667074 | 0.236942 |  0.632518 |   0.610577 |
| ENET_C0.1_L10.25 | ELASTIC_NET | SEASON_WEIGHT_2025X4 |      1408 |   0.667095 | 0.236947 |  0.63312  |   0.610577 |
| L2_C0.1          | L2_LOGISTIC | SEASON_WEIGHT_2025X4 |      1408 |   0.667099 | 0.236946 |  0.632773 |   0.610577 |
| L2_C0.03         | L2_LOGISTIC | SEASON_WEIGHT_2025X2 |      1408 |   0.667151 | 0.236941 |  0.632773 |   0.605769 |
| ENET_C0.1_L10.25 | ELASTIC_NET | RECENT_720           |       720 |   0.667169 | 0.23705  |  0.636549 |   0.605769 |
| ENET_C0.1_L10.75 | ELASTIC_NET | SEASON_WEIGHT_2025X4 |      1408 |   0.667265 | 0.237053 |  0.633908 |   0.603365 |

## 2026 적응형·온라인 학습 상위 결과

| model_id           | family        | training_strategy   | adaptation    |   log_loss |    brier |   roc_auc |   accuracy |
|:-------------------|:--------------|:--------------------|:--------------|-----------:|---------:|----------:|-----------:|
| L2_C0.03           | L2_LOGISTIC   | EXPANDING_DAILY     | DAILY_RETRAIN |   0.668838 | 0.237708 |  0.629807 |   0.591346 |
| L2_C0.03           | L2_LOGISTIC   | ROLLING_1080_DAILY  | DAILY_RETRAIN |   0.669514 | 0.237995 |  0.629969 |   0.59375  |
| ENET_C0.1_L10.25   | ELASTIC_NET   | EXPANDING_DAILY     | DAILY_RETRAIN |   0.669574 | 0.238024 |  0.627931 |   0.591346 |
| RF_D3_L8_MFsqrt    | RANDOM_FOREST | EXPANDING_DAILY     | DAILY_RETRAIN |   0.669773 | 0.238449 |  0.633885 |   0.598558 |
| ENET_C0.1_L10.25   | ELASTIC_NET   | ROLLING_1080_DAILY  | DAILY_RETRAIN |   0.670196 | 0.238386 |  0.628186 |   0.586538 |
| XGB_LR0.02_D2_MCW2 | XGBOOST       | EXPANDING_DAILY     | DAILY_RETRAIN |   0.670488 | 0.238847 |  0.621258 |   0.617788 |
| L2_C0.03           | L2_LOGISTIC   | ROLLING_720_DAILY   | DAILY_RETRAIN |   0.670858 | 0.238793 |  0.623645 |   0.584135 |
| L2_C0.03           | L2_LOGISTIC   | DECAY_HL240_DAILY   | DAILY_RETRAIN |   0.671413 | 0.238971 |  0.621444 |   0.584135 |
| ENET_C0.1_L10.25   | ELASTIC_NET   | ROLLING_720_DAILY   | DAILY_RETRAIN |   0.671756 | 0.239306 |  0.621421 |   0.596154 |
| RF_D3_L8_MFsqrt    | RANDOM_FOREST | ROLLING_1080_DAILY  | DAILY_RETRAIN |   0.671812 | 0.239452 |  0.624734 |   0.596154 |
| ENET_C0.1_L10.25   | ELASTIC_NET   | DECAY_HL240_DAILY   | DAILY_RETRAIN |   0.672353 | 0.23944  |  0.619011 |   0.586538 |
| XGB_LR0.02_D2_MCW2 | XGBOOST       | ROLLING_1080_DAILY  | DAILY_RETRAIN |   0.673115 | 0.240146 |  0.613891 |   0.59375  |
| RF_D3_L8_MFsqrt    | RANDOM_FOREST | DECAY_HL240_DAILY   | DAILY_RETRAIN |   0.673685 | 0.240364 |  0.618409 |   0.591346 |
| RF_D3_L8_MFsqrt    | RANDOM_FOREST | ROLLING_720_DAILY   | DAILY_RETRAIN |   0.675698 | 0.241353 |  0.611088 |   0.579327 |
| L2_C0.03           | L2_LOGISTIC   | DECAY_HL120_DAILY   | DAILY_RETRAIN |   0.675857 | 0.241155 |  0.607845 |   0.5625   |

## 확률 보정·앙상블

| model_id             | method                                       |   log_loss |    brier |   roc_auc |   accuracy |   n |
|:---------------------|:---------------------------------------------|-----------:|---------:|----------:|-----------:|----:|
| OOF_TOP6_MEAN        | unweighted ensemble selected by 2024-2025 CV |   0.667718 | 0.237184 |  0.631429 |   0.596154 | 416 |
| OOF_LOGIT_STACK      | out-of-time OOF logistic stack C=0.01        |   0.667952 | 0.237522 |  0.631684 |   0.605769 | 416 |
| OOF_TOP6_MEDIAN      | unweighted ensemble selected by 2024-2025 CV |   0.668203 | 0.237401 |  0.630294 |   0.596154 | 416 |
| CV_CHAMPION_PLATT    | OOF Platt calibration of L2_C0.03            |   0.668225 | 0.237539 |  0.631568 |   0.603365 | 416 |
| CV_CHAMPION_ISOTONIC | OOF isotonic calibration of L2_C0.03         |   0.725047 | 0.238443 |  0.626958 |   0.586538 | 416 |

## 핵심 판정
- 2026을 보지 않고 CV만으로 선택된 모델: **L2_C0.03**
- 해당 모델의 2026 ALL_EQUAL Log loss: **0.667389633**
- 2026에서 가장 좋은 정적 학습법: **L2_C0.1 / RECENT_720**, Log loss **0.666134784**
- 2026에서 가장 좋은 적응형 학습법: **L2_C0.03 / EXPANDING_DAILY**, Log loss **0.668838398**
- 전체 방법 중 2026 최고 관찰값: **L2_C0.1 / RECENT_720**, Log loss **0.666134784**, AUC **0.635275**

## 신규 타자 수입 ablation

| model_id                |   log_loss |    brier |   roc_auc |   accuracy |   n |
|:------------------------|-----------:|---------:|----------:|-----------:|----:|
| CV_CHAMPION_WITH_BATTER |   0.66739  | 0.237034 |  0.631568 |   0.59375  | 416 |
| CV_CHAMPION_NO_BATTER   |   0.672733 | 0.239703 |  0.619266 |   0.581731 | 416 |
| BEST_DIRECT_WITH_BATTER |   0.666135 | 0.236498 |  0.635275 |   0.596154 | 416 |
| BEST_DIRECT_NO_BATTER   |   0.673157 | 0.239875 |  0.617343 |   0.579327 | 416 |

## 통계적 비교

| new_model                 | reference_model         |   delta_log_loss |      ci_low |      ci_high |   improvement_probability |   reps |
|:--------------------------|:------------------------|-----------------:|------------:|-------------:|--------------------------:|-------:|
| p_cv_champion_with_batter | p_cv_champion_no_batter |      -0.00534339 | -0.0123637  |  0.00185636  |                    0.9264 |  10000 |
| p_best_direct_with_batter | p_best_direct_no_batter |      -0.00702224 | -0.013416   | -0.000547958 |                    0.9832 |  10000 |
| p__L2_C0.1__RECENT_720    | p__L2_C0.03__ALL_EQUAL  |      -0.00125485 | -0.00478954 |  0.00233624  |                    0.7461 |  10000 |

## 결론 사용 규칙
- CV-selected champion은 2026을 보지 않고 고른 학문적으로 깨끗한 기준 후보다.
- 2026 best observed는 학습전략 개발 후보이며, 그 숫자를 최종 일반화 성능으로 주장하면 안 된다.
- 최종 모델은 선택 후 고정하고 이후 경기에서 prospective ledger로 검증해야 한다.