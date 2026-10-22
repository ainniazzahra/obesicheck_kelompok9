"""Pipeline eksperimen ObesiCheck (AutoGluon Tabular).

Urutan: validasi data -> dedup eksak -> split stratified 80:20 (test disimpan terpisah)
-> validasi internal dari 80% data pengembangan -> training AutoGluon (eval_metric=f1_macro)
-> evaluasi final pada test set SATU kali -> simpan artefak.

Test set tidak dipakai untuk memilih model, fitur, preprocessing, maupun hyperparameter.
"""
import argparse
import contextlib
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import metadata

import pandas as pd
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score)
from sklearn.model_selection import train_test_split

import config as C
from data_utils import load_raw, validate_schema, likely_original_mask


def pkg_versions():
    names = ["autogluon.tabular", "autogluon.core", "autogluon.features", "autogluon.common", "scikit-learn",
             "pandas", "numpy", "lightgbm", "catboost", "xgboost-cpu", "xgboost"]
    out = {"python": platform.python_version(), "platform": platform.platform()}
    for n in names:
        with contextlib.suppress(metadata.PackageNotFoundError):
            out[n] = metadata.version(n)
    return out


def class_dist(y):
    vc = y.value_counts().sort_index()
    return {k: {"count": int(v), "proportion": round(float(v) / len(y), 4)} for k, v in vc.items()}


def split_data(df, features, seed):
    """Stratified 80:20 -> (dev, test); lalu dev -> (fit, validation) juga stratified."""
    dev, test = train_test_split(df, test_size=C.TEST_SIZE, random_state=seed, stratify=df[C.TARGET])
    fit, val = train_test_split(dev, test_size=C.VALIDATION_SIZE, random_state=seed, stratify=dev[C.TARGET])
    return fit.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True), dev


def save_confusion_png(cm, labels, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 6.5))
    im = ax.imshow(cm, cmap="Reds")
    ax.set_xticks(range(len(labels)), labels, rotation=40, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Prediksi"); ax.set_ylabel("Aktual"); ax.set_title(title)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, int(cm[i, j]), ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.colorbar(im, ax=ax, fraction=0.046); fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--time-limit", type=int, default=C.DEFAULT_TIME_LIMIT, help="Batas waktu fit AutoGluon (detik)")
    ap.add_argument("--preset", default=C.DEFAULT_PRESET)
    ap.add_argument("--seed", type=int, default=C.RANDOM_SEED)
    ap.add_argument("--num-cpus", default="auto")
    ap.add_argument("--with-anthropometry", action="store_true",
                    help="EKSPERIMEN PEMBANDING: sertakan Height & Weight (bocor label). Hasil ke folder terpisah, TIDAK untuk deployment.")
    args = ap.parse_args()

    reference = args.with_anthropometry
    features = C.FEATURES_WITH_ANTHROPOMETRY if reference else C.FEATURES
    model_dir = C.REFERENCE_MODEL_DIR if reference else C.MODEL_DIR
    out = C.REFERENCE_RESULTS_DIR if reference else C.RESULTS_DIR
    out.mkdir(parents=True, exist_ok=True)

    # ---- Tahap A: validasi & penyiapan data
    raw = load_raw()
    validation = validate_schema(raw)
    n_raw = len(raw)
    dup_mask = raw[C.ALL_COLUMNS].duplicated()
    n_dup = int(dup_mask.sum())
    df = raw[~dup_mask].reset_index(drop=True)  # dedup eksak SEBELUM split agar tidak ada baris identik lintas subset
    if len(df) < 100:
        raise ValueError("Jumlah data terlalu sedikit setelah dedup.")
    if df[C.TARGET].value_counts().min() < 10:
        raise ValueError("Ada kelas dengan <10 sampel; stratifikasi 80:20 tidak layak. Periksa dataset.")

    # ---- Tahap B: split
    fit, val, test, dev = split_data(df, features, args.seed)
    for name, part in (("train_fit", fit), ("validation", val), ("test", test)):
        part.to_csv(out / f"split_{name}.csv", index=False)
    ids = {n: set(p["source_row_id"]) for n, p in (("fit", fit), ("val", val), ("test", test))}
    overlap = {"fit_val": len(ids["fit"] & ids["val"]), "fit_test": len(ids["fit"] & ids["test"]), "val_test": len(ids["val"] & ids["test"])}
    if any(overlap.values()):
        raise RuntimeError(f"Overlap sampel antar subset terdeteksi: {overlap}")
    key = lambda d: d[features].round(6).astype(str).agg("|".join, axis=1)
    feat_overlap = int(key(test).isin(set(key(dev))).sum())  # baris test dengan fitur identik di data pengembangan
    manifest = {
        "random_seed": args.seed, "split": "stratified 80:20 (dev:test); dev dipecah stratified 80:20 (fit:validation)",
        "rows_original": n_raw, "exact_duplicate_rows_removed": n_dup, "rows_after_dedup": len(df),
        "development_rows": len(dev), "train_fit_rows": len(fit), "validation_rows": len(val), "test_rows": len(test),
        "class_distribution": {"all": class_dist(df[C.TARGET]), "train_fit": class_dist(fit[C.TARGET]),
                               "validation": class_dist(val[C.TARGET]), "test": class_dist(test[C.TARGET])},
        "source_row_id_overlap": overlap, "test_rows_with_identical_features_in_development": feat_overlap,
        "target": C.TARGET, "features": features, "excluded_columns": [] if reference else C.LEAKAGE_COLUMNS,
        "missing_values_by_column": validation["missing_values"],
    }
    (out / "split_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Data: {n_raw} -> {len(df)} baris (dedup {n_dup}); fit={len(fit)} val={len(val)} test={len(test)}")

    # ---- Tahap C: training AutoGluon (hanya fit + validation)
    try:
        from autogluon.tabular import TabularPredictor
    except ImportError as e:
        raise SystemExit("AutoGluon belum terpasang. Jalankan: pip install -r ml/requirements.txt") from e
    if model_dir.exists():
        shutil.rmtree(model_dir)
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    cols = features + [C.TARGET]
    t0 = time.time()
    predictor = TabularPredictor(label=C.TARGET, problem_type="multiclass", eval_metric=C.EVAL_METRIC, path=str(model_dir),
                                 log_to_file=True, log_file_path=str(out / "autogluon_fit.log"), verbosity=2)
    fit_kwargs = dict(train_data=fit[cols], tuning_data=val[cols], time_limit=args.time_limit, presets=args.preset)
    if args.num_cpus != "auto":
        fit_kwargs["num_cpus"] = int(args.num_cpus)
    predictor.fit(**fit_kwargs)
    train_seconds = round(time.time() - t0, 1)

    lb = predictor.leaderboard(silent=True)  # TANPA data test: skor = f1_macro pada validation
    lb.to_csv(out / "leaderboard_validation.csv", index=False)
    best = predictor.model_best
    best_val = float(lb.loc[lb["model"] == best, "score_val"].iloc[0])
    top_val = float(lb["score_val"].max())
    print(f"Model terpilih: {best} (macro-F1 validasi={best_val:.4f}; maksimum leaderboard={top_val:.4f})")

    # ---- Tahap D: evaluasi final pada test set (SATU kali)
    y_true = test[C.TARGET]
    y_pred = predictor.predict(test[features])
    labels = sorted(df[C.TARGET].unique().tolist())
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    zd = dict(average="macro", labels=labels, zero_division=0)  # kelas tanpa prediksi -> precision=0 (konvensi sklearn, dilaporkan)
    metrics = {
        "split": "test (20%, tidak dipakai untuk seleksi)", "test_rows": int(len(test)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_precision": float(precision_score(y_true, y_pred, **zd)),
        "macro_recall": float(recall_score(y_true, y_pred, **zd)),
        "macro_f1": float(f1_score(y_true, y_pred, **zd)),
        "labels": labels, "confusion_matrix": cm.tolist(),
        "classes_without_predictions": [l for l, c in zip(labels, cm.sum(axis=0), strict=True) if c == 0],
        "test_class_distribution": class_dist(y_true),
        "classification_report": classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0),
        "best_model": best, "validation_macro_f1_of_best_model": best_val,
        "deployable": not reference,
    }
    # Analisis sensitivitas (dari prediksi yang SAMA, tanpa evaluasi tambahan): baris yang kemungkinan asli.
    orig = likely_original_mask(test)  # test masih memuat seluruh kolom sumber; hanya dipakai untuk pelaporan
    if orig.sum() >= 20:
        metrics["sensitivity_likely_original_rows"] = {
            "n": int(orig.sum()), "accuracy": float(accuracy_score(y_true[orig], y_pred[orig])),
            "macro_f1": float(f1_score(y_true[orig], y_pred[orig], average="macro", zero_division=0)),
            "note": "Heuristik baris non-sintetis; sebaran kelas sangat timpang (didominasi Normal_Weight). Hanya indikatif.",
        }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    pd.DataFrame(metrics["classification_report"]).T.to_csv(out / "classification_report.csv")
    pd.DataFrame(cm, index=[f"aktual_{l}" for l in labels], columns=[f"prediksi_{l}" for l in labels]).to_csv(out / "confusion_matrix.csv")
    save_confusion_png(cm, labels, out / "confusion_matrix.png", "Confusion matrix (test set)" + (" - REFERENSI, bocor label" if reference else ""))
    pd.DataFrame({"source_row_id": test["source_row_id"], "actual": y_true, "predicted": y_pred}).to_csv(out / "test_predictions.csv", index=False)

    # ---- Artefak & metadata
    version = f"ag{metadata.version('autogluon.tabular')}-{datetime.now(timezone.utc):%Y%m%d}-seed{args.seed}"
    (out / "environment_versions.txt").write_text("\n".join(f"{k}=={v}" for k, v in pkg_versions().items()) + "\n", encoding="utf-8")
    try:  # pip freeze lengkap hanya jika pip tersedia di lingkungan (mis. tidak ada pada venv buatan uv)
        freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, timeout=120, check=True).stdout
        (out / "pip_freeze.txt").write_text(freeze, encoding="utf-8")
    except (subprocess.SubprocessError, OSError):
        print("pip freeze tidak tersedia; hanya environment_versions.txt (paket utama) yang disimpan.")
    config = {"model_version": version, "reference_experiment_with_anthropometry": reference, "target": C.TARGET, "features": features,
              "classes": list(predictor.class_labels), "random_seed": args.seed, "autogluon_preset": args.preset,
              "autogluon_time_limit_seconds": args.time_limit, "training_seconds": train_seconds, "eval_metric": C.EVAL_METRIC,
              "validation_strategy": "tuning_data = 20% stratified dari 80% data pengembangan (tidak menyentuh test)",
              "model_selection": "AutoGluon memilih model dengan score_val (f1_macro) tertinggi pada validation",
              "best_model": best, "validation_macro_f1_of_best_model": best_val,
              "candidate_models_trained": lb["model"].tolist(), "final_refit_on_full_development": False,
              "libraries": pkg_versions(), "created_at_utc": datetime.now(timezone.utc).isoformat()}
    (out / "experiment_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    if not reference:  # info yang dibaca backend
        info = {"model_version": version, "best_model": best, "features": features, "classes": config["classes"],
                "target": C.TARGET, "metrics": {k: metrics[k] for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1")},
                "test_rows": metrics["test_rows"]}
        (out / "model_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    predictor.save_space()  # buang artefak yang tidak diperlukan untuk inferensi (model terpilih tetap sama)

    print(json.dumps({k: metrics[k] for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "best_model")}, indent=2))
    print("Artefak disimpan di", out)


if __name__ == "__main__":
    main()
