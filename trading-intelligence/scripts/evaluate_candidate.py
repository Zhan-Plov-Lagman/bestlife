"""Offline, JSON-only evaluation. No weights are loaded or promoted."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.learning import ModelVersion, assert_no_leakage, evaluate_probabilities, temporal_split

parser = argparse.ArgumentParser()
parser.add_argument("dataset", type=Path, help="JSON list: time, feature_time, label, out_of_sample_probability")
parser.add_argument("--horizon", type=float, required=True)
parser.add_argument("--embargo", type=float, default=0)
parser.add_argument("--version", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.dataset.stat().st_size > 20_000_000:
    parser.error("Dataset too large for this lightweight JSON evaluator; use a batch pipeline")
raw = args.dataset.read_bytes()
rows = json.loads(raw)
splits = temporal_split([r["time"] for r in rows], args.horizon, args.embargo)
assert_no_leakage([r["feature_time"] for r in rows], [r["time"] for r in rows])
test = [rows[i] for i in splits["test"]]
metrics = evaluate_probabilities([r["label"] for r in test], [r["out_of_sample_probability"] for r in test])
model = ModelVersion(version=args.version, dataset_sha256=hashlib.sha256(raw).hexdigest(), metrics=metrics)
args.output.write_text(json.dumps({"candidate": model.model_dump(), "split_indices": splits, "limitations": "Caller must prove probabilities are out-of-sample. No trading performance inferred."}, indent=2), encoding="utf-8")
print(f"Saved candidate evaluation to {args.output}. Not activated.")
