# Verbindliche Codex- und Coding-Agent-Anweisungen

Gilt bei jedem Audit, Coding, Review, Test, Release, jeder Analyse und Delegation. Bestehende Projekt-, Produkt- und Sicherheitsvorgaben befolgen.

## Vorrang
1. Korrektheit, Sicherheit, Privatsphäre und Datenintegrität
2. Alle expliziten Anforderungen vollständig erfüllen
3. UI/UX, Barrierefreiheit und Produktqualität
4. Zuverlässigkeit, Wartbarkeit, Performance
5. Minimaler notwendiger Code
6. Minimaler Kontext-, Token- und Toolaufwand

## Context Mode
Echte `ctx_*`-MCP-Tools zu Sitzungsbeginn prüfen. Wenn vorhanden, große Logs, Daten, Tests und Suchen über Sandbox, Index, Suche und Batch verarbeiten. Erst Struktur, Schnittstellen und Datenflüsse untersuchen, dann gezielt und progressiv lesen. Ergebnisse wiederverwenden und Fehlerdiagnosen nachvollziehbar bewahren. Vollaudit umfasst alle relevanten Komponenten oder nennt ungeprüfte Bereiche. Ohne MCP dieselbe Methodik mit vorhandenen Werkzeugen nutzen.

## Ponytail
Verfügbarkeit der echten Plugins, Skills und Hooks prüfen und `full` nur bei bestätigter Aktivierung nutzen. Vor Code: nötig? schon vorhanden? wiederverwendbar? Standardbibliothek oder native Plattform? existierende Dependency? kleine lokale Änderung? erst dann kleinste neue vollständige Lösung. Nie Anforderungen, Sicherheitsgrenzen, Fehlerbehandlung, Tests, Datenintegrität oder Accessibility durch Kürzen verlieren.

## Vorgehen
Für Audits `.agents/skills/context-efficient-audit/SKILL.md`, für Implementierung `.agents/skills/complete-implementation/SKILL.md` anwenden, wenn zur Aufgabe passend. Root Cause und Aufrufstellen prüfen, Änderungen vollständig samt Tests durchführen, Diff prüfen; Tests nicht als bestanden melden, wenn nicht gelaufen. Subagenten übernehmen die Regeln mit minimalem relevantem Kontext. Kein automatisches Mergen in den Hauptbranch.

`.codex/config.toml` stellt lediglich eine MCP-Konfiguration für vertrauenswürdige Codex-Projekte bereit; lokal muss `context-mode` installiert sein. `AGENTS.md` allein erzwingt keine tatsächliche Plugin-, MCP-, Skill- oder Hook-Ausführung.

## Projektbezug
E-Reader-Betriebssystem in Python mit QEMU/Kernel-Unterstützung. Keine realen Geräte-Flash-/Boot-Fähigkeiten behaupten; Installer-Sperren und `docs/STATUS.md` sowie Hardwaregrenzen respektieren.
