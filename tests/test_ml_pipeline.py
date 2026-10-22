"""Uji integritas pipeline ML terhadap artefak hasil training yang benar-benar ada."""
import json
import math

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

import config as C
from data_utils import load_raw, validate_schema

R = C.RESULTS_DIR
pytestmark = pytest.mark.skipif(not (R / "metrics.json").exists(), reason="Training belum dijalankan")


def j(name):
    return json.loads((R / name).read_text(encoding="utf-8"))


def test_dataset_valid():
    df = load_raw()
    assert validate_schema(df)["problems"] == []
    assert df.shape[0] == 2111 and df[C.TARGET].nunique() == 7


def test_invalid_dataset_rejected():
    df = load_raw()
    df.loc[0, "CAEC"] = "Kadang"
    with pytest.raises(ValueError):
        validate_schema(df)
    df = load_raw(); df.loc[1, "FCVC"] = np.nan
    with pytest.raises(ValueError):
        validate_schema(df)


def test_features_exclude_target_and_leakage():
    m = j("split_manifest.json")
    assert C.TARGET not in m["features"] and "source_row_id" not in m["features"]
    assert not {"Height", "Weight"} & set(m["features"])
    assert m["features"] == C.FEATURES


def test_split_80_20_stratified_no_overlap():
    m = j("split_manifest.json")
    n = m["rows_after_dedup"]
    assert m["test_rows"] == math.ceil(n * 0.2)  # sklearn membulatkan ke atas and m["development_rows"] + m["test_rows"] == n
    assert m["train_fit_rows"] + m["validation_rows"] == m["development_rows"]
    assert m["source_row_id_overlap"] == {"fit_val": 0, "fit_test": 0, "val_test": 0}
    fit, val, test = (pd.read_csv(R / f"split_{s}.csv") for s in ("train_fit", "validation", "test"))
    ids = [set(x["source_row_id"]) for x in (fit, val, test)]
    assert not (ids[0] & ids[1]) and not (ids[0] & ids[2]) and not (ids[1] & ids[2])
    all_p = pd.concat([fit, val, test])[C.TARGET].value_counts(normalize=True)
    for part in (fit, val, test):  # stratifikasi: proporsi kelas mendekati proporsi total
        diff = (part[C.TARGET].value_counts(normalize=True) - all_p).abs().max()
        assert diff < 0.02


def test_model_selection_uses_macro_f1_on_validation():
    cfg, lb = j("experiment_config.json"), pd.read_csv(R / "leaderboard_validation.csv")
    assert cfg["eval_metric"] == "f1_macro"
    assert cfg["best_model"] == lb.sort_values("score_val", ascending=False).iloc[0]["model"]
    assert "test" not in " ".join(lb.columns).lower()
    assert cfg["reference_experiment_with_anthropometry"] is False


def test_final_metrics_match_independent_recomputation():
    m, p = j("metrics.json"), pd.read_csv(R / "test_predictions.csv")
    test = pd.read_csv(R / "split_test.csv")
    assert len(p) == m["test_rows"] == len(test) and set(p["source_row_id"]) == set(test["source_row_id"])
    kw = dict(average="macro", zero_division=0)
    assert m["accuracy"] == pytest.approx(accuracy_score(p.actual, p.predicted))
    assert m["macro_f1"] == pytest.approx(f1_score(p.actual, p.predicted, **kw))
    assert m["macro_precision"] == pytest.approx(precision_score(p.actual, p.predicted, **kw))
    assert m["macro_recall"] == pytest.approx(recall_score(p.actual, p.predicted, **kw))
    assert int(np.trace(np.array(m["confusion_matrix"]))) == int((p.actual == p.predicted).sum())


def test_artifacts_present():
    for f in ("metrics.json", "classification_report.csv", "confusion_matrix.csv", "confusion_matrix.png", "leaderboard_validation.csv",
              "experiment_config.json", "model_info.json", "environment_versions.txt", "split_manifest.json", "autogluon_fit.log"):
        assert (R / f).exists(), f


def test_saved_model_reloads_and_matches_info():
    ag = pytest.importorskip("autogluon.tabular")
    info = j("model_info.json")
    pred = ag.TabularPredictor.load(str(C.MODEL_DIR))
    assert pred.model_best == info["best_model"] and set(pred.features()) == set(info["features"])
    test = pd.read_csv(R / "split_test.csv")
    saved = pd.read_csv(R / "test_predictions.csv").set_index("source_row_id").loc[test["source_row_id"], "predicted"].to_numpy()
    assert (pred.predict(test[info["features"]]).to_numpy() == saved).all()  # model deploy = model yang dievaluasi
