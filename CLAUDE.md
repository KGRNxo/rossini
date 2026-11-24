<!-- BEGIN IMPLEMENTATION-FIRST-WORKFLOW -->
## Verbindlicher Entwicklungsmodus: IMPLEMENTATION FIRST

Diese Regel gilt projektübergreifend, solange der Nutzer keinen anderen Arbeitsmodus ausdrücklich vorgibt. Sie ergänzt bestehende Entwicklungs- und Sicherheitsregeln. Korrektheit, Datensicherheit und explizite Nutzeranforderungen haben weiterhin Vorrang.

### Priorität und Arbeitsablauf

1. Implementiere zuerst alle umsetzbaren, noch offenen oder unvollständigen Aufgaben der vorhandenen Roadmaps und Arbeitsaufträge. Optimiere danach systematisch Qualität, Stabilität, Performance, Speicher- und Ressourcenverbrauch sowie UI/UX. Bei unmittelbarem technischem Risiko darf die notwendige Optimierung früher erfolgen.
2. Eine abgeschlossene Einzelaufgabe ist **kein** Grund, den Arbeitsdurchlauf zu beenden. Beginne selbstständig mit der nächsten klar umsetzbaren Aufgabe. Vermeide künstliche Zwischenabschlüsse, wiederholte Bestandsaufnahmen und reine Berichte ohne Implementierung.
3. Nutze vorhandene Roadmaps und tatsächlichen Code als Arbeitsgrundlage. Prüfe vor Änderungen den realen Stand und vermeide Doppelarbeit, Platzhalter, Scheinimplementierungen und unnötige Architekturumbauten.
4. Arbeite innerhalb der verfügbaren Sitzung selbstständig weiter, bis keine umsetzbare Arbeit mehr möglich ist oder eine echte technische Grenze erreicht wird. Bei Sitzungs-/Kontextgrenzen dokumentiere präzise Fortschritt und nächsten Schritt. Behaupte nicht, im Hintergrund weiterzuarbeiten.

### Tests während der Implementierungsphase

5. Führe gezielte Tests für geänderte Komponenten, notwendige Build-/Compileprüfungen, relevante CI-Guards und sicherheitskritische Prüfungen durch. Behebe erkannte Regressionen direkt.
6. Starte **nicht routinemäßig nach jeder Änderung** vollständige Unit-, UI-, Simulator- oder Geräte-Testläufe und warte nicht unnötig auf deren Abschluss, solange unabhängige Implementierungsaufgaben offen sind. Ein vollständiger Lauf ist dennoch zulässig, wenn er wegen hohem Risiko, einer konkreten Regression oder einer zwingenden Freigabevoraussetzung erforderlich ist.
7. Bereits laufende Tests dürfen weiterlaufen. Bearbeite parallel konfliktfreie Aufgaben, soweit dies Ressourcen und gemeinsame Build-Artefakte erlauben. Dokumentiere ausstehende oder fehlgeschlagene Prüfungen wahrheitsgemäß.
8. Die konsolidierte vollständige Test-, Simulator-, UI- und manuelle Abnahmephase folgt nach der Implementierungs- und Optimierungsphase, sofern der Nutzer sie nicht vorher verlangt.

### Qualität, Git und Fortschritt

9. Keine Kompromisse bei Datenintegrität, Datenschutz, Sicherheit, fachlicher Korrektheit oder erforderlichen Migrationen. Performance-Optimierung muss auch Nebenläufigkeit, Speichergrenzen, Skalierung und Fehlerfälle berücksichtigen.
10. Committe und pushe abgeschlossene, sinnvoll abgegrenzte Änderungen regelmäßig auf Arbeitsbranches und erstelle bzw. aktualisiere passende Pull Requests. **Kein eigenständiger Merge nach `main`** ohne ausdrückliche Freigabe. Beachte bestehende PR-Stacks und Branch-Basen.
11. Kennzeichne nicht implementierte, nicht fachlich verifizierte oder nicht getestete Punkte korrekt. Eine administrative Freigabe gilt nicht als fachlicher Einzelbeleg.
12. Wenn Roadmaps fehlen, arbeite den expliziten Auftrag und nachvollziehbar erkannte Lücken ab, statt neue Aufgaben oder Anforderungen zu erfinden.

**Erfolgskriterium:** Möglichst vollständige, produktionsreife Implementierung und anschließende Optimierung bei angemessener laufender Absicherung. Grüne Gesamttests allein ersetzen keine fertigen Funktionen.
<!-- END IMPLEMENTATION-FIRST-WORKFLOW -->

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
