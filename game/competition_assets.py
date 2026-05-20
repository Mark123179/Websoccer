_NT_COMPETITION_KEYS = {'Nationalmannschaft', 'Nationalkader'}

_NATIONALITY_CONFEDERATION = {
    'Deutschland':        'uefa',
    'England':            'uefa',
    'Frankreich':         'uefa',
    'Irland':             'uefa',
    'Italien':            'uefa',
    'Kroatien':           'uefa',
    'Norwegen':           'uefa',
    'Österreich':         'uefa',
    'Portugal':           'uefa',
    'Schweden':           'uefa',
    'Schweiz':            'uefa',
    'Serbien':            'uefa',
    'Türkei':             'uefa',
    'Brasilien':          'conmebol',
    'Kolumbien':          'conmebol',
    'Algerien':           'caf',
    'Elfenbeinküste':     'caf',
    'Gambia':             'caf',
    'Guinea':             'caf',
    'Guinea-Bissau':      'caf',
    'Liberia':            'caf',
    'Libyen':             'caf',
    'Nigeria':            'caf',
    'Senegal':            'caf',
    'Japan':              'afc',
    'Südkorea':           'afc',
}

_CONFEDERATION_BADGE = {
    'uefa':     'game/images/competitions/nt-uefa.png',
    'conmebol': 'game/images/competitions/nt-conmebol.png',
    'caf':      'game/images/competitions/nt-caf.png',
    'afc':      'game/images/competitions/nt-afc.png',
}


def nt_competition_logo(nationality):
    conf = _NATIONALITY_CONFEDERATION.get(nationality or '')
    return _CONFEDERATION_BADGE.get(conf, 'game/images/competitions/nationalmannschaft.svg')


def competition_logo_static_path(competition, nt_nationality=None):
    if competition in _NT_COMPETITION_KEYS:
        return nt_competition_logo(nt_nationality)
    assets = {
        '1. Bundesliga': 'game/images/competitions/bundesliga.png',
        'Bundesliga': 'game/images/competitions/bundesliga.png',
        'Websoccer Liga': 'game/images/competitions/websoccer-liga.svg',
        'DFB-Pokal': 'game/images/competitions/dfb-pokal.png',
        'Pokal': 'game/images/competitions/dfb-pokal.png',
        'Champions League': 'game/images/competitions/champions-league.png',
        'CL': 'game/images/competitions/champions-league.png',
        'Supercup': 'game/images/competitions/supercup.png',
        'Europa League': 'game/images/competitions/europa-league.png',
        'EL': 'game/images/competitions/europa-league.png',
        'Europa Conference League': 'game/images/competitions/europa-conference-league.png',
        'ECL': 'game/images/competitions/europa-conference-league.png',
    }
    return assets.get(competition, '')
