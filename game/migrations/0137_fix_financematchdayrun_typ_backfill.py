"""Migration 0137: TX-basiertes Backfill für FinanceMatchdayRun-Typ-Marker.

Migration 0136 hat für alle bestehenden Runs pauschal alle 6 Typ-Marker
gesetzt — unabhängig davon, ob tatsächlich passende FinanceTransaction-Zeilen
vorhanden sind. Das würde partiell gebuchte historische Spieltage dauerhaft
als vollständig markieren und so den Lücken-Schließ-Mechanismus aushebeln.

Diese Migration ersetzt die Blanket-Marker durch einen TX-basierten Ansatz:
  1. Alle Nicht-Header-Marker löschen (typ != '').
  2. Für jeden Header-Marker die Typ-Marker aus FinanceTransaction-Zeilen
     rekonstruieren (Mapping tx.typ → Schritt-Marker).

Vereine, deren Schritte keine Buchungen erzeugt haben (z.B. Auswärtsverein
ohne Heimspiel → kein TICKET/UMFELD), bekommen keinen entsprechenden Marker.
Der nächste Aufruf von run_club_finance() führt fehlende Schritte als No-op
aus und setzt danach den Marker — vollständig idempotent.
"""
from django.db import migrations, models

# Mapping FinanceTransaction.typ → FinanceMatchdayRun.typ (Schritt-Marker)
TX_TO_RUN_TYP = {
    'TV_SOCKEL': 'TV_SOCKEL',
    'TV_PLATZ':  'TV_SOCKEL',
    'TV_KOEFF':  'TV_SOCKEL',
    'FALLSCHIRM': 'TV_SOCKEL',
    'SPONSOR_FIX':      'SPONSOR',
    'SPONSOR_VARIABEL': 'SPONSOR',
    'TICKET': 'TICKET',
    'UMFELD': 'TICKET',
    'GEHALT':           'GEHALT',
    'STADION_UNTERHALT': 'STADION',
    'STADION_SPIELTAG':  'STADION',
    'BETRIEB': 'BETRIEB',
}


def _rebuild_typ_marker(apps, schema_editor):
    """Blanket-Marker löschen und TX-basiert neu aufbauen."""
    FinanceMatchdayRun = apps.get_model('game', 'FinanceMatchdayRun')
    FinanceTransaction = apps.get_model('game', 'FinanceTransaction')

    # Alle Nicht-Header-Marker entfernen (wurden von 0136 pauschal angelegt).
    FinanceMatchdayRun.objects.exclude(typ='').delete()

    # Für jeden Header-Marker die Typ-Marker aus Transaktionen rekonstruieren.
    neue_zeilen = []
    for run in FinanceMatchdayRun.objects.filter(typ='').iterator():
        tx_typen = set(
            FinanceTransaction.objects.filter(
                club_id=run.club_id,
                saison=run.saison,
                spieltag=run.spieltag,
            ).values_list('typ', flat=True).distinct()
        )

        gefundene_run_typen = set()
        for tx_typ in tx_typen:
            run_typ = TX_TO_RUN_TYP.get(tx_typ)
            if run_typ:
                gefundene_run_typen.add(run_typ)

        for run_typ in gefundene_run_typen:
            neue_zeilen.append(FinanceMatchdayRun(
                club_id=run.club_id,
                saison=run.saison,
                spieltag=run.spieltag,
                typ=run_typ,
            ))

    if neue_zeilen:
        FinanceMatchdayRun.objects.bulk_create(neue_zeilen, ignore_conflicts=True)


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0136_financematchdayrun_typ'),
    ]

    operations = [
        migrations.RunPython(_rebuild_typ_marker, reverse_code=_noop),
    ]
