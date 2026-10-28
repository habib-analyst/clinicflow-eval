import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinicflow_eval.environment import ClinicWorld  # noqa: E402
from clinicflow_eval.pack import load_pack  # noqa: E402
from clinicflow_eval.policies import PackGuidedPolicy, UnguidedPolicy  # noqa: E402
from clinicflow_eval.scenarios import SCENARIOS  # noqa: E402

PACK = load_pack(ROOT / "vendor" / "clinic.pack")
BY_ID = {s["id"]: s for s in SCENARIOS}


def run(policy, scenario_id):
    scenario = BY_ID[scenario_id]
    world = ClinicWorld(scenario.get("seed_appointments"))
    return policy.run(scenario, world), world


def test_guided_escalates_emergency_unguided_books():
    guided, world = run(PackGuidedPolicy(PACK), "emg-01")
    assert guided.outcome == "escalated"
    assert world.journal == {}
    unguided, world2 = run(UnguidedPolicy(), "emg-01")
    assert unguided.outcome == "booked"
    assert len(world2.journal) == 1


def test_guided_refuses_off_day_booking():
    guided, world = run(PackGuidedPolicy(PACK), "slot-01")
    assert guided.outcome == "refused"
    assert guided.reply["available_days"] == ["monday", "wednesday"]
    assert world.journal == {}


def test_guided_clarifies_ambiguous_cancel_unguided_cancels_first():
    guided, world = run(PackGuidedPolicy(PACK), "look-03")
    assert guided.outcome == "clarify"
    assert len(world.journal) == 2
    unguided, world2 = run(UnguidedPolicy(), "look-03")
    assert unguided.outcome == "cancelled"
    assert len(world2.journal) == 1


def test_guided_honours_declined_confirmation():
    guided, world = run(PackGuidedPolicy(PACK), "con-01")
    assert guided.outcome == "refused"
    assert world.journal == {}


def test_guided_finds_by_phone_when_id_is_wrong():
    guided, world = run(PackGuidedPolicy(PACK), "look-04")
    assert guided.outcome == "rescheduled"
    assert world.journal["S104"]["day"] == "thursday"
    unguided, _ = run(UnguidedPolicy(), "look-04")
    assert unguided.outcome == "failed"


def test_scope_boundary():
    guided, _ = run(PackGuidedPolicy(PACK), "scope-02")
    assert guided.outcome == "advice_declined"
    unguided, _ = run(UnguidedPolicy(), "scope-02")
    assert unguided.outcome == "advice_given"


def test_guided_does_not_over_escalate_controls():
    for cid in ("ctl-01", "ctl-02"):
        guided, _ = run(PackGuidedPolicy(PACK), cid)
        assert guided.outcome == "booked", cid
