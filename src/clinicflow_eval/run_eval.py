"""Run the full clinicflow-eval suite and write results/results.json.

Usage:  python -m clinicflow_eval.run_eval [--pack PATH] [--out PATH]

Deterministic: no randomness, no network, no LLM. Rerunning produces a
byte-identical results file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .environment import ClinicWorld
from .pack import load_pack
from .policies import PackGuidedPolicy, UnguidedPolicy
from .scenarios import SCENARIOS
from .scoring import aggregate, bar_verdicts, score_run

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACK = ROOT / "vendor" / "clinic.pack"
DEFAULT_OUT = ROOT / "results" / "results.json"


def run(pack_path=DEFAULT_PACK):
    pack = load_pack(pack_path)
    arms = [PackGuidedPolicy(pack), UnguidedPolicy()]
    rows = {arm.name: [] for arm in arms}
    for scenario in SCENARIOS:
        for arm in arms:
            rows[arm.name].append(score_run(scenario, ClinicWorld, arm))
    metrics = {name: aggregate(r) for name, r in rows.items()}
    verdicts = bar_verdicts(metrics["pack-guided"], metrics["unguided"])
    return {
        "pack": {"name": pack.name, "version": pack.version,
                 "source": "clinic-plugin-pack plugin/src/clinic.pack"},
        "n_scenarios": len(SCENARIOS),
        "arms": metrics,
        "bar_verdicts": verdicts,
        "all_bars_pass": all(verdicts.values()),
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default=str(DEFAULT_PACK))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    results = run(args.pack)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    for arm, m in results["arms"].items():
        print(f"[{arm}] task_success={m['task_success']:.3f} "
              f"escalation_recall={m['escalation_recall']:.3f} "
              f"unsafe={m['unsafe_actions']} "
              f"controls={m['control_task_success']:.3f} "
              f"completeness={m['mean_completeness']:.3f} "
              f"confirm_compliance={m['confirmation_compliance']}")
    print("bars:", results["bar_verdicts"])
    print("ALL BARS PASS" if results["all_bars_pass"] else "SOME BARS FAILED")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
