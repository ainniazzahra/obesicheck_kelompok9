"""Audit dataset: profil, kualitas data, dan uji kebocoran label. Tidak mengubah data."""
import json
from config import RESULTS_DIR, TARGET, ALL_COLUMNS, DATA_PATH, ROOT, FEATURES
from data_utils import load_raw, validate_schema, likely_original_mask, bmi_rule_label


def run_audit() -> dict:
    df = load_raw()
    validation = validate_schema(df)
    d = df[ALL_COLUMNS]
    bmi = d["Weight"] / d["Height"] ** 2
    merged = d[TARGET].str.replace(r"Overweight_Level_.*", "Overweight", regex=True)
    agreement = float((bmi_rule_label(bmi) == merged).mean())
    mask = likely_original_mask(d)
    report = {
        "file": str(DATA_PATH.relative_to(ROOT)),
        "rows": int(len(d)), "columns": int(d.shape[1]),
        "dtypes": {c: str(t) for c, t in d.dtypes.items()},
        "missing_values": validation["missing_values"],
        "exact_duplicate_rows": int(d.duplicated().sum()),
        "target": TARGET,
        "target_counts": d[TARGET].value_counts().to_dict(),
        "categorical_levels": {c: d[c].value_counts().to_dict() for c in d.select_dtypes(exclude="number").columns if c != TARGET},
        "numeric_summary": d.describe().round(4).to_dict(),
        "leakage_check": {
            "finding": "Label dibentuk dari BMI = Weight/Height^2. Height dan Weight dikeluarkan dari fitur model.",
            "bmi_threshold_rule_agreement_with_label": round(agreement, 4),
            "bmi_range_per_class": {k: {"min": round(v.min(), 2), "max": round(v.max(), 2)} for k, v in bmi.groupby(d[TARGET])},
            "excluded_columns": ["Height", "Weight"],
            "model_features": FEATURES,
        },
        "synthetic_data_note": {
            "likely_original_rows_heuristic": int(mask.sum()),
            "likely_synthetic_rows_heuristic": int((~mask).sum()),
            "note": "Heuristik (nilai bulat pada skala ordinal) - bukan penanda resmi dataset. UCI 544 menyatakan 77% data sintetis (SMOTE).",
        },
    }
    return report


if __name__ == "__main__":
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rep = run_audit()
    (RESULTS_DIR / "audit_report.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ["rows", "columns", "missing_values", "exact_duplicate_rows", "target_counts"]}, indent=2))
    print("BMI-rule agreement:", rep["leakage_check"]["bmi_threshold_rule_agreement_with_label"])
