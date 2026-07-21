# 15Pick / MyPick KBO RQ1 완전 연구 아카이브 v15.0

이 아카이브는 기존 v13 전체 연구 보관본에 **V11.1 완전 신규 타자 수입 시스템**과
**V12 학습전략·머신러닝 비교**를 완전히 통합한 최신 source of truth다.

## 가장 먼저 읽기
1. `00_READ_FIRST/MASTER_HANDOVER_v15.0_20260720.txt`
2. `00_READ_FIRST/CURRENT_STATUS_v15.json`
3. `00_READ_FIRST/CURRENT_BEST_MODEL_v15.md`
4. `00_READ_FIRST/MASTER_EXPERIMENT_LEDGER_v15.csv`
5. `00_READ_FIRST/KNOWN_GAPS_AND_LIMITATIONS.md`

## 현재 핵심 결과
- 신규 타자 수입: `POWER_OBP__RATE100 / S_K5 / lineup MEAN`
- 기존 legacy 타자 수입 사용 없음
- 현재 최고 관측 개발 모델: `L2 C=0.1 / RECENT_720`
- 2026 개발 평가: Log loss `0.666134784`, Brier `0.236497862`, AUC `0.635274766`, Accuracy `59.6154%`
- 타자 block 제거 시 Log loss `0.673157026`
- 타자 incremental improvement probability `98.32%`
- 2026을 보고 학습전략을 선택했으므로 최종 untouched 성능은 아님

## 새 폴더
- `04_GIT_VIEW/EXPERIMENTS/V11_1_BATTER_INCOME`
- `04_GIT_VIEW/EXPERIMENTS/V12_TRAINING_STRATEGY`
- `05_SOURCE_CODE_AVAILABLE/V11_1_BATTER_INCOME`
- `05_SOURCE_CODE_AVAILABLE/V12_TRAINING_STRATEGY`

## 무결성 검증
```bash
python3 07_TOOLS/verify_archive.py
```

GitHub 공개 전 KBO 원자료의 재배포 조건을 확인하고, 기본적으로 private repository를 사용한다.
