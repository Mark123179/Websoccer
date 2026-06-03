from django.db import migrations


def seed_demo_loans(apps, schema_editor):
    Player = apps.get_model('game', 'Player')
    Club = apps.get_model('game', 'Club')
    PlayerSeasonStat = apps.get_model('game', 'PlayerSeasonStat')

    def find_club(*names):
        for name in names:
            club = Club.objects.filter(name__icontains=name).first()
            if club:
                return club
        return None

    bayern = find_club('Bayern')
    dortmund = find_club('Dortmund')
    if not bayern or not dortmund:
        return

    season = '2026/27'

    def ensure_season_stat(player, matches, goals, assists, minutes, grade):
        PlayerSeasonStat.objects.update_or_create(
            player=player,
            season=season,
            competition='Liga',
            defaults={
                'season_number': 1,
                'matches': matches,
                'goals': goals,
                'assists': assists,
                'minutes_played': minutes,
                'average_grade': grade,
            },
        )

    # Nico Schlotterbeck — von Dortmund an Bayern ausgeliehen (Geliehen).
    schlotterbeck = (
        Player.objects.filter(last_name__icontains='Schlotterbeck').first()
    )
    if schlotterbeck:
        schlotterbeck.club = bayern
        schlotterbeck.loan_status = 'loaned_in'
        schlotterbeck.loan_partner_club = dortmund
        schlotterbeck.loan_until = '2027-06-30'
        if not schlotterbeck.main_position_1:
            schlotterbeck.main_position_1 = 'IV'
        schlotterbeck.save()
        ensure_season_stat(schlotterbeck, matches=17, goals=1, assists=2,
                           minutes=1488, grade='2.60')

    # Lennart Karl — von Bayern an Dortmund verliehen (Verliehen).
    karl = Player.objects.filter(last_name__icontains='Karl').first()
    if karl:
        karl.club = bayern
        karl.loan_status = 'loaned_out'
        karl.loan_partner_club = dortmund
        karl.loan_until = '2027-06-30'
        if not karl.main_position_1:
            karl.main_position_1 = 'OM'
        karl.save()
        ensure_season_stat(karl, matches=12, goals=3, assists=4,
                           minutes=786, grade='2.90')


def unseed_demo_loans(apps, schema_editor):
    Player = apps.get_model('game', 'Player')
    for last_name in ('Schlotterbeck', 'Karl'):
        for player in Player.objects.filter(last_name__icontains=last_name):
            player.loan_status = 'none'
            player.loan_partner_club = None
            player.loan_until = None
            player.save()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0058_player_loan_partner_club_player_loan_status_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_demo_loans, unseed_demo_loans),
    ]
