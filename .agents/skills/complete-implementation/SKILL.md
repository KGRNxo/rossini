---
name: complete-implementation
description: Für neue Features, Bugfixes, Refactorings, Migrationen, Performancearbeiten und Releases, wenn sichere, vollständige und minimal wartbare Änderungen benötigt werden.
---
1. AGENTS.md und projektspezifische Produkt-, Design-, Sicherheits- und Testvorgaben lesen. Echte Ponytail-/Context-Mode-Verfügbarkeit prüfen.
2. Anforderungen, Akzeptanzkriterien, Architektur, betroffene Aufrufstellen, Datenmodelle, Zustände und Testpfade progressiv erfassen.
3. Ponytail: erforderlich? vorhanden? wiederverwenden? native API/Standardbibliothek? bestehende Dependency? kleine lokale Änderung? erst dann neue Implementierung.
4. Vollständig umsetzen mit relevanten Fehlerfällen, Sicherheit, Datenschutz, Datenintegrität, Accessibility, Migration und Rückwärtskompatibilität.
5. Context-Mode-Sandbox, Index und Batch bei Verfügbarkeit für große Outputs einsetzen; Diagnosen erhalten.
6. Relevante Tests, Lint, Builds und Regressionen wirklich ausführen, Diff prüfen. Keine behaupteten Prüferfolge ohne Ausführung.
7. Keine automatischen Merges; Ergebnisse, nicht gelaufene Prüfungen und Risiken berichten. Ponytail full nur nach Bestätigung.
