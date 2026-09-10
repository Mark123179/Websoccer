from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0170_managerprofile_birth_date'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tacticsetup',
            options={
                'ordering': ['club__name', 'squad_scope', 'context'],
                'verbose_name': 'Taktik',
                'verbose_name_plural': 'Taktiken',
            },
        ),
        migrations.AddField(
            model_name='tacticsetup',
            name='context',
            field=models.CharField(
                choices=[
                    ('pflicht', 'Pflichtspiel'),
                    ('freundschaft', 'Freundschaftsspiel'),
                ],
                default='pflicht',
                max_length=16,
            ),
        ),
        migrations.RemoveConstraint(
            model_name='tacticsetup',
            name='unique_club_tactic_setup_scope',
        ),
        migrations.AddConstraint(
            model_name='tacticsetup',
            constraint=models.UniqueConstraint(
                fields=('club', 'squad_scope', 'context'),
                name='unique_club_tactic_setup_scope_context',
            ),
        ),
    ]