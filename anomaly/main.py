"""Compare three anomaly detectors on time-ordered sensor data."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score, roc_curve
from sklearn.preprocessing import StandardScaler


def load_data(path=None, seed=42):
    if path:
        frame = pd.read_csv(path)
    else:
        rng = np.random.default_rng(seed)
        t = np.arange(2400)
        frame = pd.DataFrame({'timestamp': t, 'value': np.sin(t / 25) + rng.normal(0, .15, len(t)), 'label': 0})
        indices = rng.choice(len(t), 120, replace=False)
        frame.loc[indices, 'value'] += rng.choice([-1, 1], len(indices)) * rng.uniform(3, 6, len(indices))
        frame.loc[indices, 'label'] = 1
    if not {'timestamp', 'value', 'label'} <= set(frame):
        raise ValueError('CSV requires timestamp,value,label (binary ground truth).')
    frame = frame[['timestamp', 'value', 'label']].copy()
    if len(frame) < 100 or frame.isna().any().any():
        raise ValueError('At least 100 complete rows are required; missing data is not silently imputed.')
    if not np.isfinite(frame[['value', 'label']].to_numpy(dtype=float)).all():
        raise ValueError('Values must be finite.')
    if not frame.label.isin([0, 1]).all():
        raise ValueError('Labels must be 0 or 1.')
    if pd.api.types.is_numeric_dtype(frame.timestamp):
        if not np.isfinite(frame.timestamp.to_numpy()).all():
            raise ValueError('Numeric timestamps must be finite.')
    else:
        frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True, errors='raise')
    if frame.timestamp.duplicated().any():
        raise ValueError('Timestamps must be unique.')
    return frame.sort_values('timestamp').reset_index(drop=True)


def split_data(frame):
    a, b = int(len(frame) * .6), int(len(frame) * .8)
    parts = (frame.iloc[:a].copy(), frame.iloc[a:b].copy(), frame.iloc[b:].copy())
    if any(set(p.label.unique()) != {0, 1} for p in parts):
        raise ValueError('Each chronological split must contain normal and anomalous labels for evaluation.')
    return parts


def features(frame):
    # Trailing features only: no centered windows or future values.
    v = frame.value
    return np.column_stack([v, v.diff().fillna(0), v.rolling(8, min_periods=1).mean(),
                            v.rolling(8, min_periods=1).std().fillna(0)])


def choose_threshold(scores, labels):
    candidates = np.unique(np.r_[np.quantile(scores, np.linspace(0, 1, 101)), np.nextafter(scores.max(), np.inf)])
    best = max(candidates, key=lambda t: precision_recall_fscore_support(labels, scores >= t, average='binary', zero_division=0)[2])
    return float(best)


def evaluate(scores, labels, threshold):
    p, r, f, _ = precision_recall_fscore_support(labels, scores >= threshold, average='binary', zero_division=0)
    return {'precision': float(p), 'recall': float(r), 'f1': float(f),
            'roc_auc': float(roc_auc_score(labels, scores)), 'threshold': threshold}


def autoencoder_scores(train, validation, test, seed, bottleneck):
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    net = torch.nn.Sequential(torch.nn.Linear(train.shape[1], 8), torch.nn.Tanh(),
                              torch.nn.Linear(8, bottleneck), torch.nn.Tanh(),
                              torch.nn.Linear(bottleneck, 8), torch.nn.Tanh(), torch.nn.Linear(8, train.shape[1]))
    x = torch.tensor(train, dtype=torch.float32)
    optimizer = torch.optim.Adam(net.parameters(), lr=.01)
    for _ in range(160):
        optimizer.zero_grad()
        loss = ((net(x) - x) ** 2).mean()
        loss.backward()
        optimizer.step()
    net.eval()
    with torch.no_grad():
        return tuple(((net(torch.tensor(z, dtype=torch.float32)) - torch.tensor(z, dtype=torch.float32)) ** 2).mean(1).numpy()
                     for z in (validation, test))


def run(csv, output, seed=42):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    frame = load_data(csv, seed)
    train, validation, test = split_data(frame)
    all_x = features(frame)
    a, b = len(train), len(train) + len(validation)
    # Train on normal rows only; labels are required for this split.
    clean = all_x[:a][train.label.to_numpy() == 0]
    scaler = StandardScaler().fit(clean)
    x, v, t = (scaler.transform(z) for z in (clean, all_x[a:b], all_x[b:]))
    median = np.median(clean[:, 0])
    mad = max(np.median(np.abs(clean[:, 0] - median)) * 1.4826, 1e-8)
    candidates = {'robust_z': [({}, np.abs(all_x[a:b, 0] - median) / mad, np.abs(all_x[b:, 0] - median) / mad)]}
    candidates['isolation_forest'] = []
    for samples in (128, 256):
        model = IsolationForest(n_estimators=150, max_samples=min(samples, len(x)), random_state=seed, n_jobs=1).fit(x)
        candidates['isolation_forest'].append(({'max_samples': samples}, -model.score_samples(v), -model.score_samples(t)))
    candidates['autoencoder'] = []
    for bottleneck in (1, 2):
        vs, ts = autoencoder_scores(x, v, t, seed, bottleneck)
        candidates['autoencoder'].append(({'bottleneck': bottleneck}, vs, ts))
    metrics, selected = {}, {}
    prediction = test.copy()
    for name, options in candidates.items():
        ranked = []
        for params, vs, ts in options:
            threshold = choose_threshold(vs, validation.label)
            ranked.append((evaluate(vs, validation.label, threshold)['f1'], params, ts, threshold))
        _, params, scores, threshold = max(ranked, key=lambda row: row[0])
        metrics[name] = evaluate(scores, test.label, threshold) | {'parameters': params}
        selected[name] = scores
        prediction[name + '_score'] = scores
        prediction[name + '_prediction'] = (scores >= threshold).astype(int)
    prediction.to_csv(output / 'predictions.csv', index=False)
    frame.to_csv(output / 'dataset.csv', index=False)
    (output / 'metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    (output / 'experiment.json').write_text(json.dumps({'seed': seed, 'source': str(csv) if csv else 'synthetic sensor spikes',
        'split_rows': [len(train), len(validation), len(test)], 'training': 'normal labeled rows only',
        'selection': 'validation F1; no test-based tuning'}, indent=2), encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), layout='constrained')
    axes[0].plot(test.timestamp, test.value, lw=.8, color='#315d86')
    truth = test.label == 1
    axes[0].scatter(test.timestamp[truth], test.value[truth], c='#d65a42', s=22, label='Labeled anomaly')
    axes[0].set_title('Held-out sensor data'); axes[0].legend()
    for name, scores in selected.items():
        fpr, tpr, _ = roc_curve(test.label, scores)
        axes[1].plot(fpr, tpr, label=f'{name}: AUC {metrics[name]["roc_auc"]:.3f}')
    axes[1].plot([0, 1], [0, 1], '--', color='gray')
    axes[1].set(xlabel='False positive rate', ylabel='True positive rate', title='Test ROC curves')
    axes[1].legend(); fig.savefig(output / 'anomalies.png', dpi=150); plt.close(fig)
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--output', type=Path, default=Path('reports/anomaly'))
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(run(args.csv, args.output, args.seed), indent=2))
