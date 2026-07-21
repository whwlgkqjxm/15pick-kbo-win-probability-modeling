# RQ1 V7 Income-to-Prediction Integration Lab — Corrected v1.1

## 목적

선수 수입 공식을 고르는 데서 멈추지 않고, 역할별 strict-prior 평균수입을 승리확률 예측 프로그램에 어떤 구조로 적용해야 가장 잘 일반화하는지 비교했다.

## 검증 구조

- 2024 temporal OOF: 평균 방식, 팀 집계 방식, 규제 강도와 직접 결합 후보 축소
- 2025 전체 날짜 temporal OOF: 최종 평균 및 적용 방식 선택
- 2026: 선택에 사용하지 않은 post-hoc 진단
- 현재 경기와 같은 날짜 경기 결과는 모든 평균에서 제외
- 타자 선발/교체, 투수 선발/불펜 역할 분리

## 비교한 평균수입 방식

- 현재 시즌 누적 평균
- 전년도 결합 shrinkage K = 3, 5, 10, 20, 40
- 최근 3, 5, 10경기 평균
- 날짜 기준 EWMA half-life = 3, 5, 10
- K10과 최근 5/10경기 평균의 혼합

## 선택된 평균수입

**선발투수 start-only K10 shrinkage average**

경기별 선발투수 수입:

```
1000 × (
  0.216 × 아웃카운트
  + 0.132 × 탈삼진
  - 1.565 × 피홈런
  - 0.557 × 4사구
)
```

평균은 동일 시즌의 목표일 이전 선발 등판만 사용하며, 현재 시즌 표본을 전년도 동일 선수의 선발 전용 평균으로 10경기만큼 수축한다. 전년도 개인 평균이 없으면 전년도 선발 역할 리그 평균, 그것도 없으면 목표일 이전 현재 시즌 선발 리그 평균을 사용한다.

## 가장 좋은 예측 적용 구조

모든 새 수입 feature를 V2에 직접 이어 붙이는 방식이 아니었다.

### Base model A

기존 V2 Probability 21-feature model.

### Base model B

다음 9개 입력의 별도 starter-income model:

- Elo 차이
- prior 승률 차이
- prior 경기당 득실차 차이
- prior 순위 우위
- 기존 팀 불펜 strength 차이
- 새 선발 K10 평균수입 차이
- prior 선발 등판 수 차이
- 평균수입 신뢰도 차이 `n/(n+10)`
- 양 선발 history 존재 여부

### Meta model

두 base model의 out-of-fold 확률을 logit으로 변환한 뒤 Logistic Regression으로 결합했다. Meta model은 in-sample fitted probability가 아니라 temporal OOF probability만 학습한다.

## 2025 temporal OOF

| 적용 방식 | Log loss | Brier | ROC AUC | Accuracy |
|---|---:|---:|---:|---:|
| V2 direct | 0.678417 | 0.242678 | 0.600378 | 58.31% |
| Starter-income direct | 0.670455 | 0.238999 | 0.615585 | 58.17% |
| Fixed probability blend | 0.670051 | 0.238768 | 0.617302 | 57.59% |
| **Temporal logit stack** | **0.669483** | **0.238471** | **0.620432** | **58.31%** |

Temporal stack − V2 log loss:

- point: **-0.008934**
- date-cluster bootstrap CI95: **-0.017472 ~ -0.000544**
- probability of improvement: **98.14%**

## 2026 post-hoc

| 적용 방식 | Log loss | Brier | ROC AUC | Accuracy |
|---|---:|---:|---:|---:|
| V2 direct | 0.670610 | 0.238738 | 0.629691 | 59.86% |
| Starter-income direct | 0.671670 | 0.239326 | 0.622579 | 60.34% |
| Fixed probability blend | 0.669804 | 0.238373 | 0.631753 | 60.34% |
| **Temporal logit stack** | **0.667785** | **0.237311** | **0.636364** | 59.62% |

Temporal stack − V2 log loss:

- point: **-0.002825**
- date-cluster bootstrap CI95: **-0.013915 ~ +0.007985**
- probability of improvement: **69.94%**

2026 방향은 긍정적이지만 CI가 0을 포함하므로 확정적 승리로 표현하지 않는다.

## Prospective candidate formula

2024+2025 temporal OOF로 meta model을 다시 fit한 raw-logit 표현:

```
logit(P_final)
= -0.009764599
+ 0.351756111 × logit(P_V2)
+ 0.814489740 × logit(P_starter_income)
```

이는 새 선발 평균수입 모델이 주 신호이고, V2가 보완 신호로 남는 구조다.

## 결론

- 가장 좋은 평균은 단순 최근 평균이 아니라 **role-aware K10 cross-season shrinkage average**였다.
- 가장 좋은 입력 영역은 현재까지 **선발투수**였다.
- 새 수입을 기존 V2 raw feature와 한 모델에서 무조건 섞는 것보다, 별도 확률 모델로 학습한 뒤 temporal logit stacking하는 방식이 우수했다.
- 타격 라인업과 불펜 수입은 아직 최종 완성되지 않았다.
- V7 stack은 prospective challenger이며, 미래 경기 검증 전 V2를 최종 대체했다고 선언하지 않는다.

## Correction

초기 V7 v1은 첫 2025 경기일을 누락해 fold 경계를 이동시킨 결함이 있었다. v1.1에서 모든 2025 날짜를 포함해 수정했다. 이 문서의 v1.1 수치만 권위가 있다.
