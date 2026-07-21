# 현재 최고 모델과 성능 — v15

## 두 가지를 구분한다

### 현재 최고 관측 개발 모델
`L2_C0.1_RECENT_720`

- 신규 타자 수입: POWER_OBP__RATE100 / S_K5 / lineup MEAN
- clean start-only 선발 K10
- team post-starter responsibility-run features
- legacy 타자 수입 사용 없음
- legacy 선발 수입과 clean starter 수입 혼합 없음
- 최근 720 decision games 정적 학습

2026 개발 평가 416경기:
- Log loss: `0.666134784`
- Brier: `0.236497862`
- AUC: `0.635274766`
- Accuracy: `59.6154%`

이 모델은 2026을 보고 학습전략을 선택한 development champion이다.

### 2026을 보지 않고 선택한 과학적 기준 후보
`L2_C0.03_ALL_EQUAL`

2024~2025 temporal CV:
- Log loss: `0.668642531`
- Brier: `0.237899237`
- AUC: `0.628609439`

2026 개발 평가:
- Log loss: `0.667389633`
- Brier: `0.237034393`
- AUC: `0.631567973`
- Accuracy: `59.3750%`

## 타자 수입 독립 기여
RECENT_720 동일 학습법에서 신규 타자 block을 제거하면 Log loss가
`0.666134784 → 0.673157026`으로 악화됐다.

- delta: `-0.007022242`
- bootstrap CI95: `-0.013416 ~ -0.000547958`
- 개선 확률: `98.32%`

## 과학적 상태
미래 경기에서 동결 후 prospective validation을 통과한 최종 champion은 아직 없다.
