import logging

logger = logging.getLogger(__name__)

_NT_COMPETITION_KEYS = {'Nationalmannschaft', 'Nationalkader'}

_NATIONALITY_CONFEDERATION = {
    'Albanien':             'uefa',
    'Andorra':              'uefa',
    'Armenien':             'uefa',
    'Aserbaidschan':        'uefa',
    'Belarus':              'uefa',
    'Belgien':              'uefa',
    'Bosnien-Herzegowina':  'uefa',
    'Bosnien und Herzegowina': 'uefa',
    'Bulgarien':            'uefa',
    'Dänemark':             'uefa',
    'Deutschland':          'uefa',
    'England':              'uefa',
    'Estland':              'uefa',
    'Finnland':             'uefa',
    'Frankreich':           'uefa',
    'Georgien':             'uefa',
    'Griechenland':         'uefa',
    'Irland':               'uefa',
    'Island':               'uefa',
    'Israel':               'uefa',
    'Italien':              'uefa',
    'Kasachstan':           'uefa',
    'Kosovo':               'uefa',
    'Kroatien':             'uefa',
    'Lettland':             'uefa',
    'Liechtenstein':        'uefa',
    'Litauen':              'uefa',
    'Luxemburg':            'uefa',
    'Malta':                'uefa',
    'Moldau':               'uefa',
    'Monaco':               'uefa',
    'Montenegro':           'uefa',
    'Niederlande':          'uefa',
    'Nordmazedonien':       'uefa',
    'Norwegen':             'uefa',
    'Österreich':           'uefa',
    'Polen':                'uefa',
    'Portugal':             'uefa',
    'Rumänien':             'uefa',
    'Russland':             'uefa',
    'San Marino':           'uefa',
    'Schottland':           'uefa',
    'Schweden':             'uefa',
    'Schweiz':              'uefa',
    'Serbien':              'uefa',
    'Slowakei':             'uefa',
    'Slowenien':            'uefa',
    'Spanien':              'uefa',
    'Tschechien':           'uefa',
    'Türkei':               'uefa',
    'Ukraine':              'uefa',
    'Ungarn':               'uefa',
    'Vereinigtes Königreich': 'uefa',
    'Wales':                'uefa',
    'Zypern':               'uefa',
    'Argentinien':          'conmebol',
    'Bolivien':             'conmebol',
    'Brasilien':            'conmebol',
    'Chile':                'conmebol',
    'Ecuador':              'conmebol',
    'Kolumbien':            'conmebol',
    'Paraguay':             'conmebol',
    'Peru':                 'conmebol',
    'Suriname':             'conmebol',
    'Uruguay':              'conmebol',
    'Venezuela':            'conmebol',
    'Ägypten':              'caf',
    'Äquatorialguinea':     'caf',
    'Äthiopien':            'caf',
    'Algerien':             'caf',
    'Angola':               'caf',
    'Benin':                'caf',
    'Botswana':             'caf',
    'Burkina Faso':         'caf',
    'Burundi':              'caf',
    'DR Kongo':             'caf',
    'Dschibuti':            'caf',
    'Elfenbeinküste':       'caf',
    'Eritrea':              'caf',
    'Eswatini':             'caf',
    'Gabun':                'caf',
    'Gambia':               'caf',
    'Ghana':                'caf',
    'Guinea':               'caf',
    'Guinea-Bissau':        'caf',
    'Kamerun':              'caf',
    'Kap Verde':            'caf',
    'Kenia':                'caf',
    'Komoren':              'caf',
    'Kongo':                'caf',
    'Kongo (Demokratische Republik)': 'caf',
    'Kongo (Republik)':     'caf',
    'Lesotho':              'caf',
    'Liberia':              'caf',
    'Libyen':               'caf',
    'Madagaskar':           'caf',
    'Malawi':               'caf',
    'Mali':                 'caf',
    'Marokko':              'caf',
    'Mauretanien':          'caf',
    'Mauritius':            'caf',
    'Mosambik':             'caf',
    'Namibia':              'caf',
    'Niger':                'caf',
    'Nigeria':              'caf',
    'Ruanda':               'caf',
    'Sambia':               'caf',
    'São tomé und Príncipe': 'caf',
    'Senegal':              'caf',
    'Seychellen':           'caf',
    'Sierra Leone':         'caf',
    'Simbabwe':             'caf',
    'Somalia':              'caf',
    'Sudan':                'caf',
    'Südafrika':            'caf',
    'Südsudan':             'caf',
    'Tansania':             'caf',
    'Tschad':               'caf',
    'Togo':                 'caf',
    'Tunesien':             'caf',
    'Uganda':               'caf',
    'Zentralafrikanische Republik': 'caf',
    'Afghanistan':          'afc',
    'Australien':           'afc',
    'Bahrain':              'afc',
    'Bangladesch':          'afc',
    'Bhutan':               'afc',
    'Brunei':               'afc',
    'China':                'afc',
    'Indien':               'afc',
    'Indonesien':           'afc',
    'Irak':                 'afc',
    'Iran':                 'afc',
    'Japan':                'afc',
    'Jemen':                'afc',
    'Jordanien':            'afc',
    'Kambodscha':           'afc',
    'Katar':                'afc',
    'Kirgisistan':          'afc',
    'Korea (Nord)':         'afc',
    'Kuwait':               'afc',
    'Laos':                 'afc',
    'Libanon':              'afc',
    'Malaysia':             'afc',
    'Malediven':            'afc',
    'Mongolei':             'afc',
    'Myanmar':              'afc',
    'Nepal':                'afc',
    'Oman':                 'afc',
    'Pakistan':             'afc',
    'Palästina':            'afc',
    'Philippinen':          'afc',
    'Saudi-Arabien':        'afc',
    'Singapur':             'afc',
    'Sri Lanka':            'afc',
    'Südkorea':             'afc',
    'Syrien':               'afc',
    'Tadschikistan':        'afc',
    'Thailand':             'afc',
    'Timor-Leste':          'afc',
    'Turkmenistan':         'afc',
    'Usbekistan':           'afc',
    'Vereinigte Arabische Emirate': 'afc',
    'Vietnam':              'afc',
    'Antigua und Barbuda':  'concacaf',
    'Bahamas':              'concacaf',
    'Barbados':             'concacaf',
    'Belize':               'concacaf',
    'Costa Rica':           'concacaf',
    'Curacao':              'concacaf',
    'Dominica':             'concacaf',
    'Dominikanische Republik': 'concacaf',
    'El Salvador':          'concacaf',
    'Grenada':              'concacaf',
    'Guadeloupe':           'concacaf',
    'Guatemala':            'concacaf',
    'Guyana':               'concacaf',
    'Haiti':                'concacaf',
    'Honduras':             'concacaf',
    'Jamaika':              'concacaf',
    'Kanada':               'concacaf',
    'Kuba':                 'concacaf',
    'Mexiko':               'concacaf',
    'Nicaragua':            'concacaf',
    'Panama':               'concacaf',
    'St. Kitts und Nevis':  'concacaf',
    'St. Lucia':            'concacaf',
    'St. Vincent und die Grenadinen': 'concacaf',
    'Trinidad und Tobago':  'concacaf',
    'Vereinigte Staaten':   'concacaf',
    'Fidschi':              'ofc',
    'Kiribati':             'ofc',
    'Marshallinseln':       'ofc',
    'Mikronesien':          'ofc',
    'Nauru':                'ofc',
    'Neuseeland':           'ofc',
    'Palau':                'ofc',
    'Papua-Neuguinea':      'ofc',
    'Salomonen':            'ofc',
    'Samoa':                'ofc',
    'Tonga':                'ofc',
    'Tuvalu':               'ofc',
    'Vanuatu':              'ofc',
}


def _build_confederation_badge():
    from game.asset_urls import asset_url
    return {
        'caf':      asset_url('confederations', '1_conf.png'),
        'afc':      asset_url('confederations', '2_conf.png'),
        'uefa':     asset_url('confederations', '3_conf.png'),
        'concacaf': asset_url('confederations', '4_conf.png'),
        'ofc':      asset_url('confederations', '5_conf.png'),
        'conmebol': asset_url('confederations', '6_conf.png'),
    }


_GENERIC_CONFEDERATION_BADGE = None


def _generic_confederation_badge():
    global _GENERIC_CONFEDERATION_BADGE
    if _GENERIC_CONFEDERATION_BADGE is None:
        from game.asset_urls import asset_url
        _GENERIC_CONFEDERATION_BADGE = asset_url('confederations', '7_conf.png')
    return _GENERIC_CONFEDERATION_BADGE


def nt_competition_logo(nationality):
    key = nationality or ''
    conf = _NATIONALITY_CONFEDERATION.get(key)
    if conf is None and key:
        logger.warning(
            'nt_competition_logo: nationality %r is not in _NATIONALITY_CONFEDERATION — '
            'falling back to generic badge',
            key,
        )
    badge_map = _build_confederation_badge()
    return badge_map.get(conf, _generic_confederation_badge())


def competition_logo_static_path(competition, nt_nationality=None):
    """Gibt immer eine fertige URL zurück (kein relativer Static-Pfad mehr).

    Reihenfolge:
    1. NT-Wettbewerbe → Konföderation-Badge
    2. Hardcodiertes Dict (Bundesliga, CL, …) → Django-Static-URL
    3. League-DB-Lookup nach Name → Asset-Server-URL (/assets/competitions/{id}.png)
    4. Leer-String wenn kein Match
    """
    from django.templatetags.static import static as _static

    # League-Objekt → Name extrahieren, ID merken
    league_id = None
    if hasattr(competition, 'name'):
        league_id = getattr(competition, 'id', None)
        competition = competition.name

    if competition in _NT_COMPETITION_KEYS:
        return nt_competition_logo(nt_nationality)

    _HARDCODED = {
        '1. Bundesliga': 'game/images/competitions/bundesliga.png',
        'Bundesliga': 'game/images/competitions/bundesliga.png',
        'Websoccer Liga': 'game/images/competitions/websoccer-liga.svg',
        'DFB-Pokal': 'img/competitions/dfb_pokal_logo.png',
        'Pokal': 'img/competitions/dfb_pokal_logo.png',
        'Champions League': 'game/images/competitions/champions-league.png',
        'CL': 'game/images/competitions/champions-league.png',
        'Supercup': 'game/images/competitions/supercup.png',
        'Europa League': 'game/images/competitions/europa-league.png',
        'EL': 'game/images/competitions/europa-league.png',
        'Europa Conference League': 'game/images/competitions/europa-conference-league.png',
        'ECL': 'game/images/competitions/europa-conference-league.png',
    }
    if competition in _HARDCODED:
        return _static(_HARDCODED[competition])

    # DB-Fallback: Logo das über Creator hochgeladen wurde (logo_static_path)
    try:
        from game.models import League as _League
        from game.asset_urls import competition_url as _comp_url, assets_base_url as _base
        if league_id is None and competition:
            league = _League.objects.filter(name=competition).first()
        elif league_id:
            league = _League.objects.filter(id=league_id).first()
        else:
            league = None
        if league and league.logo_static_path:
            lp = league.logo_static_path
            # Neues Format: 'competitions/{id}.png' → Asset-URL
            if lp.startswith('competitions/'):
                return _base() + lp
            # Altes Format: 'game/images/competitions/…' → Static-URL
            return _static(lp)
    except Exception:
        pass

    return ''
