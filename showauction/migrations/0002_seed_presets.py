# Data-Migration: die 5 Start-Presets der Show-Auktion (Spec §3).
#
# Die Configs sind Belegungen der 16 Regel-Achsen und wurden gegen
# showauction.validator.validate_config geprüft (Stand der Anlage).
# Idempotent über update_or_create(slug) — bestehende Creator-Anpassungen
# an name/farbe/regeln werden bei erneutem Lauf überschrieben, deshalb
# läuft die Migration genau einmal; Pflege danach über den Creator.
#
# Coin-Regel (Klärung des offenen Punkts O2, Nutzer-Entscheid):
# Die Bedingung {art: coins} bedeutet VERBRAUCH — 1 Coin Eintritt pro
# Auktion+Manager, atomar mit dem ersten Gebot (Holländisch: beim
# Zuschlag-Klick), kein Refund. Alle Start-Presets setzen 1 Coin.
from django.db import migrations

PRESETS = [
    {
        'slug': 'halte',
        'name': 'Halte-Auktion',
        'color_hex': '#ffd400',
        'sort_order': 10,
        'rules_text': (
            'Offenes Hochbieten mit Haltezeit-Treppe: Nach jedem Gebot muss das '
            'Höchstgebot eine Stufe lang halten (24h → 12h → 6h → 3h → 1h). '
            'Hält es durch, ist der Spieler verkauft. Ohne Gebot platzt die '
            'Auktion nach 24 Stunden. Start bei 60 % des Marktwerts. '
            'Eintritt: 1 Hoeneß-Coin mit deinem ersten Gebot.'
        ),
        'config': {
            'gebotsrichtung': 'aufsteigend',
            'sichtbarkeit': 'hoechstgebot_und_bieter',
            'endebedingung': 'haltezeit',
            'haltezeit_verlauf': {'degressiv': [24, 12, 6, 3, 1]},
            'gebote_pro_manager': 'unbegrenzt',
            'gebot_aenderbar': 'nein',
            'mindesterhoehung': {'max_fix_prozent': {
                'fix': 100000, 'prozent': 5, 'rundung': 50000,
            }},
            'startpreis': {'prozent_mw': 60},
            'zuschlagspreis': 'eigenes_gebot',
            'teilnahmebedingungen': [{'art': 'coins', 'anzahl': 1}],
            'gewinnerermittlung': 'hoechstes_gebot',
            'reservierungsfreigabe': 'bei_ueberbietung',
        },
    },
    {
        'slug': 'undercover',
        'name': 'Undercover-Auktion',
        'color_hex': '#e8392f',
        'sort_order': 20,
        'rules_text': (
            'Verdeckte Gebote, genau eines pro Manager (bis zum Schluss '
            'änderbar). Sichtbar ist nur die Anzahl der Gebote. Nach 3 Tagen '
            'gewinnt das höchste Gebot; bei Gleichstand entscheidet das Los. '
            'Mindestgebot: 60 % des Marktwerts. Eintritt: 1 Hoeneß-Coin.'
        ),
        'config': {
            'gebotsrichtung': 'verdeckt',
            'sichtbarkeit': 'nur_gebotsanzahl',
            'endebedingung': 'deadline',
            'laufzeit_minuten': 4320,
            'gebote_pro_manager': 'genau_1',
            'gebot_aenderbar': 'ja',
            'mindesterhoehung': 'keine',
            'startpreis': {'prozent_mw': 60},
            'zuschlagspreis': 'eigenes_gebot',
            'teilnahmebedingungen': [{'art': 'coins', 'anzahl': 1}],
            'gewinnerermittlung': 'hoechstes_gebot',
            'reservierungsfreigabe': 'bei_auktionsende',
        },
    },
    {
        'slug': 'hollaendisch',
        'name': 'Holländische Auktion',
        'color_hex': '#ff7a1a',
        'sort_order': 30,
        'rules_text': (
            'Der Preis startet bei 200 % des Marktwerts und fällt alle '
            '30 Minuten um 2 Prozentpunkte. Wer zuerst zuschlägt, kauft sofort '
            'zum aktuellen Preis. Erreicht der Preis 50 % des Marktwerts ohne '
            'Zuschlag, platzt die Auktion. Eintritt: 1 Hoeneß-Coin beim Zuschlag.'
        ),
        'config': {
            'gebotsrichtung': 'fallend',
            'sichtbarkeit': 'nichts',
            'endebedingung': 'erster_zuschlag',
            'gebote_pro_manager': 'unbegrenzt',
            'mindesterhoehung': 'keine',
            'startpreis': {'prozent_mw': 200},
            'preisverfall': {
                'schritt_prozent': 2,
                'intervall_minuten': 30,
                'boden_prozent_mw': 50,
            },
            'zuschlagspreis': 'eigenes_gebot',
            'teilnahmebedingungen': [{'art': 'coins', 'anzahl': 1}],
            'gewinnerermittlung': 'erster_zuschlag',
            'reservierungsfreigabe': 'sofortige_buchung',
        },
    },
    {
        'slug': 'bereich',
        'name': 'Bereichsauktion',
        'color_hex': '#f2efe6',
        'sort_order': 40,
        'rules_text': (
            'Verdeckte Gebote, genau eines pro Manager (änderbar). Es gewinnt '
            'NICHT das höchste Gebot, sondern das dichteste an einem verborgenen '
            'Zielbereich zwischen 80 % und 130 % des Marktwerts (Breite: 10 % '
            'des Marktwerts). Liegt kein Gebot im Korridor, platzt die Auktion. '
            'Der Korridor bleibt für immer geheim. Eintritt: 1 Hoeneß-Coin.'
        ),
        'config': {
            'gebotsrichtung': 'verdeckt',
            'sichtbarkeit': 'nur_gebotsanzahl',
            'endebedingung': 'deadline',
            'laufzeit_minuten': 4320,
            'gebote_pro_manager': 'genau_1',
            'gebot_aenderbar': 'ja',
            'mindesterhoehung': 'keine',
            'startpreis': 'frei',
            'zuschlagspreis': 'eigenes_gebot',
            'teilnahmebedingungen': [{'art': 'coins', 'anzahl': 1}],
            'gewinnerermittlung': 'naechstliegend_verborgenes_ziel',
            'korridor': {
                'spanne_min_prozent': 80,
                'spanne_max_prozent': 130,
                'breite_prozent': 10,
            },
            'reservierungsfreigabe': 'bei_auktionsende',
        },
    },
    {
        'slug': 'blitz',
        'name': 'Blitz-Auktion',
        'color_hex': '#ff2d78',
        'sort_order': 50,
        'rules_text': (
            '90 Minuten Vollgas: offenes Hochbieten, jedes Gebot in den letzten '
            '5 Minuten verlängert um 5 Minuten. Start bei 60 % des Marktwerts. '
            'Eintritt: 1 Hoeneß-Coin mit deinem ersten Gebot.'
        ),
        'config': {
            'gebotsrichtung': 'aufsteigend',
            'sichtbarkeit': 'hoechstgebot_und_bieter',
            'endebedingung': 'deadline',
            'laufzeit_minuten': 90,
            'verlaengerung': {'minuten': 5, 'fenster': 5},
            'gebote_pro_manager': 'unbegrenzt',
            'gebot_aenderbar': 'nein',
            'mindesterhoehung': {'max_fix_prozent': {
                'fix': 50000, 'prozent': 3, 'rundung': 50000,
            }},
            'startpreis': {'prozent_mw': 60},
            'zuschlagspreis': 'eigenes_gebot',
            'teilnahmebedingungen': [{'art': 'coins', 'anzahl': 1}],
            'gewinnerermittlung': 'hoechstes_gebot',
            'reservierungsfreigabe': 'bei_ueberbietung',
        },
    },
]


def seed_presets(apps, schema_editor):
    ShowAuctionPreset = apps.get_model('showauction', 'ShowAuctionPreset')
    for p in PRESETS:
        ShowAuctionPreset.objects.update_or_create(
            slug=p['slug'],
            defaults={
                'name': p['name'],
                'color_hex': p['color_hex'],
                'rules_text': p['rules_text'],
                'config': p['config'],
                'is_active': True,
                'sort_order': p['sort_order'],
            },
        )


def unseed_presets(apps, schema_editor):
    ShowAuctionPreset = apps.get_model('showauction', 'ShowAuctionPreset')
    ShowAuctionPreset.objects.filter(
        slug__in=[p['slug'] for p in PRESETS],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('showauction', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_presets, unseed_presets),
    ]
