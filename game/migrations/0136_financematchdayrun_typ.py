"""Migration 0136: Idempotenz-Guard per Buchungstyp (Task #762).

Änderungen:
  1. FinanceMatchdayRun bekommt ein ``typ``-Feld (default='').
  2. Unique-Constraint wechselt von (club, saison, spieltag)
     auf (club, saison, spieltag, typ).
  3. Datenmigration: Alle bestehenden Runs (komplett ausgeführt) erhalten
     alle sechs Typ-Marker (TV_SOCKEL, SPONSOR, TICKET, GEHALT, STADION,
     BETRIEB), damit kein Wiederholungslauf sie erneut bucht.
"""
from django.db import migrations, models


ALLE_TYPEN = ['TV_SOCKEL', 'SPONSOR', 'TICKET', 'GEHALT', 'STADION', 'BETRIEB']


def _create_typ_marker(apps, schema_editor):
    """Backfill: für jeden bestehenden Haupt-Marker alle 6 Typ-Marker anlegen."""
    FinanceMatchdayRun = apps.get_model('game', 'FinanceMatchdayRun')

    vorhandene = list(FinanceMatchdayRun.objects.all().values('club_id', 'saison', 'spieltag'))
    if not vorhandene:
        return

    neue_zeilen = []
    for run in vorhandene:
        for typ in ALLE_TYPEN:
            neue_zeilen.append(FinanceMatchdayRun(
                club_id=run['club_id'],
                saison=run['saison'],
                spieltag=run['spieltag'],
                typ=typ,
            ))

    FinanceMatchdayRun.objects.bulk_create(neue_zeilen, ignore_conflicts=True)


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0135_financetransaction_referenz_mw'),
    ]

    operations = [
        migrations.AddField(
            model_name='financematchdayrun',
            name='typ',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Buchungstyp-Guard (leer = Haupt-Zeitstempel-Anker; '
                    'TV_SOCKEL / SPONSOR / TICKET / GEHALT / STADION / BETRIEB = Schritt-Marker).'
                ),
                max_length=30,
                verbose_name='Buchungstyp',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='financematchdayrun',
            unique_together={('club', 'saison', 'spieltag', 'typ')},
        ),
        migrations.RunPython(_create_typ_marker, reverse_code=_noop),
    ]
