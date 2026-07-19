"""Altdaten-Übernahme ins FinanceTransaction-Ledger (Spec Kap. 12.1).

1. Kopiert alle ClubFinancialTransaction-Zeilen als Ledger-Buchungen
   (Typ-Mapping wie game.finance.LEGACY_CATEGORY_TO_TYP; Scouting-
   Beschreibungen unter 'sonstige_ausgabe' werden als SCOUTING erkannt).
2. Bucht je Verein eine KORREKTUR_ADMIN-Eröffnungsbuchung, sodass
   Ledger-Summe == Club.budget (Konto-Cache) gilt.

Das Alt-Modell bleibt vorerst bestehen (Lesepfad alter Ansichten);
geschrieben wird nur noch ins neue Ledger.
"""
from decimal import Decimal

from django.db import migrations

LEGACY_CATEGORY_TO_TYP = {
    'ticketverkauf':     'TICKET',
    'sponsor':           'SPONSOR_FIX',
    'tv_gelder':         'TV_SOCKEL',
    'transfer_einnahme': 'TRANSFER_EIN',
    'leih_einnahme':     'TRANSFER_EIN',
    'praemie':           'PRAEMIE_POKAL',
    'sonstige_einnahme': 'KORREKTUR_ADMIN',
    'transfer_ausgabe':  'TRANSFER_AUS',
    'profigehalt':       'GEHALT',
    'jugendgehalt':      'GEHALT',
    'stadionkosten':     'AUSBAU',
    'stadionumfeld':     'UMFELD_AUSBAU',
    'sonstige_ausgabe':  'KORREKTUR_ADMIN',
}

SCOUTING_PREFIXES = ('Scoutingauftrag', 'Ausbau Scoutingbüro')


def _map_typ(category, description):
    if category == 'sonstige_ausgabe' and description.startswith(SCOUTING_PREFIXES):
        return 'SCOUTING'
    return LEGACY_CATEGORY_TO_TYP.get(category, 'KORREKTUR_ADMIN')


def forward(apps, schema_editor):
    Club = apps.get_model('game', 'Club')
    Legacy = apps.get_model('game', 'ClubFinancialTransaction')
    Ledger = apps.get_model('game', 'FinanceTransaction')

    if Ledger.objects.exists():
        return  # Nie doppelt migrieren.

    rows = []
    for old in Legacy.objects.all().order_by('created_at', 'pk').iterator():
        rows.append(Ledger(
            club_id=old.club_id,
            saison=old.season or '',
            typ=_map_typ(old.category, old.description or ''),
            betrag=old.amount,
            referenz_typ=f'legacy:{old.category}',
            referenz_id=old.pk,
            beschreibung=(old.description or '')[:200],
            datum=old.date,
        ))
        if len(rows) >= 500:
            Ledger.objects.bulk_create(rows)
            rows = []
    if rows:
        Ledger.objects.bulk_create(rows)

    # Eröffnungsbuchung je Verein: Konto-Cache = Ledger-Summe herstellen.
    from django.db.models import Sum
    sums = dict(
        Ledger.objects.values_list('club_id')
        .annotate(s=Sum('betrag'))
        .values_list('club_id', 's')
    )
    openings = []
    for club in Club.objects.all().only('id', 'budget'):
        budget = club.budget if club.budget is not None else Decimal('0.00')
        diff = budget - (sums.get(club.pk) or Decimal('0.00'))
        if diff != 0:
            openings.append(Ledger(
                club_id=club.pk,
                saison='0',
                typ='KORREKTUR_ADMIN',
                betrag=diff,
                referenz_typ='migration_opening',
                beschreibung='Eröffnungssaldo (Migration Finanzsystem Phase 1)',
            ))
    if openings:
        Ledger.objects.bulk_create(openings)


def backward(apps, schema_editor):
    Ledger = apps.get_model('game', 'FinanceTransaction')
    Ledger.objects.filter(referenz_typ__startswith='legacy:').delete()
    Ledger.objects.filter(referenz_typ='migration_opening').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0120_seed_economy_parameters'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
