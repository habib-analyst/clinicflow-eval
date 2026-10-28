"""Simulated clinic world: roster + appointment journal + tools.

The tools deliberately mirror the semantics of clinic-plugin-pack's real
MCP server (``plugin/mcp/clinic_mcp_server.py``): every call is validated
against the typed input schema, and that is all. The server performs no
availability, slot-conflict, identity, or escalation checks — in the real
plugin those guardrails live entirely in the skills and the escalation
policy. This harness exists to measure what that placement costs and buys.
"""

from __future__ import annotations

import copy


class SchemaError(ValueError):
    """Raised when a tool call violates the pack's typed input schema."""


ROSTER = [
    {"name": "Dr. Ahmed", "specialty": "cardiology", "days": ["monday", "wednesday"]},
    {"name": "Dr. Sara Iqbal", "specialty": "dermatology", "days": ["tuesday", "thursday"]},
    {"name": "Dr. John Meyer", "specialty": "general medicine",
     "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]},
    {"name": "Dr. Priya Nair", "specialty": "pediatrics", "days": ["monday", "tuesday"]},
    {"name": "Dr. Omar Farouk", "specialty": "orthopedics", "days": ["wednesday", "friday"]},
]

# Consultation grid used for slot verification and alternative offers.
TIME_GRID = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]


def _require(args: dict, spec: dict) -> None:
    for field_name, kind in spec.items():
        value = args.get(field_name)
        if value is None:
            raise SchemaError(f"missing required field: {field_name}")
        if kind == "string" and not isinstance(value, str):
            raise SchemaError(f"field {field_name} must be a string")


class ClinicWorld:
    """One scenario's world. Deterministic; no randomness anywhere."""

    def __init__(self, seed_appointments=None):
        self.roster = copy.deepcopy(ROSTER)
        self.journal = {}  # appointment_id -> appointment dict
        self._counter = 0
        for appt in seed_appointments or []:
            self._counter += 1
            record = dict(appt)
            record.setdefault("appointment_id", f"A{self._counter:03d}")
            record.setdefault("status", "confirmed")
            self.journal[record["appointment_id"]] = record

    # ---- observation helpers (what an agent can find out) ----

    def doctor(self, name):
        for doc in self.roster:
            if doc["name"] == name:
                return doc
        return None

    def slot_taken(self, doctor, day, time):
        return any(
            a["doctor"] == doctor and a["day"] == day and a["time"] == time
            for a in self.journal.values()
        )

    def free_times(self, doctor, day):
        return [t for t in TIME_GRID if not self.slot_taken(doctor, day, t)]

    def find_appointments(self, appointment_id=None, phone=None):
        out = []
        for appt in self.journal.values():
            if appointment_id is not None and appt["appointment_id"] == appointment_id:
                out.append(appt)
            elif phone is not None and appt["phone"] == phone:
                out.append(appt)
        return out

    def snapshot(self):
        return copy.deepcopy(self.journal)

    # ---- tools (schema-checked only, exactly like the real server) ----

    def doctors_search(self, specialty, day=None):
        _require({"specialty": specialty}, {"specialty": "string"})
        found = [d for d in self.roster if d["specialty"] == specialty]
        if day is not None:
            found = [d for d in found if day in d["days"]]
        return {"doctors": copy.deepcopy(found)}

    def appointment_book(self, doctor, day, time, patient_name, phone):
        _require(
            {"doctor": doctor, "day": day, "time": time,
             "patient_name": patient_name, "phone": phone},
            {"doctor": "string", "day": "string", "time": "string",
             "patient_name": "string", "phone": "string"},
        )
        self._counter += 1
        appt = {
            "appointment_id": f"A{self._counter:03d}",
            "doctor": doctor, "day": day, "time": time,
            "patient_name": patient_name, "phone": phone, "status": "confirmed",
        }
        self.journal[appt["appointment_id"]] = appt
        return dict(appt)

    def appointment_reschedule(self, appointment_id, new_day, new_time):
        _require({"new_day": new_day, "new_time": new_time},
                 {"new_day": "string", "new_time": "string"})
        appt = self.journal.get(appointment_id)
        if appt is None:
            return {"error": "appointment_not_found"}
        appt["day"], appt["time"] = new_day, new_time
        return {"appointment_id": appointment_id, "new_day": new_day, "new_time": new_time}

    def appointment_cancel(self, appointment_id):
        if appointment_id in self.journal:
            del self.journal[appointment_id]
            return {"cancelled": True}
        return {"cancelled": False}
