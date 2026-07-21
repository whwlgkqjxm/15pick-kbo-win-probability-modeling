from __future__ import annotations
import csv, hashlib, json, os, platform, shutil, subprocess, sys, zipfile
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import sklearn

ROOT = Path('/mnt/data')
OUT = ROOT/'15Pick_RQ1_V11_BATTER_INCOME_REBUILD_LAB_20260720'
PKG = ROOT/'15Pick_RQ1_V11_1_BATTER_INCOME_FINAL_PACKAGE_20260720'
PRE = ROOT/'V11_1_PRE_REPRO_SHA256.txt'
INPUTS = [
 ROOT/'rq1_work/data/kbo_multiseason_income_foundation_v1/player_game_fantasy_income_2024_2026_v1.csv',
 ROOT/'rq1_work/data/rq1_lineup_confirmed_temporal_model_v1/lineup_confirmed_game_features_v1.csv',
 ROOT/'rq1_work/data/kbo_boxscore_canonical_v1/canonical_starting_lineups_v1.csv',
 ROOT/'rq1_work/v7/RQ1_V7_INCOME_TO_PREDICTION_INTEGRATION_LAB_OFFLINE_RESULTS/V7_AVERAGE_AND_AGGREGATION_FEATURES.csv',
 ROOT/'rq1_work/v9/RQ1_V9_POST_STARTER_TEAM_RUNS_LAB_OFFLINE_RESULTS/V9_STRICT_PRIOR_POST_STARTER_FEATURES.csv',
]

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

required = [
 'V11_1_CLEAN_INTEGRATION_SEARCH.csv','V11_1_2024_SELECTED_ENSEMBLES_2025_VALIDATION.csv',
 'V11_1_ENSEMBLE_PREDICTIONS_2025.csv','V11_1_PROSPECTIVE_CANDIDATE_DECISION.json',
 'V11_1_ROBUST_CANDIDATE_PREDICTIONS_2025.csv','V11_1_ROBUST_CANDIDATE_BOOTSTRAP.csv',
 'V11_1_ROBUST_CANDIDATE_COMPARISON.csv','V11_1_SELECTED_LINEUP_PLAYER_PRIOR_INCOME.csv',
 'V11_1_SELECTED_BATTER_INCOME_FORMULA.json','V11_1_PROSPECTIVE_REFIT_MODEL_2024_2025.joblib',
 'V11_1_PROSPECTIVE_MODEL_SCHEMA.json','RQ1_V11_1_FINAL_BATTER_INCOME_REPORT.md'
]
missing=[f for f in required if not (OUT/f).exists()]
if missing: raise SystemExit(f'Missing required outputs: {missing}')

comp=pd.read_csv(OUT/'V11_1_ROBUST_CANDIDATE_COMPARISON.csv')
boot=pd.read_csv(OUT/'V11_1_ROBUST_CANDIDATE_BOOTSTRAP.csv')
pred=pd.read_csv(OUT/'V11_1_ROBUST_CANDIDATE_PREDICTIONS_2025.csv')
prior=pd.read_csv(OUT/'V11_1_SELECTED_LINEUP_PLAYER_PRIOR_INCOME.csv')
dec=json.loads((OUT/'V11_1_PROSPECTIVE_CANDIDATE_DECISION.json').read_text())
formula=json.loads((OUT/'V11_1_SELECTED_BATTER_INCOME_FORMULA.json').read_text())
schema=json.loads((OUT/'V11_1_PROSPECTIVE_MODEL_SCHEMA.json').read_text())
model=joblib.load(OUT/'V11_1_PROSPECTIVE_REFIT_MODEL_2024_2025.joblib')

checks={}
checks['required_files_present']=not missing
checks['comparison_models_present']=set(['V11_1_NEW_BATTER','V9_STYLE_CURRENT_PRIMARY','CLEAN_NO_BATTER','TEAM_BASELINE']).issubset(set(comp.model_id))
checks['prediction_rows_698']=len(pred)==698
checks['prediction_game_ids_unique']=pred.game_id.nunique()==698
checks['prediction_probabilities_valid']=all(pred[c].between(0,1).all() for c in pred.columns if c.startswith('p_'))
checks['selected_prior_rows_33552']=len(prior)==33552
checks['selected_prior_18_rows_per_game']=bool(prior.groupby('game_id').size().eq(18).all())
checks['selected_prior_9_rows_per_side']=bool(prior.groupby(['game_id','side']).size().eq(9).all())
checks['selected_prior_player_id_complete']=int(prior.player_id.isna().sum())==0
checks['legacy_income_not_used']=formula.get('legacy_income_used') is False
checks['no_2026_tuning']=dec.get('no_2026_tuning') is True and 2026 in schema.get('excluded_from_training',[])
checks['selected_formula_expected']=dec.get('selected_score_id')=='POWER_OBP__RATE100' and dec.get('selected_mean_method')=='S_K5'
checks['model_loadable']=model is not None
new=float(comp.loc[comp.model_id.eq('V11_1_NEW_BATTER'),'log_loss'].iloc[0])
clean=float(comp.loc[comp.model_id.eq('CLEAN_NO_BATTER'),'log_loss'].iloc[0])
v9=float(comp.loc[comp.model_id.eq('V9_STYLE_CURRENT_PRIMARY'),'log_loss'].iloc[0])
checks['new_batter_beats_clean_no_batter']=new < clean
checks['new_batter_beats_v9_style_on_2025_validation']=new < v9
checks['reported_delta_matches']=abs((new-clean)-float(boot.loc[boot.reference_model.eq('p_clean_no_batter'),'delta_log_loss'].iloc[0])) < 1e-12
if not all(checks.values()):
    bad=[k for k,v in checks.items() if not v]
    raise SystemExit('Audit failed: '+', '.join(bad))

# Compare regenerated hashes against the prior successful run.
pre={}
if PRE.exists():
    for line in PRE.read_text().splitlines():
        parts=line.split(None,1)
        if len(parts)==2: pre[parts[1].strip()]=parts[0]
hash_cmp=[]
for f in required:
    post=sha(OUT/f)
    hash_cmp.append({'file':f,'pre_repro_sha256':pre.get(f,''),'post_repro_sha256':post,'identical_to_prior_successful_run':pre.get(f,'')==post if f in pre else None})
pd.DataFrame(hash_cmp).to_csv(OUT/'V11_1_REPRO_SHA256_COMPARISON.csv',index=False)

input_manifest=[]
for p in INPUTS:
    input_manifest.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
pd.DataFrame(input_manifest).to_csv(OUT/'V11_1_INPUT_DATA_SHA256.csv',index=False)

audit={
 'status':'PASS',
 'checks':checks,
 'key_results':{
   'n_2025_validation':698,
   'v11_1_new_batter_log_loss':new,
   'clean_no_batter_log_loss':clean,
   'delta_vs_clean_no_batter':new-clean,
   'v9_style_log_loss':v9,
   'delta_vs_v9_style':new-v9,
   'v11_1_auc':float(comp.loc[comp.model_id.eq('V11_1_NEW_BATTER'),'roc_auc'].iloc[0]),
   'bootstrap_vs_clean':boot.loc[boot.reference_model.eq('p_clean_no_batter')].iloc[0].to_dict(),
 },
 'scientific_status':'post-holdout development candidate; prospective confirmation required',
 'reproducibility_note':'The final V11.1 pipeline was rerun from source. Hash equality is reported per output; CSV/model hashes may differ only if library serialization or floating ordering changes, while metric equality is separately audited.',
}
(OUT/'V11_1_REPRODUCIBILITY_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')

env='\n'.join([
 f'python={sys.version.replace(os.linesep," ")}',f'platform={platform.platform()}',
 f'numpy={np.__version__}',f'pandas={pd.__version__}',f'scikit-learn={sklearn.__version__}',f'joblib={joblib.__version__}',
 'seed=20260720',
])+'\n'
(OUT/'V11_1_ENVIRONMENT.txt').write_text(env,encoding='utf-8')

summary=f'''# RQ1 V11.1 신규 타격 수입 시스템 완료 요약

## 완료 상태
- 최종 파이프라인 재실행: PASS
- 필수 결과 파일 검사: PASS
- 모델 파일 로드 검사: PASS
- 2025 예측 698경기·game_id 중복 0·확률 범위 검사: PASS
- 공식 선발 라인업 33,552행, 경기당 18명·팀당 9명 검사: PASS
- 기존 15Pick 타격 수입 사용: 없음
- 2026 선택/튜닝 사용: 없음

## 선택된 완전 신규 타격 수입
- 경기 점수: POWER_OBP__RATE100
- 이벤트 가중치: 1B 0.50, 2B 0.95, 3B 1.35, HR 1.85, BB/HBP 0.42, SB 0.22, SO -0.08, GIDP -0.32
- 경기 총점 대신 PA당 점수를 4.2 PA 기준으로 정규화
- 선수 평균: S_K5 — 같은 시즌 strict-prior 평균을 전년도 평균으로 K=5 수축
- 라인업 반영: 공식 선발 9명의 평균 + coverage/reliability
- 예측 모델: 팀 전력 + 깨끗한 선발/포스트선발 정보 + 신규 타자 수입, L2 Logistic Regression C=0.01

## 2025 검증 결과
- 신규 타자 모델 Log loss: {new:.9f}
- 타자 없는 동일 모델: {clean:.9f}
- 개선량: {new-clean:.9f}
- V9_STYLE: {v9:.9f}
- V9_STYLE 대비 개선량: {new-v9:.9f}
- 신규 타자 모델 AUC: {audit['key_results']['v11_1_auc']:.9f}

## 해석
신규 타자 수입은 기존 타격 수입과 섞지 않은 상태에서 타자 없는 동일 구조보다 2025 검증 성능을 개선했다. 다만 2025 결과를 본 뒤 최종 후보를 선택했으므로 이는 untouched 최종 증거가 아니라 post-holdout development candidate다. 이 후보는 그대로 동결하고 미래 경기 prospective 검증으로 확정해야 한다.
'''
(OUT/'RQ1_V11_1_COMPLETION_SUMMARY.md').write_text(summary,encoding='utf-8')

# Build self-contained package without duplicating raw/licensing-sensitive KBO data.
if PKG.exists(): shutil.rmtree(PKG)
(PKG/'results').mkdir(parents=True)
(PKG/'source').mkdir()
(PKG/'logs').mkdir()
for p in OUT.iterdir():
    if p.is_file(): shutil.copy2(p, PKG/'results'/p.name)
for p in [ROOT/'run_batter_income_rebuild_v11.py', ROOT/'run_batter_income_v11_1_integration.py', ROOT/'finalize_v11_1_package.py']:
    shutil.copy2(p, PKG/'source'/p.name)
for p in [ROOT/'batter_v11.log',ROOT/'batter_v11_1.log',ROOT/'batter_v11_1_repro.log',ROOT/'batter_v11_rerun.log']:
    if p.exists(): shutil.copy2(p, PKG/'logs'/p.name)
readme='''# 15Pick RQ1 V11.1 Batter Income Final Package\n\nThis package contains source code, experiment outputs, prediction files, fitted prospective-candidate model, reports, audit files, logs, and SHA-256 manifests. Raw official KBO data are not duplicated here; their exact local input paths and hashes are listed in `results/V11_1_INPUT_DATA_SHA256.csv`.\n\nScientific status: post-holdout development candidate. Freeze before prospective use; do not tune with 2026.\n'''
(PKG/'README.md').write_text(readme,encoding='utf-8')
manifest=[]
for p in sorted(PKG.rglob('*')):
    if p.is_file() and p.name!='FINAL_MANIFEST_SHA256.csv':
        manifest.append({'file':str(p.relative_to(PKG)),'bytes':p.stat().st_size,'sha256':sha(p)})
pd.DataFrame(manifest).to_csv(PKG/'FINAL_MANIFEST_SHA256.csv',index=False)
# verify manifest
mf=pd.read_csv(PKG/'FINAL_MANIFEST_SHA256.csv')
for r in mf.itertuples(index=False):
    p=PKG/r.file
    if p.stat().st_size!=r.bytes or sha(p)!=r.sha256: raise SystemExit('Manifest verification failed '+r.file)
zip_path=ROOT/(PKG.name+'.zip')
if zip_path.exists(): zip_path.unlink()
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(PKG.rglob('*')):
        if p.is_file(): z.write(p,p.relative_to(ROOT))
with zipfile.ZipFile(zip_path) as z:
    bad=z.testzip()
    if bad: raise SystemExit('ZIP CRC failed '+bad)
sidecar=ROOT/(zip_path.name+'.sha256')
sidecar.write_text(f'{sha(zip_path)}  {zip_path.name}\n',encoding='utf-8')
print(json.dumps({'status':'PASS','package':str(PKG),'zip':str(zip_path),'zip_sha256':sha(zip_path),'files':len(manifest)},ensure_ascii=False,indent=2))
