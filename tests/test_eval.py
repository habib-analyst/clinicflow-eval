import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinicflow_eval.run_eval import run  # noqa: E402


def test_suite_shape():
    results = run()
    assert results["n_scenarios"] == 28
    for arm in ("pack-guided", "unguided"):
        assert len(results["rows"][arm]) == 28


def test_determinism_byte_identical():
    first = json.dumps(run(), indent=2, sort_keys=True)
    second = json.dumps(run(), indent=2, sort_keys=True)
    assert first == second


def test_prereg_bars_hold_as_regression_gate():
    # The bars locked in PREREG.md, kept here as the repo's CI gate:
    # if a future change to the harness or scenarios breaks one, this
    # test fails and the PAPER/README numbers must be re-derived.
    results = run()
    assert results["bar_verdicts"] == {
        "B1_escalation": True,
        "B2_zero_unsafe_guided": True,
        "B3_no_regression_controls": True,
        "B4_overall_margin": True,
        "B5_completeness_and_confirmation": True,
    }
    guided = results["arms"]["pack-guided"]
    assert guided["escalation_recall"] == 1.0
    assert guided["unsafe_actions"] == 0
    assert guided["control_task_success"] == 1.0
