"""Sponsoring-Modul V2: Sponsor-Modell, SponsorOffer V2-Felder, SponsorContract.

Änderungen:
  - Neues Modell: Sponsor (Stammdaten-Pool)
  - SponsorOffer: 8 neue V2-Felder (slot, sponsor FK, fix_start, fix_aktuell,
    var_rate, var_ziel, mult, runde, status)
  - Neues Modell: SponsorContract (1 Vertrag je Slot × Saison × Verein)
  - Datenmigration: alle vorhandenen SponsorOffer-Zeilen → status='legacy'
"""
from django.db import migrations, models
import django.db.models.deletion


def mark_legacy_offers(apps, schema_editor):
    SponsorOffer = apps.get_model('game', 'SponsorOffer')
    SponsorOffer.objects.all().update(status='legacy')


def unmark_legacy_offers(apps, schema_editor):
    SponsorOffer = apps.get_model('game', 'SponsorOffer')
    SponsorOffer.objects.filter(status='legacy').update(status='offen')


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0142_referee_model_v2'),
    ]

    operations = [
        # ── 1. Sponsor-Modell ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='Sponsor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=80, unique=True,
                                          verbose_name='Slug')),
                ('name', models.CharField(max_length=120, verbose_name='Firmenname')),
                ('display_name', models.CharField(blank=True, max_length=120,
                                                   verbose_name='Anzeigename (Caps)')),
                ('bereich', models.CharField(
                    choices=[
                        ('hauptsponsor', 'Hauptsponsor'),
                        ('trikotsponsor', 'Trikotsponsor'),
                        ('ausruester', 'Ausrüster'),
                        ('stadionpartner', 'Stadionpartner'),
                        ('tv_medien', 'TV- & Medienpartner'),
                    ],
                    db_index=True, max_length=20, verbose_name='Bereich',
                )),
                ('branche', models.CharField(blank=True, max_length=60,
                                              verbose_name='Branche')),
                ('aktiv', models.BooleanField(db_index=True, default=True,
                                               verbose_name='Aktiv')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Sponsor',
                'verbose_name_plural': 'Sponsoren',
                'ordering': ['bereich', 'name'],
                'indexes': [
                    models.Index(fields=['bereich', 'aktiv'],
                                 name='game_sponsor_bereich_aktiv_idx'),
                ],
            },
        ),

        # ── 2. SponsorOffer V2-Felder hinzufügen ──────────────────────────────
        migrations.AddField(
            model_name='sponsoroffer',
            name='slot',
            field=models.CharField(db_index=True, default='haupt',
                                    max_length=20, verbose_name='Sponsoring-Slot'),
        ),
        migrations.AddField(
            model_name='sponsoroffer',
            name='sponsor',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='offers', to='game.sponsor',
                verbose_name='Sponsor',
            ),
        ),
        migrations.AddField(
            model_name='sponsoroffer',
            name='fix_start',
            field=models.BigIntegerField(
                blank=True, null=True,
                verbose_name='Fixbetrag Verhandlungsstart (€)',
            ),
        ),
        migrations.AddField(
            model_name='sponsoroffer',
            name='fix_aktuell',
            field=models.BigIntegerField(
                blank=True, null=True,
                verbose_name='Fixbetrag aktuell (€)',
            ),
        ),
        migrations.AddField(
            model_name='sponsoroffer',
            name='var_rate',
            field=models.BigIntegerField(
                default=0, verbose_name='Variabler Betrag je Event (€-Cent)',
            ),
        ),
        migrations.AddField(
            model_name='sponsoroffer',
            name='var_ziel',
            field=models.CharField(
                blank=True, max_length=32, verbose_name='Zielstufe (goal_tier)',
            ),
        ),
        migrations.AddField(
            model_name='sponsoroffer',
            name='mult',
            field=models.DecimalField(
                decimal_places=4, default=1, max_digits=6,
                verbose_name='Verhandlungs-Multiplikator',
            ),
        ),
        migrations.AddField(
            model_name='sponsoroffer',
            name='runde',
            field=models.PositiveSmallIntegerField(
                default=0, verbose_name='Verhandlungsrunde',
            ),
        ),
        migrations.AddField(
            model_name='sponsoroffer',
            name='status',
            field=models.CharField(
                choices=[
                    ('offen', 'Offen'),
                    ('angenommen', 'Angenommen'),
                    ('abgesagt', 'Abgesagt'),
                    ('legacy', 'Alt (V1)'),
                ],
                db_index=True, default='legacy', max_length=12,
                verbose_name='Status',
            ),
        ),

        # ── 3. Index auf (club, saison, slot) ────────────────────────────────
        migrations.AddIndex(
            model_name='sponsoroffer',
            index=models.Index(
                fields=['club', 'saison', 'slot'],
                name='game_sponoffer_club_saison_slot_idx',
            ),
        ),

        # ── 4. Ordering aktualisieren ─────────────────────────────────────────
        migrations.AlterModelOptions(
            name='sponsoroffer',
            options={
                'ordering': ['club', 'saison', 'slot', 'id'],
                'verbose_name': 'Sponsorangebot',
                'verbose_name_plural': 'Sponsorangebote',
            },
        ),

        # ── 5. Datenmigration: vorhandene Zeilen → status='legacy' ───────────
        migrations.RunPython(mark_legacy_offers, reverse_code=unmark_legacy_offers),

        # ── 6. SponsorContract-Modell ─────────────────────────────────────────
        migrations.CreateModel(
            name='SponsorContract',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('saison', models.CharField(max_length=20, verbose_name='Saison')),
                ('club', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sponsor_contracts', to='game.club',
                    verbose_name='Verein',
                )),
                ('slot', models.CharField(max_length=20, verbose_name='Slot')),
                ('sponsor', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='contracts', to='game.sponsor',
                    verbose_name='Sponsor',
                )),
                ('offer', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='contract', to='game.sponsoroffer',
                    verbose_name='Zugrundeliegendes Angebot',
                )),
                ('fix_saison', models.BigIntegerField(
                    verbose_name='Fixbetrag Saison (€)',
                )),
                ('auto', models.BooleanField(
                    default=False, verbose_name='Automatisch gewählt',
                )),
                ('abgelaufen', models.BooleanField(
                    db_index=True, default=False, verbose_name='Abgelaufen',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Sponsoring-Vertrag',
                'verbose_name_plural': 'Sponsoring-Verträge',
                'ordering': ['saison', 'club', 'slot'],
                'indexes': [
                    models.Index(fields=['saison', 'club'],
                                 name='game_sponsorcontract_saison_club_idx'),
                    models.Index(fields=['club', 'saison', 'abgelaufen'],
                                 name='game_sponsorcontract_club_saison_abg_idx'),
                ],
            },
        ),
        migrations.AlterUniqueTogether(
            name='sponsorcontract',
            unique_together={('saison', 'club', 'slot')},
        ),
    ]
