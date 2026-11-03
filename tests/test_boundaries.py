import pandas as pd
import pytest
from anomaly.main import load_data
from security.main import scan


def test_nonfinite_timestamp_rejected(tmp_path):
    frame = pd.DataFrame({'timestamp': range(100), 'value': [1.] * 100, 'label': [0, 1] * 50})
    frame['timestamp'] = frame.timestamp.astype(float)
    frame.loc[99, 'timestamp'] = float('inf')
    path = tmp_path / 'bad.csv'; frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_data(path)


@pytest.mark.parametrize('ports,workers,timeout', [([0], 1, 1), ([65536], 1, 1), ([80], 99, 1), ([80], 1, -1)])
def test_scanner_resource_bounds(ports, workers, timeout):
    with pytest.raises(ValueError):
        scan(['127.0.0.1'], ['127.0.0.1'], ports, workers=workers, timeout=timeout)
