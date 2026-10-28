import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinicflow_eval.environment import ClinicWorld, SchemaError  # noqa: E402

SEED = [{"appointment_id": "S1", "doctor": "Dr. John Meyer", "day": "monday",
         "time": "09:00", "patient_name": "Sara Khan", "phone": "0301-1"}]


def test_search_filters_by_specialty_and_day():
    world = ClinicWorld()
    assert [d["name"] for d in world.doctors_search("cardiology")["doctors"]] == ["Dr. Ahmed"]
    assert world.doctors_search("cardiology", "tuesday")["doctors"] == []
    assert world.doctors_search("neurology")["doctors"] == []


def test_schema_validation_enforced():
    world = ClinicWorld()
    with pytest.raises(SchemaError):
        world.appointment_book("Dr. Ahmed", "monday", "09:00", "Pat", None)
    with pytest.raises(SchemaError):
        world.doctors_search(None)


def test_tool_layer_has_no_slot_logic_by_design():
    # Mirrors the real MCP server: schema-checked only. Two bookings at
    # the same doctor/day/time both succeed at the tool layer; preventing
    # the collision is the skill's job ("verify the slot is free").
    world = ClinicWorld(SEED)
    world.appointment_book("Dr. John Meyer", "monday", "09:00", "Other Pat", "0301-2")
    assert world.slot_taken("Dr. John Meyer", "monday", "09:00")
    assert len(world.journal) == 2


def test_cancel_and_reschedule_roundtrip():
    world = ClinicWorld(SEED)
    out = world.appointment_reschedule("S1", "tuesday", "10:00")
    assert out["new_day"] == "tuesday"
    assert world.appointment_reschedule("nope", "tuesday", "10:00") == {
        "error": "appointment_not_found"}
    assert world.appointment_cancel("S1") == {"cancelled": True}
    assert world.appointment_cancel("S1") == {"cancelled": False}


def test_free_times_reflect_journal():
    world = ClinicWorld(SEED)
    assert "09:00" not in world.free_times("Dr. John Meyer", "monday")
    assert "09:30" in world.free_times("Dr. John Meyer", "monday")
