from django.db import migrations


def link_kirschgutzje_to_user(apps, schema_editor):
    ManagerProfile = apps.get_model('game', 'ManagerProfile')
    User = apps.get_model('auth', 'User')

    try:
        profile = ManagerProfile.objects.get(name='Kirschgutzje')
    except ManagerProfile.DoesNotExist:
        return

    if profile.user_id is not None:
        return

    user = (
        User.objects.filter(username='Kirschgutzje').first()
        or User.objects.filter(is_superuser=True).order_by('id').first()
        or User.objects.order_by('id').first()
    )

    if user is None:
        return

    if ManagerProfile.objects.filter(user=user).exclude(pk=profile.pk).exists():
        return

    profile.user = user
    profile.save(update_fields=['user'])


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0037_seed_manager_career_stations'),
    ]

    operations = [
        migrations.RunPython(link_kirschgutzje_to_user, migrations.RunPython.noop),
    ]
