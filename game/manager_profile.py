"""Business rules shared by the private and public manager profile."""

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone


FREE_TITLES = (
    ('quaelix', 'Quälix'),
    ('laptoptrainer', 'Laptoptrainer'),
    ('taktikfuchs', 'Taktikfuchs'),
    ('motivator', 'Motivator'),
    ('kettenraucher', 'Kettenraucher'),
    ('zampano', 'Zampano'),
    ('schleifer', 'Schleifer'),
    ('schlitzohr', 'Schlitzohr'),
    ('konzepttrainer', 'Konzepttrainer'),
    ('grantler', 'Grantler'),
    ('malocher', 'Malocher'),
    ('menschenfaenger', 'Menschenfänger'),
    ('schoenwetter_trainer', 'Schönwetter-Trainer'),
)

# The progress values are intentionally persisted on the manager profile. This
# keeps unlocks permanent even if a club is later released or a statistic is
# recalculated.
UNLOCKABLE_TITLES = (
    ('pokaljaeger', 'Pokaljäger', 'Gewinne deinen ersten Pokal', 'pokalsiege', 1),
    ('serienmeister', 'Serienmeister', 'Gewinne drei Meisterschaften in Folge', 'serienmeisterschaften', 3),
    ('talentschmied', 'Talentschmied', 'Verschiebe einen Jugendspieler zu den Profis', 'jugendspieler_hochgezogen', 1),
    ('weltenbummler', 'Weltenbummler', 'Übernimm deinen dritten Verein', 'vereine', 3),
    ('aufstiegsheld', 'Aufstiegsheld', 'Steige mit einer Mannschaft auf', 'aufstiege', 1),
    ('feuerwehrmann', 'Feuerwehrmann', 'Übernimm auf einem Abstiegsplatz und halte die Klasse', 'rettungen', 1),
    ('underdog', 'Underdog', 'Werde Meister, obwohl das Saisonziel nicht Platz 1–4 war', 'underdog_meisterschaften', 1),
    ('trainer_der_saison', 'Trainer der Saison #N', 'Belege Platz 1 der globalen Saisonrangliste', 'globale_ranglistensiege', 1),
    ('trainer_der_liga', 'Trainer der Liga #N', 'Belege Platz 1 der Saisonrangliste deiner Liga', 'liga_ranglistensiege', 1),
)

TITLE_LABELS = dict(FREE_TITLES) | {
    key: label for key, label, _description, _metric, _target in UNLOCKABLE_TITLES
}
UNLOCKABLE_BY_KEY = {
    key: {
        'key': key,
        'label': label,
        'description': description,
        'metric': metric,
        'target': target,
    }
    for key, label, description, metric, target in UNLOCKABLE_TITLES
}

VISIBILITY_DEFAULTS = {
    'profile_image': 'all',
    'nickname': 'all',
    'title': 'all',
    'trainer_type': 'all',
    'nationality': 'all',
    'favourite_club': 'all',
    'email': 'private',
    'birthday': 'private',
    'residence': 'private',
    'member_since': 'private',
    'last_login': 'private',
}

LOGIN_REWARD_XP = (5, 10, 15, 20, 25, 30, 50)


def award_login_reward(manager):
    """Award one daily login step, once per local calendar day.

    The streak intentionally uses consecutive local dates rather than request
    count. A missed day starts a new track; milestone flags belong to that
    track and are reset with it.
    """
    from .models import Club, ManagerProfile

    today = timezone.localdate()
    with transaction.atomic():
        locked = ManagerProfile.objects.select_for_update().get(pk=manager.pk)
        if locked.login_last_date == today:
            return {
                'streak': locked.login_streak,
                'points_today': locked.login_points_today,
                'next_reward_days': max(0, 8 - min(locked.login_streak, 7)),
            }

        yesterday = today - timedelta(days=1)
        continuing = locked.login_last_date == yesterday
        streak = locked.login_streak + 1 if continuing else 1
        points = LOGIN_REWARD_XP[min(streak, len(LOGIN_REWARD_XP)) - 1]
        award_xp = points
        day14 = locked.login_day14_awarded if continuing else False
        day30 = locked.login_day30_awarded if continuing else False
        money_paid = locked.login_day30_money_paid if continuing else False
        if streak >= 14 and not day14:
            award_xp += 100
            day14 = True
        if streak >= 30 and not day30:
            award_xp += 250
            day30 = True

        locked.login_streak = streak
        locked.login_last_date = today
        locked.login_points_today = award_xp
        locked.login_day14_awarded = day14
        locked.login_day30_awarded = day30
        update_fields = [
            'login_streak', 'login_last_date', 'login_points_today',
            'login_day14_awarded', 'login_day30_awarded', 'updated_at',
        ]
        if streak >= 30 and not money_paid:
            club = Club.objects.filter(managed_by=locked).first()
            if club:
                from .economy.booking import book
                book(
                    club, 'KORREKTUR_ADMIN', 1_000_000,
                    beschreibung='Login-Belohnung · 30-Tage-Serie',
                    referenz_typ='manager_login', referenz_id=locked.pk,
                    pflicht=True,
                )
                locked.login_day30_money_paid = True
                money_paid = True
                update_fields.append('login_day30_money_paid')
        locked.xp = locked.xp + award_xp
        update_fields.append('xp')
        locked.save(update_fields=update_fields)

    manager.login_streak = locked.login_streak
    manager.login_last_date = locked.login_last_date
    manager.login_points_today = locked.login_points_today
    manager.login_day14_awarded = locked.login_day14_awarded
    manager.login_day30_awarded = locked.login_day30_awarded
    manager.login_day30_money_paid = locked.login_day30_money_paid
    manager.xp = locked.xp
    return {
        'streak': locked.login_streak,
        'points_today': locked.login_points_today,
        'next_reward_days': max(0, 8 - min(locked.login_streak, 7)),
    }


def level_threshold(level):
    """Total XP needed to reach *level* (level 1 starts at zero)."""
    level = max(1, int(level))
    if level == 1:
        return 0
    # Level 2 costs 800 XP, and every subsequent level costs 100 more.
    return 800 * (level - 1) + 50 * (level - 2) * (level - 1)


def level_from_xp(xp):
    xp = max(0, int(xp or 0))
    level = 1
    while level_threshold(level + 1) <= xp:
        level += 1
    return level


def xp_progress(manager):
    level = level_from_xp(manager.xp)
    current = manager.xp - level_threshold(level)
    next_cost = level_threshold(level + 1) - level_threshold(level)
    return {
        'level': level,
        'xp': manager.xp,
        'current': max(0, current),
        'next_cost': next_cost,
        'percent': min(100, round(max(0, current) / next_cost * 100)),
        'label': f'{manager.xp:,} XP'.replace(',', '.'),
    }


def merged_visibility(manager):
    values = dict(VISIBILITY_DEFAULTS)
    values.update(manager.visibility_settings or {})
    return values


def is_visible(manager, field_name):
    return merged_visibility(manager).get(field_name, 'private') == 'all'


def title_progress(manager, key):
    unlock = UNLOCKABLE_BY_KEY[key]
    value = (manager.title_progress or {}).get(unlock['metric'], 0)
    if unlock['metric'] == 'saison_score':
        value = max(value, manager.season_score)
    value = int(value or 0)
    return {
        'value': value,
        'target': unlock['target'],
        'percent': min(100, round(value / unlock['target'] * 100)),
    }


@transaction.atomic
def evaluate_titles(manager):
    """Unlock all currently achieved titles without revoking old ones."""
    from .models import ManagerTitle

    progress = manager.title_progress or {}
    for key in UNLOCKABLE_BY_KEY:
        details = title_progress(manager, key)
        if details['value'] >= details['target']:
            _title, created = ManagerTitle.objects.get_or_create(manager=manager, title_key=key)
            if created:
                from .notifications import notify
                notify(
                    manager,
                    f'Titel freigeschaltet: {TITLE_LABELS[key]}',
                    UNLOCKABLE_BY_KEY[key]['description'],
                    '/manager/profil/',
                )
    return set(manager.titles.values_list('title_key', flat=True))


def title_payload(manager):
    unlocked = evaluate_titles(manager)
    from django.db.models import Q
    from .models import ManagerProfile, ManagerTitle
    total_managers = max(1, ManagerProfile.objects.count())
    active_key = manager.active_title or manager.trainer_type
    free = []
    for key, label in FREE_TITLES:
        holder_count = ManagerProfile.objects.filter(
            Q(active_title=key)
            | (Q(active_title='') & Q(trainer_type=key))
        ).count()
        free.append({
            'key': key,
            'label': label,
            'active': key == active_key,
            'manager_percent': round(holder_count / total_managers * 100),
        })
    unlockable = []
    for key, details in UNLOCKABLE_BY_KEY.items():
        holder_count = ManagerTitle.objects.filter(title_key=key).count()
        unlockable.append({
            **details,
            **title_progress(manager, key),
            'unlocked': key in unlocked,
            'active': key == manager.active_title,
            'manager_percent': round(holder_count / total_managers * 100),
        })
    unlockable.sort(
        key=lambda item: (
            not item['unlocked'],
            -item['percent'],
            item['label'],
        )
    )
    return {
        'active_key': active_key,
        'active_label': current_title(manager),
        'free': free,
        'unlockable': unlockable,
        'featured_unlockable': unlockable[:3],
    }


def select_title(manager, key):
    if key not in TITLE_LABELS:
        raise ValueError('Dieser Titel existiert nicht.')
    if key in UNLOCKABLE_BY_KEY and not manager.titles.filter(title_key=key).exists():
        raise ValueError('Dieser Titel ist noch nicht freigeschaltet.')
    manager.active_title = key
    manager.save(update_fields=['active_title', 'updated_at'])
    return TITLE_LABELS[key]


def current_title(manager):
    return TITLE_LABELS.get(manager.active_title) or manager.trainer_type_label


def is_on_vacation(manager, on_date=None, season=None):
    on_date = on_date or date.today()
    blocks = manager.vacation_blocks.filter(
        starts_on__lte=on_date,
        ends_on__gte=on_date,
    ).exclude(
        ended_early_at__lt=on_date,
    )
    if season is not None:
        try:
            blocks = blocks.filter(season=int(season))
        except (TypeError, ValueError):
            return False
    return blocks.exists()


def create_vacation_block(manager, season, starts_on, ends_on):
    """Validate and create one vacation block for a season."""
    if starts_on < date.today():
        raise ValueError('Urlaub muss vor Beginn eingetragen werden.')
    if ends_on < starts_on:
        raise ValueError('Das Enddatum muss nach dem Startdatum liegen.')
    days = (ends_on - starts_on).days + 1
    if days < 5:
        raise ValueError('Ein Urlaubsblock muss mindestens fünf Tage dauern.')
    blocks = list(manager.vacation_blocks.filter(season=season).order_by('starts_on'))
    if len(blocks) >= 2:
        raise ValueError('Pro Saison sind höchstens zwei Urlaubsblöcke möglich.')
    if any(starts_on <= block.effective_end and ends_on >= block.starts_on for block in blocks):
        raise ValueError('Urlaubsblöcke dürfen sich nicht überschneiden.')
    if sum(block.day_count for block in blocks) + days > 14:
        raise ValueError('Pro Saison stehen höchstens 14 Urlaubstage zur Verfügung.')
    return manager.vacation_blocks.create(
        season=season,
        starts_on=starts_on,
        ends_on=ends_on,
    )


def end_vacation_early(block):
    today = date.today()
    if not block.is_active(today):
        raise ValueError('Nur ein laufender Urlaub kann vorzeitig beendet werden.')
    block.ended_early_at = today - timedelta(days=1)
    block.save(update_fields=['ended_early_at'])
    return block


def record_inactivity(manager, club, season, matchday_label, squad_scope='pro'):
    """Record one missed lineup and apply the three-stage sanction ladder."""
    from .models import InactivityRecord, ManagerCareerEntry, ManagerTimelineEntry
    from .notifications import notify

    if is_on_vacation(manager, season=season):
        return None, False
    record, created = InactivityRecord.objects.get_or_create(
        manager=manager,
        club=club,
        squad_scope=squad_scope,
        season=season,
        matchday_label=matchday_label,
    )
    if not created:
        return record, False
    manager.inactivity_season_count = manager.inactivity_records.filter(
        season=season, squad_scope=squad_scope
    ).count()
    manager.inactivity_streak = manager.inactivity_streak + 1
    update_fields = ['inactivity_season_count', 'inactivity_streak', 'updated_at']
    if manager.inactivity_streak >= 2 or manager.inactivity_season_count >= 3:
        manager.transfer_ban_until = date.max
        update_fields.append('transfer_ban_until')
        notify(manager, 'Letzte Warnung: Aufstellung fehlt',
               f'Saison {manager.inactivity_season_count}/5 · in Folge {manager.inactivity_streak}/3. '
               'Die Transfersperre endet mit deiner nächsten eigenen Aufstellung.')
    else:
        notify(manager, 'Aufstellung nicht abgegeben',
               f'Saison {manager.inactivity_season_count}/5 · in Folge {manager.inactivity_streak}/3.')
    if manager.inactivity_streak >= 3 or manager.inactivity_season_count >= 5:
        ManagerCareerEntry.objects.filter(manager=manager, active=True).update(
            active=False, ended_at=date.today(), end_reason='fired'
        )
        club.__class__.objects.filter(pk=club.pk, managed_by=manager).update(managed_by=None)
        ManagerTimelineEntry.objects.get_or_create(
            manager=manager,
            event_date=date.today(),
            category='status',
            title='Entlassung',
            defaults={
                'club': club,
                'club_name': club.name,
                'body': 'Der Verein wurde wegen anhaltender Inaktivität freigegeben.',
                'status': 'approved',
            },
        )
        notify(manager, 'Verein verloren',
               f'{club.name} wurde wegen anhaltender Inaktivität freigegeben.')
    manager.save(update_fields=update_fields)
    return record, True


def reset_inactivity_after_lineup(manager):
    if manager.inactivity_streak or manager.transfer_ban_until:
        manager.inactivity_streak = 0
        manager.transfer_ban_until = None
        manager.save(update_fields=['inactivity_streak', 'transfer_ban_until', 'updated_at'])
