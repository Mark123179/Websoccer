---
name: Pilot-Präfix in isolierten Tests
description: Django-TestClient kann präfixierte Anfragen über den Pilot-Proxy an den echten laufenden Pilot senden.
---

Präfix-Navigationstests dürfen keine HTTP-Anfragen an den laufenden Pilot weiterreichen. TestCase isoliert die Datenbank, nicht ausgehende HTTP-Aufrufe aus Middleware.

**Why:** Ein Test mit `/import-pilot` als Script-Präfix wurde vom Proxy abgefangen und lieferte einen HTTP-400-Fehler aus dem laufenden Dienst statt die lokale Testansicht auszuführen.

**How to apply:** In solchen Tests die Proxy-Middleware aus der Testkonfiguration entfernen, den Script-Präfix nachher wiederherstellen und ausschließlich Testdaten verwenden. Den echten Pilot separat lesend verifizieren.
