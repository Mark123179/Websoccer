from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0071_president_satisfaction'),
    ]

    operations = [
        migrations.CreateModel(
            name='InactivityRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('squad_scope', models.CharField(choices=[('pro', 'Profis'), ('u21', 'U21')], default='pro', max_length=10, verbose_name='Mannschaft')),
                ('season', models.CharField(blank=True, max_length=20, verbose_name='Saison')),
                ('matchday_label', models.CharField(blank=True, max_length=80, verbose_name='Spieltag')),
                ('recorded_at', models.DateTimeField(auto_now_add=True, verbose_name='Erfasst am')),
                ('club', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inactivity_records', to='game.club', verbose_name='Verein')),
                ('manager', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inactivity_records', to='game.managerprofile', verbose_name='Manager')),
            ],
            options={
                'verbose_name': 'Inaktivitäts-Eintrag',
                'verbose_name_plural': 'Inaktivitäts-Einträge',
                'ordering': ['-recorded_at'],
            },
        ),
        migrations.CreateModel(
            name='InactivityPenalty',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('given_at', models.DateTimeField(auto_now_add=True, verbose_name='Erteilt am')),
                ('reason', models.TextField(blank=True, verbose_name='Begründung')),
                ('manager', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inactivity_penalties', to='game.managerprofile', verbose_name='Manager')),
            ],
            options={
                'verbose_name': 'Inaktivitäts-Strafpunkt',
                'verbose_name_plural': 'Inaktivitäts-Strafpunkte',
                'ordering': ['-given_at'],
            },
        ),
        migrations.CreateModel(
            name='SupportTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Titel')),
                ('description', models.TextField(verbose_name='Beschreibung')),
                ('screenshot', models.FileField(blank=True, null=True, upload_to='support_tickets/', verbose_name='Screenshot')),
                ('status', models.CharField(choices=[('open', 'Offen'), ('in_progress', 'In Bearbeitung'), ('closed', 'Abgeschlossen')], default='open', max_length=20, verbose_name='Status')),
                ('admin_response', models.TextField(blank=True, verbose_name='Admin-Antwort')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')),
                ('closed_at', models.DateTimeField(blank=True, null=True, verbose_name='Abgeschlossen am')),
                ('manager', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='support_tickets', to='game.managerprofile', verbose_name='Manager')),
            ],
            options={
                'verbose_name': 'Support-Ticket',
                'verbose_name_plural': 'Support-Tickets',
                'ordering': ['-created_at'],
            },
        ),
    ]
