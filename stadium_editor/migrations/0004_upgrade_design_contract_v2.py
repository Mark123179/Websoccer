"""Upgrade legacy visual streams without ever changing Stadium capacities."""

from django.db import migrations


def upgrade(apps, schema_editor):
    # Importing the contract here is intentional: it has no model dependency
    # and keeps the data migration identical to subsequent V1 saves.
    from stadium_editor.image_validation import normalize_design_payload
    from stadium_editor.seed import load_blueprints, normalise_block_types
    from stadium_editor.capacity import distribute_capacities
    from stadium_editor.contracts import spatial_project_design

    Geometry = apps.get_model('stadium_editor', 'StadiumGeometry')
    Design = apps.get_model('stadium_editor', 'StadiumDesign')
    bvb = load_blueprints().get('borussiadortmund')

    for row in Geometry.objects.select_related('stadium__club').all():
        # Replace the known bad 51-block BVB source with the stable prototype.
        # This only changes visual geometry, never the economic Stadium fields.
        if (bvb and row.stadium.club.name == 'Borussia Dortmund'
                and len(row.geometry.get('blocks', [])) != 52):
            old_raw = row.geometry
            new_raw = normalise_block_types(row.stadium, bvb)
            design = Design.objects.filter(stadium_id=row.stadium_id).first()
            if design:
                old_effective = distribute_capacities(row.stadium, old_raw)
                new_effective = distribute_capacities(row.stadium, new_raw)
                design.design = spatial_project_design(
                    design.design, old_effective, new_effective, row.stadium.name,
                    getattr(design, 'blickrichtung', 'NORD'))
                design.blickrichtung = design.design['blickrichtung']
                design.save(update_fields=['design', 'blickrichtung', 'updated_at'])
            row.geometry = new_raw
            row.save(update_fields=['geometry', 'updated_at'])

    for design in Design.objects.select_related('stadium').all():
        if design.design.get('version') == 2:
            continue
        try:
            row = Geometry.objects.get(stadium_id=design.stadium_id)
            # Match the editor's effective grid exactly: geometry width plus
            # capacity-derived rows, with a base-colour padded final row.
            geometry = distribute_capacities(design.stadium, row.geometry)
            design.design = normalize_design_payload(
                design.design, geometry=geometry, stadium_name=design.stadium.name,
                blickrichtung=getattr(design, 'blickrichtung', 'NORD'),
            )
            design.blickrichtung = design.design['blickrichtung']
            design.save(update_fields=['design', 'blickrichtung', 'updated_at'])
        except (Geometry.DoesNotExist, ValueError):
            # Corrupt historical rows remain untouched rather than being lost.
            continue


class Migration(migrations.Migration):
    dependencies = [('stadium_editor', '0003_stadiumdesign_blickrichtung')]

    operations = [migrations.RunPython(upgrade, migrations.RunPython.noop)]