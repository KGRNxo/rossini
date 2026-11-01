# Claude Code: verbindliche Projektanweisungen

@AGENTS.md

Claude Code ist der primaere Entwicklungsagent dieses Repositorys. Die vollstaendige `AGENTS.md` gilt fuer jede Analyse, Implementierung, Audit, Review, Test, Releasevorbereitung und Subagentendelegation. Falls der Import nicht aufgeloest wird, `AGENTS.md` ausdruecklich lesen. Vorhandene Produkt-, Sicherheits-, Datenschutz- und Release-Regeln bleiben unveraendert.

Context Mode und Ponytail durchgehend anwenden; echte Plugins/MCP/Hooks nur nach Pruefung nutzen. Ponytail `full` nur wenn unterstuetzt. Impeccable fuer UI/UX, wenn vorhanden. Nie RTK und Boost gleichzeitig auf denselben Befehl anwenden. Vollstaendige Fehlerdiagnostik erhalten. Keine erfundenen Testergebnisse, keine eigenmaechtigen externen Installationen, Merges oder Deployments.

Codex bleibt optionaler Zweitagent mit denselben `AGENTS.md`-Qualitaetsregeln.

<!-- ai-workflow-shared-v1 -->
## Gemeinsame Entwicklungsregeln
Lies und beachte `docs/AI_WORKFLOW.md` fuer jede Entwicklungsaufgabe in diesem Repository.
Bestehende spezifische Regeln dieser Datei bleiben gueltig.
<!-- /ai-workflow-shared-v1 -->

<!-- claude-git-sync-v1 -->
## Git-Abschluss und GitHub-Synchronisierung

- Vor jeder Entwicklungsarbeit den aktuellen Branch, Git-Status und die projektspezifischen Git-Regeln pruefen. Fremde oder bereits vorhandene Aenderungen niemals ungefragt stagen, ueberschreiben oder verwerfen.
- Fuer Entwicklungsarbeiten auf dem Default- oder geschuetzten Branch bei sicherem Arbeitszustand einen eigenen `claude/<aufgabe>`-Branch erstellen. Bei unklaren Ausgangsbedingungen stoppen und nachfragen.
- Nach vollstaendiger Umsetzung die relevanten Tests/Builds ausfuehren und den Diff pruefen. Nur eigene, auftragsbezogene Dateien committen; keine Secrets. Fehler, fehlende Tests und Restrisiken offen melden.
- Fuer erfolgreich verifizierte Entwicklungsauftraege ist das automatische Pushen des eigenen `claude/<aufgabe>`-Arbeitsbranches zu `origin` dauerhaft vom Repository-Eigentuemer freigegeben. Vorher Remote und Upstream pruefen; bei Konflikten, fehlgeschlagenen Tests oder unsicherer Aenderungslage nicht pushen.
- Push auf Default-/geschuetzte/fremde Branches, Force-Push, destruktive Resets, Branch-Loeschungen, Pull-Request-Erstellung, Merge und Deployment nur nach ausdruecklicher gesonderter Freigabe. Strengere projektspezifische Vorgaben behalten Vorrang.
- Am Ende Branch, Commit, ausgefuehrte Tests und den GitHub-Status knapp nennen. Keine Tests oder erfolgreichen Pushes behaupten, die nicht nachgewiesen sind.
<!-- /claude-git-sync-v1 -->
