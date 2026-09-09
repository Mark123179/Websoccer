"""Spread BVB Nord standing capacity over its six lower-tier blocks."""

from copy import deepcopy

from django.db import migrations


def fix_bvb_nord_grid(apps, schema_editor):
    from stadium_editor.capacity import distribute_capacities
    from stadium_editor.contracts import spatial_project_design

    Geometry = apps.get_model('stadium_editor', 'StadiumGeometry')
    Design = apps.get_model('stadium_editor', 'StadiumDesign')
    nord_standing_block_ids = frozenset(range(37, 43))

    rows = Geometry.objects.select_related('stadium__club').filter(
        stadium__club__name='Borussia Dortmund',
    )
    for row in rows:
        blocks = row.geometry.get('blocks', [])
        if {block.get('id') for block in blocks} != set(range(52)):
            continue

        old_raw = deepcopy(row.geometry)
        new_raw = deepcopy(row.geometry)
        changed = False
        for block in new_raw['blocks']:
            block_id = block.get('id')
            if block_id in nord_standing_block_ids:
                desired = 'STEH'
            elif block.get('stand') == 'NORD':
                desired = 'SITZ'
            else:
                continue
            if block.get('type') != desired:
                block['type'] = desired
                changed = True
        if not changed:
            continue

        design = Design.objects.filter(stadium_id=row.stadium_id).first()
        if design and design.design.get('version') == 2:
            old_effective = distribute_capacities(row.stadium, old_raw)
            new_effective = distribute_capacities(row.stadium, new_raw)
            design.design = spatial_project_design(
                design.design,
                old_effective,
                new_effective,
                row.stadium.name,
                getattr(design, 'blickrichtung', 'NORD'),
            )
            design.blickrichtung = design.design['blickrichtung']
            design.save(update_fields=['design', 'blickrichtung', 'updated_at'])

        row.geometry = new_raw
        row.save(update_fields=['geometry', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [('stadium_editor', '0004_upgrade_design_contract_v2')]

    operations = [
        migrations.RunPython(fix_bvb_nord_grid, migrations.RunPython.noop),
    ]