"""Compare anomaly detectors on deduplicated KDD Cup 1999 connection records."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import urllib.request

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from anomaly.main import autoencoder_scores, choose_threshold, evaluate

SOURCE = 'https://ndownloader.figshare.com/files/5976042'
SOURCE_SHA256 = '8045aca0d84e70e622d1148d7df782496f6333bf6eb979a1b0837c42a9fd9561'
FEATURES = [str(i) for i in range(41)]
CATEGORICAL = ['1', '2', '3']
NUMERIC = [c for c in FEATURES if c not in CATEGORICAL]


def read_records(path):
    frame = pd.read_csv(path, header=None, compression='infer')
    if frame.shape[1] != 42:
        raise ValueError('KDD records require 42 columns: 41 features and an attack label.')
    frame.columns = FEATURES + ['attack']
    return frame


def clean_records(frame):
    if list(frame.columns) != FEATURES + ['attack'] or frame.isna().any().any():
        raise ValueError('Expected 41 complete KDD features and an attack label.')
    frame = frame.copy()
    frame[NUMERIC] = frame[NUMERIC].apply(pd.to_numeric, errors='raise').astype(float)
    if not np.isfinite(frame[NUMERIC].to_numpy()).all() or (frame[NUMERIC] < 0).any().any():
        raise ValueError('Numeric features must be finite and nonnegative.')
    frame[CATEGORICAL] = frame[CATEGORICAL].astype(str)
    frame['attack'] = frame.attack.astype(str).str.rstrip('.')
    if (frame.attack.str.len() == 0).any():
        raise ValueError('Attack labels cannot be empty.')
    # Hash only features, so duplicate connections cannot leak across partitions.
    frame['record_id'] = pd.util.hash_pandas_object(frame[FEATURES], index=False).map(lambda x: f'{x:016x}')
    conflicts = frame.groupby('record_id').attack.nunique()
    conflicts = set(conflicts[conflicts > 1].index)
    clean = frame.loc[~frame.record_id.isin(conflicts)].drop_duplicates('record_id').copy()
    clean['label'] = (clean.attack != 'normal').astype(int)
    clean = clean.sort_values('record_id').reset_index(drop=True)
    return clean, {'input_rows': len(frame), 'unique_unambiguous_rows': len(clean),
                   'conflicting_feature_groups_removed': len(conflicts),
                   'duplicate_or_conflicting_rows_removed': len(frame) - len(clean)}


def split_records(frame, train_size=6000, validation_size=2000, test_size=3000, seed=42):
    if min(train_size, validation_size, test_size) < 20:
        raise ValueError('Each split needs at least 20 records.')
    total = train_size + validation_size + test_size
    if total > len(frame) or set(frame.label.unique()) != {0, 1}:
        raise ValueError('Not enough records or both classes are not available.')
    if total < len(frame):
        frame, _ = train_test_split(frame, train_size=total, stratify=frame.label, random_state=seed)
    train, remainder = train_test_split(frame, train_size=train_size, stratify=frame.label, random_state=seed)
    validation, test = train_test_split(remainder, train_size=validation_size, stratify=remainder.label, random_state=seed + 1)
    parts = tuple(p.reset_index(drop=True) for p in (train, validation, test))
    if any(set(p.label.unique()) != {0, 1} for p in parts):
        raise ValueError('Each split needs normal and attack records.')
    return parts


def preprocess(train, validation, test):
    normal = train.loc[train.label == 0]
    transformer = ColumnTransformer([
        ('numeric', Pipeline([('log', FunctionTransformer(np.log1p)), ('scale', StandardScaler())]), NUMERIC),
        ('categorical', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL),
    ])
    x = transformer.fit_transform(normal[FEATURES])
    return x, transformer.transform(validation[FEATURES]), transformer.transform(test[FEATURES]), transformer


def run(path, output, train_size=6000, validation_size=2000, test_size=3000, seed=42):
    path, output = Path(path), Path(output)
    raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if raw_hash != SOURCE_SHA256:
        raise ValueError('Dataset SHA-256 does not match the published scikit-learn KDD 10% archive.')
    frame, cleaning = clean_records(read_records(path))
    train, validation, test = split_records(frame, train_size, validation_size, test_size, seed)
    x, v, t, transformer = preprocess(train, validation, test)
    output.mkdir(parents=True, exist_ok=True)
    median = np.median(x, axis=0)
    mad = np.maximum(np.median(np.abs(x - median), axis=0) * 1.4826, .1)
    robust_v, robust_t = np.abs(v - median) / mad, np.abs(t - median) / mad
    candidates = {'robust_z': [({'feature_quantile': q}, np.quantile(robust_v, q, axis=1), np.quantile(robust_t, q, axis=1)) for q in (.9, 1.)]}
    candidates['isolation_forest'] = []
    for samples in (128, 256):
        model = IsolationForest(n_estimators=150, max_samples=min(samples, len(x)), random_state=seed, n_jobs=1).fit(x)
        candidates['isolation_forest'].append(({'max_samples': samples}, -model.score_samples(v), -model.score_samples(t)))
    candidates['autoencoder'] = []
    for bottleneck in (4, 8):
        vs, ts = autoencoder_scores(x, v, t, seed, bottleneck)
        candidates['autoencoder'].append(({'bottleneck': bottleneck}, vs, ts))
    predictions = test[['record_id', 'attack', 'label']].copy()
    metrics, scores, tuning = {}, {}, {}
    for name, options in candidates.items():
        ranked = []
        tuning[name] = []
        for params, vs, ts in options:
            threshold = choose_threshold(vs, validation.label)
            validation_metrics = evaluate(vs, validation.label, threshold)
            tuning[name].append({'parameters': params, **validation_metrics})
            ranked.append((validation_metrics['f1'], params, ts, threshold))
        _, params, score, threshold = max(ranked, key=lambda row: row[0])
        metrics[name] = evaluate(score, test.label, threshold) | {'parameters': params}
        predictions[name + '_score'] = score
        predictions[name + '_prediction'] = (score >= threshold).astype(int)
        scores[name] = score
    predictions.to_csv(output / 'predictions.csv', index=False)
    assignments = pd.concat([p[['record_id', 'attack', 'label']].assign(split=name) for name, p in zip(('train', 'validation', 'test'), (train, validation, test))])
    assignments.to_csv(output / 'split-records.csv', index=False)
    metadata = {'dataset': 'KDD Cup 1999, 10% training corpus', 'source_url': SOURCE,
                'source_sha256': raw_hash, 'citation': 'https://doi.org/10.24432/C51C7N',
                'license': 'CC BY 4.0 per UCI', 'seed': seed, 'cleaning': cleaning,
                'split': 'Stratified random split after feature deduplication; not chronological and not the official corrected test set.',
                'split_rows': {n: len(p) for n, p in zip(('train', 'validation', 'test'), (train, validation, test))},
                'normal_rows_used_for_fitting': len(x), 'preprocessed_features': x.shape[1],
                'fit': 'Log1p numeric features, StandardScaler and one-hot categories fitted only on normal training records.',
                'selection': 'Hyperparameters and threshold selected by validation F1; test labels used only for evaluation.',
                'record_ids': 'pandas hash_pandas_object of 41 typed features, index=False; 16-digit hex. Hash collisions would conservatively remove extra records.',
                'environment': {'python': platform.python_version(), 'platform': platform.platform(), **{n: version(n) for n in ('numpy', 'pandas', 'scikit-learn', 'torch', 'matplotlib')}},
                'limitations': ['1999 simulated military-network intrusions, not modern enterprise logs.', 'Subset results depend on sampling and the natural class balance after deduplication.', 'This experiment does not establish production detection rates.']}
    for filename, data in [('metrics.json', metrics), ('validation.json', tuning), ('experiment.json', metadata)]:
        (output / filename).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), layout='constrained')
    for name, score in scores.items():
        fpr, tpr, _ = roc_curve(test.label, score)
        axes[0].plot(fpr, tpr, label=f'{name}: AUC {metrics[name]["roc_auc"]:.3f}')
    axes[0].plot([0, 1], [0, 1], '--', color='gray')
    axes[0].set(xlabel='False positive rate', ylabel='True positive rate', title='Held-out KDD connection records')
    axes[0].legend()
    selected = scores['isolation_forest']
    for label, color, name in [(0, '#315d86', 'Normal'), (1, '#d65a42', 'Attack')]:
        mask = test.label.to_numpy() == label
        axes[1].scatter(np.arange(len(test))[mask], selected[mask], s=7, alpha=.5, c=color, label=name)
    axes[1].axhline(metrics['isolation_forest']['threshold'], color='black', linestyle='--', label='Validation threshold')
    axes[1].set(xlabel='Held-out sample index (not time)', ylabel='Isolation Forest anomaly score', title='Labeled connections and selected threshold')
    axes[1].legend()
    fig.savefig(output / 'network-anomalies.png', dpi=140)
    plt.close(fig)
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='Path to the official kddcup.data_10_percent.gz archive')
    parser.add_argument('--download', action='store_true', help='Download the public archive if --data is absent')
    parser.add_argument('--output', type=Path, default=Path('reports/network-anomaly'))
    parser.add_argument('--train-size', type=int, default=6000)
    parser.add_argument('--validation-size', type=int, default=2000)
    parser.add_argument('--test-size', type=int, default=3000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.download and not args.data.exists():
        args.data.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(SOURCE, timeout=60) as response:
            payload = response.read(5_000_001)
        if len(payload) > 5_000_000 or hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
            raise ValueError('Downloaded dataset failed size or SHA-256 validation.')
        args.data.write_bytes(payload)
    print(json.dumps(run(args.data, args.output, args.train_size, args.validation_size, args.test_size, args.seed), indent=2))
