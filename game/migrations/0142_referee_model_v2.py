"""
Migration 0142 — Referee-Modell V2

Änderungen (Tabelle ist leer, daher kein Data-Migration nötig):
- age entfernt → birth_date DateField
- quote CharField → schlagwort CharField (Text-Display) + quote PositiveSmallInt (Qualität 1–20)
- level CharField → PositiveSmallIntegerField (1–5)
- karten_tendenz CharField → PositiveSmallIntegerField (1–20)
- spielfluss_tendenz CharField → PositiveSmallIntegerField (1–20)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0141_referee_model_and_fk'),
    ]

    operations = [
        # 1. age raus, birth_date rein
        migrations.RemoveField(model_name='referee', name='age'),
        migrations.AddField(
            model_name='referee',
            name='birth_date',
            field=models.DateField(blank=True, null=True, verbose_name='Geburtsdatum'),
        ),

        # 2. quote CharField → schlagwort (Text-Display im Popup)
        migrations.RenameField(model_name='referee', old_name='quote', new_name='schlagwort'),
        migrations.AlterField(
            model_name='referee',
            name='schlagwort',
            field=models.CharField(
                blank=True, max_length=200, verbose_name='Schlagwort/Kurzcharakter',
                help_text='Erscheint kursiv im Popup, z. B. „Souveräner Spielleiter".',
            ),
        ),

        # 3. Neues quote-Feld: Entscheidungsqualität 1–20
        migrations.AddField(
            model_name='referee',
            name='quote',
            field=models.PositiveSmallIntegerField(
                default=10,
                verbose_name='Entscheidungsqualität (1–20)',
                help_text='1=fehlerhaft, 20=makellos. P(Fehlentscheidung/Sp)=clamp((14−q)×0.7;1;8)%.',
            ),
        ),

        # 4. level CharField → PositiveSmallInt (Tabelle ist leer → direkt)
        migrations.RemoveField(model_name='referee', name='level'),
        migrations.AddField(
            model_name='referee',
            name='level',
            field=models.PositiveSmallIntegerField(
                default=3,
                verbose_name='Niveau (1–5)',
                help_text='5=Weltklasse, 4=International, 3=Erste Liga, 2=Zweite Liga, 1=Aufsteiger',
            ),
        ),

        # 5. karten_tendenz CharField → PositiveSmallInt
        migrations.RemoveField(model_name='referee', name='karten_tendenz'),
        migrations.AddField(
            model_name='referee',
            name='karten_tendenz',
            field=models.PositiveSmallIntegerField(
                default=10,
                verbose_name='Karten-Tendenz (1–20)',
                help_text='1=sehr nachsichtig, 20=sehr kartenfreudig. Invariante: karten+spielfluss=21.',
            ),
        ),

        # 6. spielfluss_tendenz CharField → PositiveSmallInt
        migrations.RemoveField(model_name='referee', name='spielfluss_tendenz'),
        migrations.AddField(
            model_name='referee',
            name='spielfluss_tendenz',
            field=models.PositiveSmallIntegerField(
                default=11,
                verbose_name='Spielfluss-Tendenz (1–20)',
                help_text='1=pfeift viel ab, 20=lässt laufen. Invariante: karten+spielfluss=21.',
            ),
        ),
    ]
