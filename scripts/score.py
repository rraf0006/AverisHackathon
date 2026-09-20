#!/usr/bin/env python3
"""Score a submission with the organisers' scorer (aggregate numbers only) and save
the result for the dashboard's "How it works" page.

    python3 scripts/score.py                        # submission.json  -> data/validation.json
    python3 scripts/score.py submission-agents.json # -> data/validation-agents.json

Scoring two files lets you compare pipeline modes on the same dataset.

Needs the organisers' Docker kit unzipped into _local/scoring-server/ (git-ignored).
We only ever read the aggregate scoreboard — never the answer key itself.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "_local" / "scoring-server" / "server"
GT = ROOT / "_local" / "scoring-server" / "data_v2" / "ground_truth.json"
if not SERVER.exists():
    sys.exit("Scorer not found: unzip sdoc-hackathon-docker.zip into _local/scoring-server/")
sys.path.insert(0, str(SERVER))
from scoring import score_all  # noqa: E402

arg = sys.argv[1] if len(sys.argv) > 1 else "submission.json"
sub_path = Path(arg) if Path(arg).is_absolute() else ROOT / arg
if not sub_path.exists():
    sys.exit(f"No such submission: {sub_path}. Run scripts/run_batch.py first.")
stem = sub_path.stem.replace("submission", "") or ""
out_path = ROOT / "data" / f"validation{stem}.json"

sub = json.loads(sub_path.read_text(encoding="utf-8"))
board = score_all(json.loads(GT.read_text(encoding="utf-8")), sub)
keep = {"final_score": board["final_score"],
        "stage1": {k: board["stage1"][k] for k in ("accuracy", "macro_f1")},
        "stage3": {k: board["stage3"][k] for k in ("defect_precision", "defect_recall", "defect_f1", "field_f1")},
        "end_to_end": board["end_to_end"],
        "reliability": {k: board["reliability"][k] for k in ("escalation_recall", "escalation_precision", "gold_review", "pred_review")}}
out_path.write_text(json.dumps(keep, indent=2), encoding="utf-8")
print(f"{sub_path.name}  ->  {out_path.relative_to(ROOT)}")
print(json.dumps(keep, indent=2))
