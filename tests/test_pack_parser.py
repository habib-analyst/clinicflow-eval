import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinicflow_eval.pack import load_pack  # noqa: E402

PACK_PATH = ROOT / "vendor" / "clinic.pack"


def test_pack_header_and_tools():
    pack = load_pack(PACK_PATH)
    assert pack.name == "clinic"
    assert pack.version == "0.1.0"
    assert pack.tools == ["doctors_search", "appointment_book",
                          "appointment_reschedule", "appointment_cancel"]


def test_skills_and_steps_parsed():
    pack = load_pack(PACK_PATH)
    assert set(pack.skills) == {"find-doctor", "book-appointment",
                                "reschedule-appointment", "cancel-appointment"}
    book = pack.skills["book-appointment"]
    assert book.tool == "appointment_book"
    assert book.steps[0] == "Verify the doctor has a free slot at the requested time."
    assert len(book.steps) == 3
    cancel = pack.skills["cancel-appointment"]
    assert cancel.steps[0] == "Look up the appointment by ID or phone number."


def test_escalation_policy_parsed():
    pack = load_pack(PACK_PATH)
    assert pack.escalation.context_schema == "ClinicContext"
    assert pack.escalation.defaults == {
        "message.send": "auto",
        "appointment.book": "confirm",
        "appointment.cancel": "confirm",
    }
    rules = {r["name"]: r for r in pack.escalation.rules}
    assert rules["emergency"]["tier"] == "human_only"
    assert rules["emergency"]["when"] == "is_emergency == true"
    assert pack.escalation.fallback_tier == "confirm"


def test_tier_resolution():
    pack = load_pack(PACK_PATH)
    assert pack.tier_for("appointment.book", is_emergency=True) == "human_only"
    assert pack.tier_for("appointment.cancel", is_emergency=True) == "human_only"
    assert pack.tier_for("appointment.book", is_emergency=False) == "confirm"
    # reschedule has no default: the fallback rule tier applies
    assert pack.tier_for("appointment.reschedule", is_emergency=False) == "confirm"
    assert pack.tier_for("appointment.reschedule", is_emergency=True) == "human_only"
    assert pack.tier_for("message.send", is_emergency=False) == "auto"


def test_flow_parsed():
    pack = load_pack(PACK_PATH)
    assert pack.flow["start"] == "find-doctor"
    assert pack.flow["transitions"] == {"found": "book-appointment",
                                        "none": "find-doctor"}
