# Sensor and network anomaly detection

```powershell
python -m anomaly.main
```

This compares robust Z-scores, Isolation Forest, and a PyTorch autoencoder. The default dataset contains synthetic sensor spikes.

For custom data, pass `--csv PATH`. The CSV needs `timestamp,value,label`, with labels 0 or 1, unique timestamps, and at least 100 rows. Use numeric timestamps or consistent ISO datetimes. Each train, validation, and test partition must contain both classes.

Rows are sorted by time and split 60/20/20. Features use trailing windows. The scaler and detectors fit normal training rows only, making this a semi-supervised experiment. Validation F1 selects model settings and thresholds; the test partition is held out.

Outputs in `reports/anomaly/`: `metrics.json`, `predictions.csv`, `dataset.csv`, `experiment.json`, and `anomalies.png`.

The simple threshold performs well on these obvious spikes. That result does not establish performance on network logs or subtler anomalies. Next steps are real sensor data and rolling-origin evaluation.

## Network intrusion records

The separate network experiment trains and compares the same three detector families on the KDD Cup 1999 connection benchmark. It uses 41 connection features, including protocol, service, traffic counts, and byte counts.

```powershell
python -m anomaly.network --data ../datasets/kddcup.data_10_percent.gz --download
```

The download is the public mirror used by scikit-learn. Its SHA-256 is verified before loading. Keep the archive outside the repository; the reports include its URL and checksum.

The original 494,021 rows reduce to 145,582 unique, unambiguous feature rows. Conflicting labels and duplicate feature vectors are removed before sampling. Seed 42 selects 6,000 training, 2,000 validation, and 3,000 test records. `split-records.csv` records every selected feature hash and partition so overlap can be checked.

Only the 3,620 normal training records fit the scaler, one-hot categories, and detectors. Numeric features use log1p followed by standard scaling. Categorical values unseen in training are ignored by the encoder. Validation F1 selects the robust feature quantile, Isolation Forest sample count, autoencoder bottleneck, and decision thresholds. The test labels are used only for final metrics.

| Detector | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|
| Robust Z | 0.9801 | 0.9101 | 0.9438 | 0.9785 |
| Isolation Forest | 1.0000 | 0.9067 | 0.9511 | 0.9916 |
| PyTorch autoencoder | 0.9536 | 0.9496 | 0.9516 | 0.9934 |

[Recorded results](../reports/network-anomaly/REPORT.md) include ROC curves, labeled anomaly scores, predictions, validation candidates, and runtime versions. The split is stratified and random: the data has no connection timestamp column, so sample indices are not presented as time. This experiment uses a subset of the 10% training corpus, not the official corrected test set.

KDD contains historical, simulated military-network intrusions. It provides an actual public network-connection benchmark, but is not evidence of performance on current enterprise traffic. Real modern logs and a temporal evaluation remain useful next steps.

Dataset: Stolfo, Fan, Lee, Prodromidis, and Chan (1999), [KDD Cup 1999 Data](https://doi.org/10.24432/C51C7N), UCI Machine Learning Repository, CC BY 4.0. [Original task and files](https://kdd.ics.uci.edu/databases/kddcup99/kddcup99.html).
