from django.db import models

from game.models import Stadium


class StadiumGeometry(models.Model):
    """Server-owned stadium shape and block assignment."""

    stadium = models.OneToOneField(
        Stadium,
        on_delete=models.CASCADE,
        related_name='editor_geometry',
    )
    geometry = models.JSONField(default=dict)
    schema_version = models.PositiveSmallIntegerField(default=1)
    source = models.CharField(max_length=120, blank=True, default='OSM')
    attribution = models.CharField(
        max_length=120,
        default='Blaupause: OpenStreetMap-Daten (ODbL)',
    )
    last_warning = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Stadion-Geometrie'
        verbose_name_plural = 'Stadion-Geometrien'


class StadiumDesign(models.Model):
    """Manager-editable visual layer; deliberately separate from geometry."""

    stadium = models.OneToOneField(
        Stadium,
        on_delete=models.CASCADE,
        related_name='editor_design',
    )
    design = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Stadion-Design'
        verbose_name_plural = 'Stadion-Designs'