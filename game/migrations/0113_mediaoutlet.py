from django.db import migrations, models

INITIAL_OUTLETS = [
    ('Vereinsredaktion', 'vereinsredaktion', '#e50914', 1,  False),
    ('Kicker',           'kicker',           '#d31419', 2,  True),
    ('Sky Sports',       'skysports',        '#0072c9', 3,  True),
    ('90min',            '90min',            '#14d95c', 4,  True),
    ('OneFootball',      'onefootball',      '#8fd0ff', 5,  True),
    ('Eurosport',        'eurosport',        '#ff6600', 6,  True),
    ('BBC Sport',        'bbcsport',         '#e8e2d6', 7,  True),
    ('beIN Sports',      'beinsports',       '#9f2fff', 8,  True),
    ('Fox Sports',       'foxsports',        '#c41230', 9,  True),
    ('Goal.com',         'goal',             '#22e6ff', 10, True),
    ("L'Équipe",         'lequipe',          '#1e90ff', 11, True),
    ('Marca',            'marca',            '#0075c2', 12, True),
    ('SportBild',        'sportbild',        '#e50914', 13, True),
    ('talkSPORT',        'talksport',        '#1a73e8', 14, True),
    ('The Guardian',     'theguardian',      '#00789c', 15, True),
    ('Planet Football',  'planetfootball',   '#ffd166', 16, True),
    ('World Soccer',     'worldsoccer',      '#22c55e', 17, True),
    ('Eleven Sports',    'eleven',           '#f97316', 18, True),
    ('442',              '442ch',            '#e50914', 19, True),
    ('Sport.fr',         'sportfr',          '#0f5bb5', 20, True),
    ('Sport TV',         'sporttv',          '#cc0000', 21, True),
    ('CNN Sport',        'cnn',              '#e50914', 22, True),
    ('Toronto Sun',      'torontosun',       '#e50914', 23, True),
    ('CNN Indonesia',    'cnnindonesia',     '#cc0000', 24, True),
]


def seed_outlets(apps, schema_editor):
    MediaOutlet = apps.get_model('game', 'MediaOutlet')
    for name, slug, color, order, has_logo in INITIAL_OUTLETS:
        MediaOutlet.objects.get_or_create(
            slug=slug,
            defaults={
                'name': name,
                'accent_color': color,
                'sort_order': order,
                'has_logo': has_logo,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0112_club_cmtracker_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='MediaOutlet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('name',         models.CharField(max_length=80, unique=True)),
                ('slug',         models.SlugField(max_length=60, unique=True)),
                ('accent_color', models.CharField(default='#22e6ff', max_length=7)),
                ('has_logo',     models.BooleanField(default=False)),
                ('sort_order',   models.PositiveSmallIntegerField(default=0)),
            ],
            options={'ordering': ['sort_order', 'name']},
        ),
        migrations.RunPython(seed_outlets, migrations.RunPython.noop),
    ]
