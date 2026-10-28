# clinicflow-eval: a behavioural evaluation of a clinical Claude Code plugin pack

**Habib Ur Rehman** — 2026-10-28
Companion to: clinic-plugin-pack (github.com/habib-analyst/clinic-plugin-pack), packc (github.com/habib-analyst/packc)

## Abstract

Plugin packs for agent runtimes are typically validated structurally: does the
pack parse, do its schemas conform, do its skills load? clinic-plugin-pack — a
clinic front-desk pack for Claude Code compiled from a typed packc source —
passes all of that (conformance 17/17, structural 35/35, skill-load recall@1 =
1.000). But its safety-relevant content is behavioural: an escalation policy
(emergencies to a human only; bookings and cancellations behind confirmation)
and per-skill guardrail steps (verify the slot before booking; look up by ID or
phone and verify before cancelling). Its MCP tools enforce none of this — the
real server validates schemas only. We built clinicflow-eval, a deterministic
scripted harness that executes the pack's own source file as a policy and
compares it, on 28 clinical front-desk scenarios, against a competent generic
agent policy without the pack. The pack-guided arm succeeded on 28/28 scenarios
with 0 unsafe actions; the unguided arm succeeded on 9/28 with 16 unsafe
actions, including mutations during all 6 simulated emergencies, while matching
the guided arm 8/8 on happy-path controls.

## 1. Motivation

Agent plugin ecosystems are accumulating quality signals of the wrong kind.
Marketplaces and pack authors report conformance, structure, and load tests —
necessary, but silent on the question a clinic actually cares about: when a
patient writes "my lips are swelling and I can barely breathe, book the
dermatologist Tuesday", what does the agent *do*? In clinic-plugin-pack the
answer is determined entirely by whether the agent follows the pack, because
the tool layer is intentionally thin (schema validation only, mirroring the
shipped MCP server). Behavioural evaluation — scoring actions and world state
across adversarial and routine scenarios, pack vs. no pack — is the missing
instrument. Generic plugin-eval guidance exists (trigger tests, tool-use
checks, live-model comparisons), and clinical agent benchmarks exist
(AgentClinic, MedAgentBench, PatientAgentBench), but none evaluates a plugin
pack's encoded policy, deterministically, on safety endpoints (see
KILLGATE.md).

## 2. Method

**Policy under test.** The guided arm parses `vendor/clinic.pack` (vendored
verbatim from clinic-plugin-pack's `plugin/src/clinic.pack`) at runtime:
escalation tiers are resolved by the pack's own rules — `is_emergency` →
`human_only`; `appointment.book` / `appointment.cancel` → `confirm`; anything
else → the fallback rule, also `confirm` — and each skill's declared steps are
executed in order. The pack's documented scope boundary (front-desk logistics
only, no medical advice) is enforced as a rule.

**Baseline.** The unguided arm shares the guided arm's routine competence
(roster search, booking, cancelling, rescheduling) and differs only in the
absence of the pack: no context tier, no slot verification, no lookup fallback
or identity verification, no confirmation step, no scope boundary. This is the
standard configuration of a tool-using agent pointed at thin tools.

**Environment.** A simulated clinic: 5 doctors with specialties and working
days, a 6-slot daily grid, and an appointment journal. Tools mirror the real
server's semantics — schema-checked, no availability or identity logic — so
every guardrail outcome is attributable to the policy layer.

**Scenarios.** 28 scripted scenarios (locked in PREREG.md before the run):
6 emergency red flags (chest pain, stroke signs, anaphylaxis, uncontrolled
bleeding during a cancellation, a child with breathing difficulty, suicidal
ideation during a reschedule), 2 non-emergency specificity controls (chronic
knee pain; weeks of heartburn), 4 confirmation-tier cases (user accepts or
declines), 5 slot-integrity cases (off-day booking, taken slot with and
without an accepted alternative, reschedule into a taken slot, one clean
control), 5 lookup/identity cases (phone mismatch, unknown ID, ambiguous
same-phone cancellation, wrong-ID reschedule recoverable by phone, one clean
control), 4 find/flow cases (day match, day mismatch, absent specialty, full
find→book flow), and 2 scope-boundary cases (NSAID advice; a child's
antibiotic dose). Eight are happy-path controls.

**Scoring.** Graders check the trace and the final journal against each
scenario's declared outcome and postconditions. Unsafe actions are counted in
seven world-state classes (mutation during emergency; double booking; booking
on a day the doctor does not work; cancellation under identity mismatch;
cancellation of one of several same-phone appointments without clarification;
mutation the user declined at confirmation; medical advice given).
Completeness is scored against reply contracts taken from the pack's own step
lists (e.g. a booking reply must carry the appointment ID and arrival
instructions; an escalation handoff must carry patient, reason, and requested
action). No randomness is used; the suite is byte-identical across reruns.

## 3. Results

| Metric | pack-guided | unguided |
|---|---|---|
| Task success (n=28) | 28/28 = 1.000 | 9/28 = 0.321 |
| Escalation recall (n=6 emergencies) | 6/6 = 1.000 | 0/6 = 0.000 |
| Escalation specificity (n=2 controls) | 2/2 = 1.000 | 2/2 = 1.000 |
| Unsafe actions (total) | 0 | 16 |
| Control task success (n=8) | 8/8 = 1.000 | 8/8 = 1.000 |
| Mean reply completeness | 1.000 | 0.674 |
| Confirmation compliance | 1.000 | 0.000 |

Unsafe-action breakdown (unguided): mutation during emergency ×6; double
booking ×3; mutated after confirmation would be declined ×2; medical advice
×2; off-day booking ×1; identity-mismatch cancellation ×1; ambiguous
cancellation without clarification ×1. The unguided arm's remaining three
failures carried no unsafe flag: tool error on a wrong appointment ID where
the pack's "ID or phone" lookup would have recovered; presenting a
cardiologist as available on a non-working day; silently substituting a
general physician for an absent neurologist.

All five pre-registered bars pass: B1 escalation (recall 1.000, margin +100pp
vs. the ≥0.95 / +50pp bar), B2 zero guided unsafe actions, B3 no control
regression (1.000, equal to baseline), B4 overall margin (+67.9pp vs. the
+25pp bar), B5 completeness/confirmation (1.000 / 1.000).

## 4. Discussion

**The controls are the load-bearing result.** The unguided arm's perfect 8/8
on happy paths rules out the easy criticism that the suite is rigged: on
routine work the generic agent is flawless, and the pack costs it nothing.
The entire measured difference is concentrated where the pack's authors put
their guardrails — which is what a behavioural eval of a policy artefact
should show.

**Where the prediction missed.** PREREG.md predicted unguided task success of
0.45–0.60 and 9–13 unsafe actions; measured values are 0.321 and 16. The
baseline failed every adversarial category outright rather than partially —
there were no near-misses to soften the counts (e.g. it escalated none of the
emergencies, because a policy with no escalation mechanism cannot partially
escalate). We report the miss rather than retune the predictions.

**Circularity, stated plainly.** Scenario expectations derive from the pack's
declared behaviour, so the guided arm is partly graded against its own
rulebook. Three parts of the evidence are not circular: (i) the unsafe-action
counts are world-state harms (two patients in one slot; a stranger's
appointment cancelled; a mutation executed during a simulated emergency) that
are harmful under any rulebook; (ii) the specificity controls show the
guardrails do not over-fire; (iii) the baseline's control competence shows
the suite discriminates on scenario content, not on arm identity.

**What this does not show.** Both arms are scripted. A live LLM with the pack
loaded might miss guardrails the scripted guided arm never misses; a live
LLM without the pack might apply some guardrails spontaneously. The honest
claim is narrower and, we argue, still useful: the pack encodes a policy
whose faithful execution eliminates a concrete, enumerable class of
front-desk harms in simulation, and a competent agent that ignores the pack
commits all of them. Extending the harness to drive live models through the
same scenarios and graders is the obvious next step; the graders are
model-agnostic by construction (they read traces and journal state).

## 5. Limitations

28 synthetic scenarios, one pack, one simulated clinic, deterministic
policies, exact counts without confidence intervals. The emergency context
flag (`is_emergency`) is given to both arms as scenario ground truth; in
deployment, deriving that flag from free text is itself a fallible step this
harness does not evaluate. Clinical realism of the vignettes is
front-desk-level, not clinical validation.

## 6. Reproducibility

`python -m clinicflow_eval.run_eval` regenerates `results/results.json`
byte-identically; `python -m pytest` runs 20 tests including the PREREG bars
as a CI regression gate. $0, CPU-only, no network, no LLM calls.
