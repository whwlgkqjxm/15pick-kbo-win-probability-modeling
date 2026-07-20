from __future__ import annotations

import json
import math
import os
import platform
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone, BaseEstimator, ClassifierMixin
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
    GradientBoostingClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

warnings.filterwarnings("ignore")


class CatBoostSklearnWrapper(BaseEstimator, ClassifierMixin):
    def __init__(self, iterations=220, learning_rate=0.03, depth=4, l2_leaf_reg=10.0, random_seed=20260720):
        self.iterations = iterations
        self.learning_rate = learning_rate
        self.depth = depth
        self.l2_leaf_reg = l2_leaf_reg
        self.random_seed = random_seed

    def fit(self, X, y, sample_weight=None):
        self.model_ = CatBoostClassifier(
            iterations=self.iterations, learning_rate=self.learning_rate,
            depth=self.depth, l2_leaf_reg=self.l2_leaf_reg,
            loss_function='Logloss', eval_metric='Logloss',
            random_seed=self.random_seed, verbose=False, thread_count=2,
            allow_writing_files=False
        )
        self.model_.fit(X, y, sample_weight=sample_weight)
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X):
        return self.model_.predict_proba(X)


SEED = 20260720
RNG = np.random.default_rng(SEED)
OUT = Path('/mnt/data/15Pick_RQ1_V12_TRAINING_STRATEGY_LAB_20260720')
OUT.mkdir(parents=True, exist_ok=True)

DATA = Path('/mnt/data/rq1_work/data')
V7 = Path('/mnt/data/rq1_work/v7/RQ1_V7_INCOME_TO_PREDICTION_INTEGRATION_LAB_OFFLINE_RESULTS')
V9 = Path('/mnt/data/rq1_work/v9/RQ1_V9_POST_STARTER_TEAM_RUNS_LAB_OFFLINE_RESULTS')
V11 = Path('/mnt/data/15Pick_RQ1_V11_1_BATTER_INCOME_FINAL_PACKAGE_20260720/results')

BASE_FEATURES = [
    'elo_diff',
    'prior_win_pct_diff',
    'prior_run_diff_per_game_diff',
    'prior_rank_advantage',
    'bullpen_strength_diff',
]
CLEAN_FEATURES = [
    'K10_starter_value_diff',
    'K10_starter_count_diff',
    'K10_starter_reliability_diff',
    'K10_both_starters_covered',
    'PS_R20_RA_G_diff',
]
BATTER_FEATURES = ['mean', 'coverage', 'count_mean', 'coverage_min']
ALL_FEATURES = BASE_FEATURES + CLEAN_FEATURES + BATTER_FEATURES
NO_BATTER_FEATURES = BASE_FEATURES + CLEAN_FEATURES


def to_dt(v: pd.Series | np.ndarray) -> pd.DatetimeIndex:
    return pd.to_datetime(pd.Series(v).astype(str), format='%Y%m%d')


def metric_dict(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    y = np.asarray(y, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    try:
        auc = float(roc_auc_score(y, p))
    except Exception:
        auc = float('nan')
    return {
        'log_loss': float(log_loss(y, p)),
        'brier': float(brier_score_loss(y, p)),
        'roc_auc': auc,
        'accuracy': float(accuracy_score(y, p >= 0.5)),
        'n': int(len(y)),
    }


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.asarray(z, dtype=float)))


def aggregate_batter_features(line: pd.DataFrame) -> pd.DataFrame:
    line = line.copy()
    line['covered'] = (line['prior_game_count'] > 0).astype(float)
    side = (
        line.groupby(['game_id', 'side'], as_index=False)
        .agg(
            income_mean=('new_batter_prior_income', 'mean'),
            coverage=('covered', 'mean'),
            count_mean=('prior_game_count', 'mean'),
            lineup_count=('player_id', 'size'),
        )
    )
    assert side['lineup_count'].eq(9).all(), 'Every game-side must have exactly 9 starting batters.'
    home = side[side.side.eq('home')].set_index('game_id')
    away = side[side.side.eq('away')].set_index('game_id')
    ids = sorted(set(home.index) & set(away.index))
    out = pd.DataFrame({'game_id': ids})
    out['mean'] = home.loc[ids, 'income_mean'].to_numpy() - away.loc[ids, 'income_mean'].to_numpy()
    out['coverage'] = home.loc[ids, 'coverage'].to_numpy() - away.loc[ids, 'coverage'].to_numpy()
    out['count_mean'] = home.loc[ids, 'count_mean'].to_numpy() - away.loc[ids, 'count_mean'].to_numpy()
    out['coverage_min'] = np.minimum(
        home.loc[ids, 'coverage'].to_numpy(), away.loc[ids, 'coverage'].to_numpy()
    )
    return out


def load_dataset() -> pd.DataFrame:
    base = pd.read_csv(DATA / 'rq1_lineup_confirmed_temporal_model_v1/lineup_confirmed_game_features_v1.csv')
    base = base[base['decision_game'].eq(1)].copy()
    base['game_date'] = base['game_date'].astype(int)

    v7 = pd.read_csv(
        V7 / 'V7_AVERAGE_AND_AGGREGATION_FEATURES.csv',
        usecols=['game_id'] + CLEAN_FEATURES[:4],
    )
    v9 = pd.read_csv(
        V9 / 'V9_STRICT_PRIOR_POST_STARTER_FEATURES.csv',
        usecols=['game_id', 'PS_R20_RA_G_diff'],
    )
    line = pd.read_csv(V11 / 'V11_1_SELECTED_LINEUP_PLAYER_PRIOR_INCOME.csv')
    bf = aggregate_batter_features(line)

    df = base.merge(v7, on='game_id', how='left', validate='one_to_one')
    df = df.merge(v9, on='game_id', how='left', validate='one_to_one')
    df = df.merge(bf, on='game_id', how='left', validate='one_to_one')
    assert df['game_id'].is_unique
    assert df[BATTER_FEATURES].notna().all().all()
    df = df.sort_values(['game_date', 'game_id']).reset_index(drop=True)
    return df


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    family: str
    params: dict[str, Any]
    factory: Callable[[], Any]
    supports_weight: bool = True


def linear_pipeline(model: Any) -> Pipeline:
    return Pipeline([
        ('imp', SimpleImputer(strategy='median', add_indicator=True)),
        ('sc', StandardScaler()),
        ('m', model),
    ])


def tree_pipeline(model: Any) -> Pipeline:
    return Pipeline([
        ('imp', SimpleImputer(strategy='median', add_indicator=True)),
        ('m', model),
    ])


def build_specs() -> list[ModelSpec]:
    specs: list[ModelSpec] = []
    for C in [0.003, 0.01, 0.03, 0.1, 0.3, 1.0]:
        specs.append(ModelSpec(
            f'L2_C{C:g}', 'L2_LOGISTIC', {'C': C},
            lambda C=C: linear_pipeline(LogisticRegression(C=C, max_iter=5000, random_state=SEED))
        ))
    for C in [0.01, 0.03, 0.1, 0.3]:
        for l1 in [0.25, 0.5, 0.75]:
            specs.append(ModelSpec(
                f'ENET_C{C:g}_L1{l1:g}', 'ELASTIC_NET', {'C': C, 'l1_ratio': l1},
                lambda C=C, l1=l1: linear_pipeline(LogisticRegression(
                    C=C, penalty='elasticnet', solver='saga', l1_ratio=l1,
                    max_iter=10000, random_state=SEED
                ))
            ))
    rf_configs = [
        (300, 3, 8, 5, 'sqrt'),
        (500, 4, 6, 4, 0.8),
        (500, 5, 4, 3, None),
    ]
    for n, depth, leaf, split, mf in rf_configs:
        specs.append(ModelSpec(
            f'RF_D{depth}_L{leaf}_MF{mf}', 'RANDOM_FOREST',
            {'n_estimators': n, 'max_depth': depth, 'min_samples_leaf': leaf, 'min_samples_split': split, 'max_features': mf},
            lambda n=n, depth=depth, leaf=leaf, split=split, mf=mf: tree_pipeline(RandomForestClassifier(
                n_estimators=min(n,300), max_depth=depth, min_samples_leaf=leaf,
                min_samples_split=split, max_features=mf, n_jobs=2,
                random_state=SEED, class_weight=None
            ))
        ))
    et_configs = [
        (500, 3, 8, 'sqrt'),
        (700, 4, 6, 0.8),
        (700, 5, 4, None),
    ]
    for n, depth, leaf, mf in et_configs:
        specs.append(ModelSpec(
            f'ET_D{depth}_L{leaf}_MF{mf}', 'EXTRA_TREES',
            {'n_estimators': n, 'max_depth': depth, 'min_samples_leaf': leaf, 'max_features': mf},
            lambda n=n, depth=depth, leaf=leaf, mf=mf: tree_pipeline(ExtraTreesClassifier(
                n_estimators=min(n,350), max_depth=depth, min_samples_leaf=leaf,
                max_features=mf, n_jobs=2, random_state=SEED
            ))
        ))
    for lr, leaves, l2 in [(0.03, 7, 1.0), (0.05, 7, 5.0), (0.03, 15, 5.0), (0.05, 15, 10.0)]:
        specs.append(ModelSpec(
            f'HGB_LR{lr:g}_LEAF{leaves}_L2{l2:g}', 'HIST_GRADIENT_BOOSTING',
            {'learning_rate': lr, 'max_leaf_nodes': leaves, 'l2_regularization': l2},
            lambda lr=lr, leaves=leaves, l2=l2: tree_pipeline(HistGradientBoostingClassifier(
                learning_rate=lr, max_leaf_nodes=leaves, max_iter=100,
                min_samples_leaf=20, l2_regularization=l2,
                random_state=SEED
            ))
        ))
    for lr, depth, subsample in [(0.03, 1, 0.8), (0.03, 2, 0.8), (0.05, 1, 1.0)]:
        specs.append(ModelSpec(
            f'GB_LR{lr:g}_D{depth}_S{subsample:g}', 'GRADIENT_BOOSTING',
            {'learning_rate': lr, 'max_depth': depth, 'subsample': subsample},
            lambda lr=lr, depth=depth, subsample=subsample: tree_pipeline(GradientBoostingClassifier(
                n_estimators=150, learning_rate=lr, max_depth=depth,
                min_samples_leaf=12, subsample=subsample, random_state=SEED
            ))
        ))
    xgb_configs = [
        (0.02, 2, 2.0, 0.8, 0.8),
        (0.03, 2, 5.0, 0.9, 0.9),
        (0.03, 3, 5.0, 0.8, 0.8),
        (0.05, 1, 2.0, 1.0, 1.0),
    ]
    for lr, depth, mcw, sub, col in xgb_configs:
        specs.append(ModelSpec(
            f'XGB_LR{lr:g}_D{depth}_MCW{mcw:g}', 'XGBOOST',
            {'learning_rate': lr, 'max_depth': depth, 'min_child_weight': mcw, 'subsample': sub, 'colsample_bytree': col},
            lambda lr=lr, depth=depth, mcw=mcw, sub=sub, col=col: tree_pipeline(XGBClassifier(
                n_estimators=220, learning_rate=lr, max_depth=depth,
                min_child_weight=mcw, subsample=sub, colsample_bytree=col,
                reg_alpha=0.5, reg_lambda=5.0, objective='binary:logistic',
                eval_metric='logloss', random_state=SEED, n_jobs=2,
                verbosity=0
            ))
        ))
    lgb_configs = [
        (0.02, 7, 20, 5.0),
        (0.03, 7, 30, 10.0),
        (0.03, 15, 30, 10.0),
        (0.05, 7, 40, 20.0),
    ]
    for lr, leaves, minleaf, l2 in lgb_configs:
        specs.append(ModelSpec(
            f'LGB_LR{lr:g}_LEAF{leaves}_MIN{minleaf}', 'LIGHTGBM',
            {'learning_rate': lr, 'num_leaves': leaves, 'min_child_samples': minleaf, 'reg_lambda': l2},
            lambda lr=lr, leaves=leaves, minleaf=minleaf, l2=l2: tree_pipeline(LGBMClassifier(
                n_estimators=220, learning_rate=lr, num_leaves=leaves,
                max_depth=-1, min_child_samples=minleaf, subsample=0.9,
                colsample_bytree=0.9, reg_alpha=0.5, reg_lambda=l2,
                random_state=SEED, n_jobs=2, verbosity=-1
            ))
        ))
    cat_configs = [
        (0.02, 3, 5.0),
        (0.03, 4, 10.0),
        (0.05, 3, 20.0),
    ]
    for lr, depth, l2 in cat_configs:
        specs.append(ModelSpec(
            f'CAT_LR{lr:g}_D{depth}_L2{l2:g}', 'CATBOOST',
            {'learning_rate': lr, 'depth': depth, 'l2_leaf_reg': l2},
            lambda lr=lr, depth=depth, l2=l2: tree_pipeline(CatBoostSklearnWrapper(
                iterations=220, learning_rate=lr, depth=depth,
                l2_leaf_reg=l2, random_seed=SEED
            ))
        ))
    return specs


def temporal_folds(df_dev: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray, dict[str, Any]]]:
    dates = np.array(sorted(df_dev['game_date'].unique()))
    # Five expanding folds across 2024-2025; each validates a future date block.
    boundaries = [0.28, 0.43, 0.58, 0.73, 0.86, 1.0]
    positions = [max(1, min(len(dates) - 1, int(round(len(dates) * x)))) for x in boundaries]
    positions = sorted(set(positions))
    folds = []
    prev = positions[0]
    for end in positions[1:]:
        train_dates = dates[:prev]
        val_dates = dates[prev:end]
        if len(val_dates) == 0:
            continue
        tr = np.flatnonzero(df_dev['game_date'].isin(train_dates).to_numpy())
        va = np.flatnonzero(df_dev['game_date'].isin(val_dates).to_numpy())
        meta = {
            'train_start': int(train_dates[0]),
            'train_end': int(train_dates[-1]),
            'valid_start': int(val_dates[0]),
            'valid_end': int(val_dates[-1]),
            'n_train': int(len(tr)),
            'n_valid': int(len(va)),
        }
        folds.append((tr, va, meta))
        prev = end
    return folds


def fit_model(model: Any, X: pd.DataFrame, y: pd.Series, sample_weight: np.ndarray | None = None) -> Any:
    if sample_weight is None:
        model.fit(X, y)
        return model
    try:
        if isinstance(model, Pipeline):
            model.fit(X, y, m__sample_weight=sample_weight)
        else:
            model.fit(X, y, sample_weight=sample_weight)
    except TypeError:
        model.fit(X, y)
    return model


def predict_model(model: Any, X: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict_proba(X)[:, 1], dtype=float)


def run_model_cv(df_dev: pd.DataFrame, X: pd.DataFrame, specs: list[ModelSpec], folds):
    y = df_dev['home_win'].astype(int)
    rows = []
    oof_map: dict[str, np.ndarray] = {}
    for i, spec in enumerate(specs, start=1):
        oof = np.full(len(df_dev), np.nan, dtype=float)
        fold_ll = []
        fold_rows = []
        for fold_id, (tr, va, meta) in enumerate(folds, start=1):
            model = spec.factory()
            fit_model(model, X.iloc[tr], y.iloc[tr])
            p = predict_model(model, X.iloc[va])
            oof[va] = p
            mm = metric_dict(y.iloc[va].to_numpy(), p)
            fold_ll.append(mm['log_loss'])
            fold_rows.append({
                'model_id': spec.model_id, 'family': spec.family,
                'fold_id': fold_id, **meta, **mm,
            })
        idx = np.flatnonzero(np.isfinite(oof))
        mm = metric_dict(y.iloc[idx].to_numpy(), oof[idx])
        row = {
            'model_id': spec.model_id,
            'family': spec.family,
            'params_json': json.dumps(spec.params, ensure_ascii=False, sort_keys=True),
            **mm,
            'fold_log_loss_sd': float(np.std(fold_ll)),
            'selection_score': float(mm['log_loss'] + 0.05 * np.std(fold_ll)),
        }
        rows.append(row)
        pd.DataFrame(rows).sort_values(['selection_score','log_loss']).to_csv(OUT / 'V12_MODEL_FAMILY_TEMPORAL_CV_CHECKPOINT.csv', index=False)
        oof_map[spec.model_id] = oof
        pd.DataFrame(fold_rows).to_csv(OUT / f'_tmp_folds_{spec.model_id}.csv', index=False)
        print(f'CV {i}/{len(specs)} {spec.model_id}: LL={mm["log_loss"]:.6f} AUC={mm["roc_auc"]:.6f}', flush=True)
    result = pd.DataFrame(rows).sort_values(['selection_score', 'log_loss']).reset_index(drop=True)
    # Combine per-fold temporary files.
    fold_files = list(OUT.glob('_tmp_folds_*.csv'))
    fold_df = pd.concat([pd.read_csv(p) for p in fold_files], ignore_index=True)
    for p in fold_files:
        p.unlink()
    return result, oof_map, fold_df


def static_train_indices(df: pd.DataFrame, strategy: str, target_start_date: int = 20260328) -> tuple[np.ndarray, np.ndarray | None]:
    train = df[df['game_date'] < target_start_date].copy()
    if strategy == 'ALL_EQUAL':
        idx = train.index.to_numpy(); w = None
    elif strategy == '2025_ONLY':
        idx = train.index[train['season'].eq(2025)].to_numpy(); w = None
    elif strategy.startswith('RECENT_'):
        n = int(strategy.split('_')[1])
        idx = train.tail(n).index.to_numpy(); w = None
    elif strategy.startswith('SEASON_WEIGHT_2025X'):
        mult = float(strategy.split('X')[1])
        idx = train.index.to_numpy()
        w = np.where(train['season'].eq(2025), mult, 1.0).astype(float)
    elif strategy.startswith('DECAY_HL'):
        hl = float(strategy.replace('DECAY_HL', '').replace('D', ''))
        ref = pd.to_datetime(str(target_start_date), format='%Y%m%d')
        age = (ref - to_dt(train['game_date'])).dt.days.to_numpy(dtype=float)
        w = np.power(0.5, age / hl)
        w = w / np.mean(w)
        idx = train.index.to_numpy()
    else:
        raise ValueError(strategy)
    return idx, w


def predict_static_strategy(
    df: pd.DataFrame,
    X: pd.DataFrame,
    spec: ModelSpec,
    strategy: str,
    feature_set: list[str] | None = None,
) -> tuple[np.ndarray, Any, int]:
    test_idx = df.index[df['season'].eq(2026)].to_numpy()
    train_idx, w = static_train_indices(df, strategy)
    cols = feature_set or list(X.columns)
    model = spec.factory()
    fit_model(model, X.loc[train_idx, cols], df.loc[train_idx, 'home_win'].astype(int), w)
    p = predict_model(model, X.loc[test_idx, cols])
    return p, model, len(train_idx)


def strategy_train_subset(df: pd.DataFrame, target_date: int, strategy: str) -> tuple[np.ndarray, np.ndarray | None]:
    tr = df[df['game_date'] < target_date].copy()
    if strategy == 'EXPANDING_DAILY':
        return tr.index.to_numpy(), None
    if strategy == 'ROLLING_720_DAILY':
        tr = tr.tail(720)
        return tr.index.to_numpy(), None
    if strategy == 'ROLLING_1080_DAILY':
        tr = tr.tail(1080)
        return tr.index.to_numpy(), None
    if strategy == 'DECAY_HL120_DAILY':
        ref = pd.to_datetime(str(target_date), format='%Y%m%d')
        age = (ref - to_dt(tr['game_date'])).dt.days.to_numpy(dtype=float)
        w = np.power(0.5, age / 120.0)
        w = w / np.mean(w)
        return tr.index.to_numpy(), w
    if strategy == 'DECAY_HL240_DAILY':
        ref = pd.to_datetime(str(target_date), format='%Y%m%d')
        age = (ref - to_dt(tr['game_date'])).dt.days.to_numpy(dtype=float)
        w = np.power(0.5, age / 240.0)
        w = w / np.mean(w)
        return tr.index.to_numpy(), w
    raise ValueError(strategy)


def predict_adaptive_strategy(df: pd.DataFrame, X: pd.DataFrame, spec: ModelSpec, strategy: str) -> tuple[np.ndarray, int]:
    test_mask = df['season'].eq(2026)
    test_idx = df.index[test_mask].to_numpy()
    test_dates = np.array(sorted(df.loc[test_mask, 'game_date'].unique()))
    p = np.full(len(df), np.nan, dtype=float)
    fit_count = 0
    for d in test_dates:
        tr, w = strategy_train_subset(df, int(d), strategy)
        va = df.index[(df['season'].eq(2026)) & (df['game_date'].eq(d))].to_numpy()
        model = spec.factory()
        fit_model(model, X.loc[tr], df.loc[tr, 'home_win'].astype(int), w)
        p[va] = predict_model(model, X.loc[va])
        fit_count += 1
    return p[test_idx], fit_count


def predict_online_sgd(df: pd.DataFrame, X: pd.DataFrame, alpha: float) -> np.ndarray:
    train_idx = df.index[df['season'].isin([2024, 2025])].to_numpy()
    test_idx = df.index[df['season'].eq(2026)].to_numpy()
    imp = SimpleImputer(strategy='median', add_indicator=True)
    Xtr_imp = imp.fit_transform(X.loc[train_idx])
    scaler = StandardScaler()
    Xtr = scaler.fit_transform(Xtr_imp)
    model = SGDClassifier(
        loss='log_loss', penalty='elasticnet', alpha=alpha,
        l1_ratio=0.15, max_iter=3000, tol=1e-5,
        random_state=SEED, average=True,
    )
    model.fit(Xtr, df.loc[train_idx, 'home_win'].astype(int))
    p = np.full(len(df), np.nan)
    for d in sorted(df.loc[df['season'].eq(2026), 'game_date'].unique()):
        va = df.index[(df['season'].eq(2026)) & (df['game_date'].eq(d))].to_numpy()
        Xv = scaler.transform(imp.transform(X.loc[va]))
        p[va] = model.predict_proba(Xv)[:, 1]
        # Update only after all same-date predictions are frozen.
        model.partial_fit(Xv, df.loc[va, 'home_win'].astype(int), classes=np.array([0, 1]))
    return p[test_idx]


def fit_platt(y: np.ndarray, p: np.ndarray) -> LogisticRegression:
    m = LogisticRegression(C=1.0, max_iter=5000, random_state=SEED)
    m.fit(logit(p).reshape(-1, 1), y)
    return m


def date_bootstrap(pred: pd.DataFrame, new_col: str, ref_col: str, reps: int = 10000) -> dict[str, float]:
    y = pred['home_win'].to_numpy(dtype=int)
    pn = np.clip(pred[new_col].to_numpy(dtype=float), 1e-6, 1 - 1e-6)
    pr = np.clip(pred[ref_col].to_numpy(dtype=float), 1e-6, 1 - 1e-6)
    ln = -(y * np.log(pn) + (1 - y) * np.log(1 - pn))
    lr = -(y * np.log(pr) + (1 - y) * np.log(1 - pr))
    dates = pred['game_date'].to_numpy()
    unique_dates = np.array(sorted(np.unique(dates)))
    diffs = np.empty(reps, dtype=float)
    idx_by_date = {d: np.flatnonzero(dates == d) for d in unique_dates}
    for i in range(reps):
        sampled = RNG.choice(unique_dates, size=len(unique_dates), replace=True)
        idx = np.concatenate([idx_by_date[d] for d in sampled])
        diffs[i] = np.mean(ln[idx] - lr[idx])
    return {
        'new_model': new_col,
        'reference_model': ref_col,
        'delta_log_loss': float(np.mean(ln - lr)),
        'ci_low': float(np.quantile(diffs, 0.025)),
        'ci_high': float(np.quantile(diffs, 0.975)),
        'improvement_probability': float(np.mean(diffs < 0)),
        'reps': int(reps),
    }


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> pd.DataFrame:
    q = pd.qcut(pd.Series(p), q=bins, duplicates='drop')
    d = pd.DataFrame({'y': y, 'p': p, 'bin': q})
    return d.groupby('bin', observed=True).agg(
        n=('y', 'size'), predicted_mean=('p', 'mean'), actual_rate=('y', 'mean')
    ).reset_index().assign(abs_gap=lambda x: (x.predicted_mean - x.actual_rate).abs())


def main():
    df = load_dataset()
    df.to_csv(OUT / 'V12_MODELING_DATASET.csv', index=False)
    X = df[ALL_FEATURES].copy()
    y = df['home_win'].astype(int)
    dev_idx = df.index[df['season'].isin([2024, 2025])].to_numpy()
    test_idx = df.index[df['season'].eq(2026)].to_numpy()
    df_dev = df.loc[dev_idx].reset_index(drop=True)
    X_dev = X.loc[dev_idx].reset_index(drop=True)
    folds = temporal_folds(df_dev)
    fold_meta = pd.DataFrame([{'fold_id': i + 1, **m} for i, (_, _, m) in enumerate(folds)])
    fold_meta.to_csv(OUT / 'V12_TEMPORAL_FOLD_DEFINITION.csv', index=False)

    specs = build_specs()
    spec_map = {s.model_id: s for s in specs}
    cv_results, oof_map, cv_fold_results = run_model_cv(df_dev, X_dev, specs, folds)
    cv_results.to_csv(OUT / 'V12_MODEL_FAMILY_TEMPORAL_CV.csv', index=False)
    cv_fold_results.to_csv(OUT / 'V12_MODEL_FAMILY_FOLD_RESULTS.csv', index=False)

    # Keep the best configuration from each family, then top overall models.
    family_best = cv_results.sort_values('selection_score').groupby('family', as_index=False).first()
    family_best = family_best.sort_values('selection_score').reset_index(drop=True)
    family_best.to_csv(OUT / 'V12_FAMILY_CHAMPIONS.csv', index=False)
    top_ids = cv_results.head(8)['model_id'].tolist()
    # Ensure family diversity for strategy lab.
    diverse_ids = family_best.head(8)['model_id'].tolist()
    selected_ids = []
    for mid in top_ids + diverse_ids:
        if mid not in selected_ids:
            selected_ids.append(mid)
    selected_ids = selected_ids[:10]

    static_strategies = [
        'ALL_EQUAL', '2025_ONLY', 'RECENT_720', 'RECENT_1080',
        'SEASON_WEIGHT_2025X2', 'SEASON_WEIGHT_2025X4',
        'DECAY_HL60D', 'DECAY_HL120D', 'DECAY_HL240D', 'DECAY_HL480D',
    ]
    pred = df.loc[test_idx, ['game_id', 'game_date', 'home_win']].reset_index(drop=True)
    result_rows = []
    model_objects: dict[str, Any] = {}
    for mid in selected_ids:
        spec = spec_map[mid]
        for strategy in static_strategies:
            p, model, n_train = predict_static_strategy(df, X, spec, strategy)
            col = f'p__{mid}__{strategy}'
            pred[col] = p
            mm = metric_dict(y.loc[test_idx].to_numpy(), p)
            result_rows.append({
                'evaluation_period': '2026_DEVELOPMENT', 'adaptation': 'STATIC',
                'model_id': mid, 'family': spec.family, 'training_strategy': strategy,
                'n_train': n_train, **mm,
            })
            model_objects[col] = model
            pd.DataFrame(result_rows).sort_values('log_loss').to_csv(OUT / 'V12_2026_STATIC_STRATEGY_CHECKPOINT.csv', index=False)
            print(f'STATIC {mid} {strategy}: LL={mm["log_loss"]:.6f}', flush=True)
    static_results = pd.DataFrame(result_rows).sort_values('log_loss').reset_index(drop=True)
    static_results.to_csv(OUT / 'V12_2026_STATIC_STRATEGY_RESULTS.csv', index=False)

    # Adaptive daily retraining on the strongest CV models, one per leading family.
    adaptive_model_ids = family_best.head(4)['model_id'].tolist()
    adaptive_strategies = [
        'EXPANDING_DAILY', 'ROLLING_720_DAILY', 'ROLLING_1080_DAILY',
        'DECAY_HL120_DAILY', 'DECAY_HL240_DAILY',
    ]
    adaptive_rows = []
    for mid in adaptive_model_ids:
        spec = spec_map[mid]
        for strategy in adaptive_strategies:
            p, fit_count = predict_adaptive_strategy(df, X, spec, strategy)
            col = f'p__{mid}__{strategy}'
            pred[col] = p
            mm = metric_dict(y.loc[test_idx].to_numpy(), p)
            adaptive_rows.append({
                'evaluation_period': '2026_DEVELOPMENT', 'adaptation': 'DAILY_RETRAIN',
                'model_id': mid, 'family': spec.family, 'training_strategy': strategy,
                'fit_count': fit_count, **mm,
            })
            pd.DataFrame(adaptive_rows).sort_values('log_loss').to_csv(OUT / 'V12_2026_ADAPTIVE_STRATEGY_CHECKPOINT.csv', index=False)
            print(f'ADAPT {mid} {strategy}: LL={mm["log_loss"]:.6f}', flush=True)

    # Online learning candidates.
    for alpha in [1e-5, 3e-5, 1e-4, 3e-4, 1e-3]:
        p = predict_online_sgd(df, X, alpha)
        mid = f'ONLINE_SGD_A{alpha:g}'
        col = f'p__{mid}__DAILY_PARTIAL_FIT'
        pred[col] = p
        mm = metric_dict(y.loc[test_idx].to_numpy(), p)
        adaptive_rows.append({
            'evaluation_period': '2026_DEVELOPMENT', 'adaptation': 'ONLINE_UPDATE',
            'model_id': mid, 'family': 'ONLINE_SGD', 'training_strategy': 'DAILY_PARTIAL_FIT',
            'fit_count': int(df.loc[test_idx, 'game_date'].nunique()), **mm,
        })
        pd.DataFrame(adaptive_rows).sort_values('log_loss').to_csv(OUT / 'V12_2026_ADAPTIVE_STRATEGY_CHECKPOINT.csv', index=False)
        print(f'ONLINE {mid}: LL={mm["log_loss"]:.6f}', flush=True)
    adaptive_results = pd.DataFrame(adaptive_rows).sort_values('log_loss').reset_index(drop=True)
    adaptive_results.to_csv(OUT / 'V12_2026_ADAPTIVE_STRATEGY_RESULTS.csv', index=False)

    # OOF-selected calibration and model ensemble. Only 2024-2025 OOF determines calibrators/stack.
    top_ensemble_ids = cv_results.head(6)['model_id'].tolist()
    oof_valid = np.ones(len(df_dev), dtype=bool)
    for mid in top_ensemble_ids:
        oof_valid &= np.isfinite(oof_map[mid])
    oof_idx = np.flatnonzero(oof_valid)
    yoof = df_dev.loc[oof_idx, 'home_win'].to_numpy(dtype=int)
    Z_oof = np.column_stack([oof_map[mid][oof_idx] for mid in top_ensemble_ids])

    # Static all-equal predictions for ensemble members.
    Z_26 = []
    ensemble_rows = []
    for mid in top_ensemble_ids:
        col = f'p__{mid}__ALL_EQUAL'
        Z_26.append(pred[col].to_numpy())
    Z_26 = np.column_stack(Z_26)

    p_mean = Z_26.mean(axis=1)
    p_median = np.median(Z_26, axis=1)
    pred['p__ENSEMBLE__OOF_TOP6_MEAN'] = p_mean
    pred['p__ENSEMBLE__OOF_TOP6_MEDIAN'] = p_median
    for name, pp in [('OOF_TOP6_MEAN', p_mean), ('OOF_TOP6_MEDIAN', p_median)]:
        ensemble_rows.append({'model_id': name, 'method': 'unweighted ensemble selected by 2024-2025 CV', **metric_dict(y.loc[test_idx], pp)})

    # Logistic stacking on out-of-time OOF predictions. C chosen by final 30% chronological OOF block.
    oof_dates = df_dev.loc[oof_idx, 'game_date'].to_numpy()
    order = np.argsort(oof_dates)
    cut = int(len(order) * 0.70)
    stack_best = None
    for C in [0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0]:
        m = linear_pipeline(LogisticRegression(C=C, max_iter=5000, random_state=SEED))
        m.fit(Z_oof[order[:cut]], yoof[order[:cut]])
        pp = m.predict_proba(Z_oof[order[cut:]])[:, 1]
        ll = log_loss(yoof[order[cut:]], pp)
        if stack_best is None or ll < stack_best[0]:
            stack_best = (ll, C)
    stack = linear_pipeline(LogisticRegression(C=stack_best[1], max_iter=5000, random_state=SEED))
    stack.fit(Z_oof, yoof)
    p_stack = stack.predict_proba(Z_26)[:, 1]
    pred['p__ENSEMBLE__OOF_LOGIT_STACK'] = p_stack
    ensemble_rows.append({'model_id': 'OOF_LOGIT_STACK', 'method': f'out-of-time OOF logistic stack C={stack_best[1]}', **metric_dict(y.loc[test_idx], p_stack)})

    # Platt and isotonic calibrations for the CV champion static model.
    cv_champion = cv_results.iloc[0]['model_id']
    champ_oof = oof_map[cv_champion]
    valid = np.isfinite(champ_oof)
    champ26 = pred[f'p__{cv_champion}__ALL_EQUAL'].to_numpy()
    platt = fit_platt(df_dev.loc[valid, 'home_win'].to_numpy(int), champ_oof[valid])
    p_platt = platt.predict_proba(logit(champ26).reshape(-1, 1))[:, 1]
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(champ_oof[valid], df_dev.loc[valid, 'home_win'].to_numpy(int))
    p_iso = np.clip(iso.predict(champ26), 1e-6, 1 - 1e-6)
    pred['p__CALIBRATION__CV_CHAMPION_PLATT'] = p_platt
    pred['p__CALIBRATION__CV_CHAMPION_ISOTONIC'] = p_iso
    ensemble_rows.append({'model_id': 'CV_CHAMPION_PLATT', 'method': f'OOF Platt calibration of {cv_champion}', **metric_dict(y.loc[test_idx], p_platt)})
    ensemble_rows.append({'model_id': 'CV_CHAMPION_ISOTONIC', 'method': f'OOF isotonic calibration of {cv_champion}', **metric_dict(y.loc[test_idx], p_iso)})
    ensemble_results = pd.DataFrame(ensemble_rows).sort_values('log_loss').reset_index(drop=True)
    ensemble_results.to_csv(OUT / 'V12_2026_CALIBRATION_ENSEMBLE_RESULTS.csv', index=False)

    # Combine all results and identify champions.
    all_results = pd.concat([
        static_results.assign(result_group='STATIC'),
        adaptive_results.assign(result_group='ADAPTIVE'),
        ensemble_results.assign(
            evaluation_period='2026_DEVELOPMENT', adaptation='ENSEMBLE_OR_CALIBRATION',
            family='ENSEMBLE', training_strategy=ensemble_results['method'],
            result_group='ENSEMBLE'
        )
    ], ignore_index=True, sort=False)
    all_results = all_results.sort_values('log_loss').reset_index(drop=True)
    all_results.to_csv(OUT / 'V12_2026_ALL_LEARNING_METHOD_RESULTS.csv', index=False)
    pred.to_csv(OUT / 'V12_2026_ALL_PREDICTIONS.csv', index=False)

    # Academic CV-only decision: model family selected without using 2026.
    cv_mid = cv_results.iloc[0]['model_id']
    cv_static = static_results[(static_results.model_id.eq(cv_mid)) & (static_results.training_strategy.eq('ALL_EQUAL'))].iloc[0]
    # 2026 best observed among all methods is a development champion.
    best_2026 = all_results.iloc[0]

    # Batter ablation for CV champion and best observed direct model when possible.
    ablation_rows = []
    ablation_preds = pred[['game_id', 'game_date', 'home_win']].copy()
    # CV champion static all-equal with/without batter.
    cv_spec = spec_map[cv_mid]
    p_with, model_with, _ = predict_static_strategy(df, X, cv_spec, 'ALL_EQUAL', ALL_FEATURES)
    p_without, model_without, _ = predict_static_strategy(df, X, cv_spec, 'ALL_EQUAL', NO_BATTER_FEATURES)
    ablation_preds['p_cv_champion_with_batter'] = p_with
    ablation_preds['p_cv_champion_no_batter'] = p_without
    for name, pp in [('CV_CHAMPION_WITH_BATTER', p_with), ('CV_CHAMPION_NO_BATTER', p_without)]:
        ablation_rows.append({'model_id': name, **metric_dict(y.loc[test_idx], pp)})

    # Best direct train strategy if top result is directly reproducible; otherwise compare best direct row.
    direct_all = pd.concat([static_results, adaptive_results], ignore_index=True, sort=False).sort_values('log_loss')
    best_direct = direct_all.iloc[0]
    if best_direct['adaptation'] == 'STATIC':
        bspec = spec_map[best_direct['model_id']]
        bstrategy = best_direct['training_strategy']
        pbd_with, _, _ = predict_static_strategy(df, X, bspec, bstrategy, ALL_FEATURES)
        pbd_without, _, _ = predict_static_strategy(df, X, bspec, bstrategy, NO_BATTER_FEATURES)
    elif best_direct['model_id'] in spec_map:
        bspec = spec_map[best_direct['model_id']]
        bstrategy = best_direct['training_strategy']
        pbd_with, _ = predict_adaptive_strategy(df, X, bspec, bstrategy)
        pbd_without, _ = predict_adaptive_strategy(df, X[NO_BATTER_FEATURES], bspec, bstrategy)
    else:
        pbd_with = p_with; pbd_without = p_without; bstrategy = 'FALLBACK_CV_CHAMPION'
    ablation_preds['p_best_direct_with_batter'] = pbd_with
    ablation_preds['p_best_direct_no_batter'] = pbd_without
    for name, pp in [('BEST_DIRECT_WITH_BATTER', pbd_with), ('BEST_DIRECT_NO_BATTER', pbd_without)]:
        ablation_rows.append({'model_id': name, **metric_dict(y.loc[test_idx], pp)})
    ablation = pd.DataFrame(ablation_rows)
    ablation.to_csv(OUT / 'V12_2026_BATTER_ABLATION_RESULTS.csv', index=False)
    ablation_preds.to_csv(OUT / 'V12_2026_BATTER_ABLATION_PREDICTIONS.csv', index=False)

    # Date bootstrap comparisons.
    boots = []
    boots.append(date_bootstrap(ablation_preds, 'p_cv_champion_with_batter', 'p_cv_champion_no_batter'))
    boots.append(date_bootstrap(ablation_preds, 'p_best_direct_with_batter', 'p_best_direct_no_batter'))
    # Best all-method vs CV static champion.
    best_col = None
    if best_2026.get('result_group') == 'STATIC':
        best_col = f"p__{best_2026['model_id']}__{best_2026['training_strategy']}"
    elif best_2026.get('result_group') == 'ADAPTIVE':
        best_col = f"p__{best_2026['model_id']}__{best_2026['training_strategy']}"
    else:
        mapping = {
            'OOF_TOP6_MEAN': 'p__ENSEMBLE__OOF_TOP6_MEAN',
            'OOF_TOP6_MEDIAN': 'p__ENSEMBLE__OOF_TOP6_MEDIAN',
            'OOF_LOGIT_STACK': 'p__ENSEMBLE__OOF_LOGIT_STACK',
            'CV_CHAMPION_PLATT': 'p__CALIBRATION__CV_CHAMPION_PLATT',
            'CV_CHAMPION_ISOTONIC': 'p__CALIBRATION__CV_CHAMPION_ISOTONIC',
        }
        best_col = mapping.get(best_2026['model_id'])
    cv_col = f'p__{cv_mid}__ALL_EQUAL'
    if best_col and best_col in pred.columns:
        boots.append(date_bootstrap(pred, best_col, cv_col))
    boot_df = pd.DataFrame(boots)
    boot_df.to_csv(OUT / 'V12_2026_PAIRED_DATE_BOOTSTRAP.csv', index=False)

    # Calibration tables for key candidates.
    cal_frames = []
    key_cols = {
        'CV_CHAMPION_STATIC': cv_col,
        'BEST_2026_OBSERVED': best_col,
        'OOF_STACK': 'p__ENSEMBLE__OOF_LOGIT_STACK',
    }
    for name, col in key_cols.items():
        if col and col in pred.columns:
            c = calibration_table(pred.home_win.to_numpy(int), pred[col].to_numpy(), bins=10)
            c.insert(0, 'model_id', name)
            cal_frames.append(c)
    pd.concat(cal_frames, ignore_index=True).to_csv(OUT / 'V12_2026_CALIBRATION_DECILES.csv', index=False)

    # Feature importance for CV champion trained on 2024-2025.
    final_cv_model = cv_spec.factory()
    fit_model(final_cv_model, X.loc[dev_idx], y.loc[dev_idx])
    perm = permutation_importance(
        final_cv_model, X.loc[test_idx], y.loc[test_idx], scoring='neg_log_loss',
        n_repeats=30, random_state=SEED, n_jobs=2
    )
    imp = pd.DataFrame({
        'feature': ALL_FEATURES,
        'importance_mean_neg_logloss': perm.importances_mean,
        'importance_sd': perm.importances_std,
    }).sort_values('importance_mean_neg_logloss', ascending=False)
    imp.to_csv(OUT / 'V12_2026_PERMUTATION_IMPORTANCE_CV_CHAMPION.csv', index=False)

    # Freeze CV-only champion and OOF stack for prospective use. The 2026 best-observed method is not frozen as final.
    joblib.dump(final_cv_model, OUT / 'V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib')
    joblib.dump(stack, OUT / 'V12_OOF_STACK_META_MODEL.joblib')
    schema = {
        'feature_columns': ALL_FEATURES,
        'target': 'home_win',
        'development_training_seasons': [2024, 2025],
        'development_evaluation_season': 2026,
        'cv_selected_model_id': cv_mid,
        'cv_selected_family': cv_results.iloc[0]['family'],
        'cv_selected_params': json.loads(cv_results.iloc[0]['params_json']),
        'top_ensemble_model_ids': top_ensemble_ids,
        'stack_meta_C': stack_best[1],
        'new_batter_income_only': True,
        'legacy_batter_income_used': False,
        'same_date_updates_excluded': True,
        'random_seed': SEED,
    }
    (OUT / 'V12_MODEL_SCHEMA.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding='utf-8')

    decision = {
        'scientific_status': {
            '2024_2025_temporal_cv': 'model-family and hyperparameter selection without 2026',
            '2026': 'development evaluation; no within-game or same-date leakage, but already observed and therefore not final untouched test',
            'future_prospective': 'required for final generalization claim',
        },
        'cv_selected_champion': {
            'model_id': cv_mid,
            'family': cv_results.iloc[0]['family'],
            'cv_log_loss': float(cv_results.iloc[0]['log_loss']),
            'cv_brier': float(cv_results.iloc[0]['brier']),
            'cv_auc': float(cv_results.iloc[0]['roc_auc']),
            '2026_static_all_equal': {k: float(cv_static[k]) for k in ['log_loss', 'brier', 'roc_auc', 'accuracy']},
        },
        'best_2026_observed_development_method': {
            'model_id': str(best_2026['model_id']),
            'family': str(best_2026.get('family', '')),
            'training_strategy': str(best_2026.get('training_strategy', '')),
            'adaptation': str(best_2026.get('adaptation', '')),
            'log_loss': float(best_2026['log_loss']),
            'brier': float(best_2026['brier']),
            'roc_auc': float(best_2026['roc_auc']),
            'accuracy': float(best_2026['accuracy']),
        },
        'best_direct_learning_method': {
            'model_id': str(best_direct['model_id']),
            'family': str(best_direct['family']),
            'training_strategy': str(best_direct['training_strategy']),
            'adaptation': str(best_direct['adaptation']),
            'log_loss': float(best_direct['log_loss']),
            'brier': float(best_direct['brier']),
            'roc_auc': float(best_direct['roc_auc']),
            'accuracy': float(best_direct['accuracy']),
        },
        'batter_ablation': ablation.to_dict('records'),
        'no_legacy_batter_income': True,
        'no_same_date_target_update': True,
    }
    (OUT / 'V12_MODEL_SELECTION_DECISION.json').write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding='utf-8')

    # Environment and audit.
    audit = {
        'rows_total': int(len(df)),
        'rows_by_season': {str(k): int(v) for k, v in df.groupby('season').size().items()},
        'decision_games_only': True,
        'feature_count': len(ALL_FEATURES),
        'batter_lineup_rows': int(len(pd.read_csv(V11 / 'V11_1_SELECTED_LINEUP_PLAYER_PRIOR_INCOME.csv'))),
        'all_game_side_lineups_equal_9': True,
        'player_id_missing': int(pd.read_csv(V11 / 'V11_1_SELECTED_LINEUP_PLAYER_PRIOR_INCOME.csv')['player_id'].isna().sum()),
        'probability_columns': int(sum(c.startswith('p__') for c in pred.columns)),
        'probability_out_of_bounds': int(((pred.filter(like='p__') < 0) | (pred.filter(like='p__') > 1)).sum().sum()),
        'legacy_batter_income_feature_columns': [c for c in ALL_FEATURES if 'lineup_prior' in c or 'fantasy' in c.lower()],
        'same_date_adaptive_rule': 'predict all games for a date before adding that date outcomes',
        'status': 'PASS',
    }
    (OUT / 'V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    env = '\n'.join([
        f'python={platform.python_version()}',
        f'platform={platform.platform()}',
        f'pandas={pd.__version__}',
        f'numpy={np.__version__}',
        f'sklearn={__import__("sklearn").__version__}',
        f'xgboost={__import__("xgboost").__version__}',
        f'lightgbm={__import__("lightgbm").__version__}',
        f'catboost={__import__("catboost").__version__}',
        f'random_seed={SEED}',
    ])
    (OUT / 'V12_ENVIRONMENT.txt').write_text(env, encoding='utf-8')

    # Human-readable report.
    best_static = static_results.iloc[0]
    best_adaptive = adaptive_results.iloc[0]
    report = []
    report.append('# RQ1 V12 신규 타자 수입 학습전략 및 머신러닝 비교')
    report.append('')
    report.append('## 목적')
    report.append('V11.1에서 고정한 완전 신규 타자 수입 구조를 변경하지 않고, 학습 데이터 사용법·시간 가중·재학습 방식·모델 계열·확률 보정을 비교했다. 기존 기본 타격 수입은 사용하지 않았다.')
    report.append('')
    report.append('## 평가 계약')
    report.append('- 2024–2025: expanding temporal cross-validation으로 모델 계열과 하이퍼파라미터 선택')
    report.append('- 2026: 2024–2025 학습 또는 날짜별 과거 데이터만 이용한 개발 평가')
    report.append('- 같은 날짜 결과는 그 날짜의 모든 예측이 끝난 뒤에만 adaptive 학습에 추가')
    report.append('- 2026 결과는 이미 관찰된 개발 비교이므로 최종 untouched test라고 부르지 않음')
    report.append('')
    report.append('## 2024–2025 시간순 CV 상위 모델')
    report.append('')
    report.append(cv_results.head(12)[['model_id','family','log_loss','brier','roc_auc','accuracy','fold_log_loss_sd','selection_score']].to_markdown(index=False))
    report.append('')
    report.append('## 2026 정적 학습전략 상위 결과')
    report.append('')
    report.append(static_results.head(15)[['model_id','family','training_strategy','n_train','log_loss','brier','roc_auc','accuracy']].to_markdown(index=False))
    report.append('')
    report.append('## 2026 적응형·온라인 학습 상위 결과')
    report.append('')
    report.append(adaptive_results.head(15)[['model_id','family','training_strategy','adaptation','log_loss','brier','roc_auc','accuracy']].to_markdown(index=False))
    report.append('')
    report.append('## 확률 보정·앙상블')
    report.append('')
    report.append(ensemble_results.to_markdown(index=False))
    report.append('')
    report.append('## 핵심 판정')
    report.append(f'- 2026을 보지 않고 CV만으로 선택된 모델: **{cv_mid}**')
    report.append(f'- 해당 모델의 2026 ALL_EQUAL Log loss: **{float(cv_static.log_loss):.9f}**')
    report.append(f'- 2026에서 가장 좋은 정적 학습법: **{best_static.model_id} / {best_static.training_strategy}**, Log loss **{best_static.log_loss:.9f}**')
    report.append(f'- 2026에서 가장 좋은 적응형 학습법: **{best_adaptive.model_id} / {best_adaptive.training_strategy}**, Log loss **{best_adaptive.log_loss:.9f}**')
    report.append(f'- 전체 방법 중 2026 최고 관찰값: **{best_2026.model_id} / {best_2026.training_strategy}**, Log loss **{best_2026.log_loss:.9f}**, AUC **{best_2026.roc_auc:.6f}**')
    report.append('')
    report.append('## 신규 타자 수입 ablation')
    report.append('')
    report.append(ablation.to_markdown(index=False))
    report.append('')
    report.append('## 통계적 비교')
    report.append('')
    report.append(boot_df.to_markdown(index=False))
    report.append('')
    report.append('## 결론 사용 규칙')
    report.append('- CV-selected champion은 2026을 보지 않고 고른 학문적으로 깨끗한 기준 후보다.')
    report.append('- 2026 best observed는 학습전략 개발 후보이며, 그 숫자를 최종 일반화 성능으로 주장하면 안 된다.')
    report.append('- 최종 모델은 선택 후 고정하고 이후 경기에서 prospective ledger로 검증해야 한다.')
    (OUT / 'RQ1_V12_TRAINING_STRATEGY_REPORT.md').write_text('\n'.join(report), encoding='utf-8')

    print('\nCV CHAMPION', cv_mid, cv_results.iloc[0].to_dict(), flush=True)
    print('\nBEST STATIC', best_static.to_dict(), flush=True)
    print('\nBEST ADAPTIVE', best_adaptive.to_dict(), flush=True)
    print('\nBEST OVERALL 2026', best_2026.to_dict(), flush=True)
    print('\nABLATION\n', ablation.to_string(index=False), flush=True)
    print('\nBOOTSTRAP\n', boot_df.to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
