"""
merge_split_players

Findet und führt "geteilte Identitäten" zusammen: zwei ``Player``-Datensätze, die
dieselbe reale Person beschreiben (gleicher normalisierter Name + identisches
Geburtsdatum), aber sich **ergänzende** externe IDs tragen (z. B. einer mit
``fm_inside_id``, der andere mit ``transfermarkt_id``).

Solche Paare entstehen, wenn ein Import beide IDs nicht auf einen Datensatz
schreiben konnte, ohne mit dem Zwilling auf einem Unique-Constraint
(``fm_inside_id`` / ``transfermarkt_id``) zu kollidieren (siehe HSV-Import,
Task #542). Sehr wahrscheinlich existieren weitere solche Dubletten aus früheren
Importen.

Merge-Logik:
    * Kanonisch bleibt der Datensatz mit mehr abhängigen Daten (Edit-Logs,
      Quell-Ratings, Saison-Statistiken, externe IDs, Vereinszugehörigkeit …).
    * Alle abhängigen Datensätze (Reverse-FKs / O2O) des Zwillings werden auf den
      kanonischen Datensatz umgehängt. Kollidiert dabei eine Zeile mit einem
      bereits vorhandenen Unique-Constraint des kanonischen Datensatzes, bleibt
      die kanonische Zeile erhalten und die des Zwillings wird verworfen.
    * Externe Skalar-IDs (fm_inside_id, transfermarkt_id, api_football_id,
      wsc_player_id) sowie Profil-URLs werden auf den kanonischen Datensatz
      übertragen, sofern dort leer.
    * Der Zwilling wird gelöscht; das Stärkeprofil des kanonischen Datensatzes
      wird neu berechnet und ein System-Edit-Log dokumentiert den Merge.

Usage:
    python manage.py merge_split_players              # Dry-Run (sicher, Default)
    python manage.py merge_split_players --apply      # führt den Merge aus
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from game.club_import.normalization import normalize_name
from game.models import Player, PlayerEditLog

# Eindeutige externe Skalar-IDs, die eine reale Person identifizieren.
# Bei Übereinstimmung in EINER dieser Kennungen (beide gesetzt) handelt es sich
# um VERSCHIEDENE Personen → kein Merge.
EXTERNAL_SCALAR_FIELDS = ['fm_inside_id', 'transfermarkt_id', 'api_football_id']

# Felder, die vom Zwilling übernommen werden, falls beim kanonischen Datensatz
# leer (None / '').
COPY_IF_EMPTY_FIELDS = [
    'fm_inside_id', 'transfermarkt_id', 'api_football_id', 'wsc_player_id',
    'transfermarkt_profile_url', 'transfermarkt_market_value_url',
    'height_cm', 'strong_foot', 'shirt_number', 'nationalities', 'nt_nationality',
]


def _identity_set(player):
    """Menge externer IDs eines Spielers als ``(kind, value)``-Tupel.

    Enthält die Skalar-IDs (fm/tm/af) sowie alle ``PlayerExternalId``-Einträge
    (z. B. CMTracker) über deren Quell-Code.
    """
    ids = set()
    for kind, field in [
        ('fm', 'fm_inside_id'),
        ('tm', 'transfermarkt_id'),
        ('af', 'api_football_id'),
    ]:
        value = getattr(player, field)
        if value:
            ids.add((kind, value))
    for code, ext in player.external_ids.values_list('source__code', 'external_id'):
        ids.add((code, ext))
    return ids


def _id_kinds(identity_set):
    return {kind for kind, _ in identity_set}


def is_split_pair(a, b):
    """True, wenn ``a`` und ``b`` eine geteilte Identität sind.

    Bedingungen:
        * Beide tragen mindestens eine externe ID.
        * Keine ID-Art (fm/tm/af/sofifa …) ist bei beiden gesetzt
          (sonst verschiedene Personen).
        * Jeder Datensatz trägt mindestens eine ID, die der andere nicht hat
          (echte Ergänzung, kein reines Duplikat).
    """
    set_a = _identity_set(a)
    set_b = _identity_set(b)
    if not set_a or not set_b:
        return False
    kinds_a = _id_kinds(set_a)
    kinds_b = _id_kinds(set_b)
    if kinds_a & kinds_b:  # gleiche ID-Art bei beiden → Konflikt
        return False
    if not (set_a - set_b) or not (set_b - set_a):
        return False
    return True


def _dependent_count(player):
    """Zählt alle abhängigen Datensätze (Reverse-FKs / O2O) eines Spielers."""
    total = 0
    for rel in player._meta.related_objects:
        accessor = rel.get_accessor_name()
        if rel.one_to_one:
            try:
                getattr(player, accessor)
                total += 1
            except rel.related_model.DoesNotExist:
                pass
            except Exception:
                pass
        else:
            try:
                total += getattr(player, accessor).count()
            except Exception:
                pass
    return total


def _choose_canonical(a, b):
    """Wählt den zu behaltenden (kanonischen) Datensatz und den Zwilling.

    Priorität: mehr abhängige Daten → hat aktuellen Verein → niedrigere PK
    (älter).
    """
    count_a = _dependent_count(a)
    count_b = _dependent_count(b)
    if count_a != count_b:
        return (a, b) if count_a > count_b else (b, a)
    has_club_a = a.club_id is not None
    has_club_b = b.club_id is not None
    if has_club_a != has_club_b:
        return (a, b) if has_club_a else (b, a)
    return (a, b) if a.pk <= b.pk else (b, a)


def _id_summary(player):
    parts = []
    for label, field in [
        ('fm', 'fm_inside_id'),
        ('tm', 'transfermarkt_id'),
        ('af', 'api_football_id'),
        ('wsc', 'wsc_player_id'),
    ]:
        value = getattr(player, field)
        if value:
            parts.append(f'{label}={value}')
    for code, ext in player.external_ids.values_list('source__code', 'external_id'):
        parts.append(f'{code}={ext}')
    return ', '.join(parts) or '—'


def merge_players(canonical, twin):
    """Führt ``twin`` in ``canonical`` zusammen. Erwartet eigene Transaktion."""
    # 1. Abhängige Datensätze umhängen.
    for rel in twin._meta.related_objects:
        field_name = rel.field.name
        related_model = rel.related_model
        rows = list(related_model.objects.filter(**{field_name: twin}))
        for obj in rows:
            setattr(obj, field_name, canonical)
            try:
                with transaction.atomic():
                    obj.save()
            except IntegrityError:
                # Kollision mit vorhandenem Unique-Constraint des kanonischen
                # Datensatzes → Zwillingszeile verwerfen.
                related_model.objects.filter(pk=obj.pk).delete()

    # 2. Skalar-IDs / Profilfelder sichern, bevor der Zwilling gelöscht wird.
    twin_values = {f: getattr(twin, f) for f in COPY_IF_EMPTY_FIELDS}
    twin_label = f'{twin.full_name} (#{twin.pk})'
    twin_ids = _id_summary(twin)

    # 3. Zwilling löschen → gibt die Unique-Constraints auf Player frei.
    twin.delete()

    # 4. Fehlende Felder vom Zwilling übernehmen.
    changed = []
    for field in COPY_IF_EMPTY_FIELDS:
        current = getattr(canonical, field)
        new_value = twin_values[field]
        if (current is None or current == '') and new_value not in (None, ''):
            setattr(canonical, field, new_value)
            changed.append(field)
    if changed:
        canonical.save(update_fields=changed)

    # 5. Stärkeprofil neu berechnen (kann durch übernommene Ratings/IDs steigen).
    try:
        from game.club_import.import_service import _recalculate_strength
        _recalculate_strength(canonical)
    except Exception:
        pass

    # 6. Merge dokumentieren.
    PlayerEditLog.objects.create(
        player=canonical,
        changed_by=None,
        category=PlayerEditLog.CATEGORY_SYSTEM,
        summary=(
            f'Geteilte Identität zusammengeführt: {twin_label} entfernt, '
            f'IDs/Daten übernommen ({twin_ids}).'
        ),
    )
    return changed


class Command(BaseCommand):
    help = (
        'Findet doppelte Spieler-Datensätze mit geteilter Identität '
        '(gleicher Name + Geburtsdatum, sich ergänzende IDs) und führt sie '
        'zusammen. Dry-Run per Default.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Merge tatsächlich ausführen (ohne Flag nur Dry-Run-Vorschau).',
        )

    def handle(self, *args, **options):
        do_apply = options['apply']

        # Spieler mit Geburtsdatum gruppieren nach (normalisierter Name, DOB).
        groups = defaultdict(list)
        for player in Player.objects.filter(date_of_birth__isnull=False):
            key_name = normalize_name(player.full_name)
            if not key_name:
                continue
            groups[(key_name, player.date_of_birth)].append(player)

        pairs = []
        ambiguous = []
        for (key_name, dob), members in groups.items():
            if len(members) < 2:
                continue
            if len(members) > 2:
                ambiguous.append((key_name, dob, members))
                continue
            a, b = members
            if is_split_pair(a, b):
                canonical, twin = _choose_canonical(a, b)
                pairs.append((canonical, twin))

        if ambiguous:
            self.stdout.write(self.style.WARNING(
                f'\n{len(ambiguous)} mehrdeutige Gruppe(n) mit >2 gleichnamigen '
                'Datensätzen (gleiches Geburtsdatum) — manuelle Prüfung nötig, '
                'übersprungen:'
            ))
            for key_name, dob, members in ambiguous:
                names = ', '.join(f'{m.full_name} (#{m.pk})' for m in members)
                self.stdout.write(f'  [{dob}] {names}')

        if not pairs:
            self.stdout.write(self.style.SUCCESS(
                '\nKeine geteilten Identitäten zum Zusammenführen gefunden.'
            ))
            return

        self.stdout.write(
            f'\n{len(pairs)} geteilte Identität(en) gefunden:'
        )
        for canonical, twin in pairs:
            self.stdout.write(
                f'\n  • {canonical.full_name} [{canonical.date_of_birth}]'
            )
            self.stdout.write(
                f'      BEHALTEN  #{canonical.pk}: {_id_summary(canonical)} '
                f'({_dependent_count(canonical)} abh. Datensätze)'
            )
            self.stdout.write(
                f'      ENTFERNEN #{twin.pk}: {_id_summary(twin)} '
                f'({_dependent_count(twin)} abh. Datensätze)'
            )

        if not do_apply:
            self.stdout.write(self.style.WARNING(
                f'\nDry-Run: {len(pairs)} Paar(e) würden zusammengeführt. '
                'Mit --apply tatsächlich ausführen.'
            ))
            return

        merged = 0
        failed = 0
        for canonical, twin in pairs:
            try:
                with transaction.atomic():
                    merge_players(canonical, twin)
                merged += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  Zusammengeführt: #{twin.pk} → #{canonical.pk} '
                    f'({canonical.full_name})'
                ))
            except Exception as exc:  # noqa: BLE001 — ein Fehler darf den Lauf nicht abbrechen
                failed += 1
                self.stderr.write(self.style.ERROR(
                    f'  Fehler beim Merge #{twin.pk} → #{canonical.pk}: {exc}'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'\nFertig: {merged} zusammengeführt, {failed} fehlgeschlagen.'
        ))
