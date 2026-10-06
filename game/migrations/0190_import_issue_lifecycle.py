from collections import defaultdict
import hashlib

from django.db import migrations, models
import django.db.models.deletion


def carry_forward(apps, schema_editor):
    Issue = apps.get_model("game", "ImportIssue")
    groups = defaultdict(list)
    for row in Issue.objects.using(schema_editor.connection.alias).select_related("package").all():
        if row.package.club_id is None:
            raise RuntimeError("Import issue has no club; migration cannot invent a club.")
        groups[(row.package.club_id, row.entity, row.entity_ref, row.field)].append(row)
    for key, rows in groups.items():
        for row in rows:
            row.club_id = key[0]
            row.last_seen_package_id = row.package_id
            row.subkey = hashlib.sha256(row.note.encode()).hexdigest() if len(rows) > 1 else ""
            row.save(using=schema_editor.connection.alias,
                     update_fields=["club", "last_seen_package", "subkey"])


class Migration(migrations.Migration):
    dependencies = [("game", "0189_import_package_review_pool")]
    operations = [
        migrations.AddField(model_name="importissue", name="club",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name="import_issues", to="game.club")),
        migrations.AddField(model_name="importissue", name="last_seen_package",
            field=models.ForeignKey(null=True, blank=True, related_name="+",
                on_delete=django.db.models.deletion.SET_NULL, to="game.sourceimportrun")),
        migrations.AddField(model_name="importissue", name="subkey",
            field=models.CharField(max_length=64, blank=True, default="")),
        migrations.AddField(model_name="importissue", name="manual_value",
            field=models.JSONField(null=True, blank=True)),
        migrations.RunPython(carry_forward, migrations.RunPython.noop),
        migrations.AlterField(model_name="importissue", name="club",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name="import_issues", to="game.club")),
        migrations.AlterField(model_name="importissue", name="resolution_status",
            field=models.CharField(max_length=20, default="open", choices=[
                ("open", "Open"), ("resolved", "Von Hand erledigt"),
                ("package", "Durch neues Paket erledigt")])),
        migrations.AddConstraint(model_name="importissue", constraint=models.UniqueConstraint(
            fields=("club", "entity", "entity_ref", "field", "subkey"),
            name="unique_club_issue_subkey")),
    ]
