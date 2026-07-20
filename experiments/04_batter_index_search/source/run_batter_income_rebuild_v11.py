from __future__ import annotations
import json, math, hashlib, warnings
from pathlib import Path
from typing import List
import numpy as np, pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, HuberRegressor, LogisticRegression, PoissonRegressor, Ridge
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore')
SEED=20260720; np.random.seed(SEED)
DATA=Path('/mnt/data/rq1_work/data')
V7=Path('/mnt/data/rq1_work/v7/RQ1_V7_INCOME_TO_PREDICTION_INTEGRATION_LAB_OFFLINE_RESULTS')
V9=Path('/mnt/data/rq1_work/v9/RQ1_V9_POST_STARTER_TEAM_RUNS_LAB_OFFLINE_RESULTS')
OUT=Path('/mnt/data/15Pick_RQ1_V11_BATTER_INCOME_REBUILD_LAB_20260720'); OUT.mkdir(parents=True,exist_ok=True)
INCOME=DATA/'kbo_multiseason_income_foundation_v1/player_game_fantasy_income_2024_2026_v1.csv'
BASE=DATA/'rq1_lineup_confirmed_temporal_model_v1/lineup_confirmed_game_features_v1.csv'
STAT_COLS=['singles','doubles','triples','home_runs','walks','hit_by_pitch','stolen_bases','strikeouts','double_play','runs','rbi','game_winning_hit']
EVENT_COLS=STAT_COLS[:9]; CONTEXT_COLS=STAT_COLS
BASE_FEATURES=['elo_diff','prior_win_pct_diff','prior_run_diff_per_game_diff','prior_rank_advantage','bullpen_strength_diff']
CLEAN_STARTER_FEATURES=['K10_starter_value_diff','K10_starter_count_diff','K10_starter_reliability_diff','K10_both_starters_covered','PS_R20_RA_G_diff']
def safe_auc(y,p):
    try:return float(roc_auc_score(y,p))
    except:return float('nan')
def metrics(y,p):
    p=np.clip(np.asarray(p,float),1e-6,1-1e-6); y=np.asarray(y,int)
    return {'log_loss':float(log_loss(y,p,labels=[0,1])),'brier':float(brier_score_loss(y,p)),'roc_auc':safe_auc(y,p),'accuracy':float(accuracy_score(y,p>=.5)),'n':int(len(y))}
def make_pipe(model): return Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True)),('scaler',StandardScaler()),('model',model)])
def make_tree_pipe(model): return Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True)),('model',model)])
print('Loading data...',flush=True)
use=['season','game_date','game_id','side','team','opponent','position_type','role','occurrence_order','canonical_occurrence_key','player_id','player_name','is_starting_player','stats_json']
pg=pd.read_csv(INCOME,usecols=use); pg=pg[pg.position_type.eq('batter')].copy().reset_index(drop=True); pg.game_date=pg.game_date.astype(int)
stats=[]
for s in pg.stats_json:
 d=json.loads(s); h=float(d.get('hits',0)); d2=float(d.get('doubles',0)); d3=float(d.get('triples',0)); hr=float(d.get('home_runs',0))
 stats.append({'at_bats':float(d.get('at_bats',0)),'singles':max(0,h-d2-d3-hr),'doubles':d2,'triples':d3,'home_runs':hr,'walks':float(d.get('walks',0)),'hit_by_pitch':float(d.get('hit_by_pitch',0)),'stolen_bases':float(d.get('stolen_bases',0)),'strikeouts':float(d.get('strikeouts',0)),'double_play':float(d.get('double_play',0)),'runs':float(d.get('runs',0)),'rbi':float(d.get('rbi',0)),'game_winning_hit':float(d.get('game_winning_hit',0))})
pg=pd.concat([pg.drop(columns=['stats_json']),pd.DataFrame(stats)],axis=1); pg['pa_approx']=pg.at_bats+pg.walks+pg.hit_by_pitch
base=pd.read_csv(BASE); base=base[base.decision_game.eq(1)].copy(); base.game_date=base.game_date.astype(int)
runs_long=pd.concat([base[['game_id','away_runs']].rename(columns={'away_runs':'team_runs'}).assign(side='away'),base[['game_id','home_runs']].rename(columns={'home_runs':'team_runs'}).assign(side='home')],ignore_index=True)
pg=pg.merge(runs_long,on=['game_id','side'],how='left',validate='many_to_one')
lineup_path=DATA/'kbo_boxscore_canonical_v1/canonical_starting_lineups_v1.csv'
lineup=pd.read_csv(lineup_path,usecols=['batter_occurrence_key','batting_order']).rename(columns={'batter_occurrence_key':'canonical_occurrence_key'})
pg=pg.merge(lineup,on='canonical_occurrence_key',how='left',validate='one_to_one')
v7=pd.read_csv(V7/'V7_AVERAGE_AND_AGGREGATION_FEATURES.csv',usecols=['game_id']+CLEAN_STARTER_FEATURES[:4]); v9=pd.read_csv(V9/'V9_STRICT_PRIOR_POST_STARTER_FEATURES.csv',usecols=['game_id','PS_R20_RA_G_diff'])
base=base.merge(v7,on='game_id',how='left').merge(v9,on='game_id',how='left')
starters=pg[pg.is_starting_player.eq(1)].copy(); counts=starters.groupby(['game_id','side']).size(); assert counts.eq(9).all() and len(counts)==3728; assert pg.player_id.notna().all()
all24_dates=np.array(sorted(base.loc[base.season.eq(2024),'game_date'].unique())); design_end_idx=max(20,int(len(all24_dates)*.35)); design_end_date=int(all24_dates[design_end_idx-1]); remaining=all24_dates[design_end_idx:]; folds=[]
for ch in np.array_split(remaining,4):
 if len(ch)==0:continue
 tr=base.index[(base.season.eq(2024))&(base.game_date<int(ch[0]))].to_numpy(); va=base.index[(base.season.eq(2024))&(base.game_date.isin(set(ch.tolist())))].to_numpy(); folds.append((tr,va))
print('folds',[(len(a),len(b)) for a,b in folds],'design_end',design_end_date,flush=True)
teamagg=pg[(pg.season.eq(2024))&(pg.game_date<=design_end_date)].groupby(['game_id','side','game_date'],as_index=False)[CONTEXT_COLS+['team_runs']].sum(); sizes=pg[(pg.season.eq(2024))&(pg.game_date<=design_end_date)].groupby(['game_id','side']).size().rename('n').reset_index(); teamagg=teamagg.merge(sizes,on=['game_id','side']); teamagg.team_runs=teamagg.team_runs/teamagg.n
coef_catalog=[]
def add_coef(name,cols,coef,source):
 full={c:0. for c in STAT_COLS}
 for c,v in zip(cols,coef):full[c]=float(v)
 coef_catalog.append({'base_score_id':name,'source':source,'coefficients':full})
add_coef('LW_STANDARD',EVENT_COLS,[.47,.78,1.09,1.40,.33,.34,.20,-.05,-.37],'fixed linear run values')
add_coef('POWER_OBP',EVENT_COLS,[.50,.95,1.35,1.85,.42,.42,.22,-.08,-.32],'fixed power/on-base')
add_coef('TOTAL_BASE_PLUS',EVENT_COLS,[1,2,3,4,.70,.70,.30,-.10,-.50],'fixed total-base style')
add_coef('BALANCED_CONTEXT',CONTEXT_COLS,[.45,.80,1.15,1.55,.35,.35,.20,-.06,-.35,.20,.28,.45],'fixed context-light')
Xev=teamagg[EVENT_COLS].to_numpy(float); Xctx=teamagg[CONTEXT_COLS].to_numpy(float); yr=teamagg.team_runs.to_numpy(float)
for alpha in [.01,.1,1,10,100]:
 m=Ridge(alpha=alpha).fit(Xev,yr); add_coef(f'RIDGE_EVENT_A{alpha:g}',EVENT_COLS,m.coef_,f'Ridge team runs alpha={alpha}')
for alpha in [.01,.1,1,10,100]:
 try:m=Ridge(alpha=alpha,positive=True,solver='lbfgs').fit(Xev,yr)
 except:m=Ridge(alpha=alpha,positive=True).fit(Xev,yr)
 add_coef(f'RIDGE_POS_A{alpha:g}',EVENT_COLS,m.coef_,f'positive Ridge team runs alpha={alpha}')
for alpha in [.01,.1,1,10,100]:
 m=Ridge(alpha=alpha).fit(Xctx,yr); add_coef(f'RIDGE_CONTEXT_A{alpha:g}',CONTEXT_COLS,m.coef_,f'Ridge context team runs alpha={alpha}')
for eps in [1.2,1.5,2.0]:
 m=HuberRegressor(epsilon=eps,alpha=.001,max_iter=1000).fit(Xev,yr); add_coef(f'HUBER_EVENT_E{eps:g}',EVENT_COLS,m.coef_,f'Huber team runs epsilon={eps}')
for alpha in [0,.01,.1,1]:
 m=PoissonRegressor(alpha=alpha,max_iter=1000).fit(Xev,yr); add_coef(f'POISSON_EVENT_A{alpha:g}',EVENT_COLS,m.coef_,f'Poisson team runs alpha={alpha}')
for alpha in [.0001,.001,.01,.1]:
 for l1 in [.1,.5,.9]:
  m=ElasticNet(alpha=alpha,l1_ratio=l1,max_iter=10000,random_state=SEED).fit(Xev,yr); add_coef(f'ENET_EVENT_A{alpha:g}_L{l1:g}',EVENT_COLS,m.coef_,f'ElasticNet team runs alpha={alpha} l1={l1}')
agg=teamagg.set_index(['game_id','side']); games=[]
for gid,g in base[(base.season.eq(2024))&(base.game_date<=design_end_date)].groupby('game_id'):
 try:h=agg.loc[(gid,'home'),EVENT_COLS].to_numpy(float);a=agg.loc[(gid,'away'),EVENT_COLS].to_numpy(float)
 except:continue
 games.append((gid,*(h-a),int(g.home_win.iloc[0])))
wd=pd.DataFrame(games,columns=['game_id']+EVENT_COLS+['y'])
for C in [.01,.1,1,10]:
 pipe=make_pipe(LogisticRegression(C=C,max_iter=5000,random_state=SEED));pipe.fit(wd[EVENT_COLS],wd.y);co=pipe.named_steps['model'].coef_[0]/pipe.named_steps['scaler'].scale_;add_coef(f'WINLOGIT_EVENT_C{C:g}',EVENT_COLS,co,f'home-win logistic C={C}')
Z=(Xev-Xev.mean(0))/(Xev.std(0)+1e-9);_,_,vt=np.linalg.svd(Z,full_matrices=False);pc=vt[0]/(Xev.std(0)+1e-9)
if np.corrcoef(Xev@pc,yr)[0,1]<0:pc=-pc
add_coef('PCA_EVENT_PC1',EVENT_COLS,pc,'unsupervised PC1 early-2024')
score_catalog=[]; Xall=pg[STAT_COLS].to_numpy(float);pa=pg.pa_approx.to_numpy(float);early=((pg.season.eq(2024))&(pg.game_date<=design_end_date)).to_numpy();score_arrays={}
for rec in coef_catalog:
 coef=np.array([rec['coefficients'][c] for c in STAT_COLS]);vol=Xall@coef;rate=np.divide(vol,pa,out=np.zeros_like(vol),where=pa>0)*4.2
 for rs in [0,.25,.5,.75,1]:
  raw=(1-rs)*vol+rs*rate;mu=float(raw[early].mean());sd=float(raw[early].std()) or 1.;score=np.clip(1000+250*(raw-mu)/sd,-500,3000);sid=f"{rec['base_score_id']}__RATE{int(rs*100):03d}";score_arrays[sid]=score.astype(np.float32);score_catalog.append({'score_id':sid,'base_score_id':rec['base_score_id'],'rate_share':rs,'early_mean_raw':mu,'early_sd_raw':sd,'source':rec['source'],**{f'w_{c}':rec['coefficients'][c] for c in STAT_COLS}})
score_catalog_df=pd.DataFrame(score_catalog);score_catalog_df.to_csv(OUT/'V11_SCORE_CANDIDATE_CATALOG.csv',index=False);Path(OUT/'V11_BASE_SCORE_COEFFICIENTS.json').write_text(json.dumps(coef_catalog,ensure_ascii=False,indent=2),encoding='utf-8');print('scores',len(score_arrays),flush=True)
# Cheap design-period pre-screen for all 215 systems, then full temporal win search for the strongest diverse 50.
early_idx=np.flatnonzero(early)
keys=(pg.loc[early_idx,'game_id'].astype(str)+'|'+pg.loc[early_idx,'side'].astype(str)).to_numpy()
codes,uniques=pd.factorize(keys,sort=True)
grun=pd.DataFrame({'key':keys,'team_runs':pg.loc[early_idx,'team_runs'].to_numpy()}).groupby('key').team_runs.first().reindex(uniques).to_numpy(float)
pre=[]
for sid,sc in score_arrays.items():
    agg=np.bincount(codes,weights=sc[early_idx],minlength=len(uniques))
    corr=float(np.corrcoef(agg,grun)[0,1]) if np.std(agg)>0 else 0.0
    pre.append({'score_id':sid,'design_team_score_run_correlation':corr,'abs_correlation':abs(corr)})
pre=pd.DataFrame(pre).sort_values('abs_correlation',ascending=False)
fixed_ids=score_catalog_df[score_catalog_df.source.str.startswith('fixed')].score_id.tolist()
selected_score_ids=list(dict.fromkeys(fixed_ids+pre.head(30).score_id.tolist()))[:50]
pre['full_temporal_search_selected']=pre.score_id.isin(selected_score_ids)
pre.to_csv(OUT/'V11_ALL_SCORE_SYSTEMS_DESIGN_PRESCREEN.csv',index=False)
stage0_score_items=[(sid,score_arrays[sid]) for sid in selected_score_ids]
print('full temporal score systems',len(stage0_score_items),flush=True)
pg['_row']=np.arange(len(pg));player_groups=[]
for pid,g in pg.sort_values(['player_id','game_date','game_id','side','occurrence_order']).groupby('player_id',sort=False):
 arr=g._row.to_numpy();dates=pg.loc[arr,'game_date'].to_numpy();spl=np.r_[0,np.flatnonzero(dates[1:]!=dates[:-1])+1,len(arr)];player_groups.append((pid,arr,spl))
starter_sorted=pg[pg.is_starting_player.eq(1)].sort_values(['game_id','side','batting_order']).copy();star_rows=starter_sorted._row.to_numpy()
for _,g in starter_sorted.groupby(['game_id','side']):assert g.batting_order.astype(int).tolist()==list(range(1,10))
side_meta=starter_sorted.groupby(['game_id','side'],sort=True).first().reset_index()[['game_id','side']]
HISTORY_METHODS=['S_MEAN','S_K5','S_K10','S_K20','R3','R5','R10','R20','EWMA3','EWMA5','EWMA10','EWMA20','ALL_K10','PREV_K10','START_K10','HIER_START_ALL_K5','PA_K10','HYB_K10_R5_25','HYB_K10_R5_50','HYB_K10_R5_75']
def history_arrays(score,methods):
 out={m:np.full(len(pg),1000.,np.float32) for m in methods};cnt=np.zeros(len(pg),np.float32)
 for pid,arr,spl in player_groups:
  all_hist=[];current=None;season_hist=[];season_pa=[];starter_hist=[];prev=np.nan;ewm={3:None,5:None,10:None,20:None}
  for j in range(len(spl)-1):
   idx=arr[spl[j]:spl[j+1]];season=int(pg.loc[idx[0],'season'])
   if current is None or season!=current:
    if current is not None:prev=float(np.mean(season_hist)) if season_hist else prev
    current=season;season_hist=[];season_pa=[];starter_hist=[];ewm={3:None,5:None,10:None,20:None}
   n=len(season_hist);s=float(np.sum(season_hist)) if n else 0.;center=float(prev) if np.isfinite(prev) else 1000.;vals={}
   vals['S_MEAN']=float(np.mean(season_hist)) if n else center
   for k in [5,10,20]:vals[f'S_K{k}']=(s+k*center)/(n+k)
   for r in [3,5,10,20]:vals[f'R{r}']=float(np.mean(season_hist[-r:])) if n else center
   for h in [3,5,10,20]:vals[f'EWMA{h}']=float(ewm[h]) if ewm[h] is not None else center
   vals['ALL_K10']=(float(np.sum(all_hist))+10000)/(len(all_hist)+10) if all_hist else 1000.;vals['PREV_K10']=(s+10*center)/(n+10);vals['START_K10']=(float(np.sum(starter_hist))+10*center)/(len(starter_hist)+10)
   allmean=(s+5*center)/(n+5);vals['HIER_START_ALL_K5']=(float(np.sum(starter_hist))+5*allmean)/(len(starter_hist)+5)
   if season_hist:
    sh=np.array(season_hist);sp=np.maximum(np.array(season_pa),1);vals['PA_K10']=(float(np.sum(sh*sp))+42*center)/(float(np.sum(sp))+42)
   else:vals['PA_K10']=center
   k10=vals['S_K10'];r5=vals['R5'];vals['HYB_K10_R5_25']=.75*k10+.25*r5;vals['HYB_K10_R5_50']=.5*k10+.5*r5;vals['HYB_K10_R5_75']=.25*k10+.75*r5
   for m in methods:out[m][idx]=vals[m]
   cnt[idx]=n
   day=score[idx].astype(float).tolist();season_hist.extend(day);season_pa.extend(pg.loc[idx,'pa_approx'].astype(float).tolist());all_hist.extend(day);st=pg.loc[idx,'is_starting_player'].to_numpy()==1;starter_hist.extend(score[idx[st]].astype(float).tolist())
   for sc in day:
    for h in [3,5,10,20]:
     alpha=1-math.exp(math.log(.5)/h);ewm[h]=sc if ewm[h] is None else alpha*sc+(1-alpha)*ewm[h]
 return out,cnt
order_weights={'order_w_top':np.array([1.25,1.18,1.12,1.15,1.08,1,.88,.82,.77]),'order_w_cleanup':np.array([1.05,1.10,1.15,1.28,1.20,1,.85,.72,.65]),'order_w_pa':np.array([1.13,1.10,1.08,1.06,1.03,1,.96,.92,.88])}
def aggregate_game_features(hist,cnt,prefix='bat'):
 vals=hist[star_rows].reshape(-1,9).astype(float);cc=cnt[star_rows].reshape(-1,9).astype(float);cov=(cc>0).astype(float)
 d={'mean':vals.mean(1),'median':np.median(vals,1),'std':vals.std(1),'min':vals.min(1),'max':vals.max(1),'q25':np.quantile(vals,.25,axis=1),'q75':np.quantile(vals,.75,axis=1),'top':vals[:,:3].mean(1),'mid':vals[:,3:6].mean(1),'bottom':vals[:,6:].mean(1),'coverage':cov.mean(1),'count_mean':cc.mean(1),'count_min':cc.min(1),'count_max':cc.max(1)}
 for n,w in order_weights.items():d[n]=(vals*w).sum(1)/w.sum()
 for i in range(9):d[f'slot{i+1}']=vals[:,i]
 sf=side_meta.copy()
 for k,v in d.items():sf[k]=v
 away=sf[sf.side.eq('away')].set_index('game_id');home=sf[sf.side.eq('home')].set_index('game_id');common=sorted(set(away.index)&set(home.index));o=pd.DataFrame({'game_id':common})
 for k in d:o[f'{prefix}_{k}_diff']=home.loc[common,k].to_numpy()-away.loc[common,k].to_numpy()
 o[f'{prefix}_coverage_min']=np.minimum(home.loc[common,'coverage'].to_numpy(),away.loc[common,'coverage'].to_numpy());return o
BLOCKS={'MEAN':['mean_diff','coverage_diff','count_mean_diff','coverage_min'],'ORDER':['mean_diff','order_w_top_diff','order_w_cleanup_diff','order_w_pa_diff','top_diff','mid_diff','bottom_diff','coverage_diff','count_mean_diff','coverage_min'],'DISTRIBUTION':['mean_diff','median_diff','std_diff','min_diff','max_diff','q25_diff','q75_diff','coverage_diff','count_mean_diff','coverage_min'],'TAIL':['mean_diff','std_diff','min_diff','max_diff','top_diff','bottom_diff','coverage_diff','count_mean_diff','coverage_min'],'SLOTS':[f'slot{i}_diff' for i in range(1,10)]+['coverage_diff','count_mean_diff','coverage_min'],'FULL':['mean_diff','median_diff','std_diff','min_diff','max_diff','q25_diff','q75_diff','top_diff','mid_diff','bottom_diff','order_w_top_diff','order_w_cleanup_diff','order_w_pa_diff']+[f'slot{i}_diff' for i in range(1,10)]+['coverage_diff','count_mean_diff','count_min_diff','count_max_diff','coverage_min']}
y_all=base.home_win.astype(int)
def get_X(gf,block,include_base=True,include_clean=False):
 tmp=base[['game_id']+BASE_FEATURES+CLEAN_STARTER_FEATURES].merge(gf,on='game_id',how='left').set_index('game_id').loc[base.game_id];cols=[]
 if include_base:cols+=BASE_FEATURES
 if include_clean:cols+=CLEAN_STARTER_FEATURES
 cols += [f'bat_{x}' for x in BLOCKS[block]]
 return tmp[cols].reset_index(drop=True),cols
def cv_model(X,spec):
 preds=[];ys=[];fms=[]
 for fi,(tr,va) in enumerate(folds):
  p=spec();p.fit(X.iloc[tr],y_all.iloc[tr]);pr=p.predict_proba(X.iloc[va])[:,1];m=metrics(y_all.iloc[va],pr);m['fold']=fi;fms.append(m);preds.extend(pr);ys.extend(y_all.iloc[va])
 allm=metrics(ys,preds);allm['fold_sd']=float(np.std([m['log_loss'] for m in fms]));allm['selection_score']=allm['log_loss']+.1*allm['fold_sd'];return allm
def l2spec(C):return lambda:make_pipe(LogisticRegression(C=C,max_iter=5000,random_state=SEED))
Xbase=base[BASE_FEATURES];br=[]
for C in [.001,.003,.01,.03,.1,.3,1,3,10]:m=cv_model(Xbase,l2spec(C));br.append({'config':f'TEAM_L2_C{C}',**m})
baseline_cv=pd.DataFrame(br).sort_values('selection_score');baseline_cv.to_csv(OUT/'V11_TEAM_BASELINE_2024_CV.csv',index=False);print('base',baseline_cv.iloc[0].to_dict(),flush=True)
stage0=[]
for si,(sid,score) in enumerate(stage0_score_items,1):
 hist,cnt=history_arrays(score,['PREV_K10']);gf=aggregate_game_features(hist['PREV_K10'],cnt);X,_=get_X(gf,'ORDER',True);best=None
 for C in [.003,.01,.03,.1]:
  m=cv_model(X,l2spec(C));row={'score_id':sid,'mean_method':'PREV_K10','block':'ORDER','C':C,**m}
  if best is None or row['selection_score']<best['selection_score']:best=row
 stage0.append(best)
 if si%10==0:print('stage0',si,flush=True)
stage0=pd.DataFrame(stage0).sort_values('selection_score');stage0.to_csv(OUT/'V11_STAGE0_SCORE_SCREENING_2024.csv',index=False);top_scores=stage0.head(18).score_id.tolist();print(stage0.head(5)[['score_id','log_loss']].to_dict('records'),flush=True)
stage1=[];cache={}
for si,sid in enumerate(top_scores,1):
 hist,cnt=history_arrays(score_arrays[sid],HISTORY_METHODS)
 for method in HISTORY_METHODS:
  gf=aggregate_game_features(hist[method],cnt);cache[(sid,method)]=gf;X,_=get_X(gf,'ORDER',True);best=None
  for C in [.001,.003,.01,.03,.1,.3]:
   m=cv_model(X,l2spec(C));row={'score_id':sid,'mean_method':method,'block':'ORDER','C':C,**m}
   if best is None or row['selection_score']<best['selection_score']:best=row
  stage1.append(best)
 print('stage1',si,flush=True)
stage1=pd.DataFrame(stage1).sort_values('selection_score');stage1.to_csv(OUT/'V11_STAGE1_AVERAGE_SEARCH_2024.csv',index=False);print(stage1.head(5)[['score_id','mean_method','log_loss']].to_dict('records'),flush=True)
stage2=[]
for sid,method in stage1[['score_id','mean_method']].drop_duplicates().head(15).itertuples(index=False,name=None):
 gf=cache[(sid,method)]
 for block in BLOCKS:
  X,_=get_X(gf,block,True)
  for C in [.001,.003,.01,.03,.1,.3,1]:
   m=cv_model(X,l2spec(C));stage2.append({'score_id':sid,'mean_method':method,'block':block,'model':'LOGISTIC_L2','C':C,'l1_ratio':np.nan,**m})
  for C in [.003,.01,.03,.1]:
   for l1 in [.25,.5,.75]:
    spec=lambda C=C,l1=l1:make_pipe(LogisticRegression(C=C,penalty='elasticnet',solver='saga',l1_ratio=l1,max_iter=8000,random_state=SEED));m=cv_model(X,spec);stage2.append({'score_id':sid,'mean_method':method,'block':block,'model':'LOGISTIC_ENET','C':C,'l1_ratio':l1,**m})
stage2=pd.DataFrame(stage2).sort_values('selection_score');stage2.to_csv(OUT/'V11_STAGE2_AGGREGATION_MODEL_SEARCH_2024.csv',index=False);print(stage2.head(5)[['score_id','mean_method','block','model','C','log_loss']].to_dict('records'),flush=True)
model_specs={'HGB_L2_3':lambda:make_tree_pipe(HistGradientBoostingClassifier(max_iter=200,learning_rate=.03,max_leaf_nodes=7,l2_regularization=3,min_samples_leaf=25,random_state=SEED)),'HGB_L2_10':lambda:make_tree_pipe(HistGradientBoostingClassifier(max_iter=200,learning_rate=.03,max_leaf_nodes=7,l2_regularization=10,min_samples_leaf=30,random_state=SEED)),'GB_DEPTH1':lambda:make_tree_pipe(GradientBoostingClassifier(n_estimators=150,learning_rate=.02,max_depth=1,min_samples_leaf=20,random_state=SEED)),'GB_DEPTH2':lambda:make_tree_pipe(GradientBoostingClassifier(n_estimators=120,learning_rate=.02,max_depth=2,min_samples_leaf=25,random_state=SEED)),'EXTRA':lambda:make_tree_pipe(ExtraTreesClassifier(n_estimators=500,max_depth=4,min_samples_leaf=20,max_features=.7,class_weight='balanced',random_state=SEED,n_jobs=-1)),'RF':lambda:make_tree_pipe(RandomForestClassifier(n_estimators=500,max_depth=4,min_samples_leaf=20,max_features=.7,class_weight='balanced',random_state=SEED,n_jobs=-1))}
stage3=[]
for _,r in stage2[['score_id','mean_method','block']].drop_duplicates().head(8).iterrows():
 X,_=get_X(cache[(r.score_id,r.mean_method)],r.block,True)
 for name,spec in model_specs.items():m=cv_model(X,spec);stage3.append({'score_id':r.score_id,'mean_method':r.mean_method,'block':r.block,'model':name,'C':np.nan,'l1_ratio':np.nan,**m})
stage3=pd.DataFrame(stage3).sort_values('selection_score');stage3.to_csv(OUT/'V11_STAGE3_NONLINEAR_SEARCH_2024.csv',index=False);all_search=pd.concat([stage2,stage3],ignore_index=True).sort_values('selection_score');champ=all_search.iloc[0].to_dict();print('CHAMP',champ,flush=True)
def spec_from_row(r):
 if r['model']=='LOGISTIC_L2':return l2spec(float(r['C']))
 if r['model']=='LOGISTIC_ENET':return lambda:make_pipe(LogisticRegression(C=float(r['C']),penalty='elasticnet',solver='saga',l1_ratio=float(r['l1_ratio']),max_iter=8000,random_state=SEED))
 return model_specs[r['model']]
champ_sid=champ['score_id'];champ_method=champ['mean_method'];champ_block=champ['block'];champ_spec=spec_from_row(champ);champ_gf=cache[(champ_sid,champ_method)]
X_bat,_=get_X(champ_gf,champ_block,False);X_team_bat,_=get_X(champ_gf,champ_block,True);X_clean_bat,_=get_X(champ_gf,champ_block,True,True);X_clean=base[BASE_FEATURES+CLEAN_STARTER_FEATURES]
integration=[]
for name,X in [('TEAM_BASELINE',Xbase),('BATTER_ONLY',X_bat),('TEAM_PLUS_NEW_BATTER',X_team_bat),('CLEAN_NO_BATTER',X_clean),('CLEAN_PLUS_NEW_BATTER',X_clean_bat)]:
 for C in [.001,.003,.01,.03,.1,.3,1,3]:integration.append({'model_id':name,'family':'LOGISTIC_L2','C':C,**cv_model(X,l2spec(C))})
integration=pd.DataFrame(integration);integration.to_csv(OUT/'V11_INTEGRATION_2024_CV.csv',index=False);best_specs={name:l2spec(float(g.sort_values('selection_score').iloc[0].C)) for name,g in integration.groupby('model_id')}
train=base.season.eq(2024).to_numpy();test=base.season.eq(2025).to_numpy();final_X={'TEAM_BASELINE':Xbase,'BATTER_ONLY':X_bat,'TEAM_PLUS_NEW_BATTER':X_team_bat,'CLEAN_NO_BATTER':X_clean,'CLEAN_PLUS_NEW_BATTER':X_clean_bat};results=[];pred=base.loc[test,['game_id','game_date','home_win']].copy().reset_index(drop=True)
for name,X in final_X.items():
 pipe=best_specs[name]();pipe.fit(X.loc[train],y_all.loc[train]);p=pipe.predict_proba(X.loc[test])[:,1];pred['p_'+name.lower()]=p;results.append({'model_id':name,'selection_rule':'2024 temporal CV only',**metrics(y_all.loc[test],p)})
pipe=champ_spec();pipe.fit(X_team_bat.loc[train],y_all.loc[train]);p=pipe.predict_proba(X_team_bat.loc[test])[:,1];pred['p_2024_champion_team_batter']=p;results.append({'model_id':'2024_CHAMPION_TEAM_BATTER','selection_rule':'overall 2024 search champion',**metrics(y_all.loc[test],p)})
pco=[];pbo=[];yo=[]
for tr,va in folds:
 a=best_specs['CLEAN_NO_BATTER']();b=best_specs['BATTER_ONLY']();a.fit(X_clean.iloc[tr],y_all.iloc[tr]);b.fit(X_bat.iloc[tr],y_all.iloc[tr]);pco.extend(a.predict_proba(X_clean.iloc[va])[:,1]);pbo.extend(b.predict_proba(X_bat.iloc[va])[:,1]);yo.extend(y_all.iloc[va])
def logit(p):p=np.clip(np.asarray(p),1e-5,1-1e-5);return np.log(p/(1-p))
meta=LogisticRegression(C=.1,max_iter=5000,random_state=SEED).fit(np.c_[logit(pco),logit(pbo)],np.asarray(yo));a=best_specs['CLEAN_NO_BATTER']();b=best_specs['BATTER_ONLY']();a.fit(X_clean.loc[train],y_all.loc[train]);b.fit(X_bat.loc[train],y_all.loc[train]);pc=a.predict_proba(X_clean.loc[test])[:,1];pb=b.predict_proba(X_bat.loc[test])[:,1];ps=meta.predict_proba(np.c_[logit(pc),logit(pb)])[:,1];pred['p_clean_stack_new_batter']=ps;results.append({'model_id':'CLEAN_STACK_NEW_BATTER','selection_rule':'2024 temporal OOF logit meta C=0.1',**metrics(y_all.loc[test],ps)})
results=pd.DataFrame(results).sort_values('log_loss');results.to_csv(OUT/'V11_2025_UNTOUCHED_HOLDOUT_RESULTS.csv',index=False);pred.to_csv(OUT/'V11_2025_PREDICTIONS.csv',index=False)
rng=np.random.default_rng(SEED);dates=np.array(sorted(pred.game_date.unique()));y=pred.home_win.to_numpy(int);boot=[]
for new,ref in [('TEAM_PLUS_NEW_BATTER','TEAM_BASELINE'),('CLEAN_PLUS_NEW_BATTER','CLEAN_NO_BATTER'),('CLEAN_STACK_NEW_BATTER','CLEAN_NO_BATTER')]:
 pn=pred['p_'+new.lower()].to_numpy();po=pred['p_'+ref.lower()].to_numpy();ln=-(y*np.log(np.clip(pn,1e-6,1-1e-6))+(1-y)*np.log(np.clip(1-pn,1e-6,1-1e-6)));lo=-(y*np.log(np.clip(po,1e-6,1-1e-6))+(1-y)*np.log(np.clip(1-po,1e-6,1-1e-6)));ds=[]
 for _ in range(10000):
  sd=rng.choice(dates,size=len(dates),replace=True);idx=np.concatenate([np.flatnonzero(pred.game_date.to_numpy()==d) for d in sd]);ds.append(float(np.mean(ln[idx]-lo[idx])))
 ds=np.array(ds);boot.append({'new_model':new,'reference_model':ref,'delta_log_loss_new_minus_reference':float(np.mean(ln-lo)),'ci_low':float(np.quantile(ds,.025)),'ci_high':float(np.quantile(ds,.975)),'improvement_probability':float(np.mean(ds<0)),'bootstrap_reps':10000})
btdf=pd.DataFrame(boot);btdf.to_csv(OUT/'V11_2025_PAIRED_DATE_BOOTSTRAP.csv',index=False)
abl=[]
for block in BLOCKS:
 X,_=get_X(champ_gf,block,True);best=None
 for C in [.001,.003,.01,.03,.1,.3,1]:
  m=cv_model(X,l2spec(C));row={'block':block,'C':C,**m}
  if best is None or row['selection_score']<best['selection_score']:best=row
 pipe=l2spec(best['C'])();pipe.fit(X.loc[train],y_all.loc[train]);pp=pipe.predict_proba(X.loc[test])[:,1];abl.append({**best,**{f'holdout_{k}':v for k,v in metrics(y_all.loc[test],pp).items()}})
pd.DataFrame(abl).sort_values('selection_score').to_csv(OUT/'V11_SELECTED_SYSTEM_LINEUP_ABLATION.csv',index=False)
ch,cc=history_arrays(score_arrays[champ_sid],[champ_method]);sel=starter_sorted[['season','game_date','game_id','side','team','player_id','player_name','batting_order','_row']].copy();sel['prior_income']=ch[champ_method][star_rows];sel['prior_count']=cc[star_rows];sel.to_csv(OUT/'V11_SELECTED_LINEUP_PLAYER_PRIOR_INCOME.csv',index=False)
audit={'legacy_batter_income_used':False,'score_candidates_tested':len(score_arrays),'base_score_weight_systems':len(coef_catalog),'history_methods_tested':len(HISTORY_METHODS),'lineup_blocks_tested':len(BLOCKS),'same_date_exclusion':'assign player-date features before adding all games on that date','lineup_exact_9':bool(counts.eq(9).all()),'lineup_groups':int(len(counts)),'player_id_missing':int(pg.player_id.isna().sum()),'2026_used_for_selection_or_reporting':False,'event_weight_design_end_date':design_end_date,'selection_season':2024,'untouched_holdout_season':2025,'selected_score_id':champ_sid,'selected_history_method':champ_method,'selected_lineup_block':champ_block,'selected_model':champ['model'],'selected_model_C':None if pd.isna(champ.get('C')) else float(champ['C']),'selected_model_l1_ratio':None if pd.isna(champ.get('l1_ratio')) else float(champ['l1_ratio']),'selected_2024_cv_log_loss':float(champ['log_loss']),'selected_2024_cv_selection_score':float(champ['selection_score']),'meta_stack_coefficients':{'intercept':float(meta.intercept_[0]),'clean_no_batter_logit':float(meta.coef_[0,0]),'new_batter_logit':float(meta.coef_[0,1])}}
(OUT/'V11_MODEL_SELECTION_DECISION.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
catrow=score_catalog_df.set_index('score_id').loc[champ_sid]
report=f"""# RQ1 V11 완전 신규 타격 수입 시스템 재구축 결과

## 결론
기존 15Pick 기본 타격 수입 점수와 해당 feature를 전혀 사용하지 않았다. 공식 KBO 타격 이벤트에서 {len(score_arrays)}개 신규 경기별 점수 후보, {len(HISTORY_METHODS)}개 strict-prior 평균법, {len(BLOCKS)}개 라인업 반영 구조와 여러 모델을 2024 시간순 검증으로 비교한 뒤 2025 전체 698경기를 untouched holdout으로 평가했다. 2026은 선택이나 보고에 사용하지 않았다.

## 2024 선택 시스템
- 점수식: **{champ_sid}**
- 평균법: **{champ_method}**
- 라인업 반영: **{champ_block}**
- 모델: **{champ['model']}**
- 2024 CV log loss: **{champ['log_loss']:.9f}**
- rate share: **{catrow['rate_share']:.2f}**

## 2025 untouched holdout

{results.to_markdown(index=False)}

## 신규 타자 수입 독립 기여도

{btdf.to_markdown(index=False)}

## 감사
- 경기-팀마다 공식 선발타자 정확히 9명.
- 선수 ID 결측 0.
- player-date 전체 경기의 값을 history에 넣기 전에 feature를 계산해 같은 날짜와 더블헤더 결과를 배제.
- fantasy_points와 fantasy_income_points 미사용.
- 2024만 설계·선택, 2025만 최종 평가.

## 제한
주어진 공식 BoxScore 변수 범위 안의 광범위 탐색이다. 타구속도, 발사각, 일일 부상·엔트리, 상대 투수 구종 같은 point-in-time 자료는 포함되지 않았다. 2025 holdout은 이후 재튜닝에 다시 사용하면 안 되며 다음 단계는 동결 후 prospective 검증이다.
"""
(OUT/'RQ1_V11_BATTER_INCOME_REBUILD_REPORT.md').write_text(report,encoding='utf-8')
files=[p for p in OUT.iterdir() if p.is_file()];manifest=[]
for p in sorted(files):manifest.append({'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
pd.DataFrame(manifest).to_csv(OUT/'MANIFEST_SHA256.csv',index=False)
print('FINAL\n',results.to_string(index=False),flush=True);print('BOOT\n',btdf.to_string(index=False),flush=True);print('OUT',OUT,flush=True)
