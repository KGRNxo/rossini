# rossini: Design Excellence und verbindliche Designspezifikation

Stand 2026-11-01. Status: dokumentarisch geprüft, reale UI ausdrücklich **nicht visuell validiert**. Regeln aus vorhandenen Produkt-/Architekturentscheidungen bleiben vorrangig, wo die Designanalyse keine neue, verifizierte Entscheidung trägt.

## 1. Designvision und Prinzipien

Rossini OS: monochromes, leises E-Ink-System für Lesen, Bibliothek und sichere Recovery. Designqualität wird an verständlichen Aufgaben, ruhiger Hierarchie, ehrlichen Zuständen und funktionalem Nutzen gemessen. Jedes visuelle Mittel braucht eine erkennbare Aufgabe. Bestehende bewusste Marken- und Sicherheitsvorgaben bleiben erhalten.

## 2. Nutzerziele und UX-Leitlinien

Relevante Arbeitswege: Home, Bücher, Reader, OPDS, Einstellungen, Update/Recovery. Der Einstieg zeigt klar, wo man sich befindet und was als Nächstes möglich ist. Kein Navigations-/Wissensgedächtnis voraussetzen, das sich durch Labels und sichtbare Zustände vermeiden lässt. Fehlhandlungen verzeihen und Rückgängig ermöglichen.

## 3. Plattform- und Gerätestrategie

Monochromes, akkuschonendes Canvas mit bewusstem E-Ink-Refresh, keine Apple-Materialeffekte. Bestehende Technik: Eigene Python-Canvas-Shell; INK/MUTE/PAPER/RULE/SOFT-Tokens und M=56-Designabstand in screens.py. Bislang PC/QEMU, kein echtes Kindle-Boot.

## 4. Informationsarchitektur und Navigation

Home, Bücher, Reader, OPDS, Einstellungen, Update/Recovery. Start, aktueller Bereich, Zurückweg und Hauptaktion brauchen jeweils klare Beschriftung. Weniger häufige Aktionen kontextuell, nicht vollständig versteckt; Status und Eingaben bei Navigation erhalten.

## 5. Visuelles Designsystem und Farb-Tokens

Rossini OS: monochromes, leises E-Ink-System für Lesen, Bibliothek und sichere Recovery. Semantische Rollen statt freier Hexwerte: canvas, surface, surfaceElevated, text, textMuted, accent, onAccent, border, focus, success, warning, danger. Tokens müssen in beiden Themes und mit erhöhtem Kontrast geprüft sein. Ist kein UI-Code vorhanden, keine fiktive Palette festlegen.

## 6. Typografie

Semantische Stufen für Display, Titel, Abschnitt, Body, Label, Zahlen und Hinweise; native/dynamische Systemgrößen statt starrer Schriftmaße. Lange Labels nicht buchstabenweise umbrechen oder unsichtbar schneiden. Controls bei Platzmangel umordnen; Fließtext darf natürlich umbrechen. Tabellenzahlen tabellarisch formatieren.

## 7. Spacing, Geometrie und Layout

Eigene Python-Canvas-Shell; INK/MUTE/PAPER/RULE/SOFT-Tokens und M=56-Designabstand in screens.py. Bislang PC/QEMU, kein echtes Kindle-Boot. Vorhandene Tokens sind die Implementierungsquelle. Nur benannte, begründete neue Spacing-/Radius-Rollen. Klares Verhältnis von Canvas, Content, Action und Overlay. Nicht alle Informationen in einzelne Karten verschachteln. Primäraktion und vollständige Trefferfläche dürfen weder Clipping noch Safe Areas verletzen.

## 8. Material, Schatten, Oberflächen

Glas/Blur nur, wenn es echte Interaktionshierarchie unterstützt. Dauerhaft zu lesende Inhalte auf ruhigen deckenden Flächen. Keine ineinander geschachtelten Glasflächen und keine dekorativen Schatten. Mit Reduce Transparency deckende Alternative, bei geringer Leistung Effekte minimieren.

## 9. Komponenten und Zustände

Buttons: default, pressed, hover (wo Pointer), focus, selected (falls sinnvoll), disabled, loading, success, error. Felder: empty, editing, valid, invalid, disabled. Navigation: active/inactive, Fokus und Back. Liste/Tabelle/Karte: loading, empty, selected, error und sehr langer Inhalt. Dialog/Sheet/Popover: Fokus, Schließen, Cancel, gegebenenfalls Undo/Bestätigung. Nur funktional mögliche Zustände umsetzen; Systemkomponenten bevorzugen.

## 10. Interaktion und Motion

Press als Entwurfswert 100–150 ms, Übergang 180–260 ms, kein universeller Plattformstandard. Motion zeigt Wechsel und Beziehungen, nie Dauerpulsieren/Autoplay ohne Zweck. Reduce Motion liefert statische Alternative; Feedback immer zusätzlich als Text/Icon, wo inhaltlich nötig.

## 11. Light-, Dark- und Hochkontrast-Modus

Semantische Rollen in jedem tatsächlichen Theme mit allen Zuständen messen. Keine naive Invertierung; Texte, Dialoge, Popover, ausgewählte Zeilen und Fehlerzustände müssen lesbar bleiben. Nicht implementierte Themes sind offen, nicht durch bloße Dokumentation abgenommen.

## 12. Accessibility und kognitive Ergonomie

VoiceOver/TalkBack nach Plattform, dynamische Schrift, logische Fokusreihenfolge, Touch- bzw. Hit-Areas, alternative Gesten, Reduce Motion, Reduce Transparency und erhöhten Kontrast prüfen. Als interne Orientierung für Text 4,5:1 bzw. 3:1 groß und für essenzielle Grafiken 3:1; keine falsche Behauptung nativer Konformität.

## 13. Responsive/adaptive Regeln

E-Ink-Auflösung, Lesespalte, Hitregion und Bildschirmaktualisierung auf echter Hardware prüfen.

## 14. Icons, Illustrationen und Bildmaterial

Original-Branding und bestehende Asset-Rechte respektieren. Icons brauchen eindeutigen Zweck und bei rein bildlicher Bedienung einen semantischen Namen. Dekoratives Bildmaterial für Screenreader ausblenden, informative Motive beschreiben. Keine erfundenen Produkt-Screens.

## 15. Sprache, Microcopy und Vertrauen

Konkrete Wörter statt Werbefloskeln; fehlerhafte Eingaben und Rechteprobleme mit Handlungsempfehlung benennen. Kein falscher Erfolg, kein erfundener Preis oder Syncstatus. Destruktive Wirkung vorher sichtbar machen, möglichst Undo. Keine unnötigen Bestätigungsdialoge.

## 16. Screen-/Workflow-Anforderungen

Home, Bücher, Reader, OPDS, Einstellungen, Update/Recovery. Jeden relevanten Ablauf in Start/Standard/Loading/Empty/Error/Abbruch, vergrößerter Schrift, Keyboard/Screenreader und Rückkehr testen. Die echte Oberfläche, nicht die Dokumentation, entscheidet über die Erfüllung.

## 17. Implementierung und Wartbarkeit

Ein zentrales Designsystem statt verstreuter Werte. Bestehende native Komponenten und Tools wiederverwenden, neue Custom Controls nur bei klarer Notwendigkeit. Performance und Barrierefreiheit sind Teil der Definition of Done. Dieser Auftrag ändert ausschließlich diese Markdown-Datei, keine Quelltexte.

## 18. Design-QA und Akzeptanzkriterien

Vor Produktfreigabe repräsentative Screens aller unterstützten Themes, Hauptflows, winzige und große Ansicht, lange Werte, Fehlersituationen und Accessibility-Einstellungen auf tatsächlich laufender Software prüfen. Ergebnis mit OS, Gerät, Build, Screenshot und reproduzierbaren Schritten dokumentieren. Es wurden bei diesem Dokumenten-Audit keine Builds, Screenshots, Browserrenderings, Screenreader- oder Gerätetests ausgeführt.

## 19. Audit, Prioritäten und Quellen

Gezielt untersuchte Quellen: README.md; rossini/shell/screens.py; rossini/shell/canvas.py. Konkrete Befunde/Risiken: P0: keine Kindle-Hardwarevalidierung; E-Ink-Refresh, Hitregions und Ghosting nur real testbar. Kein Glass/Blur. P0 sind belegte kritische Nutzbarkeits-/Datenschutzdefizite oder fehlende Prüfgrundlagen, P1 Hierarchie/Lesbarkeit/Zustand/Bedienung, P2 optische Konsistenz, P3 optionaler belegbarer Feinschliff. Offizielle Referenzen: https://developer.apple.com/design/human-interface-guidelines/ und https://developer.apple.com/design/human-interface-guidelines/materials/ (Apple-Empfehlungen); https://www.w3.org/TR/WCAG22/ (für Web Konformitätsziel AA). SC 2.4.13 Focus Appearance ist AAA und nicht AA. Eigene Layout-/Timingwerte sind Vorschläge, keine behaupteten Normen.
## Zweiter Qualitätsdurchlauf und Grenzen

| Bereich | Ausgang /5 | Spezifikation nach Revision /5 | Visuelle Bestätigung |
| --- | ---: | ---: | --- |
| A Hierarchie | 2 | 4 | offen |
| B Typografie | 2 | 4 | offen |
| C Farben/Kontrast | 3 | 4 | offen |
| D Layout/Geometrie | 2 | 4 | offen |
| E Plattformqualität | 1 | 4 | offen |
| F Materialien | 0 | 4 | offen |
| G Komponenten/Zustände | 2 | 4 | offen |
| H Motion | 1 | 4 | offen |
| I Accessibility | 2 | 4 | offen |
| J Inhalt/Vertrauen | 2 | 4 | offen |
| K Engineering | 2 | 4 | offen |

Die Skala 0 bis 5 bewertet ausschließlich anhand der gezielt eingesehenen Quellen die Dokumentations- und Architekturabdeckung: 0 keine Basis, 1 defizitär, 2 inkonsistent, 3 solide, 4 hochwertige konsistente Spezifikation, 5 außergewöhnlich UND empirisch nachgewiesen. Bei leeren Repositories ist eine 0 keine Note für eine nicht existierende App. Die neue Spalte bewertet **nur die formulierten Anforderungen**, nicht die Implementierung. Weder 4/5 in dieser Tabelle noch das Bestehen der Textprüfung belegen visuelle Produktqualität. Zweite Textprüfung: alle Abschnitte 1–19 vorhanden, Referenzhierarchie, Theme, Komponenten, Motion und Datenschutz ohne bewusst neu eingeführte widersprüchliche Designvorgaben. Weiter offene Prüfungen: echte Layouts, Kontrast auf überlagerten Materialien, Fokus, große Schrift, Screenreader, Performance und Nutzbarkeit.
