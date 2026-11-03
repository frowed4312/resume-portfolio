import numpy as np
import pandas as pd
import pytest

from anomaly.network import clean_records, split_records, preprocess, read_records


def records(n=200):
    frame = pd.DataFrame({str(i): np.arange(n) + i for i in range(41)})
    for i in (1, 2, 3):
        frame[str(i)] = 'tcp' if i == 1 else 'http'
    frame['attack'] = ['normal.' if i % 2 else 'neptune.' for i in range(n)]
    return frame


def test_duplicate_connections_never_cross_splits():
    frame = records()
    cleaned, _ = clean_records(pd.concat([frame, frame.iloc[:30]], ignore_index=True))
    a = split_records(cleaned, 80, 40, 40, 42)
    b = split_records(cleaned, 80, 40, 40, 42)
    assert len(cleaned) == 200
    for x, y in zip(a, b):
        assert x.record_id.tolist() == y.record_id.tolist()
        assert set(x.label) == {0, 1}
    assert not set(a[0].record_id) & set(a[1].record_id)
    assert not set(a[0].record_id) & set(a[2].record_id)
    assert not set(a[1].record_id) & set(a[2].record_id)


def test_ambiguous_labels_are_removed():
    frame = records()
    duplicate = frame.iloc[[0]].copy()
    duplicate['attack'] = 'normal.'
    cleaned, stats = clean_records(pd.concat([frame, duplicate], ignore_index=True))
    assert len(cleaned) == 199
    assert stats['conflicting_feature_groups_removed'] == 1


def test_preprocessor_does_not_fit_holdout_categories_or_values():
    train, validation, test = split_records(clean_records(records())[0], 80, 40, 40, 42)
    x1, v1, t1, p1 = preprocess(train, validation, test)
    test = test.copy()
    test['2'] = 'holdout-only-service'
    test['0'] = 10**10
    x2, v2, t2, p2 = preprocess(train, validation, test)
    assert np.array_equal(x1, x2)
    assert np.array_equal(v1, v2)
    assert np.array_equal(p1.named_transformers_['numeric'].named_steps['scale'].mean_,
                          p2.named_transformers_['numeric'].named_steps['scale'].mean_)
    assert 'holdout-only-service' not in p2.named_transformers_['categorical'].categories_[1]
    assert np.isfinite(t2).all()


def test_reject_invalid_schema_and_nonfinite_values(tmp_path):
    p = tmp_path / 'bad.csv'
    p.write_text('1,2,normal.\n')
    with pytest.raises(ValueError, match='42'):
        read_records(p)
    frame = records()
    frame['0'] = frame['0'].astype(float)
    frame.loc[0, '0'] = np.inf
    with pytest.raises(ValueError, match='finite'):
        clean_records(frame)
