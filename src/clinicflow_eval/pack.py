"""Parser for packc ``.pack`` files (clinic subset).

Extracts exactly the behavioural content clinicflow-eval executes:
skill definitions (tool, ordered steps), the ``care`` flow transitions,
and the escalation policy (default action tiers, named rules, fallback).

The parser is intentionally small and format-specific: it targets the
packc source format used by clinic-plugin-pack's ``src/clinic.pack``,
not arbitrary pack files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Skill:
    name: str
    description: str = ""
    tool: str = ""
    input_schema: str = ""
    output_schema: str = ""
    steps: list = field(default_factory=list)
    triggers: list = field(default_factory=list)


@dataclass
class Escalation:
    context_schema: str = ""
    defaults: dict = field(default_factory=dict)  # action -> tier
    rules: list = field(default_factory=list)     # [{name, when, tier}]
    fallback_tier: str = "confirm"


@dataclass
class Pack:
    name: str = ""
    version: str = ""
    tools: list = field(default_factory=list)
    skills: dict = field(default_factory=dict)    # skill name -> Skill
    flow: dict = field(default_factory=dict)      # {start, transitions {on: skill}}
    escalation: Escalation = field(default_factory=Escalation)

    def tier_for(self, action: str, is_emergency: bool) -> str:
        """Resolve the escalation tier for an action under a context.

        Rules are evaluated in declaration order; a rule whose condition
        matches wins. Otherwise the per-action default applies, and if the
        action has no default, the pack's fallback rule tier applies.
        """
        for rule in self.escalation.rules:
            when = rule.get("when", "")
            if when == "is_emergency == true" and is_emergency:
                return rule["tier"]
            if when == "" and rule["name"] == "fallback":
                continue  # fallback handled below, after defaults
        if action in self.escalation.defaults:
            return self.escalation.defaults[action]
        return self.escalation.fallback_tier


def _block(text: str, start: int) -> str:
    """Return the brace-balanced block starting at the first '{' at/after start."""
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1 : j]
    raise ValueError("unbalanced braces in pack file")


def parse_pack(text: str) -> Pack:
    pack = Pack()

    m = re.search(r"pack\s+(\w+)\s*\{", text)
    if m:
        head = _block(text, m.start())
        nm = re.search(r'name:\s*"([^"]+)"', head)
        vm = re.search(r'version:\s*"([^"]+)"', head)
        tm = re.search(r"tools:\s*\[([^\]]+)\]", head)
        if nm:
            pack.name = nm.group(1)
        if vm:
            pack.version = vm.group(1)
        if tm:
            pack.tools = [t.strip().strip('"') for t in tm.group(1).split(",")]

    for m in re.finditer(r"skill\s+([\w-]+)\s*\{", text):
        body = _block(text, m.start())
        skill = Skill(name=m.group(1))
        dm = re.search(r'description:\s*"([^"]+)"', body)
        if dm:
            skill.description = dm.group(1)
        tm = re.search(r'tool:\s*"([^"]+)"', body)
        if tm:
            skill.tool = tm.group(1)
        im = re.search(r"input:\s*(\w+)", body)
        if im:
            skill.input_schema = im.group(1)
        om = re.search(r"output:\s*(\w+)", body)
        if om:
            skill.output_schema = om.group(1)
        sm = re.search(r"steps:\s*\[(.*?)\]", body, re.S)
        if sm:
            skill.steps = re.findall(r'"([^"]+)"', sm.group(1))
        gm = re.search(r"trigger:\s*\[([^\]]+)\]", body)
        if gm:
            skill.triggers = re.findall(r'"([^"]+)"', gm.group(1))
        pack.skills[skill.name] = skill

    fm = re.search(r"flow\s+(\w+)\s*\{", text)
    if fm:
        body = _block(text, fm.start())
        start = re.search(r"start:\s*([\w-]+)", body)
        transitions = dict(re.findall(r"on\s+(\w+)\s*->\s*([\w-]+)", body))
        pack.flow = {
            "name": fm.group(1),
            "start": start.group(1) if start else "",
            "transitions": transitions,
        }

    em = re.search(r"escalate\s*\{", text)
    if em:
        body = _block(text, em.start())
        cm = re.search(r"context:\s*(\w+)", body)
        if cm:
            pack.escalation.context_schema = cm.group(1)
        dm = re.search(r"defaults:\s*\{(.*?)\}", body, re.S)
        if dm:
            for action, tier in re.findall(r'"([^"]+)":\s*(\w+)', dm.group(1)):
                pack.escalation.defaults[action] = tier
        for rm in re.finditer(
            r"rule\s+(\w+):\s*(?:when\s+([^->]+?)\s*)?->\s*tier:\s*(\w+)", body
        ):
            name, when, tier = rm.group(1), (rm.group(2) or "").strip(), rm.group(3)
            pack.escalation.rules.append({"name": name, "when": when, "tier": tier})
            if name == "fallback":
                pack.escalation.fallback_tier = tier
    return pack


def load_pack(path) -> Pack:
    with open(path, "r", encoding="utf-8") as fh:
        return parse_pack(fh.read())
