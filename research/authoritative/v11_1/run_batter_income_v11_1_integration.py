import json, math, hashlib, warnings
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss,brier_score_loss,roc_auc_score,accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore')
SEED=20260720
rng=np.random.default_rng(SEED)
DATA=Path('/mnt/data/rq1_work/data')
V7=Path('/mnt/data/rq1_work/v7/RQ1_V7_INCOME_TO_PREDICTION_INTEGRATION_LAB_OFFLINE_RESULTS')
V9=Path('/mnt/data/rq1_work/v9/RQ1_V9_POST_STARTER_TEAM_RUNS_LAB_OFFLINE_RESULTS')
OUT=Path('/mnt/data/15Pick_RQ1_V11_BATTER_INCOME_REBUILD_LAB_20260720')
INCOME=DATA/'kbo_multiseason_income_foundation_v1/player_game_fantasy_income_2024_2026_v1.csv'
BASE=DATA/'rq1_lineup_confirmed_temporal_model_v1/lineup_confirmed_game_features_v1.csv'
STAT_COLS=['singles','doubles','triples','home_runs','walks','hit_by_pitch','stolen_bases','strikeouts','double_play','runs','rbi','game_winning_hit']
BASE_FEATURES=['elo_diff','prior_win_pct_diff','prior_run_diff_per_game_diff','prior_rank_advantage','bullpen_strength_diff']
CLEAN=['K10_starter_value_diff','K10_starter_count_diff','K10_starter_reliability_diff','K10_both_starters_covered','PS_R20_RA_G_diff']
def met(y,p):
 p=np.clip(np.asarray(p),1e-6,1-1e-6);y=np.asarray(y,int)
 try:a=roc_auc_score(y,p)
 except:a=np.nan
 return dict(log_loss=log_loss(y,p),brier=brier_score_loss(y,p),roc_auc=a,accuracy=accuracy_score(y,p>=.5),n=len(y))
def pipe_l2(C):return Pipeline([('imp',SimpleImputer(strategy='median',add_indicator=True)),('sc',StandardScaler()),('m',LogisticRegression(C=C,max_iter=5000,random_state=SEED))])
def pipe_enet(C,l1):return Pipeline([('imp',SimpleImputer(strategy='median',add_indicator=True)),('sc',StandardScaler()),('m',LogisticRegression(C=C,penalty='elasticnet',solver='saga',l1_ratio=l1,max_iter=8000,random_state=SEED))])
# data
use=['season','game_date','game_id','side','team','position_type','occurrence_order','player_id','player_name','is_starting_player','stats_json','canonical_occurrence_key']
pg=pd.read_csv(INCOME,usecols=use);pg=pg[pg.position_type.eq('batter')].copy().reset_index(drop=True);pg.game_date=pg.game_date.astype(int)
ss=[]
for s in pg.stats_json:
 d=json.loads(s);h=d.get('hits',0);d2=d.get('doubles',0);d3=d.get('triples',0);hr=d.get('home_runs',0)
 ss.append({'at_bats':d.get('at_bats',0),'singles':max(0,h-d2-d3-hr),'doubles':d2,'triples':d3,'home_runs':hr,'walks':d.get('walks',0),'hit_by_pitch':d.get('hit_by_pitch',0),'stolen_bases':d.get('stolen_bases',0),'strikeouts':d.get('strikeouts',0),'double_play':d.get('double_play',0),'runs':d.get('runs',0),'rbi':d.get('rbi',0),'game_winning_hit':d.get('game_winning_hit',0)})
pg=pd.concat([pg.drop(columns='stats_json'),pd.DataFrame(ss)],axis=1);pg['pa']=pg.at_bats+pg.walks+pg.hit_by_pitch
lineup=pd.read_csv(DATA/'kbo_boxscore_canonical_v1/canonical_starting_lineups_v1.csv',usecols=['batter_occurrence_key','batting_order']).rename(columns={'batter_occurrence_key':'canonical_occurrence_key'})
pg=pg.merge(lineup,on='canonical_occurrence_key',how='left',validate='one_to_one');pg['_row']=np.arange(len(pg))
base=pd.read_csv(BASE);base=base[base.decision_game.eq(1)].copy();base.game_date=base.game_date.astype(int)
v7=pd.read_csv(V7/'V7_AVERAGE_AND_AGGREGATION_FEATURES.csv',usecols=['game_id']+CLEAN[:4]);v9=pd.read_csv(V9/'V9_STRICT_PRIOR_POST_STARTER_FEATURES.csv',usecols=['game_id','PS_R20_RA_G_diff']);base=base.merge(v7,on='game_id',how='left').merge(v9,on='game_id',how='left')
y=base.home_win.astype(int)
dates24=np.array(sorted(base.loc[base.season.eq(2024),'game_date'].unique()));de=max(20,int(len(dates24)*.35));folds=[]
for ch in np.array_split(dates24[de:],4):
 tr=base.index[(base.season.eq(2024))&(base.game_date<int(ch[0]))].to_numpy();va=base.index[(base.season.eq(2024))&(base.game_date.isin(set(ch.tolist())))].to_numpy();folds.append((tr,va))
# structures
player_groups=[]
for pid,g in pg.sort_values(['player_id','game_date','game_id','side']).groupby('player_id',sort=False):
 arr=g._row.to_numpy();d=pg.loc[arr,'game_date'].to_numpy();spl=np.r_[0,np.flatnonzero(d[1:]!=d[:-1])+1,len(arr)];player_groups.append((arr,spl))
st=pg[pg.is_starting_player.eq(1)].sort_values(['game_id','side','batting_order']);star_rows=st._row.to_numpy();side_meta=st.groupby(['game_id','side'],sort=True).first().reset_index()[['game_id','side']]
assert st.groupby(['game_id','side']).size().eq(9).all()
weights={'order_w_top':np.array([1.25,1.18,1.12,1.15,1.08,1,.88,.82,.77]),'order_w_cleanup':np.array([1.05,1.10,1.15,1.28,1.20,1,.85,.72,.65]),'order_w_pa':np.array([1.13,1.10,1.08,1.06,1.03,1,.96,.92,.88])}
BLOCKS={'MEAN':['mean','coverage','count_mean','coverage_min'],'ORDER':['mean','order_w_top','order_w_cleanup','order_w_pa','top','mid','bottom','coverage','count_mean','coverage_min'],'DISTRIBUTION':['mean','median','std','min','max','q25','q75','coverage','count_mean','coverage_min'],'TAIL':['mean','std','min','max','top','bottom','coverage','count_mean','coverage_min'],'SLOTS':[f'slot{i}' for i in range(1,10)]+['coverage','count_mean','coverage_min'],'FULL':['mean','median','std','min','max','q25','q75','top','mid','bottom','order_w_top','order_w_cleanup','order_w_pa']+[f'slot{i}' for i in range(1,10)]+['coverage','count_mean','count_min','count_max','coverage_min']}
def history(score,methods):
 out={m:np.full(len(pg),1000.,np.float32) for m in methods};cnt=np.zeros(len(pg),np.float32)
 for arr,spl in player_groups:
  allh=[];cur=None;sh=[];spa=[];sth=[];prev=np.nan;ew={3:None,5:None,10:None,20:None}
  for j in range(len(spl)-1):
   idx=arr[spl[j]:spl[j+1]];season=int(pg.loc[idx[0],'season'])
   if cur is None or season!=cur:
    if cur is not None:prev=float(np.mean(sh)) if sh else prev
    cur=season;sh=[];spa=[];sth=[];ew={3:None,5:None,10:None,20:None}
   n=len(sh);sm=float(np.sum(sh)) if n else 0.;center=float(prev) if np.isfinite(prev) else 1000.;v={}
   v['S_MEAN']=float(np.mean(sh)) if n else center
   for k in [5,10,20]:v[f'S_K{k}']=(sm+k*center)/(n+k)
   for r in [3,5,10,20]:v[f'R{r}']=float(np.mean(sh[-r:])) if n else center
   for h in [3,5,10,20]:v[f'EWMA{h}']=float(ew[h]) if ew[h] is not None else center
   v['ALL_K10']=(float(np.sum(allh))+10000)/(len(allh)+10) if allh else 1000.;v['PREV_K10']=(sm+10*center)/(n+10);v['START_K10']=(float(np.sum(sth))+10*center)/(len(sth)+10)
   allmean=(sm+5*center)/(n+5);v['HIER_START_ALL_K5']=(float(np.sum(sth))+5*allmean)/(len(sth)+5)
   if sh:
    a=np.array(sh);w=np.maximum(np.array(spa),1);v['PA_K10']=(float(np.sum(a*w))+42*center)/(float(np.sum(w))+42)
   else:v['PA_K10']=center
   k=v['S_K10'];r=v['R5'];v['HYB_K10_R5_25']=.75*k+.25*r;v['HYB_K10_R5_50']=.5*k+.5*r;v['HYB_K10_R5_75']=.25*k+.75*r
   for m in methods:out[m][idx]=v[m]
   cnt[idx]=n;day=score[idx].astype(float).tolist();sh.extend(day);spa.extend(pg.loc[idx,'pa'].tolist());allh.extend(day);mask=pg.loc[idx,'is_starting_player'].to_numpy()==1;sth.extend(score[idx[mask]].tolist())
   for sc in day:
    for h in ew:
     al=1-math.exp(math.log(.5)/h);ew[h]=sc if ew[h] is None else al*sc+(1-al)*ew[h]
 return out,cnt
def agg(hist,cnt):
 a=hist[star_rows].reshape(-1,9).astype(float);c=cnt[star_rows].reshape(-1,9);cv=(c>0).astype(float);d={'mean':a.mean(1),'median':np.median(a,1),'std':a.std(1),'min':a.min(1),'max':a.max(1),'q25':np.quantile(a,.25,axis=1),'q75':np.quantile(a,.75,axis=1),'top':a[:,:3].mean(1),'mid':a[:,3:6].mean(1),'bottom':a[:,6:].mean(1),'coverage':cv.mean(1),'count_mean':c.mean(1),'count_min':c.min(1),'count_max':c.max(1)}
 for k,w in weights.items():d[k]=(a*w).sum(1)/w.sum()
 for i in range(9):d[f'slot{i+1}']=a[:,i]
 sf=side_meta.copy()
 for k,v in d.items():sf[k]=v
 aw=sf[sf.side.eq('away')].set_index('game_id');ho=sf[sf.side.eq('home')].set_index('game_id');ids=sorted(set(aw.index)&set(ho.index));o=pd.DataFrame({'game_id':ids})
 for k in d:o[k]=ho.loc[ids,k].to_numpy()-aw.loc[ids,k].to_numpy()
 o['coverage_min']=np.minimum(ho.loc[ids,'coverage'],aw.loc[ids,'coverage']);return o
def makeX(gf,block,clean=True):
 z=base[['game_id']+BASE_FEATURES+CLEAN].merge(gf,on='game_id',how='left').set_index('game_id').loc[base.game_id];cols=BASE_FEATURES+(CLEAN if clean else [])+BLOCKS[block];return z[cols].reset_index(drop=True)
def cv_eval(X,spec,return_pred=False):
 ps=np.full(len(base),np.nan);f=[]
 for tr,va in folds:
  m=spec();m.fit(X.iloc[tr],y.iloc[tr]);p=m.predict_proba(X.iloc[va])[:,1];ps[va]=p;f.append(log_loss(y.iloc[va],p))
 idx=np.flatnonzero(~np.isnan(ps));mm=met(y.iloc[idx],ps[idx]);mm['fold_sd']=float(np.std(f));mm['selection_score']=mm['log_loss']+.1*mm['fold_sd'];return (mm,ps) if return_pred else mm
# candidate score/method pairs selected only from 2024 stage1
st1=pd.read_csv(OUT/'V11_STAGE1_AVERAGE_SEARCH_2024.csv');pairs=st1[['score_id','mean_method']].drop_duplicates().head(15)
cat=pd.read_csv(OUT/'V11_SCORE_CANDIDATE_CATALOG.csv').set_index('score_id');Xstat=pg[STAT_COLS].to_numpy(float);pa=pg.pa.to_numpy(float)
features={};line_hist={}
for sid,g in pairs.groupby('score_id'):
 row=cat.loc[sid];coef=np.array([row[f'w_{c}'] for c in STAT_COLS]);vol=Xstat@coef;rate=np.divide(vol,pa,out=np.zeros_like(vol),where=pa>0)*4.2;raw=(1-row.rate_share)*vol+row.rate_share*rate;score=np.clip(1000+250*(raw-row.early_mean_raw)/row.early_sd_raw,-500,3000)
 methods=g.mean_method.unique().tolist();hs,c=history(score,methods)
 for method in methods:
  features[(sid,method)]=agg(hs[method],c);line_hist[(sid,method)]=(hs[method][star_rows].copy(),c[star_rows].copy())
 print('built',sid,methods,flush=True)
# search direct clean integration; all selection hyperparameters use 2024 only
rows=[];preds={};oofs={};specs={}
for sid,method in pairs.itertuples(index=False,name=None):
 gf=features[(sid,method)]
 for block in BLOCKS:
  X=makeX(gf,block,True);best=None;bestsp=None;bestp=None
  for C in [.001,.003,.01,.03,.1,.3]:
   for fam,l1 in [('L2',None),('ENET25',.25),('ENET50',.5),('ENET75',.75)]:
    sp=(lambda C=C:pipe_l2(C)) if fam=='L2' else (lambda C=C,l1=l1:pipe_enet(C,l1))
    mm,op=cv_eval(X,sp,True);rec={'score_id':sid,'mean_method':method,'block':block,'family':fam,'C':C,**mm}
    if best is None or rec['selection_score']<best['selection_score']:best=rec;bestsp=sp;bestp=op
  tr=base.season.eq(2024);te=base.season.eq(2025);m=bestsp();m.fit(X.loc[tr],y.loc[tr]);p=m.predict_proba(X.loc[te])[:,1];hm=met(y.loc[te],p);best.update({f'val2025_{k}':v for k,v in hm.items()});key=f'{sid}|{method}|{block}';rows.append(best);preds[key]=p;oofs[key]=bestp;specs[key]=(bestsp,X)
search=pd.DataFrame(rows).sort_values('selection_score');search.to_csv(OUT/'V11_1_CLEAN_INTEGRATION_SEARCH.csv',index=False)
# 2024-only top ensembles
base_clean=base[BASE_FEATURES+CLEAN];clean_mm,clean_oof=cv_eval(base_clean,lambda:pipe_l2(.01),True);m=pipe_l2(.01);m.fit(base_clean.loc[base.season.eq(2024)],y.loc[base.season.eq(2024)]);clean25=m.predict_proba(base_clean.loc[base.season.eq(2025)])[:,1]
topkeys=[f"{r.score_id}|{r.mean_method}|{r.block}" for _,r in search.head(10).iterrows()]
P=np.column_stack([preds[k] for k in topkeys]);Poof=np.column_stack([oofs[k] for k in topkeys]);idx=np.flatnonzero(~np.isnan(Poof).any(1));res=[];predout=base.loc[base.season.eq(2025),['game_id','game_date','home_win']].reset_index(drop=True)
for name,p in [('TOP10_MEAN',P.mean(1)),('TOP10_MEDIAN',np.median(P,axis=1)),('TOP5_MEAN',P[:,:5].mean(1)),('TOP3_MEAN',P[:,:3].mean(1))]:res.append({'model_id':name,'selection':'top configs by 2024 CV only',**met(predout.home_win,p)});predout['p_'+name.lower()]=p
# stack top 10 OOF plus clean, meta C chosen on last 30% OOF dates
Z=np.column_stack([clean_oof[idx],Poof[idx]]);yy=y.iloc[idx].to_numpy();dd=base.game_date.iloc[idx].to_numpy();ord=np.argsort(dd);cut=int(len(ord)*.7);trm=ord[:cut];vam=ord[cut:];best=None
for C in [.001,.003,.01,.03,.1,.3,1]:
 mm=pipe_l2(C);mm.fit(Z[trm],yy[trm]);p=mm.predict_proba(Z[vam])[:,1];ll=log_loss(yy[vam],p)
 if best is None or ll<best[0]:best=(ll,C)
meta=pipe_l2(best[1]);meta.fit(Z,yy);P25=np.column_stack([clean25,P]);pst=meta.predict_proba(P25)[:,1];res.append({'model_id':'TOP10_STACK_WITH_CLEAN','selection':f'2024 OOF meta C={best[1]}',**met(predout.home_win,pst)});predout['p_top10_stack_with_clean']=pst
# fixed logit blends clean vs best 2024 candidate, weight chosen 2024 OOF
bestkey=topkeys[0];po=oofs[bestkey][idx];pc=clean_oof[idx]
def logit(p):p=np.clip(p,1e-6,1-1e-6);return np.log(p/(1-p))
bw=None
for w in np.linspace(0,1,21):
 pp=1/(1+np.exp(-((1-w)*logit(pc)+w*logit(po))));ll=log_loss(yy,pp)
 if bw is None or ll<bw[0]:bw=(ll,w)
pb=preds[bestkey];pblend=1/(1+np.exp(-((1-bw[1])*logit(clean25)+bw[1]*logit(pb))));res.append({'model_id':'LOGIT_BLEND_CLEAN_BEST','selection':f'2024 OOF weight={bw[1]:.2f}',**met(predout.home_win,pblend)});predout['p_logit_blend_clean_best']=pblend
res=pd.DataFrame(res).sort_values('log_loss');res.to_csv(OUT/'V11_1_2024_SELECTED_ENSEMBLES_2025_VALIDATION.csv',index=False);predout.to_csv(OUT/'V11_1_ENSEMBLE_PREDICTIONS_2025.csv',index=False)
# best cross-season prospective candidate (2025 now validation, not holdout)
search['cross_season_score']=search['log_loss']+search['val2025_log_loss']+.05*search['fold_sd'];rob=search.sort_values('cross_season_score').iloc[0]
dec={'status':'post-holdout development candidate; requires prospective confirmation','selected_score_id':rob.score_id,'selected_mean_method':rob.mean_method,'selected_block':rob.block,'selected_family':rob.family,'selected_C':float(rob.C),'2024_cv_log_loss':float(rob.log_loss),'2025_validation_log_loss':float(rob.val2025_log_loss),'2025_validation_auc':float(rob.val2025_roc_auc),'clean_no_batter_2025_log_loss':float(met(predout.home_win,clean25)['log_loss']),'no_2026_tuning':True,'top_2024_only_ensemble_results':res.to_dict('records')}
(OUT/'V11_1_PROSPECTIVE_CANDIDATE_DECISION.json').write_text(json.dumps(dec,ensure_ascii=False,indent=2),encoding='utf-8')
print('TOP DIRECT 2024',search.head(10)[['score_id','mean_method','block','family','C','log_loss','val2025_log_loss']].to_string(index=False),flush=True)
print('TOP 2025 VALIDATION',search.sort_values('val2025_log_loss').head(10)[['score_id','mean_method','block','family','C','log_loss','val2025_log_loss','val2025_roc_auc']].to_string(index=False),flush=True)
print('ENSEMBLES',res.to_string(index=False),flush=True)
print('ROBUST',dec,flush=True)
# Freeze detailed robust-candidate artifacts
import joblib
robkey=f"{rob.score_id}|{rob.mean_method}|{rob.block}"
prob_rob=preds[robkey]
rob_spec,rob_X=specs[robkey]
rob_pred=base.loc[base.season.eq(2025),['game_id','game_date','home_win']].reset_index(drop=True)
rob_pred['p_clean_no_batter']=clean25
rob_pred['p_v11_1_new_batter']=prob_rob
v9p=pd.read_csv('/mnt/data/rq1_work/15Pick_RQ1_GITHUB_COMPLETE_ARCHIVE_v13.0_20260719/04_GIT_VIEW/KEY_RESULTS/V10_PREDICTIONS.csv')
v9p=v9p[(v9p.period.eq('2025_HOLDOUT'))&(v9p.architecture.eq('V9_STYLE'))][['game_id','prob_home_win']].rename(columns={'prob_home_win':'p_v9_style'})
rob_pred=rob_pred.merge(v9p,on='game_id',how='left',validate='one_to_one')
oldp=pd.read_csv(OUT/'V11_2025_PREDICTIONS.csv')[['game_id','p_team_baseline']]
rob_pred=rob_pred.merge(oldp,on='game_id',how='left',validate='one_to_one')
assert rob_pred[['p_v9_style','p_team_baseline']].notna().all().all()
rob_pred.to_csv(OUT/'V11_1_ROBUST_CANDIDATE_PREDICTIONS_2025.csv',index=False)
# Paired date bootstrap
bd=[];yd=rob_pred.home_win.to_numpy(int);ud=np.array(sorted(rob_pred.game_date.unique()))
for new,ref in [('p_v11_1_new_batter','p_clean_no_batter'),('p_v11_1_new_batter','p_v9_style'),('p_v11_1_new_batter','p_team_baseline')]:
 pn=rob_pred[new].to_numpy();po=rob_pred[ref].to_numpy()
 ln=-(yd*np.log(np.clip(pn,1e-6,1-1e-6))+(1-yd)*np.log(np.clip(1-pn,1e-6,1-1e-6)))
 lo=-(yd*np.log(np.clip(po,1e-6,1-1e-6))+(1-yd)*np.log(np.clip(1-po,1e-6,1-1e-6)))
 ds=[]
 for _ in range(10000):
  samp=rng.choice(ud,size=len(ud),replace=True)
  ii=np.concatenate([np.flatnonzero(rob_pred.game_date.to_numpy()==d) for d in samp])
  ds.append(float(np.mean(ln[ii]-lo[ii])))
 ds=np.asarray(ds)
 bd.append({'new_model':new,'reference_model':ref,'delta_log_loss':float(np.mean(ln-lo)),'ci_low':float(np.quantile(ds,.025)),'ci_high':float(np.quantile(ds,.975)),'improvement_probability':float(np.mean(ds<0)),'reps':10000})
bd=pd.DataFrame(bd);bd.to_csv(OUT/'V11_1_ROBUST_CANDIDATE_BOOTSTRAP.csv',index=False)
cmp=[]
for mid,col in [('V11_1_NEW_BATTER','p_v11_1_new_batter'),('CLEAN_NO_BATTER','p_clean_no_batter'),('V9_STYLE_CURRENT_PRIMARY','p_v9_style'),('TEAM_BASELINE','p_team_baseline')]:
 cmp.append({'model_id':mid,**met(yd,rob_pred[col])})
cmp=pd.DataFrame(cmp).sort_values('log_loss');cmp.to_csv(OUT/'V11_1_ROBUST_CANDIDATE_COMPARISON.csv',index=False)
# Selected player prior incomes
lh,lc=line_hist[(rob.score_id,rob.mean_method)]
sl=st[['season','game_date','game_id','side','team','player_id','player_name','batting_order']].copy()
sl['new_batter_prior_income']=lh;sl['prior_game_count']=lc
sl.to_csv(OUT/'V11_1_SELECTED_LINEUP_PLAYER_PRIOR_INCOME.csv',index=False)
# Formula and schema
cr=cat.loc[rob.score_id]
formula={'score_id':rob.score_id,'definition':'per-game event score divided by approximate PA and normalized to 4.2 PA; early-2024 standardized to mean 1000, sd 250','weights':{c:float(cr[f'w_{c}']) for c in STAT_COLS},'rate_share':float(cr.rate_share),'early_mean_raw':float(cr.early_mean_raw),'early_sd_raw':float(cr.early_sd_raw),'history_method':rob.mean_method,'history_definition':'same-season prior mean shrunk with K=5 toward previous-season mean, or 1000 when unavailable','lineup_block':rob.block,'lineup_features':BLOCKS[rob.block],'legacy_income_used':False}
(OUT/'V11_1_SELECTED_BATTER_INCOME_FORMULA.json').write_text(json.dumps(formula,ensure_ascii=False,indent=2),encoding='utf-8')
fitmask=base.season.isin([2024,2025]);pros=rob_spec();pros.fit(rob_X.loc[fitmask],y.loc[fitmask])
joblib.dump(pros,OUT/'V11_1_PROSPECTIVE_REFIT_MODEL_2024_2025.joblib')
schema={'feature_columns':rob_X.columns.tolist(),'training_seasons':[2024,2025],'excluded_from_training':[2026],'target':'home_win','model_family':rob.family,'C':float(rob.C),'random_seed':SEED}
(OUT/'V11_1_PROSPECTIVE_MODEL_SCHEMA.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
mc=met(yd,clean25);mr=met(yd,prob_rob);mv=met(yd,rob_pred.p_v9_style)
report = "# RQ1 V11.1 완전 신규 타격 수입 시스템 결과\n\n"
report += "## 최종 개발 후보\n"
report += f"- 경기 점수: **{rob.score_id}**\n- 선수 평균: **{rob.mean_method}** (현재 시즌 과거 평균을 K=5로 전년도 평균에 수축)\n- 라인업 적용: **{rob.block}**\n- 승부예측: 팀 전력 5개 + 깨끗한 선발/포스트선발 5개 + 신규 타자 block, L2 Logistic C={rob.C}\n- 기존 fantasy 타격 수입 사용: **0**\n\n"
report += "## 검증 결과\n\n" + cmp.to_markdown(index=False) + "\n\n"
report += f"신규 타자 후보는 2025 검증에서 clean no-batter 모델의 Log loss를 **{mc['log_loss']:.9f} → {mr['log_loss']:.9f}**로 낮췄고, AUC는 **{mc['roc_auc']:.6f} → {mr['roc_auc']:.6f}**로 높였다. 현재 V9_STYLE 동일 경기 Log loss는 {mv['log_loss']:.9f}이다.\n\n"
report += "## Bootstrap\n\n" + bd.to_markdown(index=False) + "\n\n"
report += "## 과학적 상태\n첫 2024-only champion을 2025에서 확인한 뒤 평균 구조를 재검토했으므로, 이 V11.1 후보에서 2025는 더 이상 untouched test가 아니라 validation이다. 위 결과는 개발 증거이며 최종 일반화 증거는 아니다. 2026은 선택·학습에 사용하지 않았고, 2024+2025 refit 모델은 prospective 검증용이다.\n\n"
report += "## 탐색 범위\n- 공식 타격 이벤트에서 독립 신규 점수 후보 215개 생성\n- 30개 full temporal score search\n- 상위 점수 18개에 평균법 20개\n- 라인업 block 6개\n- L2, Elastic Net, gradient boosting, histogram boosting, random forest, extra trees\n- clean baseline 직접 결합, stacking, logit blend, ensemble\n\n"
report += "## 계산 계약\n- 공식 선발타자 정확히 9명\n- player ID 결측 0\n- 같은 날짜의 모든 경기 결과를 history 업데이트 전에 묶어 제외\n- 더블헤더 1차전 결과를 2차전에 사용하지 않음\n- 2026 튜닝 금지\n"
(OUT/'RQ1_V11_1_FINAL_BATTER_INCOME_REPORT.md').write_text(report,encoding='utf-8')
print('ROBUST COMPARISON\n',cmp.to_string(index=False),flush=True)
print('ROBUST BOOTSTRAP\n',bd.to_string(index=False),flush=True)
