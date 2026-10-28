# KILLGATE — clinicflow-eval

**Date:** 2026-10-28
**Question:** Does an established behavioural evaluation harness already exist for
Claude Code plugin packs / clinical agent skills — i.e. something that scores what an
agent *does* on clinical workflow scenarios with vs. without the pack?

## What was searched (2026-10-28)

1. Web: "behavioural evaluation harness Claude Code plugin pack skills".
2. Web: "clinical agent benchmark safety evaluation red-flag escalation triage"
   (AgentClinic / MedAgentBench / PatientAgentBench / NurseSim-RL).
3. The target repo itself: habib-analyst/clinic-plugin-pack validation artefacts
   (conformance 17/17, structural 35/35, skill-load recall@1 = 1.000).
4. Habib's own shelves: packc, meddecode-safety (build dir), driftmed, conformal-med.

## What exists, and why none of it is this

- **Generic Claude Code eval tooling** — the "eval-harness" skill (eval-driven
  development for coding sessions, pass@k on task completion), Anthropic's plugin-eval
  guidance (trigger tests, tool-use checks, with/without-plugin comparison on live
  models), `mcp-doctor` (static linter for MCP server descriptions), `vetskill`
  (security scanner for skill files). All either generic-coding, static, or
  security-oriented. None scores clinical workflow behaviour, none carries safety
  endpoints (escalation recall, unsafe actions), none evaluates a clinical pack.
- **Clinical agent benchmarks** — AgentClinic, MedAgentBench, PatientAgentBench,
  NurseSim-RL. These evaluate **live LLMs** acting as doctors in diagnosis / EHR /
  triage simulations, graded by task success or LLM juries. Different object under
  test (a model's clinical reasoning), different setting (hospital/EHR, not a clinic
  front desk), non-deterministic, and none of them evaluates a plugin pack's encoded
  policy (skills + escalation tiers) or compares pack vs. no-pack on the same harness.
- **clinic-plugin-pack's own validation** — conformance, structural checks and
  skill-load recall prove the pack is well-formed and loadable. They say nothing
  about behaviour: whether following the pack changes what an agent does on an
  emergency message, a taken slot, or a mismatched-phone cancellation.
- **meddecode-safety** (Habib's project #70, killed at its own gate) — constrained
  decoding / drug-interaction optimisation. Unrelated.

## Verdict: PASS — build

No established equivalent found. The empty shelf is specific: a deterministic,
behavioural, pack-vs-no-pack evaluation of a clinical Claude Code plugin pack, where
the pack file itself is parsed and executed as the policy under test, scored on
safety endpoints. clinicflow-eval fills exactly that shelf, in scripted form, with
the scripted-policy limitation stated up front (see PREREG.md and README.md).
