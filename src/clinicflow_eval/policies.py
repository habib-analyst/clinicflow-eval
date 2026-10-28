"""The two arms.

Both policies are deterministic scripted agents with the same routine
competence. They differ only in whether the pack is applied:

* ``PackGuidedPolicy`` executes the pack as parsed from ``clinic.pack``:
  escalation tiers are resolved through ``Pack.tier_for`` (emergency rule
  -> human_only; book/cancel -> confirm; everything else -> fallback
  confirm), and each skill's declared steps are followed in order
  (verify the slot before booking; look up by ID *or phone* and verify
  identity before cancelling/rescheduling; reply with the fields the
  steps name). The pack's documented scope boundary (front-desk
  logistics only, no medical advice) is enforced.

* ``UnguidedPolicy`` is a competent generic front-desk agent without the
  pack: it searches the roster and performs exactly the mutation asked
  for, immediately. It has no context tier (it never looks at
  ``is_emergency``), no slot-verification step, no lookup fallback or
  identity check, no confirmation step, and no scope boundary — the
  standard failure surface of a tool-using agent with thin tools.
"""

from __future__ import annotations

ARRIVAL = "Please arrive 10 minutes early and bring your insurance card."

# What a generic helpful assistant reaches for when the requested
# specialty is not on the roster.
SUBSTITUTIONS = {"neurology": "general medicine"}


class Trace:
    def __init__(self):
        self.events = []       # ordered event dicts
        self.outcome = None
        self.reply = {}        # structured reply fields (the reply contract)
        self.mutations = []    # names of tools that changed the journal

    def event(self, kind, **data):
        self.events.append({"type": kind, **data})

    def tool(self, name, **data):
        self.event("tool_call", tool=name, **data)


class PackGuidedPolicy:
    name = "pack-guided"

    def __init__(self, pack):
        self.pack = pack

    # -- helpers ------------------------------------------------------

    def _tier(self, action, scenario):
        return self.pack.tier_for(action, scenario["is_emergency"])

    def _escalate(self, trace, scenario, action):
        args = scenario["request"].get("args", {})
        trace.event("escalation", tier="human_only", action=action)
        trace.outcome = "escalated"
        trace.reply = {
            "patient_name": args.get("patient_name") or args.get("phone"),
            "reason": "emergency",
            "requested_action": action,
        }
        return trace

    def _confirm(self, trace, scenario, action):
        """Confirm-tier gate. Returns True iff the user confirms."""
        trace.event("confirm_request", action=action)
        return scenario.get("user_confirms") is True

    def _lookup(self, trace, world, args):
        """Skill step 1 for cancel/reschedule: look up by ID or phone,
        verifying identity. Returns (appointment, failure_outcome)."""
        appt_id, phone = args.get("appointment_id"), args.get("phone")
        if appt_id:
            found = world.journal.get(appt_id)
            if found is not None:
                if phone is not None and found["phone"] != phone:
                    return None, "refused"  # identity mismatch
                return found, None
            # ID missed: the step says "by ID or phone" — fall back to phone.
        if phone:
            matches = world.find_appointments(phone=phone)
            if len(matches) == 1:
                return matches[0], None
            if len(matches) > 1:
                return None, "clarify"
        return None, "not_found"

    # -- skills -------------------------------------------------------

    def _book(self, trace, world, scenario, args, outcome="booked"):
        if self._tier("appointment.book", scenario) == "human_only":
            return self._escalate(trace, scenario, "appointment.book")
        doc = world.doctor(args["doctor"])
        if doc is None or args["day"] not in doc["days"]:
            trace.outcome = "refused"
            trace.reply = {"doctor": args["doctor"],
                           "available_days": doc["days"] if doc else []}
            return trace
        day, time = args["day"], args["time"]
        if world.slot_taken(args["doctor"], day, time):
            if scenario.get("user_accepts_alternative"):
                free = world.free_times(args["doctor"], day)
                if not free:
                    trace.outcome = "refused"
                    return trace
                time = free[0]
                outcome = "booked_alternative"
            else:
                trace.outcome = "refused"
                trace.reply = {"doctor": args["doctor"], "day": day,
                               "free_times": world.free_times(args["doctor"], day)}
                return trace
        if not self._confirm(trace, scenario, "appointment.book"):
            trace.outcome = "refused"
            return trace
        result = world.appointment_book(args["doctor"], day, time,
                                        args["patient_name"], args["phone"])
        trace.tool("appointment_book", appointment_id=result["appointment_id"])
        trace.mutations.append("appointment_book")
        trace.outcome = outcome
        trace.reply = {"appointment_id": result["appointment_id"],
                       "doctor": result["doctor"], "day": day, "time": time,
                       "status": result["status"], "arrival_instructions": ARRIVAL}
        return trace

    def _cancel(self, trace, world, scenario, args):
        if self._tier("appointment.cancel", scenario) == "human_only":
            return self._escalate(trace, scenario, "appointment.cancel")
        appt, failure = self._lookup(trace, world, args)
        if failure == "clarify":
            trace.event("clarify", reason="multiple_appointments_for_phone")
            trace.outcome = "clarify"
            return trace
        if failure is not None:
            trace.outcome = failure  # refused (identity) or not_found
            return trace
        if not self._confirm(trace, scenario, "appointment.cancel"):
            trace.outcome = "refused"
            return trace
        world.appointment_cancel(appt["appointment_id"])
        trace.tool("appointment_cancel", appointment_id=appt["appointment_id"])
        trace.mutations.append("appointment_cancel")
        trace.outcome = "cancelled"
        trace.reply = {"appointment_id": appt["appointment_id"], "cancelled": True,
                       "doctor": appt["doctor"], "day": appt["day"]}
        return trace

    def _reschedule(self, trace, world, scenario, args):
        if self._tier("appointment.reschedule", scenario) == "human_only":
            return self._escalate(trace, scenario, "appointment.reschedule")
        appt, failure = self._lookup(trace, world, args)
        if failure == "clarify":
            trace.event("clarify", reason="multiple_appointments_for_phone")
            trace.outcome = "clarify"
            return trace
        if failure is not None:
            trace.outcome = failure
            return trace
        doc = world.doctor(appt["doctor"])
        new_day, new_time = args["new_day"], args["new_time"]
        taken = world.slot_taken(appt["doctor"], new_day, new_time) and not (
            appt["day"] == new_day and appt["time"] == new_time)
        if doc is None or new_day not in doc["days"] or taken:
            trace.outcome = "refused"
            return trace
        if not self._confirm(trace, scenario, "appointment.reschedule"):
            trace.outcome = "refused"
            return trace
        world.appointment_reschedule(appt["appointment_id"], new_day, new_time)
        trace.tool("appointment_reschedule",
                   appointment_id=appt["appointment_id"])
        trace.mutations.append("appointment_reschedule")
        trace.outcome = "rescheduled"
        trace.reply = {"appointment_id": appt["appointment_id"],
                       "new_day": new_day, "new_time": new_time}
        return trace

    def _find(self, trace, world, scenario, args):
        result = world.doctors_search(args["specialty"], args.get("day"))
        trace.tool("doctors_search", specialty=args["specialty"])
        doctors = result["doctors"]
        if doctors:
            trace.outcome = "found"
            trace.reply = {"names": [d["name"] for d in doctors],
                           "days": {d["name"]: d["days"] for d in doctors}}
            return trace
        if args.get("day"):
            retry = world.doctors_search(args["specialty"])
            if retry["doctors"]:
                doctors = retry["doctors"]
                trace.outcome = "none_that_day"
                trace.reply = {"names": [d["name"] for d in doctors],
                               "days": {d["name"]: d["days"] for d in doctors},
                               "day_match": False}
                return trace
        # flow care: on none -> find-doctor (loop back and re-ask)
        trace.outcome = "none_reported"
        trace.reply = {"names": [], "reask": True}
        return trace

    # -- entry point ----------------------------------------------------

    def run(self, scenario, world):
        trace = Trace()
        req = scenario["request"]
        skill, args = req["skill"], req.get("args", {})
        if skill == "advice":
            # Pack scope: front-desk logistics only; no medical advice.
            trace.outcome = "advice_declined"
            trace.reply = {"offered": "front_desk_help"}
            return trace
        if skill == "book-appointment":
            return self._book(trace, world, scenario, args)
        if skill == "cancel-appointment":
            return self._cancel(trace, world, scenario, args)
        if skill == "reschedule-appointment":
            return self._reschedule(trace, world, scenario, args)
        if skill == "find-doctor":
            return self._find(trace, world, scenario, args)
        if skill == "find-then-book":
            self._find(trace, world, scenario, args)
            if trace.outcome != "found":
                return trace
            book_args = {"doctor": trace.reply["names"][0], "day": args["day"]}
            book_args.update(req["book_args"])
            trace.outcome = None
            return self._book(trace, world, scenario, book_args)
        raise ValueError(f"unknown skill: {skill}")


class UnguidedPolicy:
    name = "unguided"

    def _book(self, trace, world, scenario, args, outcome="booked"):
        result = world.appointment_book(args["doctor"], args["day"], args["time"],
                                        args["patient_name"], args["phone"])
        trace.tool("appointment_book", appointment_id=result["appointment_id"])
        trace.mutations.append("appointment_book")
        trace.outcome = outcome
        trace.reply = {"appointment_id": result["appointment_id"]}
        return trace

    def _cancel(self, trace, world, scenario, args):
        appt_id = args.get("appointment_id")
        if not appt_id:
            matches = world.find_appointments(phone=args.get("phone"))
            if not matches:
                trace.outcome = "not_found"
                return trace
            appt_id = matches[0]["appointment_id"]  # first match wins
        result = world.appointment_cancel(appt_id)
        trace.tool("appointment_cancel", appointment_id=appt_id)
        if result["cancelled"]:
            trace.mutations.append("appointment_cancel")
            trace.outcome = "cancelled"
            trace.reply = {"appointment_id": appt_id, "cancelled": True}
        else:
            trace.outcome = "not_found"
        return trace

    def _reschedule(self, trace, world, scenario, args):
        result = world.appointment_reschedule(args.get("appointment_id"),
                                              args["new_day"], args["new_time"])
        trace.tool("appointment_reschedule",
                   appointment_id=args.get("appointment_id"))
        if "error" in result:
            trace.outcome = "failed"
        else:
            trace.mutations.append("appointment_reschedule")
            trace.outcome = "rescheduled"
            trace.reply = {"appointment_id": args["appointment_id"],
                           "new_day": args["new_day"], "new_time": args["new_time"]}
        return trace

    def _find(self, trace, world, scenario, args):
        result = world.doctors_search(args["specialty"])  # day not applied
        trace.tool("doctors_search", specialty=args["specialty"])
        doctors = result["doctors"]
        if not doctors and args["specialty"] in SUBSTITUTIONS:
            sub = SUBSTITUTIONS[args["specialty"]]
            doctors = world.doctors_search(sub)["doctors"]
            trace.outcome = "substituted"
            trace.reply = {"names": [d["name"] for d in doctors]}
            return trace
        if doctors:
            trace.outcome = "found"
            trace.reply = {"names": [d["name"] for d in doctors]}
        else:
            trace.outcome = "none_reported"
            trace.reply = {"names": []}
        return trace

    def run(self, scenario, world):
        trace = Trace()
        req = scenario["request"]
        skill, args = req["skill"], req.get("args", {})
        if skill == "advice":
            trace.event("advice", topic=args.get("topic"))
            trace.outcome = "advice_given"
            trace.reply = {"advice": f"generic advice about {args.get('topic')}"}
            return trace
        if skill == "book-appointment":
            return self._book(trace, world, scenario, args)
        if skill == "cancel-appointment":
            return self._cancel(trace, world, scenario, args)
        if skill == "reschedule-appointment":
            return self._reschedule(trace, world, scenario, args)
        if skill == "find-doctor":
            return self._find(trace, world, scenario, args)
        if skill == "find-then-book":
            self._find(trace, world, scenario, args)
            if trace.outcome != "found":
                return trace
            book_args = {"doctor": trace.reply["names"][0], "day": args["day"]}
            book_args.update(req["book_args"])
            trace.outcome = None
            return self._book(trace, world, scenario, book_args)
        raise ValueError(f"unknown skill: {skill}")
