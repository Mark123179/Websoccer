---
name: 3D-Vereinsassets im Creator Mode
description: Bedeutung der 3D-Trikotuploads und der beiden Stadionzustände in der Vereinsverwaltung.
---

Die vom Nutzer als „3D-Trikots“ bezeichneten Uploads sind PNG-Texturvorlagen für Home, Away und Third, keine GLB-Modelldateien.

**Why:** Der Nutzer lieferte eine flach aufgefaltete PNG-Trikottextur und erklärte: „Wird es auch geben für Home, Away, Third.“

**How to apply:** Texturuploads von Modelldateien und bisherigen 2D-Trikotbildern unterscheiden. Kompatibilität mit einem vorhandenen 3D-Modell nicht ohne Prüfung der Texturzuordnung behaupten.

Die öffentlichen Texturpfade müssen `/static/game/images/3dkits/<FMI-ID>_home.png`, `_away.png` und `_third.png` sein, nicht auf der internen Vereins-ID beruhen.

**Why:** Der Nutzer gab ausdrücklich `/static/game/images/3dkits/907_home.png` vor und erklärte „907 für FMI´ID_home.png“.

**How to apply:** Diese URL-Konvention bei weiteren Verbrauchern und Uploadänderungen erhalten. Mutable Uploads bleiben im dauerhaften Asset-Speicher; ein neuer Static-Build darf sie nicht verdrängen.

Im Creator Mode möchte der Nutzer das Originalstadion und den aktuellen Stadionzustand sehen. „Aktuell“ bedeutet den Zustand nach einem Ausbau durch den Manager.

**Why:** Der Nutzer definierte „aktuell“ ausdrücklich mit „sollte der Manager das Stadion ausgebaut haben“.

**How to apply:** Die beiden Ansichten unterscheidbar halten; eine geplante Ausbauvorschau nicht als aktuellen Bestand ausgeben.
