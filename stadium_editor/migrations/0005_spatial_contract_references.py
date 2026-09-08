"""Add immutable spatial baselines and complete historical V2 contracts."""

from copy import deepcopy

from django.db import migrations


def upgrade(apps, schema_editor):
    from stadium_editor.capacity import distribute_capacities
    from stadium_editor.contracts import hydrate_design
    from stadium_editor.seed import _key, load_blueprints

    Geometry = apps.get_model('stadium_editor', 'StadiumGeometry')
    Design = apps.get_model('stadium_editor', 'StadiumDesign')
    blueprints = load_blueprints()

    for row in Geometry.objects.select_related('stadium__club').all():
        changed = False
        geometry = deepcopy(row.geometry)
        blueprint = blueprints.get(_key(row.stadium.club.name))
        blueprint_blocks = {
            block.get('id'): block for block in (blueprint or {}).get('blocks', [])
            if isinstance(block, dict)
        }
        for block in geometry.get('blocks', []) if isinstance(geometry, dict) else []:
            if not isinstance(block, dict):
                continue
            blueprint_source = blueprint_blocks.get(block.get('id'), block)
            for reference, source_key in (
                ('reference_rows', 'rows'), ('reference_quad', 'quad'),
                ('reference_z0', 'z0'), ('reference_z1', 'z1'),
            ):
                if reference not in block:
                    block[reference] = deepcopy(blueprint_source.get(source_key)
                                                if isinstance(blueprint_source, dict)
                                                else block.get(source_key))
                    changed = True
        if changed:
            row.geometry = geometry
            row.save(update_fields=['geometry', 'updated_at'])

    for design in Design.objects.select_related('stadium').all():
        if not isinstance(design.design, dict) or design.design.get('version') != 2:
            continue
        try:
            row = Geometry.objects.get(stadium_id=design.stadium_id)
            complete = hydrate_design(
                design.design, distribute_capacities(design.stadium, row.geometry),
                design.stadium.name, getattr(design, 'blickrichtung', 'NORD'))
        except (Geometry.DoesNotExist, ValueError, TypeError):
            continue
        if complete != design.design:
            design.design = complete
            design.blickrichtung = complete['blickrichtung']
            design.save(update_fields=['design', 'blickrichtung', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [('stadium_editor', '0004_upgrade_design_contract_v2')]

    operations = [migrations.RunPython(upgrade, migrations.RunPython.noop)]