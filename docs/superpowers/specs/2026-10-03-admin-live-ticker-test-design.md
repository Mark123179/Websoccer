# Admin-Live-Ticker-Test

Freigegeben: Admin-Navigation, automatischer Start, Originaltempo und Reset mit
neuer Simulation derselben Mannschaften. Reload setzt den bestehenden Lauf fort.

- Bayern und Dortmund bilden das feste Testpaar; drei unabhängige Simulationen
  desselben Paars ermöglichen auch den aggregierten Konferenztest.
- Die unveränderte echte Engine berechnet bei jedem Reset neue Ergebnisse;
  anschließend erzählt das unveränderte v4.1-Paket diese neuen Berichte.
- Sämtliche Engine-Aufstellungsänderungen laufen innerhalb einer ausdrücklich
  zurückgerollten Transaktion. Keine echten Spiele, Storys oder Runden anlegen.
- Nur die eigene Django-Testsession speichert neue Zeilen, Lauf-ID und Serverstart.
  Bestehende historische Ticker werden niemals angefasst.
- Einzel-Ticker und Konferenz verwenden die vorhandenen Templates, Filter und
  den vorhandenen Polling-Code. Serverseitig nur zeitlich freigegebene Zeilen.
- Reset ausschließlich per CSRF-geschütztem POST; alle Routen nur Superuser.
- Bei fehlenden Testvereinen oder Simulationsfehlern sichtbarer Fehler statt
  Ersatzgeschichte. Gleiche Endstände können bei unabhängigen Läufen vorkommen.

Prüfung: Rollen/CSRF, echte Neuberechnung, Rollback, Session-/Reload-Fortsetzung,
Freigabe nach Offset und Ausgabe nach Order; ein Browserlauf für die Admin-Seiten.