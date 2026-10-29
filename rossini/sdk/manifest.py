"""App manifest for the Rossini SDK. Apps declare what they need; the system grants nothing else.
Validation here is the single source of truth for what a manifest may contain."""
import json
import re

API_LEVEL = 1
PERMISSIONS = {"library.read": "Bibliothek lesen", "library.write": "Bibliothek ändern", "network": "Netzwerkzugriff",
               "storage.app": "Eigener Datenordner", "display.fullscreen": "Gesamten Bildschirm nutzen",
               "input.keys": "Hardwaretasten"}


class ManifestError(ValueError):
    pass


def validate(raw):
    try:
        m = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except ValueError as e:
        raise ManifestError(f"kein gültiges JSON: {e}")
    if not isinstance(m, dict):
        raise ManifestError("Manifest muss ein Objekt sein")
    if not re.fullmatch(r"[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*){2,}", str(m.get("id", ""))):
        raise ManifestError("id muss die Form 'org.beispiel.app' haben")
    if not (isinstance(m.get("name"), str) and 1 <= len(m["name"]) <= 40):
        raise ManifestError("name fehlt oder ist zu lang")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(m.get("version", ""))):
        raise ManifestError("version muss x.y.z sein")
    if not re.fullmatch(r"[\w.-]+(/[\w.-]+)*", str(m.get("entry", ""))) or ".." in str(m["entry"]).split("/"):
        raise ManifestError("entry muss ein relativer Pfad innerhalb der App sein")
    if m.get("api_level", API_LEVEL) > API_LEVEL:
        raise ManifestError(f"api_level {m['api_level']} wird nicht unterstützt (maximal {API_LEVEL})")
    perms = m.get("permissions", [])
    unknown = [p for p in perms if p not in PERMISSIONS]
    if unknown or len(set(perms)) != len(perms):
        raise ManifestError(f"unbekannte oder doppelte Berechtigungen: {unknown or perms}")
    return m
