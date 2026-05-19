from django.db import migrations


def clear_seeded_partner_clubs(apps, schema_editor):
    Club = apps.get_model('game', 'Club')
    ClubPublicProfile = apps.get_model('game', 'ClubPublicProfile')

    bayern = Club.objects.filter(fm_inside_id=915).first()
    dortmund = Club.objects.filter(fm_inside_id=907).first()
    if not bayern or not dortmund:
        return

    ClubPublicProfile.objects.filter(
        club=bayern,
        partner_club=dortmund,
    ).update(partner_club=None)
    ClubPublicProfile.objects.filter(
        club=dortmund,
        partner_club=bayern,
    ).update(partner_club=None)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0026_seed_public_club_profiles'),
    ]

    operations = [
        migrations.RunPython(clear_seeded_partner_clubs, noop_reverse),
    ]
