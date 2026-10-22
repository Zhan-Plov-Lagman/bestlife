"""Usage: python scripts/replay.py input.jsonl --output research/run-name"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.domain import MarketSnapshot, Settings
from app.replay import replay

parser = argparse.ArgumentParser()
parser.add_argument("input", type=Path)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--scenario", choices=["BASE", "ADVERSE", "ILLIQUID"], default="BASE")
parser.add_argument("--strategy", choices=["baseline-v1", "baseline-v1.1"], default="baseline-v1.1")
args = parser.parse_args()
if args.input.stat().st_size > 64 * 1024 * 1024:
    parser.error("Input exceeds 64 MiB")
snapshots = [MarketSnapshot.model_validate_json(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
args.output.mkdir(parents=True, exist_ok=False)
result = replay(snapshots, args.output / "replay.db", Settings(strategy_version=args.strategy), args.scenario)
(args.output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"report": str(args.output / "report.json"), "summary": result["summary"], "result_sha256": result["result_sha256"]}, indent=2))
