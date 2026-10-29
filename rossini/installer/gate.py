"""Installation gate. There is no override flag: a device is installable only if every condition
holds. Reasons are collected, not short-circuited, so the diagnose report shows everything missing."""
import json
import os
import re
from dataclasses import dataclass, field

from ..system.hal import ROOT

EVIDENCE = ("boots_on_hardware", "functional_tested", "recovery_tested", "recovery_independent")


@dataclass
class Decision:
    allowed: bool
    board: str = None
    reasons: list = field(default_factory=list)


def load_profiles(root=ROOT):
    out = {}
    bd = os.path.join(root, "boards")
    for name in sorted(os.listdir(bd)):
        p = os.path.join(bd, name, "profile.json")
        if os.path.exists(p):
            with open(p) as f:
                out[name] = json.load(f)
    return out


def matches(rule, facts):
    """A rule: {"fact": <key in facts>, "regex": <fullmatch pattern>}; all rules of a profile must match."""
    v = facts.get(rule.get("fact"))
    return isinstance(v, str) and re.fullmatch(rule["regex"], v) is not None


def evaluate(facts, profiles, image_verified=False, image_board=None, backup_done=False):
    cands = [(n, p) for n, p in profiles.items()
             if p.get("kind") == "hardware" and p["identification"]["rules"]
             and all(matches(r, facts) for r in p["identification"]["rules"])]
    if len(cands) != 1:
        why = "Gerät konnte keinem unterstützten Modell zugeordnet werden" if not cands else "Gerät passt auf mehrere Profile"
        return Decision(False, None, [why])
    name, p = cands[0]
    d = Decision(True, name)
    if p.get("release_status") != "released":
        d.reasons.append(f"Modell {name} hat den Status '{p.get('release_status')}', nicht 'released'")
    for e in EVIDENCE:
        if not p.get("evidence", {}).get(e):
            d.reasons.append(f"Nachweis fehlt: {e}")
    if not p.get("install_method"):
        d.reasons.append("Für dieses Modell existiert kein geprüftes Installationsverfahren")
    if not image_verified:
        d.reasons.append("Image-Signatur nicht verifiziert")
    elif image_board != name:
        d.reasons.append(f"Image ist für {image_board}, nicht für {name}")
    if not backup_done:
        d.reasons.append("Datensicherung nicht abgeschlossen")
    d.allowed = not d.reasons
    return d
