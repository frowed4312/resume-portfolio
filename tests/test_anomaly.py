import numpy as np
import pytest
from anomaly.main import load_data, split_data, run


def test_chronological_split_and_invalid_data(tmp_path):
    frame = load_data(None, 42)
    train, validation, test = split_data(frame)
    assert train.timestamp.max() < validation.timestamp.min()
    assert validation.timestamp.max() < test.timestamp.min()
    bad = tmp_path / 'bad.csv'
    bad.write_text('timestamp,value,label\n0,nan,0\n')
    with pytest.raises(ValueError):
        load_data(bad, 42)


def test_experiment_outputs_and_signal(tmp_path):
    metrics = run(None, tmp_path, 42)
    assert set(metrics) == {'robust_z', 'isolation_forest', 'autoencoder'}
    assert all(np.isfinite(m['roc_auc']) for m in metrics.values())
    assert max(m['f1'] for m in metrics.values()) > 0.7
    assert (tmp_path / 'anomalies.png').is_file()
    assert (tmp_path / 'predictions.csv').is_file()
