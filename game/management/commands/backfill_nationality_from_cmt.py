"""Management-Command: backfill_nationality_from_cmt

Befüllt Player.nationalities (und optional Player.nt_nationality) für Spieler
ohne Nationalitätsangabe über die CMTracker-API (GET /players/{id}).

Voraussetzungen:
  - CMTRACKER_API_KEY-Secret muss gesetzt sein.
  - Die API ist IP-gebunden (Hetzner-Server). Im Dev-Umfeld kommt 401/403.
  - Alle Ziel-Spieler müssen eine CMT-External-ID haben (PlayerExternalId mit
    DataSource CMTRACKER) — das ist bei allen bekannten 127 Spielern der Fall.

Ablauf:
  1. Spieler ohne nationalities UND nt_nationality ermitteln.
  2. CMT-External-ID (sofifa-Player-ID) aus PlayerExternalId laden.
  3. GET /players/{cmt_id}?db={slug} abrufen.
  4. Nationalität per _dig aus der Antwort extrahieren (info.nation.name,
     info.nationality.label, info.nationality).
  5. Via NATIONALITY_ALIASES ins Deutsche normieren.
  6. Player.nationalities schreiben (--apply erforderlich, Standard: Dry-Run).
     Wenn --set-nt: auch Player.nt_nationality auf ersten Wert setzen.

Optionen:
  --db <slug>     CMTracker-Datenbank-Slug (z. B. fc26, 26062400). Pflicht.
  --apply         Schreibt Änderungen in die Datenbank (Standard: Dry-Run).
  --set-nt        Setzt zusätzlich Player.nt_nationality auf die primäre Nation
                  (nur wenn nt_nationality bisher leer ist).
  --club <Name>   Schränkt auf einen Verein ein (Teilstring, case-insensitive).
  --limit <N>     Verarbeitet maximal N Spieler (zum Test).
  --sleep <s>     Pause in Sekunden zwischen API-Aufrufen (Standard: 0.2).
"""

import time

from django.core.management.base import BaseCommand, CommandError

from game.cmtracker_api import CmtrackerClient, CmtrackerError, _dig
from game.models import (
    NATIONALITY_ALIASES,
    DataSource,
    Player,
    PlayerExternalId,
)


def _extract_nationality(player_data):
    """Zieht Erst- und Zweitnationalität aus einem CMT-API-Spielerobjekt.

    Probiert verschiedene Pfade, die in der CMT-API je nach DB-Slug vorkommen.
    Gibt (primary, secondary) als Strings zurück (leer = nicht gefunden).
    """
    primary = (
        _dig(player_data, 'info.nation.name') or
        _dig(player_data, 'info.nationality.label') or
        _dig(player_data, 'info.nationality') or
        ''
    )
    secondary = (
        _dig(player_data, 'info.secondNation.name') or
        _dig(player_data, 'info.secondnationality.label') or
        _dig(player_data, 'info.secondnationality') or
        ''
    )
    return (
        str(primary).strip() if primary else '',
        str(secondary).strip() if secondary else '',
    )


def _normalize(raw):
    """Normiert einen rohen Nationalitätswert via NATIONALITY_ALIASES.

    Gibt den kanonischen deutschen Namen zurück, oder den Rohwert falls
    kein Alias-Eintrag vorhanden ist.
    """
    if not raw:
        return ''
    key = raw.lower()
    return NATIONALITY_ALIASES.get(key, raw)


class Command(BaseCommand):
    help = (
        'Backfill: nationalities aus CMTracker-API für Spieler ohne Nationalität. '
        'Benötigt --db <slug>. Standard: Dry-Run; --apply zum Schreiben. '
        'API-Zugang erfordert CMTRACKER_API_KEY und korrekte Server-IP (Hetzner).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--db',
            metavar='SLUG',
            default='',
            help='CMTracker-Datenbank-Slug (z. B. fc26, 26062400). Pflicht im Live-Betrieb.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Änderungen in die Datenbank schreiben (Standard: Dry-Run).',
        )
        parser.add_argument(
            '--set-nt',
            action='store_true',
            help='Setzt auch Player.nt_nationality auf die primäre Nation (nur wenn bisher leer).',
        )
        parser.add_argument(
            '--club',
            metavar='NAME',
            default='',
            help='Nur Spieler dieses Vereins verarbeiten (Teilstring, case-insensitive).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Maximalanzahl Spieler (0 = alle).',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.2,
            help='Pause in Sekunden zwischen API-Aufrufen (Standard: 0.2).',
        )

    def handle(self, *args, **options):
        db_slug = options['db'].strip()
        apply = options['apply']
        set_nt = options['set_nt']
        club_filter = options['club'].strip()
        limit = options['limit']
        sleep_s = options['sleep']

        mode = 'APPLY' if apply else 'DRY-RUN'
        self.stdout.write(self.style.WARNING(
            f'backfill_nationality_from_cmt [{mode}]'
            + (f'  db={db_slug}' if db_slug else '')
            + ('  --set-nt' if set_nt else '')
        ))

        qs = (
            Player.objects
            .filter(nationalities='', nt_nationality='')
            .select_related('club')
            .order_by('club__name', 'last_name', 'first_name')
        )
        if club_filter:
            qs = qs.filter(club__name__icontains=club_filter)
        if limit:
            qs = qs[:limit]

        players = list(qs)
        total = len(players)

        if total == 0:
            self.stdout.write(self.style.SUCCESS('Keine Spieler ohne Nationalität gefunden.'))
            return

        self.stdout.write(f'Zu verarbeitende Spieler: {total}')

        cmt_source = DataSource.objects.filter(code=DataSource.CODE_CMTRACKER).first()
        if not cmt_source:
            raise CommandError('DataSource CMTRACKER nicht gefunden.')

        player_ids = [p.id for p in players]
        ext_id_map = {
            ei.player_id: ei.external_id
            for ei in PlayerExternalId.objects.filter(
                player_id__in=player_ids,
                source=cmt_source,
            )
        }

        without_cmt_id = sum(1 for p in players if not ext_id_map.get(p.id))
        if without_cmt_id:
            self.stdout.write(
                self.style.WARNING(
                    f'  {without_cmt_id} Spieler ohne CMT-External-ID — werden übersprungen.'
                )
            )

        try:
            client = CmtrackerClient()
        except CmtrackerError as exc:
            raise CommandError(
                f'CMTracker-Client konnte nicht initialisiert werden: {exc}\n'
                'Bitte CMTRACKER_API_KEY-Secret setzen und auf dem Produktionsserver ausführen.'
            ) from exc

        self.stdout.write('')

        ok = 0
        skipped_no_id = 0
        skipped_no_data = 0
        errors = 0
        consecutive_auth_errors = 0
        _AUTH_ABORT_THRESHOLD = 3
        unknowns = {}

        for player in players:
            cmt_id = ext_id_map.get(player.id)
            if not cmt_id:
                skipped_no_id += 1
                continue

            try:
                data = client.get_player(cmt_id, db=db_slug or None)
                consecutive_auth_errors = 0
            except CmtrackerError as exc:
                err_str = str(exc)
                self.stdout.write(
                    self.style.ERROR(
                        f'  [FEHLER] {player.full_name} (cmt={cmt_id}): {exc}'
                    )
                )
                errors += 1
                if '401' in err_str or '403' in err_str:
                    consecutive_auth_errors += 1
                    if consecutive_auth_errors >= _AUTH_ABORT_THRESHOLD:
                        self.stdout.write(self.style.ERROR(
                            f'\n  Abbruch nach {_AUTH_ABORT_THRESHOLD} aufeinanderfolgenden '
                            'Authentifizierungsfehlern.\n'
                            '  Bitte CMTRACKER_API_KEY-Secret prüfen und auf dem '
                            'Produktionsserver ausführen (API ist IP-gebunden).\n'
                            f'  Verbleibende {total - ok - skipped_no_id - errors - skipped_no_data} '
                            'Spieler wurden nicht verarbeitet.'
                        ))
                        break
                else:
                    consecutive_auth_errors = 0
                if sleep_s:
                    time.sleep(sleep_s)
                continue

            if sleep_s:
                time.sleep(sleep_s)

            raw_primary, raw_secondary = _extract_nationality(data)

            if not raw_primary:
                self.stdout.write(
                    f'  [leer]  {player.full_name} (cmt={cmt_id}): '
                    'keine Nationalität in API-Antwort'
                )
                skipped_no_data += 1
                continue

            primary = _normalize(raw_primary)
            secondary = _normalize(raw_secondary) if raw_secondary else ''

            parts = [primary]
            if secondary and secondary != primary:
                parts.append(secondary)
            nationalities_value = ', '.join(parts)

            if primary not in unknowns and primary not in __import__('game.models', fromlist=['COUNTRY_FLAG_ASSETS']).COUNTRY_FLAG_ASSETS:
                unknowns[primary] = unknowns.get(primary, 0) + 1

            club_label = player.club.name if player.club else '(kein Verein)'
            self.stdout.write(
                f'  {player.full_name} [{club_label}]: '
                f'nationalities={nationalities_value!r}'
                + (f' nt_nationality={primary!r}' if set_nt else '')
            )

            if apply:
                update_fields = ['nationalities']
                player.nationalities = nationalities_value
                if set_nt and not player.nt_nationality:
                    player.nt_nationality = primary
                    update_fields.append('nt_nationality')
                player.save(update_fields=update_fields)

            ok += 1

        self.stdout.write('')
        self.stdout.write('── Ergebnis ────────────────────────────────────────')
        self.stdout.write(
            f'  {"Gesetzt" if apply else "Würden gesetzt"}: {ok}'
        )
        self.stdout.write(f'  Ohne CMT-ID übersprungen: {skipped_no_id}')
        self.stdout.write(f'  Keine Daten in API-Antwort: {skipped_no_data}')
        self.stdout.write(f'  API-Fehler: {errors}')

        if unknowns:
            self.stdout.write(
                self.style.WARNING(
                    f'\n  {len(unknowns)} Nationalitätswerte nicht in COUNTRY_FLAG_ASSETS '
                    '(kein Flag verfügbar):'
                )
            )
            for val, cnt in sorted(unknowns.items(), key=lambda x: -x[1]):
                self.stdout.write(f'    {cnt:>4}×  {val!r}')
            self.stdout.write(
                '  → Diese Werte in NATIONALITY_ALIASES + COUNTRY_FLAG_ASSETS nachtragen.'
            )

        if not apply:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'Dry-Run — keine DB-Änderungen. Mit --apply schreiben.'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('\nBackfill abgeschlossen.'))
