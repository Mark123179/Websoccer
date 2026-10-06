from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver
from game import models as m
from .runtime import package_mode


def ensure_ready(league):
    if package_mode() and m.ImportIssue.objects.filter(
            club__league=league, severity="blocking", resolution_status="open").exists():
        raise ValidationError("Ligastart gesperrt: offene sperrende Arbeitslisteneinträge.")


@receiver(pre_save, sender=m.LeagueSeasonState, dispatch_uid="package_league_start_guard")
def guard_state(sender, instance, **kwargs):
    if package_mode():
        ensure_ready(instance.league)


@receiver(pre_save, sender=m.SeasonFixture, dispatch_uid="package_fixture_start_guard")
def guard_fixture(sender, instance, **kwargs):
    if package_mode():
        ensure_ready(instance.league)
