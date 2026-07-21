# RQ1 V10 Official Game-Page Feature Lab — Final v1.1

## 질문

KBO 공식 일정 페이지에서 연결되는 경기별 공식 자료만으로 다음 신호를 누수 없이 구축했을 때 V9보다 승리확률 예측이 좋아지는가?

1. 선발투수 예상 소화 이닝/아웃카운트
2. 선발투수 유형 × 공식 선발 라인업 상성
3. 타선 상·중·하위 구간과 타순 가중 구조
4. 공식 라인업 연속성 및 핵심 선발 이탈 proxy
5. V9와 독립 모델 학습 후 temporal logit stacking

## 데이터 계약

- 경기 인덱스와 경기 데이터: KBO 공식 Schedule/GameCenter 계열에서 이미 동결한 원본·canonical BoxScore.
- 선수 투타 유형: KBO 공식 선수 프로필 원본.
- 목표 경기 및 같은 날짜 경기 결과는 history update에서 제외.
- 2024 temporal folds에서 feature configuration과 regularization만 선택.
- 2025 전체 시즌 698경기는 새 V10 프로토콜의 untouched holdout.
- 2026은 post-hoc 진단만 수행.

## 실제 구축 가능성 감사

- 전체 경기: 1,864.
- 공식 선발 라인업 정확히 18명인 경기: 1,864/1,864.
- 타자 타격 유형 coverage: 92.00%.
- 선발투수 투구 유형 coverage: 99.97%.
- 현재 경기 사용: 없음.
- 같은 날짜 결과 사용: 없음.

동결 자료만으로 구현하지 않은 항목:

- **실제 선발 교체 시점 이후 발생한 모든 득점**: frozen BoxScore에는 완전한 play-by-play 득점 타임라인이 없어 책임실점과 실제 발생 시점을 분리할 수 없음.
- **과거 날짜별 공식 1군 엔트리/결장 상태**: 일별 등록 현황 snapshot이 freeze에 없어 공식 라인업 연속성·missing-regular proxy만 시험.

## 2025 untouched holdout 결과

| Architecture | Log loss | Brier | AUC | Accuracy |
|---|---:|---:|---:|---:|
| V9_STYLE | 0.667336 | 0.237412 | 0.6286 | 58.31% |
| V10_COMBINED_MODEL | 0.667817 | 0.237603 | 0.6292 | 59.74% |
| V10_MATCHUP | 0.668703 | 0.237977 | 0.6266 | 59.74% |
| V10_LINEUP | 0.669236 | 0.238337 | 0.6221 | 57.88% |
| V10_WORKLOAD | 0.670077 | 0.238797 | 0.6190 | 59.17% |
| V10_SEPARATE_BLOCKS | 0.670090 | 0.238760 | 0.6204 | 59.17% |

### 최고 새 challenger 대 V9

- Log loss 변화: **+0.000481** — 악화.
- Brier 변화: **+0.000191** — 악화.
- AUC 변화: **+0.000690** — 미세 개선.
- Accuracy 변화: **+1.43 percentage points** — 개선.
- 날짜 단위 paired bootstrap log-loss CI95: **[-0.002909, +0.003879]**.
- challenger가 log loss를 개선할 확률: **38.48%**.

따라서 V10 combined는 적중률을 높였지만 확률 예측의 primary metrics인 Log loss와 Brier를 악화시켰다. 정식 교체 근거가 아니다.

## 2026 post-hoc

| Architecture | Log loss | Brier | AUC | Accuracy |
|---|---:|---:|---:|---:|
| V9_STYLE | 0.665999 | 0.236103 | 0.6392 | 61.78% |
| V10_COMBINED_MODEL | 0.665777 | 0.236161 | 0.6419 | 60.58% |

2026에서는 V10 combined가 log loss를 -0.000223 개선했지만, 이 기간은 이미 여러 연구 단계에서 관찰된 post-hoc 자료이므로 모델 선택 근거로 사용할 수 없다.

## 최종 결정

- **Primary 유지: V9-style architecture.**
- V10 combined: accuracy-oriented prospective challenger로만 보존.
- 이번에 시험한 workload·matchup·lineup-continuity feature는 공식 경기 자료에서 누수 없이 만들 수 있었지만, 2025 untouched holdout에서 확률 성능의 incremental improvement를 만들지 못했다.
- 다음으로 실질적으로 새로운 정보가 될 후보는 GameCenter play-by-play 기반의 실제 선발 교체 후 득점과 날짜별 공식 1군 등록 snapshot이다.

## 프로토콜 주의

이 보고서의 V9_STYLE 절대 수치는 이전 V9 보고서의 0.669004와 같은 실험 구간이 아니다. V10에서는 2024만으로 설정을 선택하고 2025 전체를 untouched holdout으로 다시 정의했다. 따라서 V10 내부 상대 비교는 공정하지만, 과거 보고서의 절대 수치와 단순 병합해서는 안 된다.
