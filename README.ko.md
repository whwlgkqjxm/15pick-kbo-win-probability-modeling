# 15Pick — 역할별 선수 활약 지표를 활용한 KBO 승리확률 예측

**15Pick**은 경기 전에 이용 가능한 정보만 사용해 KBO 경기의 승리확률을 예측하는 연구 프로젝트다. 핵심 목적은 선수 활약 점수 자체를 소개하는 것이 아니라, 복잡한 선수 기록을 압축한 역할별 활약 지표가 기존 팀 전력 및 경기 전 정보에 추가적인 예측 가치를 제공하는지 검증하는 것이다.

[English README](README.md)

## 연구 동기

15Pick은 판타지 스포츠와 포인트 기반 승부예측 기능을 제공하는 웹사이트로 시작했다. 야구 선수의 활약은 단타, 장타, 볼넷, 삼진, 병살, 투구 이닝, 피홈런 등 서로 성격이 다른 많은 기록에 분산되어 있다. 야구에 익숙하지 않은 사용자에게는 이 기록들을 한눈에 비교하기가 어렵고, 타자와 투수처럼 역할이 다른 선수들을 직관적으로 이해하기도 쉽지 않다.

그래서 15Pick은 공식 경기 기록을 하나의 **선수 활약 점수**로 요약했다. 이 점수의 원래 목적은 복잡한 기록을 단순화해 사용자가 선수들의 최근 활약 정도를 쉽게 비교하도록 돕는 것이었다.

하지만 이해하기 쉬운 점수가 통계적으로도 유용하다는 보장은 없다. 여러 기록을 하나로 압축하는 과정에서 중요한 정보가 사라질 수도 있고, 임의의 가중치가 불안정한 신호를 만들 수도 있다. 이 의문에서 다음 연구가 시작되었다.

> **역할별 선수 활약 지표가 단순한 화면 표시용 점수를 넘어 실제 미래 경기의 승리확률 예측에도 도움이 되는가?**

따라서 이 저장소의 중심은 **KBO 승리확률 예측 모델**이며, 선수 활약 지표는 그 모델에 추가되는 연구 변수다.

## Research Question

> **공식 KBO 경기 기록으로 구축한 역할별 strict-prior 복합 선수 활약 지표는 기존 팀 전력과 일반적인 경기 전 정보만 사용하는 모델보다 KBO 경기의 승리확률 예측을 개선하는가?**

## 핵심 결과

같은 모델, 같은 학습 구간, 같은 기존 경기 전 변수를 유지한 상태에서 타자와 선발투수 활약 지표를 추가하자 모든 주요 지표가 개선되었다.

### 2026년 416경기 기준 최고 개발 결과

| 변수 구성 | Log loss ↓ | Brier ↓ | ROC AUC ↑ | Accuracy ↑ |
|---|---:|---:|---:|---:|
| 기존 팀·경기 전 변수만 사용 | 0.683942 | 0.245313 | 0.575781 | 54.33% |
| + 타자 활약 지표 | 0.678611 | 0.242599 | 0.603188 | 57.45% |
| + 선발투수 활약 지표 | 0.673157 | 0.239875 | 0.617343 | 57.93% |
| **+ 타자와 선발투수 활약 지표** | **0.666135** | **0.236498** | **0.635275** | **59.62%** |

기존 변수만 사용한 모델과 비교한 개선폭은 다음과 같다.

- Log loss: **−0.017807**
- Brier score: **−0.008815**
- ROC AUC: **+0.059494**
- 정확도: **+5.29%p**
- 날짜 단위 bootstrap에서 Log loss 개선 확률: **98.69%**
- Log-loss 차이의 95% bootstrap 구간: **[−0.033154, −0.002114]**

![선수 활약 지표 ablation](reports/figures/primary_ablation_logloss.png)

타자만 추가한 모델과 선발투수만 추가한 모델이 각각 기준 모델보다 좋아졌고, 두 지표를 함께 사용했을 때 가장 좋은 결과가 나왔다. 이는 두 역할별 지표가 서로 완전히 중복되지 않는 정보를 제공한다는 근거다.

## 실제 야구 승부예측 연구와의 비교 목표

야구 승부예측에는 모든 연구에 적용되는 절대적인 성공 기준이 없다. 리그, 데이터 단위, 사용 가능한 정보 시점, 변수, 검증 방식에 따라 성능이 달라지기 때문이다.

Li, Huang, and Li(2022)는 기존 MLB 다음 경기 예측 연구의 정확도가 대체로 **55–62%**라고 정리했고, 해당 연구의 feature-selected SVM은 **65.75% 정확도와 0.6501 AUC**를 기록했다. Soto Valero(2016)의 비교 연구에서는 최고 모델의 정확도가 **58.92%**였다.

| 비교 수준 | Accuracy | ROC AUC | Log loss | Brier |
|---|---:|---:|---:|---:|
| 0.5 중립 확률 예측 | 50.00% | 0.5000 | 0.6931 | 0.2500 |
| 일반적인 MLB 연구 맥락 | 약 55–62% | 연구별 상이 | 대부분 미보고 | 대부분 미보고 |
| 강한 MLB 연구 사례 | 65.75% | 0.6501 | 미보고 | 미보고 |
| **15Pick 현재 개발 모델** | **59.62%** | **0.6353** | **0.6661** | **0.2365** |

이 수치들은 직접적인 순위표가 아니라 외부 맥락이다. 15Pick은 KBO 전체 경기를 대상으로 시간순 strict-prior 검증을 수행하며, 비교 연구들은 리그와 검증 방식이 다르다.

### 향후 성공 판정 기준

1. **학문적 가치:** 선수 활약 지표를 포함한 모델이 동일 조건의 미포함 모델보다 Log loss와 Brier score를 모두 개선해야 한다.
2. **경쟁력 있는 예측:** 미래 동결 평가에서 약 **60% 정확도**, **AUC 0.63 이상**을 유지하고 calibration이 안정적이어야 한다.
3. **도전 목표:** Log loss와 Brier를 악화시키지 않으면서 **AUC 약 0.65**에 접근한다.
4. **최종 확정:** 모델을 동결한 뒤 실제 미래 경기 예측 원장에서도 결과가 재현되어야 한다.

승패 정확도만 높이는 것이 목적은 아니다. 15Pick은 승리확률을 출력하므로 Log loss, Brier score, calibration을 우선한다.

자세한 내용은 [`docs/external_benchmarks_and_success_criteria.md`](docs/external_benchmarks_and_success_criteria.md)에 정리했다.

## 불펜투수 활약 지표의 negative result

선수 단위 불펜투수 활약 지표를 추가했을 때 예측 성능은 개선되지 않았다.

| 평가 | 기준 Log loss | 불펜투수 지표 추가 | 차이 |
|---|---:|---:|---:|
| 2025 불펜 영역 모델 | 0.687435 | 0.687444 | **+0.000009** |
| 2025 선발 stack에 추가 | 0.669483 | 0.674253 | **+0.004770** |
| 2026 사후 추가 | 0.667785 | 0.668898 | **+0.001113** |

Log loss는 낮을수록 좋으므로 양수 차이는 악화다. 독립적인 2025 비교의 개선 확률도 **49.95%**로 사실상 무효였다.

이 결과는 불펜의 중요성이 낮다는 뜻이 아니다. 경기 전에 선수 단위 불펜 전력을 정확하게 표현하기 어려웠다는 뜻이다.

- 선발투수와 달리 실제 등판할 구원투수는 경기 전에 확정되지 않는다.
- 투입 선수는 이닝, 점수차, 레버리지, 선발 교체 시점, 좌우 상성, 감독 전략에 따라 경기 중 결정된다.
- 실제 등판자를 사용하면 경기 후 정보를 사용하는 누수가 발생한다.
- 반대로 전체 불펜 후보를 평균내면 출전하지 않을 선수들이 포함되어 신호가 희석된다.
- 최근 투구 수, 연투, 휴식일, 부상 및 엔트리 상태에 따라 실제 가용성이 계속 변한다.
- 불펜투수는 표본 이닝이 작고 역할과 레버리지의 영향을 크게 받아 개인 평균의 분산이 높다.

MLB 연구에서도 최근 투구량이 구원투수의 단기 컨디션에 영향을 줄 수 있고, 투수 교체는 좌우 상성과 경기 상황을 반영한 전략적 의사결정으로 설명된다. 최종 모델은 선수별 불펜 지표 대신 **팀 단위 strict-prior 선발 이후 실점 억제 지표**를 사용한다.

![불펜투수 지표 negative result](reports/figures/relief_pitcher_index_negative_result.png)

자세한 분석은 [`docs/relief_pitcher_index_negative_result.md`](docs/relief_pitcher_index_negative_result.md)에 있다.

## 과학적 상태

두 가지 모델을 구분한다.

1. **시간순 CV 선택 모델:** 2024–2025만 사용해 L2 Logistic Regression `C=0.03`을 선택했다. 2026 평가에서 선수 활약 지표 추가 시 Log loss가 `0.683516 → 0.667390`으로 개선되었다.
2. **현재 최고 개발 모델:** 최근 720경기를 사용하는 L2 Logistic Regression `C=0.1`이다. Log loss가 `0.683942 → 0.666135`로 개선되었다.

두 번째 모델이 현재 가장 좋은 결과를 기록했지만, 2026 결과를 연구 과정에서 반복적으로 확인했다. 따라서 untouched final test나 production champion이라고 부르지 않으며, 최종 결론은 미래 경기 prospective 검증이 필요하다.

## 데이터 기반

| 항목 | 규모 |
|---|---:|
| 공식 일정 행 | 2,047 |
| 완료 경기 | 1,864 |
| 취소·연기 경기 | 183 |
| 기간 | 2024, 2025, 2026년 7월 9일까지 |
| 선수-경기 occurrence | 65,554 |
| 타자 occurrence | 47,353 |
| 투수 occurrence | 18,201 |
| 공식 선발 라인업 행 | 33,552 |
| 선수 식별 완료 | 65,554 / 65,554 |
| 같은 날짜 누수 위반 | 0 |

무승부는 이진 모델 학습에서 제외했다. 시즌별 모델 행은 2024년 710경기, 2025년 698경기, 2026년 416경기다.

전체 KBO 원본 데이터는 공개 저장소에 재배포하지 않는다. 대신 스키마, 합성 예제, 유지 코드, 집계 결과와 데이터 계보를 제공한다.

## 역할별 선수 활약 지표

### 타자 활약 지표

```text
0.50·1B + 0.95·2B + 1.35·3B + 1.85·HR
+ 0.42·BB + 0.42·HBP + 0.22·SB
− 0.08·SO − 0.32·GIDP
```

경기 점수를 4.2타석 기준으로 정규화하고 1,000을 중심으로 표준화한다. 이후 `K=5` shrinkage를 적용한 strict-prior 선수 평균을 만든다. 경기 변수는 공식 선발 9명의 평균 지표, 이력 coverage, 이전 경기 수와 최소 coverage로 구성한다.

### 선발투수 활약 지표

```text
1000 × (
  0.216·아웃카운트
  + 0.132·삼진
  − 1.565·피홈런
  − 0.557·(볼넷 + 사구)
)
```

선발 등판 기록만 사용하며 구원 등판은 섞지 않는다. `K=10` strict-prior shrinkage로 초기 시즌과 적은 표본을 안정화한다.

공식 정의는 [`docs/player_performance_indices.md`](docs/player_performance_indices.md)에 있다.

## 누수 방지와 검증

예측 시점은 공식 선발 라인업과 선발투수가 확인된 경기 전이다.

- 목표 경기 결과는 변수에 포함하지 않는다.
- 목표 경기와 같은 날짜의 모든 결과를 제외한다.
- 더블헤더 1차전 결과를 같은 날 2차전에 사용하지 않는다.
- 결측치 처리와 scaling은 학습 데이터에서만 적합한다.
- shuffled split이 아니라 시간순 검증을 사용한다.
- 실제 목표 경기의 구원투수를 경기 전 변수로 사용하지 않는다.
- 취소 경기는 평가에서 제외하거나 void 처리한다.
- 불확실성은 날짜 단위 paired bootstrap으로 평가한다.

## 모델 및 학습전략 비교

총 42개 설정에서 다음을 비교했다.

- L2 Logistic Regression, Elastic Net
- Random Forest, Extra Trees
- Gradient Boosting, HistGradientBoosting
- XGBoost, LightGBM, CatBoost
- stacking, blending, calibration
- 전체 이력, 최근 window, time decay, rolling, expanding, online 학습

시간순 확률 예측에서는 규제가 강한 Logistic Regression이 가장 안정적이었다. 복잡한 모델이 자동으로 더 좋은 일반화 성능을 만들지는 않았다.

## 연구 진행 과정

1. 2026년 한 시즌만 사용한 초기 모델은 확률이 지나치게 압축되고 성능이 약했다.
2. 2024–2026 다년 데이터로 표본 안정성을 높였다.
3. 고차원 변수와 복잡 모델은 Logistic Regression보다 좋지 않았다.
4. 역할 audit에서 선발·교체 타자와 선발·구원 투수 이력이 혼합된 문제를 발견했다.
5. 선발투수 지표를 선발 등판만 사용하도록 재구축했다.
6. 공식 라인업과 세부 타격 기록을 사용해 타자 지표를 재구축했다.
7. 선수 단위 불펜투수 지표는 무효 또는 악화 결과를 보였다.
8. 전체 이력과 최근 window 등 학습전략을 비교했다.
9. 최종 ablation에서 기존 변수, 타자 지표, 선발 지표, 두 지표 결합을 같은 조건으로 비교했다.

## 저장소 구조

```text
15pick-kbo-win-probability/
├── configs/
├── data/
├── docs/
├── experiments/
├── models/
├── reports/
├── scripts/
├── src/fifteenpick_prediction/
└── tests/
```

## 재현 및 검증

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
make check
```

로컬 모델링 데이터로 ablation을 다시 실행하려면:

```bash
python scripts/reproduce_player_index_ablation.py \
  --data /path/to/modeling_dataset.csv \
  --protocol best-development \
  --output reports/reproduced_player_index_ablation.csv
```

## 다음 연구 단계

현재 모델과 기준 모델을 동결하고, 매 경기 시작 전에 입력·모델 hash와 예측확률을 수정 불가능한 원장에 기록한다. 충분한 미래 경기 표본이 쌓인 뒤 Log loss, Brier score, calibration, AUC, accuracy와 날짜 단위 불확실성을 평가한다.

## 참고문헌

- Li, S.-F., Huang, M.-L., & Li, Y.-Z. (2022). *Exploring and Selecting Features to Predict the Next Outcomes of MLB Games*. **Entropy, 24**(2), 288. https://doi.org/10.3390/e24020288
- Soto Valero, C. (2016). *Predicting Win-Loss Outcomes in MLB Regular Season Games—A Comparative Study Using Data Mining Methods*. **International Journal of Computer Science in Sport, 15**(2), 91–112. https://doi.org/10.1515/ijcss-2016-0007
- Burris, K., & Coleman, J. (2018). *Out of Gas: Quantifying Fatigue in MLB Relievers*. **Journal of Quantitative Analysis in Sports, 14**(2), 57–64. https://doi.org/10.1515/jqas-2018-0007
- Hirotsu, N., & Wright, M. (2005). *Modelling a Baseball Game to Optimise Pitcher Substitution Strategies Incorporating Handedness of Players*. **IMA Journal of Management Mathematics, 16**(2), 179–194. https://doi.org/10.1093/imaman/dpi009
