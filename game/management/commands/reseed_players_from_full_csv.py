"""DB-Reset & Voll-Reimport der Spieler aus dem 116-Spalten-CSV-Export.

Loescht ALLE bestehenden Player (inkl. aller abhaengigen CASCADE-Tabellen),
setzt die Taktik-Aufstellungen (TacticSetup / TacticTemplate JSON) zurueck und
importiert die ~424 Spieler aus der vollen Export-CSV neu.

CSV-Format: 116 Spalten, Trennzeichen Semikolon, UTF-8 mit BOM. Header-Namen
(ws_id, vorname, nachname, ... fm_*, ea_*, ss_*, ...) werden ueber einen
Header-Namen-Map angesprochen, nicht ueber feste Indizes.

Erzeugt pro Zeile:
  - Player (Stammdaten, Positionen, WS-Verein + RL-Verein, Marktwert, Gehalt,
    Vertrag, Leihe, Verletzung/Sperre, IDs, generierte wsc_player_id)
  - PlayerSourceRating EA  (aus ea_*)
  - PlayerSourceRating FM  (aus fm_*)
  - PlayerExternalId(SoFIFA) (sofern sofifa_id vorhanden)
  - PlayerStrengthProfile  (base aus basis_staerke, form_modifier 0 = neutral,
    freshness aus frische) -> base wird danach per Engine neu berechnet
  - PlayerMarketValueSnapshot (aus marktwert, update_current=False)
  - PlayerRLFormProfile    (neutral, Defaults; api_football_id fehlt in CSV)
  - PlayerSeasonStat       (nur wenn ss_* befuellt)
  - PlayerTransferHistory  (nur wenn transfer_* befuellt)

Nach dem Import werden die Spielstaerken ueber calculate_player_strengths neu
berechnet (form_modifier/freshness bleiben erhalten).
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from game.models import (
    Club,
    DataSource,
    Player,
    PlayerExternalId,
    PlayerMarketValueSnapshot,
    PlayerRLFormProfile,
    PlayerSeasonStat,
    PlayerSourceRating,
    PlayerStrengthProfile,
    PlayerTransferHistory,
    TacticSetup,
    TacticTemplate,
)
from game.tactics import default_bench, default_lineup, default_substitutions

DEFAULT_CSV = (
    'attached_assets/spieler_mit_tm_fmi_sofifa_1781099498576.csv'
)

# Attribut-Spalten (ohne ea_/fm_ Praefix) = Feldnamen auf PlayerSourceRating.
ATTR_COLUMNS = [
    'tempo', 'ausdauer', 'kraft', 'technik', 'dribbling', 'passspiel',
    'flanken', 'abschluss', 'kopfball', 'zweikampf', 'defensivstellung',
    'uebersicht', 'teamwork', 'ecken', 'freistoss', 'elfmeter',
    'tw_reflexe', 'tw_fangsicherheit', 'tw_eins_gegen_eins',
    'tw_stellungsspiel', 'tw_passen',
]

VALID_POSITIONS = {code for code, _ in Player.POSITION_CHOICES}
VALID_FEET = {'L', 'R', 'B'}
VALID_LOAN = {'none', 'loaned_in', 'loaned_out'}


class Command(BaseCommand):
    help = (
        'Loescht alle Spieler und importiert die ~424 Spieler aus dem vollen '
        '116-Spalten-CSV-Export neu.'
    )

    def add_arguments(self, parser):
        parser.add_argument('csv_path', nargs='?', default=DEFAULT_CSV)
        parser.add_argument(
            '--confirm', action='store_true',
            help='Bestaetigt das unwiderrufliche Loeschen aller Spieler.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Parst die CSV und zeigt eine Bilanz, ohne in die DB zu '
                 'schreiben (kein Loeschen, kein Import).',
        )
        parser.add_argument(
            '--skip-recalculate', action='store_true',
            help='Spielstaerken nach dem Import NICHT neu berechnen.',
        )

    # ── Parsing-Helfer ───────────────────────────────────────────────────
    @staticmethod
    def _int(raw, lo=None, hi=None):
        raw = (raw or '').strip()
        if not raw:
            return None
        try:
            val = int(float(raw.replace(',', '.')))
        except ValueError:
            return None
        if lo is not None and val < lo:
            val = lo
        if hi is not None and val > hi:
            val = hi
        return val

    @staticmethod
    def _decimal(raw):
        raw = (raw or '').strip().replace(',', '.')
        if not raw:
            return None
        try:
            return Decimal(raw)
        except InvalidOperation:
            return None

    @staticmethod
    def _date(raw):
        raw = (raw or '').strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None

    @staticmethod
    def _bool(raw):
        return (raw or '').strip().lower() in {'1', 'true', 'wahr', 'ja', 'yes'}

    @staticmethod
    def _pos(raw):
        raw = (raw or '').strip()
        return raw if raw in VALID_POSITIONS else ''

    def handle(self, *args, **options):
        import csv

        csv_path = options['csv_path']
        dry_run = options['dry_run']

        if not dry_run and not options['confirm']:
            raise CommandError(
                'Dieser Befehl loescht ALLE Spieler unwiderruflich. '
                'Zum Ausfuehren --confirm setzen (oder --dry-run zum Testen).'
            )

        try:
            with open(csv_path, encoding='utf-8-sig', newline='') as fh:
                reader = csv.reader(fh, delimiter=';')
                header = next(reader)
                rows = [r for r in reader if any(c.strip() for c in r)]
        except FileNotFoundError:
            raise CommandError(f'CSV nicht gefunden: {csv_path}')

        col = {name.strip().lstrip('\ufeff'): idx for idx, name in enumerate(header)}

        def cell(row, name):
            idx = col.get(name)
            if idx is None or idx >= len(row):
                return ''
            return row[idx].strip()

        # Pflichtspalten pruefen
        required = ['vorname', 'nachname', 'alter', 'position', 'ws_club_id',
                    'fm_inside_id', 'ea_rating', 'fm_rating', 'marktwert']
        missing = [c for c in required if c not in col]
        if missing:
            raise CommandError(f'CSV-Header fehlen Spalten: {missing}')

        # Club-Lookups
        clubs_by_id = {c.id: c for c in Club.objects.all()}
        clubs_by_name = {c.name: c for c in Club.objects.all()}

        self.stdout.write(f'CSV: {csv_path} — {len(rows)} Datenzeilen.')

        if dry_run:
            self._dry_run_report(rows, cell, clubs_by_id, clubs_by_name)
            return

        sofifa_ds, _ = DataSource.objects.get_or_create(
            code=DataSource.CODE_SOFIFA, defaults={'name': 'SoFIFA'})
        tm_ds, _ = DataSource.objects.get_or_create(
            code=DataSource.CODE_TRANSFERMARKT, defaults={'name': 'Transfermarkt'})
        today = timezone.localdate()

        with transaction.atomic():
            # 1) Loeschen
            deleted = Player.objects.count()
            Player.objects.all().delete()
            self.stdout.write(self.style.WARNING(
                f'{deleted} Spieler (+ abhaengige CASCADE-Daten) geloescht.'))

            # 2) Taktik-Aufstellungen zuruecksetzen (JSON-IDs sind tot)
            for model in (TacticSetup, TacticTemplate):
                model.objects.all().update(
                    lineup=default_lineup(),
                    bench=default_bench(),
                    substitutions=default_substitutions(),
                )
            TacticSetup.objects.all().update(is_confirmed=False, confirmed_at=None)
            self.stdout.write('Taktik-Aufstellungen zurueckgesetzt.')

            # 3) Import
            created = 0
            warnings = []
            for line_no, row in enumerate(rows, start=2):
                try:
                    created += self._import_row(
                        row, cell, line_no, clubs_by_id, clubs_by_name,
                        sofifa_ds, tm_ds, today, warnings,
                    )
                except Exception as exc:  # noqa: BLE001
                    raise CommandError(
                        f'Zeile {line_no} ({cell(row, "vorname")} '
                        f'{cell(row, "nachname")}): {exc}'
                    )

        self.stdout.write(self.style.SUCCESS(f'{created} Spieler importiert.'))
        for w in warnings:
            self.stdout.write(self.style.WARNING(f'  ⚠ {w}'))

        if not options['skip_recalculate']:
            self.stdout.write('Berechne Spielstaerken neu …')
            call_command('calculate_player_strengths')

        self.stdout.write(self.style.SUCCESS('Fertig.'))

    # ── Eine Zeile importieren ───────────────────────────────────────────
    def _import_row(self, row, cell, line_no, clubs_by_id, clubs_by_name,
                    sofifa_ds, tm_ds, today, warnings):
        c = lambda name: cell(row, name)  # noqa: E731

        # Verein (per ID, am verlaesslichsten)
        club = None
        club_id = self._int(c('ws_club_id'))
        if club_id is not None:
            club = clubs_by_id.get(club_id)
            if club is None:
                warnings.append(
                    f'Zeile {line_no}: ws_club_id {club_id} unbekannt — ohne Verein.')

        rl_club = clubs_by_name.get(c('echtleben_club')) if c('echtleben_club') else None

        # Positionen (Spec: position/hauptposition -> main_position_1;
        # pos_neben_1/2/3 -> secondary_position_1/2/3)
        position = self._pos(c('position'))
        sec_1 = self._pos(c('pos_neben_1'))
        sec_2 = self._pos(c('pos_neben_2'))
        sec_3 = self._pos(c('pos_neben_3'))

        # IDs
        fm_inside_id = self._int(c('fm_inside_id'))
        wsc_id = f'WSC-{fm_inside_id}' if fm_inside_id else f'WSC-L{line_no}'

        # potential (Player.potential): bevorzugt FM, sonst EA, sonst Default
        pot = self._int(c('fm_potential'), 0, 100)
        if pot is None:
            pot = self._int(c('ea_potential'), 0, 100)
        if pot is None:
            pot = 50

        strong_foot = c('fuss') if c('fuss') in VALID_FEET else ''
        loan_status = c('leihstatus') if c('leihstatus') in VALID_LOAN else 'none'

        player = Player.objects.create(
            first_name=c('vorname'),
            last_name=c('nachname'),
            wsc_player_id=wsc_id,
            fm_inside_id=fm_inside_id,
            transfermarkt_id=self._int(c('transfermarkt_id')),
            api_football_id=None,
            date_of_birth=self._date(c('geburtsdatum')),
            nationalities=c('nationalitaet')[:150],
            nt_nationality=c('nt_nationalitaet')[:60],
            age=self._int(c('alter')) or 0,
            height_cm=self._int(c('groesse_cm')),
            strong_foot=strong_foot,
            shirt_number=self._int(c('trikot_nr')),
            position=position,
            primary_position=position,
            main_position_1=position,
            secondary_position_1=sec_1,
            secondary_position_2=sec_2,
            secondary_position_3=sec_3,
            potential=pot,
            market_value=self._decimal(c('marktwert')) or Decimal('0'),
            salary_per_match=self._decimal(c('gehalt_pro_spiel')) or Decimal('0'),
            contract_until=self._date(c('vertrag_bis')),
            club=club,
            real_life_club=rl_club,
            ws_injury_type=c('verletzt_typ')[:120],
            ws_injury_days_remaining=self._int(c('verletzt_tage_rest')) or 0,
            ws_suspension_reason=c('gesperrt_grund')[:120],
            ws_suspension_matches_remaining=self._int(c('gesperrt_spiele_rest')) or 0,
            loan_status=loan_status,
            loan_until=self._date(c('leihe_bis')),
            is_on_transfer_list=self._bool(c('auf_transferliste')),
            is_on_loan_list=self._bool(c('auf_leihliste')),
        )

        # Quellen-Ratings EA + FM
        self._create_source_rating(player, c, 'ea', PlayerSourceRating.SOURCE_EA)
        self._create_source_rating(player, c, 'fm', PlayerSourceRating.SOURCE_FM)

        # Externe SoFIFA-ID
        sofifa_id = c('sofifa_id')
        if sofifa_id:
            PlayerExternalId.objects.create(
                player=player, source=sofifa_ds, external_id=sofifa_id)

        # Staerkeprofil (base wird spaeter per Engine neu berechnet;
        # form_modifier neutral 0, freshness aus CSV erhalten)
        PlayerStrengthProfile.objects.create(
            player=player,
            base_strength=self._decimal(c('basis_staerke')) or Decimal('50.00'),
            form_modifier=Decimal('0.00'),
            freshness=self._decimal(c('frische')) or Decimal('100.00'),
        )

        # RL-Form: neutral (Defaults, kein API-Mapping)
        PlayerRLFormProfile.objects.create(player=player)

        # Marktwert-Snapshot (kein Ueberschreiben von Player-Werten)
        mv = self._decimal(c('marktwert'))
        if mv is not None:
            PlayerMarketValueSnapshot.objects.create(
                player=player,
                source=tm_ds,
                recorded_at=self._date(c('mv_datum')) or today,
                value_eur=mv,
                update_current=False,
            )

        # Saison-Statistik (nur wenn vorhanden)
        if c('ss_saison'):
            PlayerSeasonStat.objects.create(
                player=player,
                season=c('ss_saison')[:20],
                matches=self._int(c('ss_spiele')) or 0,
                goals=self._int(c('ss_tore')) or 0,
                assists=self._int(c('ss_assists')) or 0,
                minutes_played=self._int(c('ss_minuten')) or 0,
                average_grade=self._decimal(c('ss_schnitt_note')),
                yellow_cards=self._int(c('ss_gelbe')) or 0,
                red_cards=self._int(c('ss_rote')) or 0,
            )

        # Transfer-Historie (nur wenn vorhanden)
        if c('transfer_datum'):
            PlayerTransferHistory.objects.create(
                player=player,
                transfer_date=self._date(c('transfer_datum')) or today,
                from_club=clubs_by_name.get(c('transfer_von')),
                to_club=clubs_by_name.get(c('transfer_nach')),
                fee_eur=self._decimal(c('transfer_fee_eur')),
            )

        return 1

    def _create_source_rating(self, player, c, prefix, source):
        rating = self._int(c(f'{prefix}_rating'), 0, 100)
        if rating is None:
            return
        data = {
            'rating': rating,
            'potential': self._int(c(f'{prefix}_potential'), 0, 100),
        }
        for attr in ATTR_COLUMNS:
            val = self._int(c(f'{prefix}_{attr}'), 0, 99)
            if val is not None:
                data[attr] = val
        PlayerSourceRating.objects.create(player=player, source=source, **data)

    # ── Dry-Run-Bilanz ───────────────────────────────────────────────────
    def _dry_run_report(self, rows, cell, clubs_by_id, clubs_by_name):
        per_club = {}
        bad_club = 0
        ea = fm = ss = tr = 0
        for row in rows:
            cid = self._int(cell(row, 'ws_club_id'))
            club = clubs_by_id.get(cid) if cid is not None else None
            if club is None:
                bad_club += 1
            else:
                per_club[club.name] = per_club.get(club.name, 0) + 1
            if cell(row, 'ea_rating'):
                ea += 1
            if cell(row, 'fm_rating'):
                fm += 1
            if cell(row, 'ss_saison'):
                ss += 1
            if cell(row, 'transfer_datum'):
                tr += 1
        self.stdout.write(self.style.WARNING('── DRY-RUN: nichts geschrieben ──'))
        self.stdout.write(f'Spieler gesamt: {len(rows)}')
        self.stdout.write(f'EA-Ratings: {ea} | FM-Ratings: {fm} | '
                          f'Saison-Stats: {ss} | Transfers: {tr}')
        if bad_club:
            self.stdout.write(self.style.ERROR(
                f'Zeilen mit unbekanntem ws_club_id: {bad_club}'))
        self.stdout.write('Kadergroessen:')
        for name in sorted(per_club):
            self.stdout.write(f'  {per_club[name]:>3}  {name}')
