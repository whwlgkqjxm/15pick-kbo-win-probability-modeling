from pathlib import Path
import hashlib, json, shutil, zipfile, platform
import pandas as pd
import numpy as np
import joblib
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

SEED=20260720
ROOT=Path('/mnt/data')
OUT=ROOT/'15Pick_RQ1_V12_TRAINING_STRATEGY_LAB_20260720'
PKG=ROOT/'15Pick_RQ1_V12_TRAINING_STRATEGY_FINAL_PACKAGE_20260720'
if PKG.exists(): shutil.rmtree(PKG)
(PKG/'results').mkdir(parents=True)
(PKG/'source').mkdir()
(PKG/'inputs_reference').mkdir()

# Save the 2026-best observed development candidate model (selected using 2026 evaluation, so not final untouched).
df=pd.read_csv(OUT/'V12_MODELING_DATASET.csv')
features=['elo_diff','prior_win_pct_diff','prior_run_diff_per_game_diff','prior_rank_advantage','bullpen_strength_diff','K10_starter_value_diff','K10_starter_count_diff','K10_starter_reliability_diff','K10_both_starters_covered','PS_R20_RA_G_diff','mean','coverage','count_mean','coverage_min']
train=df[df.game_date<20260328].tail(720)
test=df[df.season.eq(2026)]
model=Pipeline([('imp',SimpleImputer(strategy='median',add_indicator=True)),('sc',StandardScaler()),('m',LogisticRegression(C=.1,max_iter=5000,random_state=SEED))])
model.fit(train[features],train.home_win.astype(int))
joblib.dump(model,OUT/'V12_2026_BEST_OBSERVED_RECENT720_MODEL.joblib')

# Verify predictions for CV model and best-development model.
pred=pd.read_csv(OUT/'V12_2026_ALL_PREDICTIONS.csv')
cv=joblib.load(OUT/'V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib')
p_cv=cv.predict_proba(test[features])[:,1]
p_dev=model.predict_proba(test[features])[:,1]
checks={
 'cv_model_max_abs_prediction_error':float(np.max(np.abs(p_cv-pred['p__L2_C0.03__ALL_EQUAL'].to_numpy()))),
 'development_model_max_abs_prediction_error':float(np.max(np.abs(p_dev-pred['p__L2_C0.1__RECENT_720'].to_numpy()))),
 'cv_model_loaded':True,
 'development_model_loaded':True,
 'expected_2026_rows':416,
 'actual_2026_rows':int(len(test)),
}
assert checks['cv_model_max_abs_prediction_error']<1e-12
assert checks['development_model_max_abs_prediction_error']<1e-12
(OUT/'V12_MODEL_BINARY_REPRODUCTION_AUDIT.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')

schema={
 'status':'2026-observed development candidate; not final untouched test',
 'model_id':'L2_C0.1_RECENT_720',
 'features':features,
 'training_rule':'most recent 720 decision games strictly before 2026-03-28',
 'training_rows':int(len(train)),
 'training_start_game_date':int(train.game_date.min()),
 'training_end_game_date':int(train.game_date.max()),
 'C':0.1,
 'legacy_batter_income_used':False,
 'new_batter_income_system':'POWER_OBP__RATE100 / S_K5 / lineup MEAN',
 'random_seed':SEED,
}
(OUT/'V12_2026_BEST_OBSERVED_MODEL_SCHEMA.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')

# Input hashes.
inputs=[
 ROOT/'rq1_work/data/rq1_lineup_confirmed_temporal_model_v1/lineup_confirmed_game_features_v1.csv',
 ROOT/'rq1_work/v7/RQ1_V7_INCOME_TO_PREDICTION_INTEGRATION_LAB_OFFLINE_RESULTS/V7_AVERAGE_AND_AGGREGATION_FEATURES.csv',
 ROOT/'rq1_work/v9/RQ1_V9_POST_STARTER_TEAM_RUNS_LAB_OFFLINE_RESULTS/V9_STRICT_PRIOR_POST_STARTER_FEATURES.csv',
 ROOT/'15Pick_RQ1_V11_1_BATTER_INCOME_FINAL_PACKAGE_20260720/results/V11_1_SELECTED_LINEUP_PLAYER_PRIOR_INCOME.csv',
 ROOT/'15Pick_RQ1_V11_1_BATTER_INCOME_FINAL_PACKAGE_20260720/results/V11_1_SELECTED_BATTER_INCOME_FORMULA.json',
 ROOT/'run_v12_training_strategy_lab.py',
]
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
pd.DataFrame([{'path':str(p),'size_bytes':p.stat().st_size,'sha256':sha(p)} for p in inputs]).to_csv(OUT/'V12_INPUT_DATA_SHA256.csv',index=False)

# Copy all results and source.
for p in OUT.iterdir():
 if p.is_file(): shutil.copy2(p,PKG/'results'/p.name)
shutil.copy2(ROOT/'run_v12_training_strategy_lab.py',PKG/'source'/'run_v12_training_strategy_lab.py')
shutil.copy2(ROOT/'finalize_v12_training_strategy_package.py',PKG/'source'/'finalize_v12_training_strategy_package.py')
for name in ['V11_1_SELECTED_BATTER_INCOME_FORMULA.json','V11_1_PROSPECTIVE_MODEL_SCHEMA.json']:
 shutil.copy2(ROOT/'15Pick_RQ1_V11_1_BATTER_INCOME_FINAL_PACKAGE_20260720/results'/name,PKG/'inputs_reference'/name)

readme=f'''# 15Pick RQ1 V12 Training Strategy Final Package

## Purpose
Hold the V11.1 entirely new batter-income system fixed and compare temporal machine-learning and training strategies.

## Data contract
- 2024-2025: expanding temporal cross-validation for model-family/hyperparameter selection.
- 2026: development evaluation only.
- Each 2026 adaptive prediction uses only rows with game_date earlier than the target date.
- All games on the same date are predicted before that date's outcomes are added.
- No legacy batter-income feature is used.

## Main results
- CV-selected model: L2 Logistic C=0.03.
- 2026 static all-history Log loss: 0.667389633.
- 2026 best observed development strategy: L2 Logistic C=0.1 trained on recent 720 decision games.
- Best observed 2026: Log loss 0.666134784, Brier 0.236497862, AUC 0.635274766, Accuracy 59.6154%.
- Same best method without new batter-income block: Log loss 0.673157026.
- Batter block delta Log loss: -0.007022242; paired-date bootstrap CI [-0.013416, -0.000548], improvement probability 98.32%.

## Scientific interpretation
The 2026 comparison has no within-game or same-date leakage, but 2026 has been observed and used to compare methods. Therefore the recent-720 model is a development champion, not an untouched final test result. Freeze the method and evaluate prospectively on future games.

## Key files
- results/RQ1_V12_TRAINING_STRATEGY_REPORT.md
- results/V12_2026_ALL_LEARNING_METHOD_RESULTS.csv
- results/V12_2026_BATTER_ABLATION_RESULTS.csv
- results/V12_2026_PAIRED_DATE_BOOTSTRAP.csv
- results/V12_MODEL_SELECTION_DECISION.json
- results/V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json
- results/V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib
- results/V12_2026_BEST_OBSERVED_RECENT720_MODEL.joblib
'''
(PKG/'README.md').write_text(readme,encoding='utf-8')

# Manifest.
files=sorted([p for p in PKG.rglob('*') if p.is_file()])
manifest=pd.DataFrame([{'relative_path':str(p.relative_to(PKG)),'size_bytes':p.stat().st_size,'sha256':sha(p)} for p in files])
manifest.to_csv(PKG/'FINAL_MANIFEST_SHA256.csv',index=False)
# Add manifest itself after writing (separate root hash is enough; avoid self-referential hash).

zip_path=ROOT/'15Pick_RQ1_V12_TRAINING_STRATEGY_FINAL_PACKAGE_20260720.zip'
if zip_path.exists(): zip_path.unlink()
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(PKG.rglob('*')):
  if p.is_file(): z.write(p,p.relative_to(PKG.parent))
with zipfile.ZipFile(zip_path) as z:
 bad=z.testzip()
 assert bad is None
zip_sha=sha(zip_path)
(ROOT/(zip_path.name+'.sha256')).write_text(f'{zip_sha}  {zip_path.name}\n',encoding='utf-8')
print(json.dumps({'zip':str(zip_path),'zip_sha256':zip_sha,'files':len([p for p in PKG.rglob("*") if p.is_file()]),'prediction_audit':checks},indent=2))
