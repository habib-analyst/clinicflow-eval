# clinicflow-eval

**A behavioural evaluation harness for [clinic-plugin-pack](https://github.com/habib-analyst/clinic-plugin-pack)** — Habib Ur Rehman's medical plugin pack for Claude Code. The pack's own test suite proves it is well-formed (conformance 17/17, structural 35/35, skill-load recall@1 = 1.000). This harness asks the next question: **does following the pack change what an agent actually does** — on an emergency message, a taken slot, a wrong phone number, a request for medical advice?

> **What this is, honestly:** a *scripted* behavioural harness. The "agent" in each arm is a deterministic policy program, not a live LLM. The pack-guided policy is not a paraphrase of the pack — it is driven by **parsing the pack's own `clinic.pack` source at runtime** (skill steps, escalation tiers, care flow) and executing it against a simulated clinic. Results measure the pack's *encoded policy* and its consequences in the simulated world. They are not a live-LLM evaluation and not clinical validation. See `PREREG.md` for the locked design, metrics and bars, and `PAPER.md` for the full write-up.

## Why this exists

In clinic-plugin-pack, the MCP tools are deliberately thin: the real server validates calls against the typed schema and nothing more. Every behavioural guardrail — *escalate emergencies to a human, verify the slot is free before booking, look the appointment up and verify identity before cancelling, ask for confirmation before mutating anything, never give medical advice* — lives in the skills and the escalation policy. If an agent ignores the pack, the tools will happily execute unsafe actions. clinicflow-eval measures exactly that gap.

## Design

- **Environment** — a simulated clinic (5-doctor roster, appointment journal) whose tools mirror the real MCP server's semantics: schema-checked only, no slot/identity/escalation logic.
- **Arms** — two scripted policies with identical routine competence:
  - *pack-guided*: executes the parsed pack (emergency rule → `human_only`; book/cancel → `confirm` tier; fallback → `confirm`; skill steps in order; scope boundary enforced).
  - *unguided*: a competent generic front-desk agent that performs exactly what is asked, immediately — no context tier, no slot verification, no lookup/identity check, no confirmation step, no scope boundary.
- **Scenarios** — 28 scripted cases in 6 categories: emergency red flags (6) plus non-emergency specificity controls (2), confirmation (4), slot integrity (5), lookup & identity (5), find & flow (4), scope boundary (2). Eight are happy-path controls where a fair harness must let the unguided arm do well — and it does (8/8).
- **Scoring** — outcomes are graded on world state (the appointment journal), not reply text: a double booking is a double booking regardless of how politely it is phrased. Unsafe actions are counted in seven classes. No randomness anywhere; reruns are byte-identical.

## Results (28 scenarios, pre-registered bars in `PREREG.md`)

| Metric | pack-guided | unguided |
|---|---|---|
| Task success | **28/28 (1.000)** | 9/28 (0.321) |
| Red-flag escalation recall (6 emergencies) | **6/6 (1.000)** | 0/6 (0.000) |
| Escalation specificity (2 non-emergency controls) | 2/2 (1.000) | 2/2 (1.000) |
| Unsafe actions | **0** | **16** |
| Task success on 8 happy-path controls | 8/8 (1.000) | 8/8 (1.000) |
| Reply completeness (pack's own reply contracts) | **1.000** | 0.674 |
| Confirmation compliance (mutations preceded by a confirmation request) | **1.000** | 0.000 |

The unguided arm's 16 unsafe actions: 6 mutations during emergencies (it booked, cancelled or rescheduled straight through chest pain, stroke signs, anaphylaxis, uncontrolled bleeding, a child struggling to breathe, and suicidal ideation), 3 double bookings, 2 mutations the user would have declined at a confirmation step, 2 instances of medical advice (including a child's antibiotic dose), 1 booking on a day the doctor does not work, 1 cancellation under an identity mismatch, 1 cancellation of one of several same-phone appointments without asking which. It also failed without an unsafe flag three times: it could not recover from a wrong appointment ID (the pack's "look up by ID *or phone*" step could), it presented a cardiologist as available on a day she does not work, and it silently substituted a general physician for a requested neurologist.

All five pre-registered bars pass. Two honest notes: the unguided arm did *worse* than the ranges predicted in `PREREG.md` (task success 0.321 vs. predicted 0.45–0.60; unsafe 16 vs. predicted 9–13) — it failed every adversarial category outright rather than partially. And the guided arm is partly scored against its own rulebook; the non-circular evidence is the consequence side — the journal states the unguided arm produced are harmful under any rulebook, while its perfect control score shows the suite is not rigged against it.

## Quickstart

```bash
pip install -e .          # or just use PYTHONPATH=src
python -m clinicflow_eval.run_eval   # writes results/results.json, prints the table
python -m pytest                     # 20 tests, incl. the PREREG bars as a CI regression gate
```

## Layout

- `vendor/clinic.pack` — the pack source under test, vendored verbatim from clinic-plugin-pack (`plugin/src/clinic.pack`, MIT, © Habib Ur Rehman).
- `src/clinicflow_eval/pack.py` — parser for the pack format (skills, steps, flow, escalation policy).
- `src/clinicflow_eval/environment.py` — the simulated clinic and its schema-only tools.
- `src/clinicflow_eval/policies.py` — the two arms.
- `src/clinicflow_eval/scenarios.py` — the 28 scenarios with declared expectations.
- `src/clinicflow_eval/scoring.py` — graders, safety flags, metrics, bar verdicts.
- `PREREG.md` — design, metric definitions and bars, locked before the run.
- `KILLGATE.md` — the prior-art check: why nothing established already does this.
- `PAPER.md` — full write-up.

## Limits

Scripted policies, a 28-scenario synthetic suite, one pack. A live LLM might apply some guardrails spontaneously (shrinking the gap) or fail some the scripted guided policy never misses (growing it). Percentages are exact counts on this suite, not population estimates. Nothing here is clinical validation, and the pack itself remains a front-desk logistics tool — this harness evaluates workflow behaviour only.

## License

MIT — see `LICENSE`. The vendored `clinic.pack` is part of clinic-plugin-pack, also MIT, © Habib Ur Rehman.
