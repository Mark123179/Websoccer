import secrets

from django.contrib.staticfiles import finders
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from .tactics import (
    SQUAD_PRO,
    SQUAD_SCOPE_CHOICES,
    default_bench,
    default_conditions,
    default_formation,
    default_half_tactic,
    default_instructions,
    default_lineup,
    default_standards,
    default_substitutions,
    field_player_count,
    formation_code,
    validate_formation,
)


COUNTRY_FLAG_ASSETS = {
    'Afghanistan': {'code': 'AF', 'asset_id': '106'},
    'Ägypten': {'code': 'EG', 'asset_id': '16'},
    'Albanien': {'code': 'AL', 'asset_id': '752'},
    'Algerien': {'code': 'DZ', 'asset_id': '5'},
    'Andorra': {'code': 'AD', 'asset_id': '753'},
    'Angola': {'code': 'AO'},
    'Antigua und Barbuda': {'code': 'AG', 'asset_id': '361'},
    'Äquatorialguinea': {'code': 'GQ', 'asset_id': '17'},
    'Argentinien': {'code': 'AR', 'asset_id': '1649'},
    'Armenien': {'code': 'AM', 'asset_id': '754'},
    'Aserbaidschan': {'code': 'AZ', 'asset_id': '756'},
    'Äthiopien': {'code': 'ET', 'asset_id': '19'},
    'Australien': {'code': 'AU', 'asset_id': '1435'},
    'Cookinseln': {'code': 'CK', 'asset_id': '1436'},
    'Bahamas': {'code': 'BS', 'asset_id': '363'},
    'Bahrain': {'code': 'BH', 'asset_id': '107'},
    'Bangladesch': {'code': 'BD', 'asset_id': '108'},
    'Barbados': {'code': 'BB'},
    'Belarus': {'code': 'BY', 'asset_id': '758'},
    'Belgien': {'code': 'BE', 'asset_id': '757'},
    'Belize': {'code': 'BZ'},
    'Benin': {'code': 'BJ', 'asset_id': '7'},
    'Bhutan': {'code': 'BT', 'asset_id': '109'},
    'Bolivien': {'code': 'BO', 'asset_id': '1650'},
    'Bosnien und Herzegowina': {'code': 'BA', 'asset_id': '759'},
    'Bosnien-Herzegowina': {'code': 'BA', 'asset_id': '759'},
    'Botswana': {'code': 'BW'},
    'Brasilien': {'code': 'BR', 'asset_id': '1651'},
    'Brunei': {'code': 'BN'},
    'Bulgarien': {'code': 'BG', 'asset_id': '760'},
    'Burkina Faso': {'code': 'BF', 'asset_id': '8'},
    'Burundi': {'code': 'BI', 'asset_id': '9'},
    'Chile': {'code': 'CL', 'asset_id': '1652'},
    'China': {'code': 'CN', 'asset_id': '110'},
    'Hongkong': {'code': 'HK', 'asset_id': '111'},
    'Costa Rica': {'code': 'CR', 'asset_id': '366'},
    'Curacao': {'code': 'CW', 'asset_id': '380'},
    'Dänemark': {'code': 'DK', 'asset_id': '764'},
    'Deutschland': {'code': 'DE', 'asset_id': '771'},
    'Dominica': {'code': 'DM', 'asset_id': '368'},
    'Dominikanische Republik': {'code': 'DO'},
    'Dschibuti': {'code': 'DJ', 'asset_id': '15'},
    'Ecuador': {'code': 'EC', 'asset_id': '1654'},
    'Elfenbeinküste': {'code': 'CI', 'asset_id': '24'},
    'El Salvador': {'code': 'SV', 'asset_id': '370'},
    'England': {'code': 'GB-ENG', 'asset_id': '765'},
    'Färöer': {'code': 'FO', 'asset_id': '767'},
    'Eritrea': {'code': 'ER', 'asset_id': '18'},
    'Estland': {'code': 'EE', 'asset_id': '766'},
    'Eswatini': {'code': 'SZ', 'asset_id': '47'},
    'Fidschi': {'code': 'FJ', 'asset_id': '1437'},
    'Finnland': {'code': 'FI', 'asset_id': '768'},
    'Frankreich': {'code': 'FR', 'asset_id': '769'},
    'Guadeloupe': {'code': 'GP'},
    'Gabun': {'code': 'GA'},
    'Gambia': {'code': 'GM', 'asset_id': '20'},
    'Georgien': {'code': 'GE', 'asset_id': '770'},
    'Ghana': {'code': 'GH', 'asset_id': '21'},
    'Grenada': {'code': 'GD', 'asset_id': '371'},
    'Griechenland': {'code': 'GR', 'asset_id': '772'},
    'Guatemala': {'code': 'GT'},
    'Guinea': {'code': 'GN', 'asset_id': '22'},
    'Guinea-Bissau': {'code': 'GW', 'asset_id': '23'},
    'Guyana': {'code': 'GY', 'asset_id': '374'},
    'Haiti': {'code': 'HT', 'asset_id': '375'},
    'Honduras': {'code': 'HN', 'asset_id': '376'},
    'Indien': {'code': 'IN', 'asset_id': '112'},
    'Indonesien': {'code': 'ID', 'asset_id': '113'},
    'Irak': {'code': 'IQ', 'asset_id': '115'},
    'Iran': {'code': 'IR', 'asset_id': '114'},
    'Irland': {'code': 'IE', 'asset_id': '789'},
    'Island': {'code': 'IS', 'asset_id': '774'},
    'Israel': {'code': 'IL', 'asset_id': '775'},
    'Italien': {'code': 'IT', 'asset_id': '776'},
    'Jamaika': {'code': 'JM', 'asset_id': '377'},
    'Japan': {'code': 'JP', 'asset_id': '116'},
    'Jemen': {'code': 'YE', 'asset_id': '146'},
    'Jordanien': {'code': 'JO', 'asset_id': '117'},
    'Kambodscha': {'code': 'KH', 'asset_id': '118'},
    'Kamerun': {'code': 'CM', 'asset_id': '11'},
    'Kanada': {'code': 'CA', 'asset_id': '364'},
    'Kaimaninseln': {'code': 'KY', 'asset_id': '365'},
    'Kap Verde': {'code': 'CV', 'asset_id': '12'},
    'Kasachstan': {'code': 'KZ', 'asset_id': '119'},
    'Katar': {'code': 'QA', 'asset_id': '132'},
    'Kenia': {'code': 'KE', 'asset_id': '25'},
    'Kirgisistan': {'code': 'KG', 'asset_id': '121'},
    'Kiribati': {'code': 'KI'},
    'Kolumbien': {'code': 'CO', 'asset_id': '1653'},
    'Komoren': {'code': 'KM'},
    'Kongo (Demokratische Republik)': {'code': 'CD', 'asset_id': '53'},
    'Kongo (Republik)': {'code': 'CG', 'asset_id': '49'},
    'Kongo': {'code': 'CG', 'asset_id': '49'},
    'DR Kongo': {'code': 'CD', 'asset_id': '53'},
    'Korea (Nord)': {'code': 'KP', 'asset_id': '129'},
    'Kosovo': {'code': 'XK', 'asset_id': '217945'},
    'Kroatien': {'code': 'HR', 'asset_id': '761'},
    'Kuba': {'code': 'CU', 'asset_id': '367'},
    'Kuwait': {'code': 'KW', 'asset_id': '120'},
    'Laos': {'code': 'LA', 'asset_id': '122'},
    'Macau': {'code': 'MO', 'asset_id': '124'},
    'Lesotho': {'code': 'LS', 'asset_id': '26'},
    'Lettland': {'code': 'LV', 'asset_id': '777'},
    'Libanon': {'code': 'LB', 'asset_id': '123'},
    'Liberia': {'code': 'LR', 'asset_id': '27'},
    'Libyen': {'code': 'LY', 'asset_id': '28'},
    'Liechtenstein': {'code': 'LI', 'asset_id': '778'},
    'Litauen': {'code': 'LT', 'asset_id': '779'},
    'Luxemburg': {'code': 'LU', 'asset_id': '780'},
    'Madagaskar': {'code': 'MG', 'asset_id': '29'},
    'Malawi': {'code': 'MW', 'asset_id': '30'},
    'Malaysia': {'code': 'MY', 'asset_id': '125'},
    'Malediven': {'code': 'MV', 'asset_id': '126'},
    'Mali': {'code': 'ML', 'asset_id': '31'},
    'Malta': {'code': 'MT', 'asset_id': '782'},
    'Marokko': {'code': 'MA', 'asset_id': '34'},
    'Marshallinseln': {'code': 'MH'},
    'Mauretanien': {'code': 'MR', 'asset_id': '32'},
    'Mauritius': {'code': 'MU', 'asset_id': '33'},
    'Mexiko': {'code': 'MX', 'asset_id': '379'},
    'Mikronesien': {'code': 'FM'},
    'Moldau': {'code': 'MD', 'asset_id': '783'},
    'Monaco': {'code': 'MC', 'asset_id': '5630219'},
    'Mongolei': {'code': 'MN'},
    'Montenegro': {'code': 'ME'},
    'Mosambik': {'code': 'MZ', 'asset_id': '35'},
    'Myanmar': {'code': 'MM', 'asset_id': '127'},
    'Namibia': {'code': 'NA', 'asset_id': '36'},
    'Nauru': {'code': 'NR'},
    'Nepal': {'code': 'NP', 'asset_id': '128'},
    'Neuseeland': {'code': 'NZ', 'asset_id': '1438'},
    'Nicaragua': {'code': 'NI'},
    'Niederlande': {'code': 'NL', 'asset_id': '784'},
    'Niger': {'code': 'NE', 'asset_id': '37'},
    'Nigeria': {'code': 'NG', 'asset_id': '38'},
    'Nordmazedonien': {'code': 'MK', 'asset_id': '781'},
    'Nordirland': {'code': 'GB-NIR', 'asset_id': '785'},
    'Norwegen': {'code': 'NO', 'asset_id': '786'},
    'Oman': {'code': 'OM', 'asset_id': '130'},
    'Österreich': {'code': 'AT', 'asset_id': '755'},
    'Pakistan': {'code': 'PK'},
    'Palästina': {'code': 'PS', 'asset_id': '131'},
    'Palau': {'code': 'PW'},
    'Panama': {'code': 'PA', 'asset_id': '382'},
    'Papua-Neuguinea': {'code': 'PG', 'asset_id': '1439'},
    'Paraguay': {'code': 'PY', 'asset_id': '1655'},
    'Peru': {'code': 'PE', 'asset_id': '1656'},
    'Philippinen': {'code': 'PH', 'asset_id': '141'},
    'Polen': {'code': 'PL', 'asset_id': '787'},
    'Portugal': {'code': 'PT', 'asset_id': '788'},
    'Ruanda': {'code': 'RW', 'asset_id': '39'},
    'Rumänien': {'code': 'RO', 'asset_id': '790'},
    'Russland': {'code': 'RU', 'asset_id': '791'},
    'Salomonen': {'code': 'SB', 'asset_id': '1440'},
    'Sambia': {'code': 'ZM', 'asset_id': '54'},
    'Samoa': {'code': 'WS', 'asset_id': '1444'},
    'Tahiti': {'code': 'PF', 'asset_id': '1441'},
    'San Marino': {'code': 'SM', 'asset_id': '792'},
    'São tomé und Príncipe': {'code': 'ST', 'asset_id': '40'},
    'Saudi-Arabien': {'code': 'SA', 'asset_id': '133'},
    'Schottland': {'code': 'GB-SCT', 'asset_id': '793'},
    'Schweden': {'code': 'SE', 'asset_id': '797'},
    'Schweiz': {'code': 'CH', 'asset_id': '798'},
    'Senegal': {'code': 'SN', 'asset_id': '41'},
    'Serbien': {'code': 'RS', 'asset_id': '802'},
    'Seychellen': {'code': 'SC', 'asset_id': '42'},
    'Sierra Leone': {'code': 'SL', 'asset_id': '43'},
    'Simbabwe': {'code': 'ZW', 'asset_id': '55'},
    'Singapur': {'code': 'SG', 'asset_id': '134'},
    'Slowakei': {'code': 'SK', 'asset_id': '794'},
    'Slowenien': {'code': 'SI', 'asset_id': '795'},
    'Somalia': {'code': 'SO', 'asset_id': '44'},
    'Spanien': {'code': 'ES', 'asset_id': '796'},
    'Sri Lanka': {'code': 'LK', 'asset_id': '136'},
    'St. Kitts und Nevis': {'code': 'KN'},
    'St. Lucia': {'code': 'LC'},
    'St. Vincent und die Grenadinen': {'code': 'VC'},
    'Südafrika': {'code': 'ZA', 'asset_id': '45'},
    'Sudan': {'code': 'SD', 'asset_id': '46'},
    'Südkorea': {'code': 'KR', 'asset_id': '135'},
    'Südsudan': {'code': 'SS'},
    'Suriname': {'code': 'SR', 'asset_id': '385'},
    'Syrien': {'code': 'SY', 'asset_id': '137'},
    'Chinesisch-Taipeh': {'code': 'TW', 'asset_id': '138'},
    'Tadschikistan': {'code': 'TJ', 'asset_id': '139'},
    'Tansania': {'code': 'TZ', 'asset_id': '48'},
    'Thailand': {'code': 'TH', 'asset_id': '140'},
    'Timor-Leste': {'code': 'TL'},
    'Togo': {'code': 'TG', 'asset_id': '50'},
    'Tonga': {'code': 'TO', 'asset_id': '1442'},
    'Trinidad und Tobago': {'code': 'TT', 'asset_id': '387'},
    'Tschad': {'code': 'TD', 'asset_id': '14'},
    'Tschechien': {'code': 'CZ', 'asset_id': '763'},
    'Tunesien': {'code': 'TN', 'asset_id': '51'},
    'Türkei': {'code': 'TR', 'asset_id': '799'},
    'Turkmenistan': {'code': 'TM', 'asset_id': '142'},
    'Tuvalu': {'code': 'TV'},
    'Uganda': {'code': 'UG', 'asset_id': '52'},
    'Ukraine': {'code': 'UA', 'asset_id': '800'},
    'Ungarn': {'code': 'HU', 'asset_id': '773'},
    'Uruguay': {'code': 'UY', 'asset_id': '1657'},
    'Usbekistan': {'code': 'UZ', 'asset_id': '144'},
    'Vanuatu': {'code': 'VU', 'asset_id': '1443'},
    'Venezuela': {'code': 'VE', 'asset_id': '1658'},
    'Vereinigte Arabische Emirate': {'code': 'AE', 'asset_id': '143'},
    'Vereinigte Staaten': {'code': 'US', 'asset_id': '390'},
    'Vereinigtes Königreich': {'code': 'GB'},
    'Vietnam': {'code': 'VN', 'asset_id': '145'},
    'Wales': {'code': 'GB-WLS', 'asset_id': '801'},
    'Zentralafrikanische Republik': {'code': 'CF', 'asset_id': '13'},
    'Zypern': {'code': 'CY', 'asset_id': '762'},
}

NATIONALITY_ALIASES = {
    'afghanistan': 'Afghanistan',
    'albania': 'Albanien',
    'algeria': 'Algerien',
    'andorra': 'Andorra',
    'angola': 'Angola',
    'antigua and barbuda': 'Antigua und Barbuda',
    'argentina': 'Argentinien',
    'armenia': 'Armenien',
    'australia': 'Australien',
    'austria': 'Österreich',
    'azerbaijan': 'Aserbaidschan',
    'bahamas': 'Bahamas',
    'bahrain': 'Bahrain',
    'bangladesh': 'Bangladesch',
    'barbados': 'Barbados',
    'belarus': 'Belarus',
    'weißrussland': 'Belarus',
    'belgium': 'Belgien',
    'belize': 'Belize',
    'benin': 'Benin',
    'bhutan': 'Bhutan',
    'bolivia': 'Bolivien',
    'bosnia and herzegovina': 'Bosnien und Herzegowina',
    'bosnia': 'Bosnien und Herzegowina',
    'botswana': 'Botswana',
    'brazil': 'Brasilien',
    'brunei': 'Brunei',
    'bulgaria': 'Bulgarien',
    'burkina faso': 'Burkina Faso',
    'burundi': 'Burundi',
    'cambodia': 'Kambodscha',
    'cameroon': 'Kamerun',
    'canada': 'Kanada',
    'cape verde': 'Kap Verde',
    'cabo verde': 'Kap Verde',
    'central african republic': 'Zentralafrikanische Republik',
    'chad': 'Tschad',
    'chile': 'Chile',
    'china': 'China',
    "china pr": 'China',
    'colombia': 'Kolumbien',
    'comoros': 'Komoren',
    'congo': 'Kongo (Republik)',
    'congo dr': 'Kongo (Demokratische Republik)',
    'democratic republic of congo': 'Kongo (Demokratische Republik)',
    'dr congo': 'Kongo (Demokratische Republik)',
    'costa rica': 'Costa Rica',
    'croatia': 'Kroatien',
    'cuba': 'Kuba',
    'curacao': 'Curacao',
    'cyprus': 'Zypern',
    'czech republic': 'Tschechien',
    'czechia': 'Tschechien',
    'denmark': 'Dänemark',
    'djibouti': 'Dschibuti',
    'dominica': 'Dominica',
    'dominican republic': 'Dominikanische Republik',
    'ecuador': 'Ecuador',
    'egypt': 'Ägypten',
    'el salvador': 'El Salvador',
    'england': 'England',
    'equatorial guinea': 'Äquatorialguinea',
    'eritrea': 'Eritrea',
    'estonia': 'Estland',
    'eswatini': 'Eswatini',
    'ethiopia': 'Äthiopien',
    'fiji': 'Fidschi',
    'finland': 'Finnland',
    'france': 'Frankreich',
    'gabon': 'Gabun',
    'gambia': 'Gambia',
    'georgia': 'Georgien',
    'germany': 'Deutschland',
    'ghana': 'Ghana',
    'greece': 'Griechenland',
    'grenada': 'Grenada',
    'guadeloupe': 'Guadeloupe',
    'guatemala': 'Guatemala',
    'guinea': 'Guinea',
    'guinea-bissau': 'Guinea-Bissau',
    'guyana': 'Guyana',
    'haiti': 'Haiti',
    'holland': 'Niederlande',
    'honduras': 'Honduras',
    'hungary': 'Ungarn',
    'iceland': 'Island',
    'india': 'Indien',
    'indonesia': 'Indonesien',
    'iran': 'Iran',
    'iraq': 'Irak',
    'ireland': 'Irland',
    'republic of ireland': 'Irland',
    'israel': 'Israel',
    'italy': 'Italien',
    'ivory coast': 'Elfenbeinküste',
    "cote d'ivoire": 'Elfenbeinküste',
    'jamaica': 'Jamaika',
    'japan': 'Japan',
    'jordan': 'Jordanien',
    'kazakhstan': 'Kasachstan',
    'kenya': 'Kenia',
    'kiribati': 'Kiribati',
    'kosovo': 'Kosovo',
    'kuwait': 'Kuwait',
    'kyrgyzstan': 'Kirgisistan',
    'laos': 'Laos',
    'latvia': 'Lettland',
    'lebanon': 'Libanon',
    'lesotho': 'Lesotho',
    'liberia': 'Liberia',
    'libya': 'Libyen',
    'liechtenstein': 'Liechtenstein',
    'lithuania': 'Litauen',
    'luxembourg': 'Luxemburg',
    'madagascar': 'Madagaskar',
    'malawi': 'Malawi',
    'malaysia': 'Malaysia',
    'maldives': 'Malediven',
    'mali': 'Mali',
    'malta': 'Malta',
    'marshallinseln': 'Marshallinseln',
    'marshall islands': 'Marshallinseln',
    'mauritania': 'Mauretanien',
    'mauritius': 'Mauritius',
    'mexico': 'Mexiko',
    'micronesia': 'Mikronesien',
    'moldova': 'Moldau',
    'monaco': 'Monaco',
    'mongolia': 'Mongolei',
    'montenegro': 'Montenegro',
    'morocco': 'Marokko',
    'mozambique': 'Mosambik',
    'myanmar': 'Myanmar',
    'namibia': 'Namibia',
    'nauru': 'Nauru',
    'nepal': 'Nepal',
    'netherlands': 'Niederlande',
    'new zealand': 'Neuseeland',
    'nicaragua': 'Nicaragua',
    'niger': 'Niger',
    'nigeria': 'Nigeria',
    'north korea': 'Korea (Nord)',
    'north macedonia': 'Nordmazedonien',
    'northern ireland': 'Nordirland',
    'north ireland': 'Nordirland',
    'norway': 'Norwegen',
    'oman': 'Oman',
    'pakistan': 'Pakistan',
    'palau': 'Palau',
    'palestine': 'Palästina',
    'panama': 'Panama',
    'papua new guinea': 'Papua-Neuguinea',
    'paraguay': 'Paraguay',
    'peru': 'Peru',
    'philippines': 'Philippinen',
    'poland': 'Polen',
    'portugal': 'Portugal',
    'qatar': 'Katar',
    'romania': 'Rumänien',
    'russia': 'Russland',
    'rwanda': 'Ruanda',
    'samoa': 'Samoa',
    'san marino': 'San Marino',
    'sao tome and principe': 'São tomé und Príncipe',
    "são tomé and príncipe": 'São tomé und Príncipe',
    'saudi arabia': 'Saudi-Arabien',
    'scotland': 'Schottland',
    'senegal': 'Senegal',
    'serbia': 'Serbien',
    'seychelles': 'Seychellen',
    'sierra leone': 'Sierra Leone',
    'singapore': 'Singapur',
    'slovakia': 'Slowakei',
    'slovenia': 'Slowenien',
    'solomon islands': 'Salomonen',
    'somalia': 'Somalia',
    'south africa': 'Südafrika',
    'south korea': 'Südkorea',
    'korea republic': 'Südkorea',
    'south sudan': 'Südsudan',
    'spain': 'Spanien',
    'sri lanka': 'Sri Lanka',
    'sudan': 'Sudan',
    'suriname': 'Suriname',
    'sweden': 'Schweden',
    'switzerland': 'Schweiz',
    'syria': 'Syrien',
    'tajikistan': 'Tadschikistan',
    'tanzania': 'Tansania',
    'thailand': 'Thailand',
    'timor-leste': 'Timor-Leste',
    'east timor': 'Timor-Leste',
    'togo': 'Togo',
    'tonga': 'Tonga',
    'trinidad and tobago': 'Trinidad und Tobago',
    'tunisia': 'Tunesien',
    'turkey': 'Türkei',
    'türkiye': 'Türkei',
    'turkmenistan': 'Turkmenistan',
    'tuvalu': 'Tuvalu',
    'uganda': 'Uganda',
    'ukraine': 'Ukraine',
    'united arab emirates': 'Vereinigte Arabische Emirate',
    'uae': 'Vereinigte Arabische Emirate',
    'united kingdom': 'Vereinigtes Königreich',
    'united states': 'Vereinigte Staaten',
    'united states of america': 'Vereinigte Staaten',
    'usa': 'Vereinigte Staaten',
    'uruguay': 'Uruguay',
    'uzbekistan': 'Usbekistan',
    'vanuatu': 'Vanuatu',
    'venezuela': 'Venezuela',
    'vietnam': 'Vietnam',
    'wales': 'Wales',
    'yemen': 'Jemen',
    'zambia': 'Sambia',
    'zimbabwe': 'Simbabwe',
}


STRENGTH_DEFAULT_BASE = Decimal('40.00')
STRENGTH_QUANT = Decimal('0.01')
SNAPSHOT_HISTORY_LIMIT = 10


def strength_decimal(value):
    return Decimal(str(value)).quantize(STRENGTH_QUANT)


def prune_snapshot_history(model, filters, limit=SNAPSHOT_HISTORY_LIMIT):
    stale_ids = list(
        model.objects.filter(**filters).order_by(
            '-recorded_at',
            '-id',
        ).values_list('id', flat=True)[limit:]
    )
    if stale_ids:
        model.objects.filter(id__in=stale_ids).delete()


class DataSource(models.Model):
    CODE_TRANSFERMARKT = 'TM'
    CODE_FMINSIDE = 'FM'
    CODE_CMTRACKER = 'CMTRACKER'
    CODE_API_FOOTBALL = 'API_FOOTBALL'
    CODE_WEBSOCCER = 'WSC'
    CODE_CHOICES = [
        (CODE_TRANSFERMARKT, 'Transfermarkt'),
        (CODE_FMINSIDE, 'FMInside'),
        (CODE_CMTRACKER, 'CMTracker'),
        (CODE_API_FOOTBALL, 'API-Football'),
        (CODE_WEBSOCCER, 'Websoccer'),
    ]

    code = models.CharField(max_length=40, unique=True, choices=CODE_CHOICES)
    name = models.CharField(max_length=100)
    base_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Datenquelle'
        verbose_name_plural = 'Datenquellen'

    def __str__(self):
        return self.name


class StrengthFormulaSettings(models.Model):
    name = models.CharField(max_length=100, default='Standard')
    is_active = models.BooleanField(default=True)
    rating_modifier_factor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text='Faktor fuer (Spieler-Rating - Liga-Medianrating).',
    )
    default_league_median_rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('6.80'),
        help_text='Fallback, bis der Median dynamisch aus Massendaten berechnet wird.',
    )
    default_freshness = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
        help_text='Wird genutzt, wenn noch kein Spieler-Frischewert gepflegt ist.',
    )
    notes = models.TextField(
        blank=True,
        help_text='Balancing-Notizen, z. B. Peak-Verteilung oder offene Tests.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Spielstaerke-Modifikator'
        verbose_name_plural = 'Spielstaerke-Modifikatoren'

    def __str__(self):
        return self.name

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).order_by('id').first()


class StrengthModifierRule(models.Model):
    CATEGORY_MINUTES = 'minutes'
    CATEGORY_FRESHNESS = 'freshness'
    CATEGORY_CHOICES = [
        (CATEGORY_MINUTES, 'Minutenquote'),
        (CATEGORY_FRESHNESS, 'Frische'),
    ]

    settings = models.ForeignKey(
        StrengthFormulaSettings,
        on_delete=models.CASCADE,
        related_name='modifier_rules',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    label = models.CharField(max_length=100)
    min_value = models.DecimalField(max_digits=6, decimal_places=2)
    max_value = models.DecimalField(max_digits=6, decimal_places=2)
    modifier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text='Staerkepunkte. Bei Frische sind Abzuege negativ.',
    )
    risk_label = models.CharField(
        max_length=80,
        blank=True,
        help_text='Nur fuer Frische relevant, z. B. leichtes Risiko.',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = [
            'category',
            'sort_order',
            '-min_value',
        ]
        verbose_name = 'Spielstaerke-Regel'
        verbose_name_plural = 'Spielstaerke-Regeln'

    def __str__(self):
        return f'{self.get_category_display()} {self.min_value}-{self.max_value}: {self.modifier}'

    def matches(self, value):
        value = Decimal(value)
        return self.min_value <= value <= self.max_value


class League(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    level = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Liga-Ebene',
        help_text=(
            'Ebene im Ligasystem des Landes: 1 = Erstliga, 2 = Zweitliga. '
            'Steuert TV_SPLIT_LIGA und SPONSOR_SOCKEL (Finanzsystem Kap. 6/7).'
        ),
    )
    api_football_id = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
    )
    strength_coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        help_text='Liga-Koeffizient fuer Form- und Leistungsgewichtung.',
    )
    coefficient_source = models.CharField(
        max_length=100,
        blank=True,
        help_text='z. B. UEFA association coefficient oder interne Einstufung.',
    )
    logo_static_path = models.CharField(
        max_length=240,
        blank=True,
        help_text='Pfad zum Liga-Logo im Format competitions/{id}_comp.png — wird automatisch beim Hochladen gesetzt, nicht manuell befüllen.',
    )

    @property
    def logo_url(self):
        from .competition_assets import competition_logo_static_path
        return competition_logo_static_path(self)

    cl_spots = models.PositiveSmallIntegerField(
        default=2,
        verbose_name='Champions-League-Plätze',
    )
    el_spots = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Europa-League-Plätze',
    )
    conference_spots = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Conference-League-Plätze',
    )
    relegation_spots = models.PositiveSmallIntegerField(
        default=3,
        verbose_name='Abstiegsplätze',
    )
    season_winner = models.ForeignKey(
        'Club',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='league_titles',
        verbose_name='Meister (aktuelle Saison)',
    )
    cup_winner = models.ForeignKey(
        'Club',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cup_titles_legacy',
        verbose_name='Pokalsieger (Legacy — nicht mehr genutzt)',
    )

    COMPETITION_TYPE_LEAGUE = 'league'
    COMPETITION_TYPE_CUP = 'cup'
    COMPETITION_TYPE_CHOICES = [
        (COMPETITION_TYPE_LEAGUE, 'Liga'),
        (COMPETITION_TYPE_CUP, 'Pokal'),
    ]
    competition_type = models.CharField(
        max_length=10,
        choices=COMPETITION_TYPE_CHOICES,
        default=COMPETITION_TYPE_LEAGUE,
        verbose_name='Wettbewerbstyp',
    )
    max_teams = models.PositiveSmallIntegerField(
        default=18,
        verbose_name='Max. Teilnehmer',
        help_text='Maximale Anzahl Vereine (Liga) bzw. Pokalteilnehmer.',
    )

    @property
    def is_cup(self) -> bool:
        return self.competition_type == self.COMPETITION_TYPE_CUP

    def __str__(self):
        return self.name


class Club(models.Model):
    fm_inside_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True
    )
    api_football_id = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
    )
    transfermarkt_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text='Transfermarkt-Vereins-ID. Eindeutige Erkennung beim Import.',
    )
    cmtracker_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='CMTracker-Vereins-ID (Spalte existiert live bereits manuell).',
    )
    transfermarkt_profile_url = models.URLField(
        blank=True,
        help_text='Kanonischer Transfermarkt-Vereinslink.',
    )
    is_import_placeholder = models.BooleanField(
        default=False,
        verbose_name='Platzhalterverein',
        help_text=(
            'Automatisch beim Spielerimport angelegter Minimal-Verein '
            '(realer Stammverein / Leihgeber). Ohne Liga, Stadion, Finanzen.'
        ),
    )
    import_name_provisional = models.BooleanField(
        default=False,
        verbose_name='Vereinsname vorläufig (Import)',
        help_text=(
            'Beim Anlegen eines neuen Vereins per Spielerimport wurde der Name '
            'manuell eingegeben und soll noch durch den von Transfermarkt '
            'erkannten Namen bestätigt/aktualisiert werden.'
        ),
    )

    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20)
    founded_year = models.IntegerField()

    budget = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    # Transfersystem v2: harte Reservierungen (Escrow-Cache). Invariante:
    # reserved = Summe der Geldanteile aller führenden eigenen Gebote +
    # aller offenen gesendeten Deal-/Leihanfragen. Verfügbar = budget − reserved.
    # Wird transaktional nachgeführt und ist per
    # game.transfer_v2.escrow.recalc_reserved(club) reparierbar; die aktiven
    # FinanceReservation-Zeilen bleiben die Wahrheit, dieses Feld der Cache.
    reserved = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='Reserviert (€)',
        help_text='Cache der aktiven harten Reservierungen (Transfersystem v2).',
    )

    fan_popularity = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Fanbeliebtheit (1–100)',
        help_text='Wie beliebt ist der Verein bei Fans? Beeinflusst die Stadionauslastung.',
    )

    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE
    )

    managed_by = models.OneToOneField(
        'ManagerProfile',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_club',
        verbose_name='Aktueller Trainer',
        help_text=(
            'Welcher Manager leitet diesen Verein gerade? '
            'Bitte nicht direkt bearbeiten — stattdessen im Vereins-Admin '
            '"Trainer zuweisen" oder "Trainer entlassen" nutzen, '
            'damit die Karrierekarte automatisch aktualisiert wird.'
        ),
    )

    JOB_NONE = 'none'
    JOB_FREE_PICK = 'free_pick'
    JOB_NORMAL = 'normal'
    JOB_TOP = 'top'
    JOB_AVAILABILITY_CHOICES = [
        (JOB_NONE,      'Nicht freigegeben'),
        (JOB_FREE_PICK, 'Free Pick'),
        (JOB_NORMAL,    'Normale Bewerbung'),
        (JOB_TOP,       'Top-Bewerbung'),
    ]

    job_availability_type = models.CharField(
        max_length=20,
        choices=JOB_AVAILABILITY_CHOICES,
        default=JOB_FREE_PICK,
        verbose_name='Job-Freigabe',
        help_text=(
            'Legt fest, ob und mit welcher Bewerbungsart der Verein '
            'auf der Job-Angebote-Liste erscheint. '
            'Wird vom Creator nach einer Trainer-Entlassung manuell gesetzt.'
        ),
    )

    ai_buyer_paused = models.BooleanField(
        'KI-Käufer pausiert',
        default=False,
        help_text='Pausiert den KI-Käufer-Prüflauf dieses Vereins '
                  '(Admin-Eingriff über die KI-Transferzentrale).',
    )

    def __str__(self):
        return self.name

    def _asset_stem(self):
        """Dateinamen-Präfix für Club-Assets: FMI-ID wenn vorhanden, sonst ws_<pk>."""
        return str(self.fm_inside_id) if self.fm_inside_id else f'ws_{self.pk}'

    @property
    def crest_static_path(self):
        """Absolute Wappen-URL (fertige URL, KEIN Static-Pfad mehr).

        Vereine mit fm_inside_id laden aus der Assets-Struktur
        (ASSETS_BASE_URL + clubs/logos/{id}_club.png, kein Dateisystem-Check);
        Vereine ohne fm_inside_id (ws_<pk>) behalten den bisherigen
        Static-Fallback, aber ebenfalls als fertige URL.
        """
        if self.fm_inside_id:
            from .asset_urls import club_logo_url
            return club_logo_url(self.fm_inside_id)
        stem = self._asset_stem()
        for ext in ('png', 'svg'):
            path = f'game/images/crests/{stem}.{ext}'
            if finders.find(path):
                from django.templatetags.static import static
                return static(path)
        return ''

    @property
    def kit_static_paths(self):
        import os as _os
        from .asset_urls import assets_root, _base as _assets_base
        stem = self._asset_stem()
        kits = []
        for label, suffix in (('Heim', 'home'), ('Auswärts', 'away'), ('Third', 'third')):
            url = ''
            assets_path = _os.path.join(assets_root(), 'clubs', 'kits', f'{stem}_{suffix}.png')
            if _os.path.exists(assets_path):
                url = f'{_assets_base()}clubs/kits/{stem}_{suffix}.png'
            else:
                for ext in ('svg', 'png'):
                    candidate = f'game/images/kits/{stem}_{suffix}.{ext}'
                    if finders.find(candidate):
                        from django.templatetags.static import static
                        url = static(candidate)
                        break
            kits.append({'label': label, 'path': url})
        return kits


class Stadium(models.Model):
    club = models.OneToOneField(
        Club,
        on_delete=models.CASCADE,
        related_name='stadium',
    )
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=100)
    lawn_quality = models.PositiveSmallIntegerField(
        default=85,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Rasenqualität (1–100)',
    )

    nord_standing = models.PositiveIntegerField(default=0, verbose_name='Nord – Stehplätze')
    nord_seating  = models.PositiveIntegerField(default=0, verbose_name='Nord – Sitzplätze')
    nord_vip      = models.PositiveIntegerField(default=0, verbose_name='Nord – VIP')

    ost_standing  = models.PositiveIntegerField(default=0, verbose_name='Ost – Stehplätze')
    ost_seating   = models.PositiveIntegerField(default=0, verbose_name='Ost – Sitzplätze')
    ost_vip       = models.PositiveIntegerField(default=0, verbose_name='Ost – VIP')

    sued_standing = models.PositiveIntegerField(default=0, verbose_name='Süd – Stehplätze')
    sued_seating  = models.PositiveIntegerField(default=0, verbose_name='Süd – Sitzplätze')
    sued_vip      = models.PositiveIntegerField(default=0, verbose_name='Süd – VIP')

    west_standing = models.PositiveIntegerField(default=0, verbose_name='West – Stehplätze')
    west_seating  = models.PositiveIntegerField(default=0, verbose_name='West – Sitzplätze')
    west_vip      = models.PositiveIntegerField(default=0, verbose_name='West – VIP')

    price_standing = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('15.00'),
        verbose_name='Ticketpreis Steh (€)',
    )
    price_seating = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('35.00'),
        verbose_name='Ticketpreis Sitz (€)',
    )
    price_vip = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('120.00'),
        verbose_name='Ticketpreis VIP (€)',
    )

    # Stadionumfeld-Einrichtungen (0 = nicht vorhanden, max 3)
    nlz_level      = models.PositiveSmallIntegerField(default=0, verbose_name='NLZ Stufe')
    medizin_level  = models.PositiveSmallIntegerField(default=0, verbose_name='Medizin Stufe')
    training_level = models.PositiveSmallIntegerField(default=0, verbose_name='Trainingsgelände Stufe')
    office_level   = models.PositiveSmallIntegerField(default=0, verbose_name='Geschäftsstelle Stufe')

    @property
    def capacity_total(self):
        return (
            self.nord_standing + self.nord_seating + self.nord_vip +
            self.ost_standing  + self.ost_seating  + self.ost_vip  +
            self.sued_standing + self.sued_seating + self.sued_vip +
            self.west_standing + self.west_seating + self.west_vip
        )

    @property
    def capacity_standing(self):
        return self.nord_standing + self.ost_standing + self.sued_standing + self.west_standing

    @property
    def capacity_seating(self):
        return self.nord_seating + self.ost_seating + self.sued_seating + self.west_seating

    @property
    def capacity_vip(self):
        return self.nord_vip + self.ost_vip + self.sued_vip + self.west_vip

    def __str__(self):
        return f'{self.name} ({self.club.name})'

    class Meta:
        verbose_name = 'Stadion'
        verbose_name_plural = 'Stadien'


class StadiumExpansion(models.Model):
    STAND_CHOICES = [
        ('NORD', 'Nordkurve'),
        ('OST',  'Osttribüne'),
        ('SUED', 'Südkurve'),
        ('WEST', 'Westtribüne'),
    ]
    SEAT_TYPE_CHOICES = [
        ('STEH', 'Stehplatz'),
        ('SITZ', 'Sitzplatz'),
        ('VIP',  'VIP'),
    ]

    stadium    = models.ForeignKey(
        Stadium,
        on_delete=models.CASCADE,
        related_name='expansions',
    )
    stand      = models.CharField(max_length=4, choices=STAND_CHOICES)
    seat_type  = models.CharField(max_length=4, choices=SEAT_TYPE_CHOICES)
    seats_added = models.PositiveIntegerField()
    cost       = models.DecimalField(max_digits=14, decimal_places=2)
    ordered_at = models.DateTimeField(auto_now_add=True)
    # Bauzeit (Kap. 5.3): Zahlung sofort, Kapazität erst bei Fertigstellung.
    completes_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Fertigstellung',
        help_text='Wanduhr-Zeitpunkt, ab dem die Plätze aktiv werden (leer = sofort).',
    )
    applied = models.BooleanField(
        default=True, verbose_name='Kapazität übernommen',
        help_text='True, sobald die Plätze auf das Stadion gebucht wurden.',
    )

    class Meta:
        verbose_name = 'Stadionausbau'
        verbose_name_plural = 'Stadionausbauten'
        ordering = ['-ordered_at']

    def __str__(self):
        return (
            f'{self.stadium.name}: +{self.seats_added} {self.get_seat_type_display()} '
            f'({self.get_stand_display()})'
        )


class MatchdayRevenue(models.Model):
    """
    Protokolliert Stadioneinnahmen nach einem Heimspiel.
    Wird bei jedem Heimspiel automatisch berechnet und dem Vereinsbudget gutgeschrieben.
    """

    stadium = models.ForeignKey(
        'Stadium',
        on_delete=models.CASCADE,
        related_name='revenue_entries',
        verbose_name='Stadion',
    )
    match_result = models.OneToOneField(
        'MatchResult',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matchday_revenue',
        verbose_name='Spielergebnis',
    )
    match_label = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Spielbezeichnung',
    )
    competition_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Wettbewerb',
    )
    auslastung_pct = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        verbose_name='Auslastung (%)',
        help_text='Tatsächliche Auslastung dieses Spieltags in Prozent (0–100).',
    )
    attendance = models.PositiveIntegerField(
        default=0,
        verbose_name='Zuschauer',
    )
    attendance_standing = models.PositiveIntegerField(
        default=0, verbose_name='Zuschauer Stehplätze',
    )
    attendance_seating = models.PositiveIntegerField(
        default=0, verbose_name='Zuschauer Sitzplätze',
    )
    attendance_vip = models.PositiveIntegerField(
        default=0, verbose_name='Zuschauer VIP',
    )
    revenue_standing = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Einnahmen Stehplätze (€)',
    )
    revenue_seating = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Einnahmen Sitzplätze (€)',
    )
    revenue_vip = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Einnahmen VIP (€)',
    )
    revenue_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Gesamteinnahmen (€)',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Verbucht am',
    )

    class Meta:
        verbose_name = 'Spieltags-Einnahmen'
        verbose_name_plural = 'Spieltags-Einnahmen'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'{self.stadium.name} – {self.match_label or self.competition_name}: '
            f'{self.revenue_total:,.0f} € ({self.auslastung_pct} %)'
        )


class ClubPublicProfile(models.Model):
    club = models.OneToOneField(
        Club,
        on_delete=models.CASCADE,
        related_name='public_profile',
    )
    stadium_name = models.CharField(max_length=120, blank=True)
    stadium_capacity = models.PositiveIntegerField(default=0)
    average_attendance = models.PositiveIntegerField(default=0)
    city_name = models.CharField(max_length=120, blank=True)
    city_country = models.CharField(max_length=100, blank=True)
    map_lat = models.FloatField(null=True, blank=True, verbose_name='Breitengrad (Karte)')
    map_lng = models.FloatField(null=True, blank=True, verbose_name='Längengrad (Karte)')
    stadium_image_static_path = models.CharField(max_length=240, blank=True)
    city_image_static_path = models.CharField(max_length=240, blank=True)
    partner_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='partnered_public_profiles',
    )

    class Meta:
        verbose_name = 'Oeffentliches Vereinsprofil'
        verbose_name_plural = 'Oeffentliche Vereinsprofile'

    def __str__(self):
        return f'Profil {self.club}'


class ClubTrophy(models.Model):
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='public_trophies',
    )
    competition_name = models.CharField(max_length=120)
    count = models.PositiveSmallIntegerField(default=1)
    trophy_asset_id = models.CharField(max_length=80, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'competition_name']
        verbose_name = 'Vereinstitel'
        verbose_name_plural = 'Vereinstitel'

    # All FM Inside asset IDs below were visually verified against the badge
    # image files in game/static/game/images/trophies/ on 2026-06-02.
    # Each image was rendered and cross-checked against the known competition
    # trophy/badge.  No incorrect mappings were found; all IDs are confirmed.
    COMPETITION_DEFAULT_ASSETS = {
        # Continental / global — visually verified
        'Intercontinental':    'international-cup-1',
        'Champions League':    '1301394',
        'Copa Libertadores':   '1002136',   # confirmed: tall silver Copa Libertadores trophy
        'Europa League':       '1001960',   # confirmed: Europa League cup
        'Klub-WM':             '1001959',
        'FIFA Club World Cup': '1001959',
        'Club World Cup':      '1001959',
        # Germany — visually verified
        'Bundesliga':          '22',
        'DFB-Pokal':           '1301410',
        'DFL-Supercup':        '1301397',
        'Supercup':            '1301397',
        'DFB-Ligapokal':       '100',
        # England — visually verified
        'Premier League':      '1301393',   # confirmed: crown-topped trophy with lion handles
        'FA Cup':              '1301406',   # confirmed: silver cup with round handles
        # Spain — visually verified
        'La Liga':             '1301395',   # confirmed: silver La Liga trophy
        'Copa del Rey':        '1301417',   # confirmed: ornate golden cup
        'Supercopa de España': '1301419',   # confirmed
        # Italy — visually verified
        'Serie A':             '1301398',   # confirmed: distinctive golden sphere trophy
        'Coppa Italia':        '1301407',   # confirmed: ornate silver cup
        # Netherlands — visually verified
        'Eredivisie':          '1301412',   # confirmed: golden Eredivisie Schaal bowl
        'KNVB Cup':            '1301411',   # confirmed
        # Portugal — visually verified
        'Primeira Liga':       '1301403',   # confirmed
        'Taça de Portugal':    '1301404',   # confirmed: distinctive Portuguese cup badge
        # Serbia — visually verified
        'Superliga Srbije':    '1301427',   # confirmed: ornate league trophy
        'Kup Srbije':          '1301426',   # confirmed: Serbian cup competition badge
        # South America — domestic (no confirmed FM Inside badge IDs available;
        # generic competition-type assets are used as the best visual fallback)
        'Brasileirão':         'national championship 1',
        'Copa do Brasil':      'national cup 1',
        'Taça Brasil':         'national cup 1',
        'Primera División':    'national championship 1',
        'Copa Argentina':      'national cup 1',
        'Copa Uruguay':        'national cup 1',
        'División de Honor':   'national championship 1',
        'Copa Paraguay':       'national cup 1',
    }

    def save(self, *args, **kwargs):
        if not self.trophy_asset_id and self.competition_name in self.COMPETITION_DEFAULT_ASSETS:
            self.trophy_asset_id = self.COMPETITION_DEFAULT_ASSETS[self.competition_name]
        super().save(*args, **kwargs)

    @property
    def trophy_static_path(self):
        from .player_assets import get_cached_trophy_static_path

        return get_cached_trophy_static_path(self.trophy_asset_id)

    def __str__(self):
        return f'{self.club} - {self.competition_name}'


class MatchResult(models.Model):
    RESULT_WIN = 'SIEG'
    RESULT_DRAW = 'UNENTSCHIEDEN'
    RESULT_LOSS = 'NIEDERLAGE'
    RESULT_CHOICES = [
        (RESULT_WIN, 'Sieg'),
        (RESULT_DRAW, 'Unentschieden'),
        (RESULT_LOSS, 'Niederlage'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='match_results',
        verbose_name='Verein',
    )
    season = models.CharField(
        max_length=20,
        blank=True,
        help_text='Saison, z. B. "2023/24"',
        verbose_name='Saison',
    )
    competition_name = models.CharField(
        max_length=120,
        verbose_name='Wettbewerb',
    )
    matchday_label = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='Spieltag',
    )
    date_label = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='Datum',
    )
    home_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='home_match_results',
        verbose_name='Heimverein',
    )
    away_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='away_match_results',
        verbose_name='Auswärtsverein',
    )
    home_goals = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Heimtore')
    away_goals = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Auswärtstore')
    result_label = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        verbose_name='Ergebnis',
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text='Niedrigere Zahlen erscheinen zuerst (chronologische Reihenfolge).',
        verbose_name='Sortierreihenfolge',
    )

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Spielergebnis'
        verbose_name_plural = 'Spielergebnisse'

    def __str__(self):
        hg = self.home_goals if self.home_goals is not None else '?'
        ag = self.away_goals if self.away_goals is not None else '?'
        home = self.home_club.name if self.home_club else '?'
        away = self.away_club.name if self.away_club else '?'
        return f'{home} {hg}:{ag} {away} ({self.season})'


class TacticSetup(models.Model):
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='tactic_setups',
    )
    squad_scope = models.CharField(
        max_length=12,
        choices=SQUAD_SCOPE_CHOICES,
        default=SQUAD_PRO,
    )
    formation = models.JSONField(default=default_formation, blank=True)
    lineup = models.JSONField(default=default_lineup, blank=True)
    bench = models.JSONField(default=default_bench, blank=True)
    standards = models.JSONField(default=default_standards, blank=True)
    substitutions = models.JSONField(default=default_substitutions, blank=True)
    first_half = models.JSONField(default=default_half_tactic, blank=True)
    second_half = models.JSONField(default=default_half_tactic, blank=True)
    instructions = models.JSONField(default=default_instructions, blank=True)
    conditions = models.JSONField(default=default_conditions, blank=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    lineup_confirmed_matchday = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Bestätigt für Spieltag',
        help_text='Spieltagnummer, für die der Manager die Aufstellung zuletzt bestätigt hat.',
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name='Gesperrt',
        help_text='Taktik während laufender Spieltagssimulation gesperrt.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'squad_scope'],
                name='unique_club_tactic_setup_scope',
            ),
        ]
        ordering = ['club__name', 'squad_scope']
        verbose_name = 'Taktik'
        verbose_name_plural = 'Taktiken'

    def clean(self):
        super().clean()
        validate_formation(self.formation)
        if len(self.bench or []) > 7:
            raise ValidationError('Es sind maximal 7 Bankspieler erlaubt.')
        if len(self.substitutions or []) > 5:
            raise ValidationError('Es sind maximal 5 Wechsel erlaubt.')

    @property
    def formation_code(self):
        return formation_code(self.formation)

    @property
    def field_player_count(self):
        return field_player_count(self.formation)

    def __str__(self):
        return f'{self.club} - {self.get_squad_scope_display()} - {self.formation_code}'


class TacticTemplate(models.Model):
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='tactic_templates',
    )
    squad_scope = models.CharField(
        max_length=12,
        choices=SQUAD_SCOPE_CHOICES,
        default=SQUAD_PRO,
    )
    name = models.CharField(max_length=80)
    formation = models.JSONField(default=default_formation, blank=True)
    lineup = models.JSONField(default=default_lineup, blank=True)
    bench = models.JSONField(default=default_bench, blank=True)
    standards = models.JSONField(default=default_standards, blank=True)
    substitutions = models.JSONField(default=default_substitutions, blank=True)
    first_half = models.JSONField(default=default_half_tactic, blank=True)
    second_half = models.JSONField(default=default_half_tactic, blank=True)
    instructions = models.JSONField(default=default_instructions, blank=True)
    conditions = models.JSONField(default=default_conditions, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'squad_scope', 'name'],
                name='unique_club_tactic_template_scope_name',
            ),
        ]
        ordering = ['club__name', 'squad_scope', 'name']
        verbose_name = 'Taktikvorlage'
        verbose_name_plural = 'Taktikvorlagen'

    def clean(self):
        super().clean()
        validate_formation(self.formation)
        if len(self.bench or []) > 7:
            raise ValidationError('Es sind maximal 7 Bankspieler erlaubt.')
        if len(self.substitutions or []) > 5:
            raise ValidationError('Es sind maximal 5 Wechsel erlaubt.')
        if self.club_id and self.squad_scope:
            existing = TacticTemplate.objects.filter(
                club_id=self.club_id,
                squad_scope=self.squad_scope,
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.count() >= 10:
                raise ValidationError('Es sind maximal 10 Taktikvorlagen pro Bereich erlaubt.')

    @property
    def formation_code(self):
        return formation_code(self.formation)

    def __str__(self):
        return f'{self.club} - {self.get_squad_scope_display()} - {self.name}'


class ClubNewsItem(models.Model):
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='public_news',
    )
    title = models.CharField(max_length=160)
    subtitle = models.TextField(blank=True, default='')
    category = models.CharField(max_length=50, default='Sonstiges')
    outlet = models.CharField(max_length=50, default='Vereinsredaktion')
    published_at = models.DateField(default=timezone.localdate)
    views_count = models.PositiveIntegerField(default=0)
    is_new = models.BooleanField(default=False)
    is_social = models.BooleanField(default=False)
    card_data = models.JSONField(null=True, blank=True)
    blocks = models.JSONField(default=list)
    img_path = models.CharField(max_length=240, blank=True, default='')
    img_height = models.PositiveSmallIntegerField(default=120)
    thumbnail_static_path = models.CharField(max_length=240, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='published_news',
        verbose_name='Verfasser',
    )

    class Meta:
        ordering = ['sort_order', '-published_at', '-id']
        verbose_name = 'Vereinsnews'
        verbose_name_plural = 'Vereinsnews'

    def __str__(self):
        return f'{self.club} - {self.title}'

    def to_vn_dict(self, request=None):
        """Serialisiert das Item für vereinsnews.js (VN_DATA.art/social)."""
        author = self.published_by
        return {
            'id': f'db_{self.pk}',
            'pk': self.pk,
            'kat': self.category,
            'outlet': self.outlet,
            'title': self.title,
            'sub': self.subtitle,
            'date': self.published_at.strftime('%d.%m.%Y'),
            'views': self.views_count,
            'isNew': self.is_new,
            'img': self.img_path or None,
            'imgH': self.img_height,
            'card': self.card_data,
            'blocks': self.blocks or [],
            'author': author.username if author else None,
            'author_url': f'/manager/{author.username}/' if author else None,
        }


class LeagueNews(models.Model):
    """Liga-News — nicht vereinsgebunden, für die Liga-Seite."""
    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name='news_items',
        verbose_name='Liga',
    )
    title = models.CharField(max_length=160, verbose_name='Titel')
    published_at = models.DateField(default=timezone.localdate, verbose_name='Veröffentlicht')
    thumbnail_static_path = models.CharField(max_length=240, blank=True, verbose_name='Vorschaubild')
    body = models.TextField(blank=True, verbose_name='Text')
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', '-published_at', '-id']
        verbose_name = 'Liga-News'
        verbose_name_plural = 'Liga-News'

    def __str__(self):
        return f'[{self.league}] {self.title}'


class LeagueStandings(models.Model):
    """Ligatabelle — eine Zeile pro Verein pro Saison.

    Wird bei Saisonbeginn mit 0 initialisiert.
    Der Admin kann `point_deduction` setzen (Punktabzug).
    `points` wird bei jeder Ergebnisänderung aktualisiert.
    `form` speichert die letzten 5 Spiele als String, z.B. 'WWDLW'.
    `position_change` = vorherige Position - aktuelle Position (>0 = aufgestiegen).
    """

    FORM_WIN = 'W'
    FORM_DRAW = 'D'
    FORM_LOSS = 'L'

    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name='standings',
        verbose_name='Liga',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.CASCADE,
        related_name='league_standings',
        verbose_name='Verein',
    )
    season = models.CharField(
        max_length=20,
        default='0',
        verbose_name='Saison',
        help_text='Numerische Saisonnummer als String (z. B. "0", "1", "2") – passend zu GameSeasonState.current_season.',
    )
    position = models.PositiveSmallIntegerField(default=0, verbose_name='Platz')
    position_change = models.SmallIntegerField(
        default=0,
        verbose_name='Platzierungsänderung',
        help_text='Positiv = aufgestiegen, negativ = abgestiegen, 0 = unverändert.',
    )
    played = models.PositiveSmallIntegerField(default=0, verbose_name='Spiele')
    won = models.PositiveSmallIntegerField(default=0, verbose_name='Siege')
    drawn = models.PositiveSmallIntegerField(default=0, verbose_name='Unentschieden')
    lost = models.PositiveSmallIntegerField(default=0, verbose_name='Niederlagen')
    goals_for = models.PositiveSmallIntegerField(default=0, verbose_name='Tore')
    goals_against = models.PositiveSmallIntegerField(default=0, verbose_name='Gegentore')
    points = models.SmallIntegerField(default=0, verbose_name='Punkte')
    point_deduction = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Punktabzug',
        help_text='Vom Admin vergebener Punktabzug (wird von Punkten abgezogen).',
    )
    form = models.CharField(
        max_length=5,
        blank=True,
        default='',
        verbose_name='Form (letzte 5)',
        help_text='5-stelliger String aus W/D/L, neuestes Ergebnis zuerst. z.B. "WWDLW".',
    )

    @property
    def goal_difference(self):
        return self.goals_for - self.goals_against

    @property
    def goals_display(self):
        return f'{self.goals_for}:{self.goals_against}'

    class Meta:
        ordering = ['position', '-points', 'club__name']
        unique_together = [('league', 'club', 'season')]
        verbose_name = 'Ligatabelle-Eintrag'
        verbose_name_plural = 'Ligatabelle'

    def __str__(self):
        return f'{self.season} | #{self.position} {self.club.name} ({self.points} Pkt)'


class SeasonFixture(models.Model):
    """Spielplan — ein Eintrag pro Partie pro Spieltag.

    `home_goals`/`away_goals` sind None, solange das Spiel nicht gespielt wurde.
    `home_lineup_set`/`away_lineup_set` zeigen, ob die Aufstellung steht (Haken).
    """

    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name='fixtures',
        verbose_name='Liga',
    )
    matchday = models.PositiveSmallIntegerField(verbose_name='Spieltag')
    home_club = models.ForeignKey(
        'Club',
        on_delete=models.CASCADE,
        related_name='home_fixtures',
        verbose_name='Heimverein',
    )
    away_club = models.ForeignKey(
        'Club',
        on_delete=models.CASCADE,
        related_name='away_fixtures',
        verbose_name='Auswärtsverein',
    )
    scheduled_date = models.DateField(null=True, blank=True, verbose_name='Datum')
    scheduled_time = models.TimeField(null=True, blank=True, verbose_name='Uhrzeit')
    season = models.CharField(max_length=20, default='0', verbose_name='Saison')
    home_goals = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Heimtore')
    away_goals = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Auswärtstore')
    is_played = models.BooleanField(default=False, verbose_name='Gespielt')
    home_lineup_set = models.BooleanField(default=False, verbose_name='Heimaufstellung steht')
    away_lineup_set = models.BooleanField(default=False, verbose_name='Auswärtsaufstellung steht')
    home_lineup_malus = models.BooleanField(
        default=False,
        verbose_name='Heim-Stärkemalus (-20 %)',
        help_text='Automatisch gesetzt wenn der Heim-Manager keine Aufstellung gestellt hat.',
    )
    away_lineup_malus = models.BooleanField(
        default=False,
        verbose_name='Auswärts-Stärkemalus (-20 %)',
        help_text='Automatisch gesetzt wenn der Auswärts-Manager keine Aufstellung gestellt hat.',
    )
    simulated_match = models.OneToOneField(
        'SimulatedMatch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='season_fixture',
        verbose_name='Spielbericht (V2)',
        help_text='Verlinkter SimulatedMatch-Eintrag mit V2-Report-Daten.',
    )

    @property
    def result_display(self):
        if self.is_played and self.home_goals is not None and self.away_goals is not None:
            return f'{self.home_goals}:{self.away_goals}'
        return None

    class Meta:
        ordering = ['matchday', 'scheduled_date', 'scheduled_time']
        verbose_name = 'Spielplan-Eintrag'
        verbose_name_plural = 'Spielplan'

    def __str__(self):
        result = f' ({self.home_goals}:{self.away_goals})' if self.is_played else ''
        return f'[{self.league}] ST{self.matchday}: {self.home_club.short_name} vs {self.away_club.short_name}{result}'


class Player(models.Model):
    POSITION_CHOICES = [
        ('TW', 'TW'),
        ('IV', 'IV'),
        ('LV', 'LV'),
        ('RV', 'RV'),
        ('LOV', 'LOV'),
        ('ROV', 'ROV'),
        ('DM', 'DM'),
        ('ZM', 'ZM'),
        ('LM', 'LM'),
        ('RM', 'RM'),
        ('LOM', 'LOM'),
        ('ROM', 'ROM'),
        ('OM', 'OM'),
        ('LF', 'LF'),
        ('RF', 'RF'),
        ('ST', 'ST'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    wsc_player_id = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        help_text='Stabile Websoccer-ID fuer Assets, Graphen und externe Zuordnung.',
    )
    fm_inside_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True
    )
    transfermarkt_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True
    )
    api_football_id = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
    )
    transfermarkt_profile_url = models.URLField(blank=True)
    transfermarkt_market_value_url = models.URLField(blank=True)
    date_of_birth = models.DateField(
        null=True,
        blank=True
    )
    nationalities = models.CharField(
        max_length=150,
        blank=True
    )
    nt_nationality = models.CharField(
        'Nationalmannschafts-Nation',
        max_length=60,
        blank=True,
        help_text=(
            'Die Nation, für die der Spieler international registriert ist. '
            'Wird für das NT-Badge auf dem Spielerprofil verwendet. '
            'Leer lassen, um automatisch die erste Nationalität zu verwenden.'
        ),
    )
    age = models.IntegerField()
    height_cm = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Koerpergroesse in Zentimetern.',
    )
    strong_foot = models.CharField(
        max_length=10,
        blank=True,
        choices=[
            ('L', 'Links'),
            ('R', 'Rechts'),
            ('B', 'Beidfuss'),
        ],
        help_text='Staerkerer Fuss des Spielers.',
    )
    shirt_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Trikotnummer des Spielers.',
    )

    position = models.CharField(
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    primary_position = models.CharField(
        max_length=100,
        choices=POSITION_CHOICES,
        blank=True
    )
    source_positions = models.CharField(
        max_length=100,
        choices=POSITION_CHOICES,
        blank=True
    )
    main_position_1 = models.CharField(
        'HP 1',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    main_position_2 = models.CharField(
        'HP 2',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    main_position_3 = models.CharField(
        'HP 3',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    secondary_position_1 = models.CharField(
        'NP 1',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    secondary_position_2 = models.CharField(
        'NP 2',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    secondary_position_3 = models.CharField(
        'NP 3',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )

    potential = models.IntegerField(default=50)

    market_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            'Marktwert in Euro. NULL bedeutet "unbekannt" — nie automatisch '
            'auf 0 setzen, da 0 ein echter Wert wäre.'
        ),
    )
    salary_per_match = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    contract_until = models.DateField(
        null=True,
        blank=True
    )

    club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    real_life_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        related_name='real_life_players',
        null=True,
        blank=True,
        help_text='Aktueller realer Verein, getrennt vom Websoccer-Verein.'
    )
    ws_injury_type = models.CharField(
        max_length=120,
        blank=True,
        help_text='Nur Websoccer-Verletzung, z. B. Muskelverletzung.'
    )
    ws_injury_days_remaining = models.PositiveSmallIntegerField(default=0)
    ws_suspension_reason = models.CharField(
        max_length=120,
        blank=True,
        help_text='Nur Websoccer-Sperre, z. B. Rotsperre.'
    )
    ws_suspension_matches_remaining = models.PositiveSmallIntegerField(default=0)

    LOAN_STATUS_CHOICES = [
        ('none', 'Kein Leihverhältnis'),
        ('loaned_in', 'Geliehen'),
        ('loaned_out', 'Verliehen'),
        ('extern_loan', 'Extern verliehen'),
    ]
    loan_status = models.CharField(
        'Leihstatus',
        max_length=12,
        choices=LOAN_STATUS_CHOICES,
        default='none',
        blank=True,
        help_text='Geliehen = im Verein aktiv, gehört einem anderen Verein. '
                  'Verliehen = gehört diesem Verein, spielt aktuell woanders.',
    )
    loan_partner_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        related_name='loan_partner_players',
        null=True,
        blank=True,
        help_text='Der andere Verein des Leihgeschäfts (Stamm- bzw. Leihverein).',
    )
    loan_until = models.DateField(
        'Leihe bis',
        null=True,
        blank=True,
    )
    is_on_transfer_list = models.BooleanField(
        'Auf Transferliste',
        default=False,
    )
    is_on_loan_list = models.BooleanField(
        'Auf Leihliste',
        default=False,
    )

    # ── Verkaufskategorien (Finanzsystem Phase 4, Spec Kap. 9.1) ──────────
    SALE_CATEGORY_CHOICES = [
        ('GELD', 'Verkauf gegen Geld'),
        ('TAUSCH', 'Nur Tausch'),
        ('GELD_TAUSCH', 'Geld oder Tausch'),
        ('UVK', 'Unverkäuflich'),
    ]
    sale_category = models.CharField(
        'Verkaufskategorie',
        max_length=12,
        choices=SALE_CATEGORY_CHOICES,
        default='UVK',
        help_text='Manager-Markierung: KI bietet nur auf GELD und '
                  'GELD_TAUSCH — und nur, wenn die Markierung sichtbar ist.',
    )
    sale_visible_to_ai = models.BooleanField(
        'Markierung für KI sichtbar',
        default=False,
        help_text='Nur sichtbar geschaltete Markierungen erhalten KI-Angebote '
                  '(Postfach-Hygiene).',
    )

    # ── Wechselsperre (Show-Auktion, Spec §7.1) ────────────────────────────
    transfer_locked_until = models.DateField(
        'Wechselsperre bis',
        null=True,
        blank=True,
        help_text='Bis zu diesem Datum (exklusiv) ist kein Vereinswechsel '
                  'möglich. Wird u. a. beim Show-Auktions-Zuschlag gesetzt '
                  '(21 Tage).',
    )

    @property
    def is_transfer_locked(self):
        if not self.transfer_locked_until:
            return False
        from django.utils import timezone as _tz
        return self.transfer_locked_until > _tz.localdate()

    @property
    def transfer_lock_days_remaining(self):
        if not self.transfer_locked_until:
            return 0
        from django.utils import timezone as _tz
        return max((self.transfer_locked_until - _tz.localdate()).days, 0)

    # ── Scouting-Pool (Task #594) ──────────────────────────────────────────
    POOL_STATUS_NONE = 'none'
    POOL_STATUS_SCOUTABLE = 'scoutable'
    POOL_STATUS_AUCTION_RESERVED = 'auction_reserved'
    POOL_STATUS_UNAVAILABLE = 'unavailable'
    POOL_STATUS_SHOW_AUCTION = 'show_auction'
    POOL_STATUS_CHOICES = [
        (POOL_STATUS_NONE, 'WSC-Spieler (kein Pool)'),
        (POOL_STATUS_SCOUTABLE, 'Scoutbar (Pool)'),
        (POOL_STATUS_AUCTION_RESERVED, 'Auktion reserviert'),
        (POOL_STATUS_UNAVAILABLE, 'Nicht verfügbar'),
        (POOL_STATUS_SHOW_AUCTION, 'Show-Auktion (Raum)'),
    ]
    pool_status = models.CharField(
        'Pool-Status',
        max_length=20,
        choices=POOL_STATUS_CHOICES,
        default=POOL_STATUS_NONE,
        help_text=(
            'Steuert die Scouting-Verfügbarkeit. Scoutbar ist nur erlaubt, '
            'wenn der Spieler keinen WSC-Verein hat (club=None). '
            'Auktion reserviert = Top-Star/Top-Talent, nie über Scouting.'
        ),
    )
    SCOUTING_CATEGORY_CHOICES = [
        ('', '– keine –'),
        ('backup', 'Back-up'),
        ('ergaenzung', 'Ergänzungsspieler'),
        ('rotation', 'Rotationsspieler'),
        ('stammkraft', 'Stammkraft'),
        ('talent', 'Jugendspieler / Talent'),
        ('topstar', 'Top-Star'),
        ('toptalent', 'Top-Talent'),
    ]
    scouting_category = models.CharField(
        'Scouting-Kategorie',
        max_length=20,
        choices=SCOUTING_CATEGORY_CHOICES,
        blank=True,
        default='',
        help_text='Absolute Klassifizierung für die Scouting-Suche (Creator-Pflege).',
    )
    wsc_conflict = models.BooleanField(
        'WSC-Konflikt',
        default=False,
        help_text='Markiert einen ungeklärten Konflikt mit einer WSC-Vereinszuordnung.',
    )
    is_callable = models.BooleanField(
        'Einberufbar',
        default=False,
        help_text='Spieler darf bei dünnem Pool ergänzend einberufen werden.',
    )
    admin_reviewed = models.BooleanField(
        'Admin-geprüft',
        default=False,
        help_text='Poolspieler wurde von einem Admin freigegeben.',
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_loaned_in(self):
        return self.loan_status == 'loaned_in'

    @property
    def is_loaned_out(self):
        return self.loan_status == 'loaned_out'

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def portrait_static_path(self):
        """Absolute Spielerbild-URL (fertige URL, KEIN Static-Pfad mehr).

        Mit fm_inside_id: Assets-Struktur (players/face_{id}.png), rein
        String-basiert ohne Dateisystem-Check — fehlende Bilder fängt der
        client-seitige onerror-Fallback ab. Ohne fm_inside_id: Default-SVG.
        """
        if not self.fm_inside_id:
            from .asset_urls import default_player_url
            return default_player_url()

        from .asset_urls import player_face_url
        return player_face_url(self.fm_inside_id)

    @property
    def cmt_headshot_url(self):
        """Beste CMT-Headshot-URL: cached-media > CDN-URL > ''."""
        try:
            prof = self.cmt_profile
        except Exception:
            return ''
        if prof.player_image_cached_path:
            from django.conf import settings
            return settings.MEDIA_URL + prof.player_image_cached_path
        return prof.player_image_url or ''

    @property
    def portrait_url(self):
        """Vollständige Portrait-URL für Templates.

        Konsistent mit den Club-Wappen: immer der Assets-Server-Pfad
        (portrait_static_path); fehlende Bilder fängt der client-seitige
        onerror-Fallback ab. CMT-Headshots werden nicht mehr verwendet.
        """
        return self.portrait_static_path

    @property
    def nation_badge_url(self):
        """CDN-URL für das Nationalitäts-Badge des Spielers.

        Nutzt nt_nationality (falls gesetzt), sonst die erste Nationalität
        aus dem nationalities-Feld. Gibt '' zurück wenn kein asset_id
        für die Nation hinterlegt ist.
        """
        nation = (self.nt_nationality or '').strip()
        if not nation and self.nationalities:
            nation = self.nationalities.split(',')[0].strip()
        if not nation:
            return ''
        entry = COUNTRY_FLAG_ASSETS.get(nation)
        if not entry:
            return ''
        asset_id = entry.get('asset_id')
        if not asset_id:
            return ''
        return f'https://playwebsoccer.de/assets/nations/{asset_id}_nation.png'

    @property
    def profile_portrait_static_path(self):
        from .player_assets import get_cached_profile_portrait_static_path

        return get_cached_profile_portrait_static_path(self)

    @property
    def strong_foot_label(self):
        return dict(self._meta.get_field('strong_foot').choices).get(
            self.strong_foot,
            '-',
        )

    @property
    def nationality_badges(self):
        from .asset_urls import flag_url as _flag_url
        countries = [
            country.strip()
            for country in self.nationalities.split(',')
            if country.strip()
        ]

        if not countries:
            try:
                cmt = self.cmt_profile
                if cmt.nationality:
                    countries = [cmt.nationality]
                if cmt.second_nationality and cmt.second_nationality not in countries:
                    countries.append(cmt.second_nationality)
            except Exception:
                pass

        return [
            {
                'name': country,
                'code': COUNTRY_FLAG_ASSETS.get(country, {'code': country[:2].upper()})['code'],
                'flag_url': (
                    _flag_url(COUNTRY_FLAG_ASSETS[country]['asset_id'])
                ) if country in COUNTRY_FLAG_ASSETS and COUNTRY_FLAG_ASSETS[country].get('asset_id') else '',
            }
            for country in countries
        ]

    @property
    def flag_url(self):
        """Flag URL der primären Nationalität via FM-Nation-ID."""
        from .asset_urls import flag_url as _flag_url
        nation = (self.nt_nationality or '').strip()
        if not nation and self.nationalities:
            nation = self.nationalities.split(',')[0].strip()
        if not nation:
            return ''
        asset = COUNTRY_FLAG_ASSETS.get(nation, {})
        aid = asset.get('asset_id', '')
        return _flag_url(aid) if aid else ''

    @property
    def nation_name(self):
        """Primäre Nationalität (Ländername)."""
        nation = (self.nt_nationality or '').strip()
        if not nation and self.nationalities:
            nation = self.nationalities.split(',')[0].strip()
        return nation

    @property
    def primary_nation_crest(self):
        countries = [
            country.strip()
            for country in self.nationalities.split(',')
            if country.strip()
        ]
        if not countries:
            return {}

        country = countries[0]
        nation_asset = COUNTRY_FLAG_ASSETS.get(country)
        if not nation_asset:
            return {}

        from .player_assets import get_cached_nation_static_path

        static_path = get_cached_nation_static_path(nation_asset.get('asset_id', ''))
        if not static_path:
            return {}

        return {
            'name': country,
            'static_path': static_path,
        }

    @property
    def main_positions(self):
        return [
            position
            for position in [
                self.main_position_1,
                self.main_position_2,
                self.main_position_3,
            ]
            if position
        ]

    @property
    def secondary_positions(self):
        return [
            position
            for position in [
                self.secondary_position_1,
                self.secondary_position_2,
                self.secondary_position_3,
            ]
            if position
        ]

    @property
    def all_position_codes(self):
        return self.main_positions + self.secondary_positions

    @property
    def is_ws_injured(self):
        return bool(self.ws_injury_type and self.ws_injury_days_remaining > 0)

    @property
    def is_ws_suspended(self):
        return bool(
            self.ws_suspension_reason and self.ws_suspension_matches_remaining > 0
        )

    def get_source_rating(self, source):
        prefetched_ratings = getattr(
            self,
            '_prefetched_objects_cache',
            {},
        ).get('source_ratings')

        if prefetched_ratings is not None:
            for rating in prefetched_ratings:
                if rating.source == source:
                    return rating

            return None

        return self.source_ratings.filter(source=source).first()

    @property
    def cmtracker_source_rating(self):
        return self.get_source_rating(PlayerSourceRating.SOURCE_CMTRACKER)

    @property
    def fm_source_rating(self):
        return self.get_source_rating(PlayerSourceRating.SOURCE_FM)

    @property
    def source_rating_count(self):
        return sum(
            1
            for rating in [self.cmtracker_source_rating, self.fm_source_rating]
            if rating
        )

    @property
    def source_base_quality(self):
        if self.source_rating_count == 2:
            return 'complete'

        if self.source_rating_count == 1:
            return 'partial'

        return 'default'

    @property
    def source_base_quality_label(self):
        labels = {
            'complete': 'CMTracker + FM',
            'partial': 'nur eine Quelle',
            'default': 'Default 40.00',
        }
        return labels[self.source_base_quality]

    @property
    def uses_default_base_strength(self):
        return self.source_base_quality == 'default'

    @property
    def calculated_base_strength(self):
        ea_rating = self.cmtracker_source_rating
        fm_rating = self.fm_source_rating

        if ea_rating and fm_rating:
            return strength_decimal(ea_rating.rating + fm_rating.rating)

        if ea_rating:
            return strength_decimal(ea_rating.rating * 2)

        if fm_rating:
            return strength_decimal(fm_rating.rating * 2)

        return STRENGTH_DEFAULT_BASE

    @property
    def calculated_potential_strength(self):
        ea_rating = self.cmtracker_source_rating
        fm_rating = self.fm_source_rating

        ea_potential = ea_rating.potential if ea_rating else None
        fm_potential = fm_rating.potential if fm_rating else None

        if ea_potential is not None and fm_potential is not None:
            return strength_decimal(ea_potential + fm_potential)

        if ea_potential is not None:
            return strength_decimal(ea_potential * 2)

        if fm_potential is not None:
            return strength_decimal(fm_potential * 2)

        if self.uses_default_base_strength:
            return None

        return self.calculated_base_strength

    @property
    def source_strength_explanation(self):
        ea_rating = self.cmtracker_source_rating
        fm_rating = self.fm_source_rating
        lines = []

        if ea_rating:
            lines.append(f'CMTracker Staerke: {ea_rating.rating}')
        else:
            lines.append('CMTracker Staerke fehlt')

        if fm_rating:
            lines.append(f'FM Staerke: {fm_rating.rating}')
        else:
            lines.append('FM Staerke fehlt')

        if self.calculated_base_strength is not None:
            if ea_rating and fm_rating:
                lines.append(
                    f'Base = CMTracker + FM = {self.calculated_base_strength:.2f}'
                )
            elif ea_rating:
                lines.append(
                    f'Base = CMTracker * 2 = {self.calculated_base_strength:.2f}'
                )
            elif fm_rating:
                lines.append(
                    f'Base = FM * 2 = {self.calculated_base_strength:.2f}'
                )
            else:
                lines.append('Base = Default = 40.00')
        else:
            lines.append('Base kann erst mit CMTracker- und FM-Wert berechnet werden')

        if ea_rating and ea_rating.potential is not None:
            lines.append(f'CMTracker Potential: {ea_rating.potential}')
        else:
            lines.append('CMTracker Potential fehlt')

        if fm_rating and fm_rating.potential is not None:
            lines.append(f'FM Potential: {fm_rating.potential}')
        else:
            lines.append('FM Potential fehlt')

        if self.calculated_potential_strength is not None:
            lines.append(
                'Potential-Ceiling = '
                f'{self.calculated_potential_strength:.2f}'
            )

        return ' | '.join(lines)

    @classmethod
    def from_db(cls, db, field_names, values, **kwargs):
        instance = super().from_db(db, field_names, values, **kwargs)
        # Geladenen Vereinsstand merken, um echte Vereinswechsel beim
        # Speichern zu erkennen (Vereinsstationen-Historie, Phase 0
        # Finanzsystem). Wichtig: nur aus __dict__ lesen — bei .only()/
        # defer()-Loads ohne club würde ein Attributzugriff sonst eine
        # zusätzliche Query pro Instanz auslösen (N+1).
        instance._loaded_club_id = instance.__dict__.get(
            'club_id', _CLUB_HISTORY_UNSET
        )
        return instance

    def save(self, *args, **kwargs):
        if self.nationalities:
            self.nationalities = ', '.join(
                p.strip()
                for p in self.nationalities.replace(';', ',').split(',')
                if p.strip()
            )
        is_new = self._state.adding
        old_club_id = self.__dict__.get('_loaded_club_id', _CLUB_HISTORY_UNSET)
        if (
            not is_new
            and old_club_id is _CLUB_HISTORY_UNSET
            and self.pk is not None
            and 'club_id' in self.__dict__
        ):
            # Instanz wurde ohne club-Feld geladen (.only()/defer()), aber der
            # Verein wurde gesetzt: alten Stand vor dem Schreiben holen, damit
            # echte Wechsel nicht verloren gehen.
            old_club_id = (
                type(self).objects.filter(pk=self.pk)
                .values_list('club_id', flat=True)
                .first()
            )
        super().save(*args, **kwargs)
        self._track_club_history(is_new, old_club_id)
        self._loaded_club_id = self.__dict__.get(
            'club_id', _CLUB_HISTORY_UNSET
        )

    def _track_club_history(self, is_new, old_club_id):
        """Erfasst eine Vereinsstation bei Neuanlage mit Verein oder echtem
        Vereinswechsel. Creator-/Admin-Korrekturen setzen
        ``_suppress_club_history`` und erzeugen keine Zeile."""
        if getattr(self, '_suppress_club_history', False):
            return
        # Nur aus __dict__ lesen: bei weiterhin deferred club-Feld darf hier
        # keine Nachlade-Query ausgelöst werden (Feld unberührt = kein Wechsel).
        club_id = self.__dict__.get('club_id')
        if not club_id:
            return
        changed = is_new or (
            old_club_id is not _CLUB_HISTORY_UNSET
            and old_club_id != club_id
        )
        if not changed:
            return
        from game.club_history import record_club_stint
        record_club_stint(self.pk, club_id)


# Sentinel: unterscheidet „Instanz wurde nicht aus der DB geladen" von
# „Spieler war vereinslos (club_id=None)".
_CLUB_HISTORY_UNSET = object()


class PlayerExternalId(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='external_ids',
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='player_external_ids',
    )
    external_id = models.CharField(max_length=120)
    profile_url = models.URLField(blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    db_slug = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='DB-Slug',
        help_text='Optionaler Datenbank-Slug der Quell-DB (z. B. 26062400 für FC26).',
    )
    source_url = models.URLField(blank=True, verbose_name='Quell-URL')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Zuletzt gesehen',
        help_text='Letzter Import-Zeitpunkt, bei dem diese ID in der Quelle vorhanden war.',
    )

    class Meta:
        ordering = ['player__last_name', 'player__first_name', 'source__name']
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'external_id'],
                name='unique_external_player_id_per_source',
            ),
            models.UniqueConstraint(
                fields=['player', 'source'],
                name='unique_player_external_id_per_source',
            ),
        ]
        verbose_name = 'Spieler-ID'
        verbose_name_plural = 'Spieler-IDs'

    def __str__(self):
        return f'{self.player} - {self.source.code}: {self.external_id}'


class ClubExternalId(models.Model):
    """Externe IDs pro Verein (CMT, TM, FMI …) getrennt gespeichert."""

    club = models.ForeignKey(
        'Club',
        on_delete=models.CASCADE,
        related_name='external_ids',
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='club_external_ids',
    )
    external_id = models.CharField(max_length=120)
    db_slug = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='DB-Slug',
    )
    source_url = models.URLField(blank=True, verbose_name='Quell-URL')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, verbose_name='Zuletzt gesehen')

    class Meta:
        ordering = ['club__name', 'source__name']
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'external_id'],
                name='unique_external_club_id_per_source',
            ),
            models.UniqueConstraint(
                fields=['club', 'source'],
                name='unique_club_external_id_per_source',
            ),
        ]
        verbose_name = 'Vereins-ID'
        verbose_name_plural = 'Vereins-IDs'

    def __str__(self):
        return f'{self.club} - {self.source.code}: {self.external_id}'


class PlayerCMTProfile(models.Model):
    """Normalisiertes CMTracker-Spielerprofil (FC26, db=26062400).

    Wird bei jedem Import aus derselben oder neuerer CMT-DB vollständig
    überschrieben. Kein manueller Override-Schutz in V1.
    """

    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name='cmt_profile',
    )
    db_slug = models.CharField(max_length=50, verbose_name='DB-Slug')
    database_version = models.CharField(max_length=50, blank=True, verbose_name='DB-Version')
    cmt_player_id = models.CharField(max_length=40, db_index=True, verbose_name='CMT-Spieler-ID')

    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    known_as = models.CharField(max_length=100, blank=True, verbose_name='Bekannt als')
    display_name = models.CharField(max_length=100, blank=True, verbose_name='Anzeigename')
    nationality = models.CharField(max_length=60, blank=True, verbose_name='Nationalität')
    second_nationality = models.CharField(max_length=60, blank=True, verbose_name='2. Nationalität')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Geburtsdatum')

    overall = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Overall')
    potential = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Potential')
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Größe (cm)')
    weight_kg = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Gewicht (kg)')
    preferred_foot = models.CharField(max_length=10, blank=True, verbose_name='Starker Fuß')
    body_type = models.CharField(max_length=30, blank=True, verbose_name='Körpertyp')
    emotion = models.CharField(max_length=30, blank=True, verbose_name='Emotion')

    real_life_club = models.CharField(max_length=120, blank=True, verbose_name='Echtleben-Verein')
    on_loan_from_club = models.CharField(max_length=120, blank=True, verbose_name='Leihgeber')

    playstyles = models.JSONField(default=list, blank=True, verbose_name='PlayStyles')
    playstyles_plus = models.JSONField(default=list, blank=True, verbose_name='PlayStyles+')
    roles = models.JSONField(default=list, blank=True, verbose_name='Rollen')
    role_plus = models.JSONField(default=list, blank=True, verbose_name='Rolle+')
    role_plus_plus = models.JSONField(default=list, blank=True, verbose_name='Rolle++')

    player_image_url = models.URLField(blank=True, verbose_name='Spielerbild-URL')
    player_image_cached_path = models.CharField(max_length=255, blank=True, verbose_name='Spielerbild (lokal)')

    raw_payload = models.JSONField(default=dict, verbose_name='Rohpayload')
    payload_hash = models.CharField(max_length=64, blank=True, verbose_name='Payload-Hash')
    imported_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstimport')
    fetched_at = models.DateTimeField(null=True, blank=True, verbose_name='Abgerufen')
    last_imported_at = models.DateTimeField(null=True, blank=True, verbose_name='Letzter Import')
    last_verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Letzte Prüfung')
    source_priority = models.PositiveSmallIntegerField(default=10, verbose_name='Quell-Priorität')
    data_quality_flags = models.JSONField(default=dict, blank=True, verbose_name='Qualitäts-Flags')
    missing_required_fields = models.JSONField(default=list, blank=True, verbose_name='Fehlende Pflichtfelder')

    class Meta:
        verbose_name = 'CMT-Spielerprofil'
        verbose_name_plural = 'CMT-Spielerprofile'

    def __str__(self):
        return f'CMT {self.cmt_player_id} → {self.player}'


class PlayerCMTAttributeProfile(models.Model):
    """Vollständige CMTracker-Attribute eines Spielers (FC26).

    Wird bei jedem Import überschrieben.
    """

    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name='cmt_attribute_profile',
    )
    db_slug = models.CharField(max_length=50, verbose_name='DB-Slug')

    pac = models.PositiveSmallIntegerField(null=True, blank=True)
    sho = models.PositiveSmallIntegerField(null=True, blank=True)
    pas = models.PositiveSmallIntegerField(null=True, blank=True)
    dri = models.PositiveSmallIntegerField(null=True, blank=True)
    def_rating = models.PositiveSmallIntegerField(null=True, blank=True, db_column='def_rating', verbose_name='def')
    phy = models.PositiveSmallIntegerField(null=True, blank=True)

    acceleration = models.PositiveSmallIntegerField(null=True, blank=True)
    sprint_speed = models.PositiveSmallIntegerField(null=True, blank=True)
    agility = models.PositiveSmallIntegerField(null=True, blank=True)
    balance = models.PositiveSmallIntegerField(null=True, blank=True)
    jumping = models.PositiveSmallIntegerField(null=True, blank=True)
    stamina = models.PositiveSmallIntegerField(null=True, blank=True)
    strength = models.PositiveSmallIntegerField(null=True, blank=True)
    reactions = models.PositiveSmallIntegerField(null=True, blank=True)
    aggression = models.PositiveSmallIntegerField(null=True, blank=True)
    composure = models.PositiveSmallIntegerField(null=True, blank=True)
    interceptions = models.PositiveSmallIntegerField(null=True, blank=True)
    positioning = models.PositiveSmallIntegerField(null=True, blank=True)
    vision = models.PositiveSmallIntegerField(null=True, blank=True)
    ball_control = models.PositiveSmallIntegerField(null=True, blank=True)
    crossing = models.PositiveSmallIntegerField(null=True, blank=True)
    dribbling = models.PositiveSmallIntegerField(null=True, blank=True)
    finishing = models.PositiveSmallIntegerField(null=True, blank=True)
    freekick_accuracy = models.PositiveSmallIntegerField(null=True, blank=True)
    heading_accuracy = models.PositiveSmallIntegerField(null=True, blank=True)
    long_passing = models.PositiveSmallIntegerField(null=True, blank=True)
    short_passing = models.PositiveSmallIntegerField(null=True, blank=True)
    marking = models.PositiveSmallIntegerField(null=True, blank=True)
    shot_power = models.PositiveSmallIntegerField(null=True, blank=True)
    long_shots = models.PositiveSmallIntegerField(null=True, blank=True)
    standing_tackle = models.PositiveSmallIntegerField(null=True, blank=True)
    sliding_tackle = models.PositiveSmallIntegerField(null=True, blank=True)
    volleys = models.PositiveSmallIntegerField(null=True, blank=True)
    curve = models.PositiveSmallIntegerField(null=True, blank=True)
    penalties = models.PositiveSmallIntegerField(null=True, blank=True)

    gk_diving = models.PositiveSmallIntegerField(null=True, blank=True)
    gk_handling = models.PositiveSmallIntegerField(null=True, blank=True)
    gk_kicking = models.PositiveSmallIntegerField(null=True, blank=True)
    gk_reflexes = models.PositiveSmallIntegerField(null=True, blank=True)
    gk_positioning = models.PositiveSmallIntegerField(null=True, blank=True)

    raw_attributes = models.JSONField(default=dict, verbose_name='Rohdaten')
    imported_at = models.DateTimeField(auto_now_add=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    payload_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name = 'CMT-Attributprofil'
        verbose_name_plural = 'CMT-Attributprofile'

    def __str__(self):
        return f'CMT-Attr → {self.player}'


class PlayerTMProfile(models.Model):
    """Transfermarkt-Profil eines Spielers (Marktwert, Position, Kader-Quelle)."""

    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name='tm_profile',
    )
    tm_player_id = models.CharField(max_length=40, blank=True, verbose_name='TM-Spieler-ID')
    tm_club_id = models.CharField(max_length=40, blank=True, verbose_name='TM-Vereins-ID')
    market_value = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True,
        verbose_name='Marktwert (€)',
    )
    market_value_date = models.DateField(null=True, blank=True, verbose_name='Marktwert-Datum')
    tm_position_raw = models.CharField(max_length=80, blank=True, verbose_name='TM-Position (Rohtext)')
    tm_position_calculated_websoccer = models.CharField(
        max_length=10, blank=True,
        verbose_name='WS-Position (berechnet)',
    )
    source_url = models.URLField(blank=True, verbose_name='TM-URL')
    imported_at = models.DateTimeField(auto_now_add=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    last_imported_at = models.DateTimeField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    data_quality_flags = models.JSONField(default=dict, blank=True)
    missing_required_fields = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'TM-Spielerprofil'
        verbose_name_plural = 'TM-Spielerprofile'

    def __str__(self):
        return f'TM {self.tm_player_id} → {self.player}'


class PlayerFMIProfile(models.Model):
    """FMInside-Profil eines Spielers (Stärke, Potential, Attribute aus FM26)."""

    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name='fmi_profile',
    )
    fmi_id = models.CharField(max_length=40, blank=True, verbose_name='FMI-ID')
    fmi_overall = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Overall (FMI)')
    fmi_potential = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Potential (FMI)')
    fmi_attributes = models.JSONField(default=dict, blank=True, verbose_name='FMI-Attribute')
    fmi_version = models.CharField(max_length=20, blank=True, verbose_name='FMI-Version (z. B. FM26)')
    imported_at = models.DateTimeField(auto_now_add=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    last_imported_at = models.DateTimeField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    data_quality_flags = models.JSONField(default=dict, blank=True)
    missing_required_fields = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'FMI-Spielerprofil'
        verbose_name_plural = 'FMI-Spielerprofile'

    def __str__(self):
        return f'FMI {self.fmi_id} → {self.player}'


class ClubCMTProfile(models.Model):
    """Normalisiertes CMTracker-Vereinsprofil."""

    club = models.OneToOneField(
        'Club',
        on_delete=models.CASCADE,
        related_name='cmt_profile',
    )
    db_slug = models.CharField(max_length=50, verbose_name='DB-Slug')
    team_id = models.CharField(max_length=40, blank=True, verbose_name='CMT-Team-ID')
    league_id = models.CharField(max_length=40, blank=True, verbose_name='CMT-Liga-ID')

    name = models.CharField(max_length=120, blank=True, verbose_name='CMT-Name')
    league_name = models.CharField(max_length=120, blank=True, verbose_name='Liga (CMT)')
    nation = models.CharField(max_length=80, blank=True, verbose_name='Nation')
    country = models.CharField(max_length=80, blank=True, verbose_name='Land')

    foundation_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Gründungsjahr')
    popularity = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Popularität')
    domestic_prestige = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Nationales Prestige')
    international_prestige = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Int. Prestige')
    profitability = models.SmallIntegerField(null=True, blank=True, verbose_name='Profitabilität')

    home_kit = models.JSONField(default=dict, blank=True, verbose_name='Heimtrikot')
    away_kit = models.JSONField(default=dict, blank=True, verbose_name='Auswärtstrikot')
    third_kit = models.JSONField(default=dict, blank=True, verbose_name='3. Trikot')

    raw_payload = models.JSONField(default=dict, verbose_name='Rohpayload')
    payload_hash = models.CharField(max_length=64, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    last_imported_at = models.DateTimeField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    source_priority = models.PositiveSmallIntegerField(default=10)
    data_quality_flags = models.JSONField(default=dict, blank=True)
    missing_required_fields = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'CMT-Vereinsprofil'
        verbose_name_plural = 'CMT-Vereinsprofile'

    def __str__(self):
        return f'CMT-Club {self.team_id} → {self.club}'


class ClubTMProfile(models.Model):
    """Transfermarkt-Vereinsprofil (Kader-/Kaderwert-Quelle)."""

    club = models.OneToOneField(
        'Club',
        on_delete=models.CASCADE,
        related_name='tm_profile',
    )
    tm_club_id = models.CharField(max_length=40, blank=True, verbose_name='TM-Vereins-ID')
    tm_club_url = models.URLField(blank=True, verbose_name='TM-Vereinsseite')
    squad_source_url = models.URLField(blank=True, verbose_name='Kaderseite (TM)')
    imported_at = models.DateTimeField(auto_now_add=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    last_imported_at = models.DateTimeField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    data_quality_flags = models.JSONField(default=dict, blank=True)
    missing_required_fields = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'TM-Vereinsprofil'
        verbose_name_plural = 'TM-Vereinsprofile'

    def __str__(self):
        return f'TM-Club {self.tm_club_id} → {self.club}'


class PlayerSourceRating(models.Model):
    SOURCE_CMTRACKER = 'CMTRACKER'
    SOURCE_FM = 'FM'
    SOURCE_CHOICES = [
        (SOURCE_CMTRACKER, 'CMTracker'),
        (SOURCE_FM, 'FMInside'),
    ]

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='source_ratings',
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
    )
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )
    potential = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    # --- Einzelattribute (0-99) pro Quelle, getrennt gespeichert ---
    # Feldspieler-Attribute (FMI hat alle; CMTracker fuellt die meisten,
    # FMI-only-Felder bleiben bei der CMTracker-Zeile NULL).
    tempo = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    ausdauer = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    kraft = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    technik = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
        help_text='Nur FMInside.',
    )
    dribbling = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    passspiel = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    flanken = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    abschluss = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    kopfball = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    zweikampf = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    defensivstellung = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
        help_text='FMI: Positioning (defensiv) / CMTracker: Stellungsspiel.',
    )
    uebersicht = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    teamwork = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
        help_text='Nur FMInside.',
    )

    # Standards
    ecken = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
        help_text='Nur FMInside.',
    )
    freistoss = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    elfmeter = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )

    # Torwart-Attribute
    tw_reflexe = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    tw_fangsicherheit = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    tw_eins_gegen_eins = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
        help_text='Nur FMInside.',
    )
    tw_stellungsspiel = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    tw_passen = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )

    source_url = models.URLField(blank=True)
    source_version = models.CharField(
        max_length=100,
        blank=True,
    )
    checked_at = models.DateField(
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            'player__last_name',
            'player__first_name',
            'source',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'player',
                    'source',
                ],
                name='unique_player_source_rating',
            ),
        ]

    def __str__(self):
        return f'{self.player} - {self.get_source_display()} {self.rating}'

    @staticmethod
    def aggregate_attribute(ea_value, fm_value):
        """Berechnet ein Quell-Attribut aus CMTracker- und FM-Wert.

        Regel:
            beide vorhanden  → Durchschnitt (gerundet)
            eine vorhanden   → dieser Wert
            keine vorhanden  → None

        NULL/0-Unterscheidung: 0 ist ein echter Wert (Quelle liefert 0),
        None bedeutet „Quelle liefert dieses Attribut nicht".
        """
        if ea_value is not None and fm_value is not None:
            return round((ea_value + fm_value) / 2)
        if ea_value is not None:
            return ea_value
        if fm_value is not None:
            return fm_value
        return None


class PlayerFormSnapshot(models.Model):
    SOURCE_API_FOOTBALL = 'api_football'
    SOURCE_SPORTDB_FLASHSCORE = 'sportdb_flashscore'
    SOURCE_CHOICES = [
        (SOURCE_API_FOOTBALL, 'API-Football'),
        (SOURCE_SPORTDB_FLASHSCORE, 'SportDB / Flashscore'),
    ]

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='form_snapshots',
    )
    source = models.CharField(
        max_length=40,
        choices=SOURCE_CHOICES,
        default=SOURCE_API_FOOTBALL,
    )
    fixture_id = models.CharField(max_length=80)
    fixture_date = models.DateField()
    league_api_football_id = models.PositiveIntegerField(null=True, blank=True)
    team_api_football_id = models.PositiveIntegerField(null=True, blank=True)
    team_name = models.CharField(max_length=120, blank=True)
    opponent_name = models.CharField(max_length=120, blank=True)
    minutes_played = models.PositiveSmallIntegerField(default=0)
    possible_minutes = models.PositiveSmallIntegerField(default=90)
    minutes_quote = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    started = models.BooleanField(default=False)
    substituted_in = models.BooleanField(default=False)
    captain = models.BooleanField(default=False)
    position = models.CharField(max_length=10, blank=True)
    rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )
    goals = models.PositiveSmallIntegerField(default=0)
    assists = models.PositiveSmallIntegerField(default=0)
    yellow_cards = models.PositiveSmallIntegerField(default=0)
    red_cards = models.PositiveSmallIntegerField(default=0)
    raw_payload = models.JSONField(default=dict, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            '-fixture_date',
            '-fixture_id',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'player',
                    'source',
                    'fixture_id',
                ],
                name='unique_player_form_snapshot_source_fixture',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.possible_minutes:
            self.minutes_quote = strength_decimal(
                Decimal(self.minutes_played) /
                Decimal(self.possible_minutes) *
                Decimal('100')
            )
        else:
            self.minutes_quote = Decimal('0.00')

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f'{self.player} - {self.fixture_date} '
            f'{self.minutes_played} Min.'
        )


class PlayerStrengthProfile(models.Model):
    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name='strength_profile'
    )

    base_strength = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('50.00'),
    )
    form_modifier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    freshness = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
        help_text='Aktuelle Websoccer-Frische. Wirkt als Punktabzug, nicht als Multiplikator.',
    )
    final_strength = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('50.00'),
    )

    updated_at = models.DateTimeField(auto_now=True)

    def calculate_final_strength(self):
        self.final_strength = strength_decimal(
            self.base_strength +
            self.form_modifier
        )

        return self.final_strength

    def save(self, *args, **kwargs):
        self.calculate_final_strength()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.player} - "
            f"StÃ¤rke {self.final_strength:.2f}"
        )


class PlayerMarketValueSnapshot(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='market_value_snapshots',
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='market_value_snapshots',
    )
    recorded_at = models.DateField(default=timezone.localdate)
    value_eur = models.DecimalField(max_digits=15, decimal_places=2)
    profile_url = models.URLField(blank=True)
    source_version = models.CharField(max_length=100, blank=True)
    update_current = models.BooleanField(
        default=True,
        help_text='Aktualisiert Player.market_value und salary_per_match beim Speichern.',
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'source', 'recorded_at'],
                name='unique_player_market_value_snapshot',
            ),
        ]
        verbose_name = 'Marktwert-Snapshot'
        verbose_name_plural = 'Marktwert-Snapshots'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.update_current:
            salary_per_match = (
                self.value_eur / Decimal('1000000')
            ) * Decimal('5000')
            Player.objects.filter(pk=self.player_id).update(
                market_value=self.value_eur,
                salary_per_match=salary_per_match,
            )
        prune_snapshot_history(
            PlayerMarketValueSnapshot,
            {
                'player_id': self.player_id,
                'source_id': self.source_id,
            },
        )

    def __str__(self):
        return f'{self.player} - {self.value_eur:.0f} EUR'


class PlayerSeasonStat(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_season_stats',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ws_player_season_stats',
        verbose_name='Verein',
    )
    season = models.CharField(max_length=20, default='2026/27')
    season_number = models.PositiveSmallIntegerField(default=1)
    competition = models.CharField(max_length=120, default='Liga')
    matches = models.PositiveSmallIntegerField(default=0)
    starts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Startelf-Einsätze',
    )
    goals = models.PositiveSmallIntegerField(default=0)
    assists = models.PositiveSmallIntegerField(default=0)
    substitutions_in = models.PositiveSmallIntegerField(default=0)
    substitutions_out = models.PositiveSmallIntegerField(default=0)
    yellow_cards = models.PositiveSmallIntegerField(default=0)
    red_cards = models.PositiveSmallIntegerField(default=0)
    dismissals = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Platzverweise (GelbRot + DirektRot)',
        help_text='Summe aus Gelb-Rot- und Direktrot-Karten.',
    )
    player_of_match_awards = models.PositiveSmallIntegerField(default=0)
    minutes_played = models.PositiveIntegerField(default=0)
    average_grade = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Websoccer-Note (Durchschnitt). 1.00 ist sehr gut, 6.00 schwach.',
    )
    rating_sum = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Noten-Summe',
        help_text='Summe aller Einzelnoten für Ø-Berechnung.',
    )
    rating_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Noten-Anzahl',
        help_text='Anzahl der gewerteten Einsätze (mit Note).',
    )
    rating_best = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Beste Note',
        help_text='Niedrigster Notenwert (1.0 = beste mögliche Note).',
    )
    rating_worst = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Schlechteste Note',
        help_text='Höchster Notenwert (6.0 = schlechteste mögliche Note).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-season_number', 'competition']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'season', 'competition'],
                name='unique_player_ws_season_stat',
            ),
        ]
        verbose_name = 'WS-Saisonstatistik'
        verbose_name_plural = 'WS-Saisonstatistiken'

    def __str__(self):
        return f'{self.player} - {self.season} {self.competition}'


class PlayerTransferHistory(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_transfer_history',
    )
    transfer_date = models.DateField(default=timezone.localdate)
    season = models.CharField(max_length=20, blank=True)
    from_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outgoing_ws_transfers',
    )
    to_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_ws_transfers',
    )
    fee_eur = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transfer_date', '-id']
        verbose_name = 'WS-Transfer'
        verbose_name_plural = 'WS-Transfers'

    def __str__(self):
        return f'{self.player} - {self.transfer_date}'


class PlayerClubHistory(models.Model):
    """Vereinsstation eines Spielers: eine Zeile pro Spieler+Verein+Saison.

    Grundlage für die Ausbildungsabgabe (Spec Finanzsystem, Phase 0) und
    fürs Datencenter. Vereinslose Phasen und der Pseudo-Verein
    „Karrierende" erzeugen keine Zeile.
    """

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='club_history',
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='player_club_history',
    )
    season = models.PositiveSmallIntegerField(
        help_text='Globale Saisonnummer (GameSeasonState, beginnt bei 0).',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'club', 'season'],
                name='unique_player_club_history_season',
            ),
        ]
        ordering = ['season', 'id']
        verbose_name = 'Vereinsstation'
        verbose_name_plural = 'Vereinsstationen'

    def __str__(self):
        return f'{self.player} @ {self.club} (Saison {self.season})'


class PlayerInjuryRecord(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_injury_records',
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    injury_type = models.CharField(max_length=120)
    days_missed = models.PositiveSmallIntegerField(default=0)
    competition = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date', '-id']
        verbose_name = 'WS-Verletzung'
        verbose_name_plural = 'WS-Verletzungen'

    def __str__(self):
        return f'{self.player} - {self.injury_type}'


class PlayerSuspensionRecord(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_suspension_records',
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=120)
    matches_missed = models.PositiveSmallIntegerField(default=0)
    competition = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date', '-id']
        verbose_name = 'WS-Sperre'
        verbose_name_plural = 'WS-Sperren'

    def __str__(self):
        return f'{self.player} - {self.reason}'


class PlayerAwardTitle(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_awards_titles',
    )
    title = models.CharField(max_length=120)
    season = models.CharField(max_length=20, blank=True)
    competition = models.CharField(max_length=120, blank=True)
    trophy_asset_id = models.CharField(
        max_length=80,
        blank=True,
        help_text='Dateiname oder ID aus Images/Trophies ohne Dateiendung.',
    )
    count = models.PositiveSmallIntegerField(default=1)
    awarded_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-awarded_at', '-id']
        verbose_name = 'WS-Auszeichnung/Titel'
        verbose_name_plural = 'WS-Auszeichnungen/Titel'

    COMPETITION_DEFAULT_ASSETS = {
        # Global — FIFA World Cup
        'FIFA World Cup':           'international cup 1',
        'World Cup':                'international cup 1',
        'Weltmeisterschaft':        'international cup 1',
        'WM':                       'international cup 1',
        # Global — secondary international tournaments
        'FIFA Confederations Cup':  'international cup 2',
        'Confederations Cup':       'international cup 2',
        'Konföderationen-Pokal':    'international cup 2',
        'Olympic Games':            'international cup 2',
        'Olympische Spiele':        'international cup 2',
        'Olympia':                  'international cup 2',
        'FIFA U-20 World Cup':      'international cup 2',
        'FIFA U-17 World Cup':      'international cup 2',
        # UEFA
        'UEFA European Championship': 'continental cup 1',
        'UEFA Euro':                'continental cup 1',
        'Europameisterschaft':      'continental cup 1',
        'EM':                       'continental cup 1',
        'UEFA Nations League':      'continental cup 2',
        'Nations League':           'continental cup 2',
        # CONMEBOL
        'Copa América':             'continental cup 1',
        'Copa America':             'continental cup 1',
        'CONMEBOL Copa América':    'continental cup 1',
        # CAF
        'Africa Cup of Nations':    'continental cup 1',
        'AFCON':                    'continental cup 1',
        'Afrikameisterschaft':      'continental cup 1',
        # AFC
        'AFC Asian Cup':            'continental cup 1',
        'Asian Cup':                'continental cup 1',
        'Asienmeisterschaft':       'continental cup 1',
        # CONCACAF
        'CONCACAF Gold Cup':        'continental cup 1',
        'Gold Cup':                 'continental cup 1',
        'CONCACAF Nations League':  'continental cup 2',
    }

    def save(self, *args, **kwargs):
        if not self.trophy_asset_id and self.title in self.COMPETITION_DEFAULT_ASSETS:
            self.trophy_asset_id = self.COMPETITION_DEFAULT_ASSETS[self.title]
        super().save(*args, **kwargs)

    @property
    def trophy_static_path(self):
        from .player_assets import get_cached_trophy_static_path

        return get_cached_trophy_static_path(self.trophy_asset_id)

    def __str__(self):
        return f'{self.player} - {self.title}'


class PlayerSourceRatingSnapshot(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='source_rating_snapshots',
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='source_rating_snapshots',
    )
    recorded_at = models.DateField(default=timezone.localdate)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    potential = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    source_url = models.URLField(blank=True)
    source_version = models.CharField(max_length=100, blank=True)
    update_current = models.BooleanField(
        default=True,
        help_text='Aktualisiert PlayerSourceRating fuer die aktuelle Staerkeberechnung.',
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'source', 'recorded_at'],
                name='unique_player_source_rating_snapshot',
            ),
        ]
        verbose_name = 'Source-Rating-Snapshot'
        verbose_name_plural = 'Source-Rating-Snapshots'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.update_current and self.source.code in {
            PlayerSourceRating.SOURCE_CMTRACKER,
            PlayerSourceRating.SOURCE_FM,
        }:
            PlayerSourceRating.objects.update_or_create(
                player=self.player,
                source=self.source.code,
                defaults={
                    'rating': self.rating,
                    'potential': self.potential,
                    'source_url': self.source_url,
                    'source_version': self.source_version,
                    'checked_at': self.recorded_at,
                    'notes': self.notes,
                },
            )
        prune_snapshot_history(
            PlayerSourceRatingSnapshot,
            {
                'player_id': self.player_id,
                'source_id': self.source_id,
            },
        )

    def __str__(self):
        return f'{self.player} - {self.source.code} {self.rating}'


class SourceImportRun(models.Model):
    """Import-Log eines CSV-Imports (Quelle/Version/Datei/Bilanz)."""

    SOURCE_CMTRACKER = 'cmtracker'
    SOURCE_CHOICES = [
        (SOURCE_CMTRACKER, 'CMTracker'),
    ]

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_CMTRACKER,
    )
    version = models.CharField(
        max_length=100,
        blank=True,
        help_text='z. B. FC26_2025-09-19',
    )
    file_name = models.CharField(max_length=255, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    dry_run = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_import_runs',
    )
    total_rows = models.PositiveIntegerField(default=0)
    count_new = models.PositiveIntegerField(default=0)
    count_updated = models.PositiveIntegerField(default=0)
    count_unchanged = models.PositiveIntegerField(default=0)
    count_unmatched = models.PositiveIntegerField(default=0)
    count_error = models.PositiveIntegerField(default=0)
    unmatched = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-imported_at', '-id']
        verbose_name = 'Import-Lauf'
        verbose_name_plural = 'Import-Läufe'

    def __str__(self):
        return f'{self.get_source_display()} {self.version} ({self.imported_at:%Y-%m-%d %H:%M})'


class PlayerWeightedRatingSnapshot(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='weighted_rating_snapshots',
    )
    source = models.CharField(
        max_length=40,
        choices=PlayerFormSnapshot.SOURCE_CHOICES,
        default=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
    )
    recorded_at = models.DateField(default=timezone.localdate)
    fixture_reference = models.CharField(max_length=120, blank=True)
    weighted_rating = models.DecimalField(max_digits=4, decimal_places=2)
    rating_minutes = models.PositiveSmallIntegerField(default=0)
    match_count = models.PositiveSmallIntegerField(default=0)
    window_label = models.CharField(
        max_length=80,
        default='Letzte 10 Spiele',
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'source', 'recorded_at', 'fixture_reference'],
                name='unique_player_weighted_rating_snapshot',
            ),
        ]
        verbose_name = 'Gewichteter Rating-Snapshot'
        verbose_name_plural = 'Gewichtete Rating-Snapshots'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        prune_snapshot_history(
            PlayerWeightedRatingSnapshot,
            {
                'player_id': self.player_id,
                'source': self.source,
            },
        )

    def __str__(self):
        return f'{self.player} - {self.weighted_rating:.2f}'


class PlayerStrengthSnapshot(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='strength_snapshots',
    )
    recorded_at = models.DateField(default=timezone.localdate)
    match_reference = models.CharField(max_length=120, blank=True)
    base_strength = models.DecimalField(max_digits=6, decimal_places=2)
    final_strength = models.DecimalField(max_digits=6, decimal_places=2)
    max_strength = models.DecimalField(max_digits=6, decimal_places=2)
    last_10_average_strength = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    freshness = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    form_modifier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'recorded_at', 'match_reference'],
                name='unique_player_strength_snapshot',
            ),
        ]
        verbose_name = 'Staerke-Snapshot'
        verbose_name_plural = 'Staerke-Snapshots'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        prune_snapshot_history(
            PlayerStrengthSnapshot,
            {
                'player_id': self.player_id,
            },
        )

    def __str__(self):
        return f'{self.player} - {self.recorded_at} {self.final_strength:.2f}'


class PlayerEditLog(models.Model):
    """Audit-Log: jede Creator-Änderung an einem Spielerprofil."""

    CATEGORY_PROFIL    = 'profil'
    CATEGORY_VEREIN    = 'verein'
    CATEGORY_POSITION  = 'position'
    CATEGORY_SOURCE    = 'source'
    CATEGORY_STAERKE   = 'staerke'
    CATEGORY_BILD      = 'bild'
    CATEGORY_VERLETZUNG = 'verletzung'
    CATEGORY_SYSTEM    = 'system'

    CATEGORY_CHOICES = [
        (CATEGORY_PROFIL,     'Profil'),
        (CATEGORY_VEREIN,     'Verein & Vertrag'),
        (CATEGORY_POSITION,   'Positionen'),
        (CATEGORY_SOURCE,     'Quelldaten'),
        (CATEGORY_STAERKE,    'Stärke'),
        (CATEGORY_BILD,       'Bild'),
        (CATEGORY_VERLETZUNG, 'Verletzung / Sperre'),
        (CATEGORY_SYSTEM,     'System'),
    ]

    CATEGORY_ICONS = {
        'profil':     '👤',
        'verein':     '🏟',
        'position':   '📍',
        'source':     '📊',
        'staerke':    '⚡',
        'bild':       '🖼',
        'verletzung': '🏥',
        'system':     '⚙',
    }

    player = models.ForeignKey(
        'Player',
        on_delete=models.CASCADE,
        related_name='edit_logs',
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='player_edit_logs',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    summary = models.TextField()

    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'Spieler-Änderungslog'
        verbose_name_plural = 'Spieler-Änderungslogs'

    def __str__(self):
        actor = self.changed_by.username if self.changed_by_id else 'System'
        return f'{self.player} | {self.category} | {actor} | {self.changed_at:%Y-%m-%d %H:%M}'

    @property
    def icon(self):
        return self.CATEGORY_ICONS.get(self.category, '•')


def _rl_form_season_default():
    from datetime import date as _d
    today = _d.today()
    return today.year if today.month >= 7 else today.year - 1


class PlayerRLFormProfile(models.Model):
    """Aggregiertes RL-Form-Profil eines Spielers (API-Football-Quelle)."""

    STATUS_NOT_MAPPED            = 'not_mapped'
    STATUS_NOT_FETCHED           = 'not_fetched'
    STATUS_FETCHED               = 'fetched'
    STATUS_NO_MINUTES            = 'no_minutes'
    STATUS_MINUTES_WITHOUT_RATING = 'minutes_without_rating'
    STATUS_API_ERROR             = 'api_error'
    STATUS_STALE                 = 'stale'

    STATUS_CHOICES = [
        (STATUS_NOT_MAPPED,             'Kein Mapping'),
        (STATUS_NOT_FETCHED,            'Noch nicht abgerufen'),
        (STATUS_FETCHED,                'Abgerufen'),
        (STATUS_NO_MINUTES,             'Keine Einsätze'),
        (STATUS_MINUTES_WITHOUT_RATING, 'Minuten ohne Note'),
        (STATUS_API_ERROR,              'API-Fehler'),
        (STATUS_STALE,                  'Veraltet'),
    ]

    player = models.OneToOneField(
        'Player',
        on_delete=models.CASCADE,
        related_name='rl_form_profile',
    )
    api_football_player_id  = models.IntegerField(null=True, blank=True)
    api_football_team_id    = models.PositiveIntegerField(null=True, blank=True)
    api_football_team_name  = models.CharField(max_length=120, blank=True)
    api_football_season     = models.PositiveSmallIntegerField(default=_rl_form_season_default)

    rl_form_score         = models.SmallIntegerField(default=0)
    rl_form_fit           = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.00'))
    rl_form_avg_rating    = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    rl_form_minutes       = models.IntegerField(default=0)
    rl_form_minutes_share = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    rl_form_games_checked = models.SmallIntegerField(default=0)
    rl_form_games_played  = models.SmallIntegerField(default=0)
    rl_form_status        = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_NOT_MAPPED,
    )
    rl_form_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'RL-Form-Profil'
        verbose_name_plural = 'RL-Form-Profile'

    def __str__(self):
        sign = '+' if self.rl_form_score >= 0 else ''
        return f'{self.player} | RL-Form {sign}{self.rl_form_score} ({self.rl_form_status})'


class ApiFootballDailyUsage(models.Model):
    """Zählt API-Football-Requests pro Kalendertag (Tages-Budget: 100)."""

    date         = models.DateField(unique=True)
    request_count = models.PositiveIntegerField(default=0)

    DAILY_LIMIT = 100
    WARN_THRESHOLD = 80

    class Meta:
        verbose_name = 'API-Football Tagesverbrauch'
        verbose_name_plural = 'API-Football Tagesverbräuche'
        ordering = ['-date']

    def __str__(self):
        return f'{self.date}: {self.request_count}/{self.DAILY_LIMIT}'

    @classmethod
    def record(cls, count=1):
        """Zählt `count` Requests für heute hoch (atomic)."""
        from django.db.models import F
        from datetime import date
        today = date.today()
        obj, created = cls.objects.get_or_create(date=today, defaults={'request_count': 0})
        cls.objects.filter(pk=obj.pk).update(request_count=F('request_count') + count)

    @classmethod
    def today_count(cls):
        """Gibt den heutigen Verbrauch zurück (0 falls noch keine Einträge)."""
        from datetime import date
        try:
            return cls.objects.get(date=date.today()).request_count
        except cls.DoesNotExist:
            return 0


class PlayerEditRequest(models.Model):
    FIELD_NATIONALITIES = 'nationalities'
    FIELD_REAL_LIFE_CLUB = 'real_life_club'
    FIELD_MARKET_VALUE = 'market_value'
    FIELD_MAIN_POSITIONS = 'main_positions'
    FIELD_SECONDARY_POSITIONS = 'secondary_positions'
    FIELD_SOURCE_RATING = 'source_rating'
    FIELD_DEFAULT_BASE = 'default_base'
    FIELD_CHOICES = [
        (FIELD_NATIONALITIES, 'Nationalitaet'),
        (FIELD_REAL_LIFE_CLUB, 'RL-Verein'),
        (FIELD_MARKET_VALUE, 'Marktwert'),
        (FIELD_MAIN_POSITIONS, 'Hauptpositionen'),
        (FIELD_SECONDARY_POSITIONS, 'Nebenpositionen'),
        (FIELD_SOURCE_RATING, 'Source Rating'),
        (FIELD_DEFAULT_BASE, 'Default-Basisstaerke'),
    ]

    STATUS_OPEN = 'open'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Offen'),
        (STATUS_ACCEPTED, 'Angenommen'),
        (STATUS_REJECTED, 'Abgelehnt'),
    ]

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='edit_requests',
    )
    field_name = models.CharField(
        max_length=40,
        choices=FIELD_CHOICES,
    )
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    requester_name = models.CharField(max_length=120, blank=True)
    requester_note = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    decision_note = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decided_player_edit_requests',
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            'status',
            '-created_at',
        ]
        verbose_name = 'Spielerbearbeitungsantrag'
        verbose_name_plural = 'Spielerbearbeitungsantraege'

    def __str__(self):
        return f'{self.player} - {self.get_field_name_display()}'

    def _parse_decimal(self, value):
        normalized = value.strip().replace('.', '').replace(',', '.')
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise ValidationError('Der neue Marktwert ist keine gueltige Zahl.') from exc

    def _parse_positions(self, value):
        valid_positions = {position for position, label in Player.POSITION_CHOICES}
        positions = [
            position.strip().upper()
            for position in value.replace(';', ',').split(',')
            if position.strip()
        ]

        if len(positions) > 3:
            raise ValidationError('Es sind maximal drei Positionen erlaubt.')

        invalid_positions = [
            position
            for position in positions
            if position not in valid_positions
        ]
        if invalid_positions:
            raise ValidationError(
                f"Ungueltige Position(en): {', '.join(invalid_positions)}"
            )

        return positions

    def apply_to_player(self):
        player = self.player
        value = self.new_value.strip()

        if self.field_name == self.FIELD_NATIONALITIES:
            player.nationalities = value
            player.save(update_fields=['nationalities'])
            return

        if self.field_name == self.FIELD_REAL_LIFE_CLUB:
            if not value:
                player.real_life_club = None
            else:
                club = None
                if value.isdigit():
                    club = Club.objects.filter(pk=int(value)).first()

                if club is None:
                    club = Club.objects.filter(name__iexact=value).first()

                if club is None:
                    raise ValidationError('Der neue RL-Verein wurde nicht gefunden.')

                player.real_life_club = club

            player.save(update_fields=['real_life_club'])
            return

        if self.field_name == self.FIELD_MARKET_VALUE:
            player.market_value = self._parse_decimal(value)
            player.save(update_fields=['market_value'])
            return

        if self.field_name == self.FIELD_MAIN_POSITIONS:
            positions = self._parse_positions(value)
            player.main_position_1 = positions[0] if len(positions) > 0 else ''
            player.main_position_2 = positions[1] if len(positions) > 1 else ''
            player.main_position_3 = positions[2] if len(positions) > 2 else ''
            player.position = player.main_position_1
            player.save(
                update_fields=[
                    'main_position_1',
                    'main_position_2',
                    'main_position_3',
                    'position',
                ]
            )
            return

        if self.field_name == self.FIELD_SECONDARY_POSITIONS:
            positions = self._parse_positions(value)
            player.secondary_position_1 = positions[0] if len(positions) > 0 else ''
            player.secondary_position_2 = positions[1] if len(positions) > 1 else ''
            player.secondary_position_3 = positions[2] if len(positions) > 2 else ''
            player.primary_position = player.secondary_position_1
            player.source_positions = player.secondary_position_1
            player.save(
                update_fields=[
                    'secondary_position_1',
                    'secondary_position_2',
                    'secondary_position_3',
                    'primary_position',
                    'source_positions',
                ]
            )
            return

        raise ValidationError(
            'Dieser Antrag ist eine Markierung und muss manuell bearbeitet werden.'
        )

    def accept(self, user=None):
        self.apply_to_player()
        self.status = self.STATUS_ACCEPTED
        self.decided_by = user if user and user.is_authenticated else None
        self.decided_at = timezone.now()
        self.save(update_fields=['status', 'decided_by', 'decided_at', 'updated_at'])

    def reject(self, user=None):
        self.status = self.STATUS_REJECTED
        self.decided_by = user if user and user.is_authenticated else None
        self.decided_at = timezone.now()
        self.save(update_fields=['status', 'decided_by', 'decided_at', 'updated_at'])


class PlayerDataReview(Player):
    class Meta:
        proxy = True
        verbose_name = 'Spieler-Datenpruefung'
        verbose_name_plural = 'Spieler-Datenpruefung'


class ManagerProfile(models.Model):
    TRAINER_TYPE_CHOICES = [
        ('laptoptrainer', 'Laptoptrainer'),
        ('taktikfuchs', 'Taktikfuchs'),
        ('motivator', 'Motivator'),
        ('talentschmied', 'Talentschmied'),
        ('transferstratege', 'Transferstratege'),
        ('pokaljager', 'Pokaljäger'),
        ('offensivarchitekt', 'Offensivarchitekt'),
        ('underdog', 'Underdog-Flüsterer'),
        ('aufstiegsheld', 'Aufstiegsheld'),
        ('defensivmeister', 'Defensivmeister'),
        ('weltenbummler', 'Weltenbummler'),
        ('serienmeister', 'Serienmeister'),
        ('feuerwehrmann', 'Feuerwehrmann'),
        ('vereinslegende', 'Vereinslegende'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='manager_profile',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100, unique=True)
    trainer_type = models.CharField(
        max_length=30,
        choices=TRAINER_TYPE_CHOICES,
        default='laptoptrainer',
    )
    nationality_flag = models.CharField(
        max_length=200,
        blank=True,
        default='',
    )
    nationality_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
    )
    member_since = models.DateField(null=True, blank=True)
    profile_image = models.CharField(max_length=200, blank=True, default='')
    name_confirmed = models.BooleanField(
        default=False,
        help_text='True, sobald der Manager einen eigenen Namen gespeichert hat (nicht mehr der Standard-Username).',
    )
    xp = models.PositiveIntegerField(default=0)
    xp_max = models.PositiveIntegerField(default=15000)
    level = models.PositiveIntegerField(default=1)
    highscore = models.CharField(max_length=50, blank=True, default='–')
    updated_at = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Zuletzt online',
        help_text='Wird bei jedem Seitenaufruf aktualisiert (max. alle 2 Minuten).',
    )
    favourite_club = models.ForeignKey(
        'Club',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Lieblingsverein',
    )

    class Meta:
        verbose_name = 'Manager-Profil'
        verbose_name_plural = 'Manager-Profile'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(nationality_name='') | ~models.Q(nationality_flag=''),
                name='managerprofile_nationality_name_requires_flag',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.nationality_name and not self.nationality_flag:
            raise ValidationError(
                {'nationality_name': 'Eine Nationalität darf nur gesetzt werden, wenn auch ein Flag-URL vorhanden ist.'}
            )

    @property
    def trainer_type_label(self):
        return dict(self.TRAINER_TYPE_CHOICES).get(self.trainer_type, self.trainer_type)

    @property
    def xp_pct(self):
        if not self.xp_max:
            return 0
        return round(self.xp / self.xp_max * 100)

    @property
    def xp_label(self):
        return f'{self.xp:,} / {self.xp_max:,} XP'.replace(',', '.')


class ManagerCareerStation(models.Model):
    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='career_stations',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manager_career_stations',
    )
    order = models.PositiveSmallIntegerField(default=1)
    custom_club_name = models.CharField(max_length=150, blank=True)
    city_name = models.CharField(max_length=120)
    city_country = models.CharField(max_length=100, blank=True)
    map_x = models.PositiveSmallIntegerField(default=271)
    map_y = models.PositiveSmallIntegerField(default=214)
    started_at = models.DateField(null=True, blank=True)
    ended_at = models.DateField(null=True, blank=True)
    games_played = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['manager', 'order']
        verbose_name = 'Manager-Karriere-Station'
        verbose_name_plural = 'Manager-Karriere-Stationen'

    def __str__(self):
        return f'{self.manager} – {self.city_name}'

    @property
    def is_current(self):
        return self.ended_at is None

    @property
    def period_label(self):
        if self.started_at:
            start = self.started_at.strftime('%-d. %b %Y')
        else:
            start = '?'
        if self.ended_at:
            end = self.ended_at.strftime('%-d. %b %Y')
        else:
            end = 'heute'
        return f'{start} – {end}'

    @property
    def titles_count(self):
        if self.club_id:
            from django.db.models import Sum
            result = ClubTrophy.objects.filter(club_id=self.club_id).aggregate(total=Sum('count'))
            return result['total'] or 0
        return 0


class ManagerTimelineEntry(models.Model):
    """Vom Manager eingereichter Timeline-Eintrag im Managerprofil.

    Farbe/Ton ist je Kategorie fest vorgegeben (CATEGORY_TONES) und
    bei allen Managern einheitlich.
    """

    CATEGORY_CHOICES = [
        ('verein', 'Verein'),
        ('titel', 'Titel'),
        ('finale', 'Finale'),
        ('jugend', 'Jugend'),
        ('status', 'Status'),
    ]

    CATEGORY_TONES = {
        'verein': 'cyan',
        'titel': 'gold',
        'finale': 'red',
        'jugend': 'green',
        'status': 'red',
    }

    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='timeline_entries',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manager_timeline_entries',
    )
    club_name = models.CharField(max_length=150, blank=True)
    event_date = models.DateField()
    category = models.CharField(max_length=12, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=120)
    body = models.TextField(blank=True)
    player = models.ForeignKey(
        'Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manager_timeline_entries',
    )
    result_text = models.CharField(max_length=20, blank=True)
    show_trophy = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ausstehend'),
        (STATUS_APPROVED, 'Genehmigt'),
        (STATUS_REJECTED, 'Abgelehnt'),
    ]
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['event_date', 'id']
        verbose_name = 'Manager-Timeline-Eintrag'
        verbose_name_plural = 'Manager-Timeline-Einträge'

    def __str__(self):
        return f'{self.manager} – {self.title} ({self.event_date})'

    @property
    def tone(self):
        return self.CATEGORY_TONES.get(self.category, 'cyan')


class ManagerNotes(models.Model):
    """Persönlicher Notizblock eines Managers (Tablet-Overlay).

    Manager-gebunden und vereinsunabhängig: Notizen bleiben beim
    Vereinswechsel erhalten und werden nur vom Manager selbst gelöscht.
    Struktur von ``data``:
    [{id, title, content, todos: [{id, text, done}], updatedAt}, ...]
    """

    manager = models.OneToOneField(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='notes',
    )
    data = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Manager-Notizen'
        verbose_name_plural = 'Manager-Notizen'

    def __str__(self):
        return f'Notizen von {self.manager}'


# ============================================================
#  Präsident — Saisonziele & Hoeneß-Coin
# ============================================================

class SeasonGoal(models.Model):
    """Vom Präsidenten zu Saisonbeginn verkündetes Ziel eines Vereins.

    Das Ziel wird aus der Kaderstärke (Summe der Top-11 base_strength)
    relativ zur restlichen Liga abgeleitet und zu Saisonende gegen die
    erreichte Platzierung geprüft.
    """

    TIER_MEISTER = 'meister'
    TIER_TOP4 = 'top4'
    TIER_INTERNATIONAL = 'international'
    TIER_MITTELFELD = 'mittelfeld'
    TIER_KLASSENERHALT = 'klassenerhalt'
    TIER_CHOICES = [
        (TIER_MEISTER, 'Meister'),
        (TIER_TOP4, 'Top 4'),
        (TIER_INTERNATIONAL, 'Internationale Plätze'),
        (TIER_MITTELFELD, 'Gesichertes Mittelfeld'),
        (TIER_KLASSENERHALT, 'Klassenerhalt'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='season_goals',
    )
    season_number = models.PositiveSmallIntegerField(default=1)
    goal_tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    rank_in_league = models.PositiveSmallIntegerField(
        help_text='Kaderstärke-Rang innerhalb der Liga bei Zielverkündung.',
    )
    league_size = models.PositiveSmallIntegerField(default=0)
    squad_strength = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Summe der Top-11 base_strength bei Zielverkündung.',
    )
    required_max_rank = models.PositiveSmallIntegerField(
        default=0,
        help_text='Maximal erlaubter Endplatz, um das Ziel zu erfüllen.',
    )
    final_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    achieved = models.BooleanField(
        null=True,
        blank=True,
        help_text='Leer = noch nicht ausgewertet, sonst erfüllt/verfehlt.',
    )
    declared_at = models.DateTimeField(auto_now_add=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Saisonziel'
        verbose_name_plural = 'Saisonziele'
        ordering = ['-season_number', 'rank_in_league']
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'season_number'],
                name='seasongoal_unique_club_season',
            ),
        ]

    def __str__(self):
        return f'{self.club} – Saison {self.season_number}: {self.goal_tier_label}'

    @property
    def goal_tier_label(self):
        return dict(self.TIER_CHOICES).get(self.goal_tier, self.goal_tier)

    @property
    def is_pending(self):
        return self.achieved is None


class HoenessCoin(models.Model):
    """Hoeneß-Coin-Guthaben eines Managers — Belohnung für erfüllte Saisonziele."""

    manager = models.OneToOneField(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='hoeness_coins',
    )
    amount = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hoeneß-Coin-Guthaben'
        verbose_name_plural = 'Hoeneß-Coin-Guthaben'

    def __str__(self):
        return f'{self.manager} – {self.amount} Hoeneß-Coin'


class CoinTransaction(models.Model):
    """Protokolliert jede einzelne Hoeneß-Coin-Buchung (Einnahme oder Ausgabe)."""

    REASON_WIN = 'win'
    REASON_BIG_WIN = 'big_win'
    REASON_SEASON_GOAL = 'season_goal'
    REASON_BOOST_TRANSFER = 'boost_transfer'
    REASON_SCOUT_TALENT = 'scout_talent'
    REASON_SHOW_AUCTION = 'show_auction'

    REASON_CHOICES = [
        (REASON_WIN,            'Sieg'),
        (REASON_BIG_WIN,        'Kantersieg'),
        (REASON_SEASON_GOAL,    'Saisonziel erfüllt'),
        (REASON_BOOST_TRANSFER, 'Transfermarkt-Boost'),
        (REASON_SCOUT_TALENT,   'Talentscout'),
        (REASON_SHOW_AUCTION,   'Show-Auktion (Eintritt)'),
    ]

    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='coin_transactions',
    )
    amount = models.SmallIntegerField(
        help_text='Positiv = verdient, negativ = ausgegeben.',
    )
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Coin-Transaktion'
        verbose_name_plural = 'Coin-Transaktionen'
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f'{self.manager} {sign}{self.amount} ({self.get_reason_display()})'


class Notification(models.Model):
    """Minimale Manager-Benachrichtigung (Glocke im Header).

    Ungebündelt: jedes Ereignis erzeugt eine eigene Zeile (Spec
    Show-Auktion §12). Empfänger ist das ManagerProfile — nicht der Club —
    damit auch vereinslose Manager erreichbar sind. Erstellung läuft über
    game.notifications.notify(); die Liste unter /benachrichtigungen/
    markiert beim Öffnen alles als gelesen.
    """

    recipient = models.ForeignKey(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=240, blank=True, default='')
    url = models.CharField(max_length=200, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]
        verbose_name = 'Benachrichtigung'
        verbose_name_plural = 'Benachrichtigungen'

    def __str__(self):
        return f'{self.recipient}: {self.title}'


class GameSeasonState(models.Model):
    """Globaler, vom Admin gesteuerter Saison-Status.

    Hält die aktuelle Saisonnummer (beginnt bei 0) und ob die Saison
    offiziell gestartet wurde. Erst nach dem Start verkündet der
    Präsident die Saisonziele — vorher bleiben sie unter Verschluss.
    Es existiert nur eine Zeile (Singleton).
    """

    current_season = models.PositiveSmallIntegerField(
        default=0,
        help_text='Aktuelle Saisonnummer (beginnt bei 0).',
    )
    is_started = models.BooleanField(
        default=False,
        help_text='Erst wenn aktiv, verkündet der Präsident die Saisonziele.',
    )
    started_at = models.DateTimeField(null=True, blank=True)
    transfer_window_open = models.BooleanField(
        'Transferfenster offen',
        default=False,
        help_text='Admin-Schalter (KI-Transferzentrale): Nur bei offenem '
                  'Fenster laufen KI-Käufer-Prüfläufe.',
    )
    transfer_window_id = models.CharField(
        'Transferfenster-ID',
        max_length=20,
        blank=True,
        default='',
        help_text='Kennung des aktuellen/letzten Fensters (z. B. "0-S1"). '
                  'Fenster-Zähler und Talent-Cooldowns hängen an dieser ID.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Saison-Status'
        verbose_name_plural = 'Saison-Status'

    def __str__(self):
        zustand = 'gestartet' if self.is_started else 'nicht gestartet'
        return f'Saison {self.current_season} ({zustand})'

    def save(self, *args, **kwargs):
        """Speichert den Saison-Status und löst beim Saisonwechsel/-start
        fällige Scouting-Zuschlagstermine auf.

        Hintergrund: Die reguläre Auflösung fälliger Fenster hängt an
        ``close_matchday()``. Ist die letzte Saison abgeschlossen
        (season_complete) und wird kein weiterer Spieltag mehr geschlossen,
        bleiben Gebote mit einem Zuschlagstermin in der Sommerpause sonst
        dauerhaft ACTIVE. Beim Vorrücken der Saisonnummer oder beim
        offiziellen Start einer Saison schließen wir diese Lücke.
        """
        is_transition = False
        advanced = False
        prev_season = None
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).only(
                'current_season', 'is_started'
            ).first()
            if previous is not None:
                prev_season = previous.current_season
                advanced = self.current_season != previous.current_season
                started = self.is_started and not previous.is_started
                is_transition = advanced or started

        super().save(*args, **kwargs)

        # Beim Vorrücken der Saisonnummer: Vereinsstationen-Snapshot für die
        # neue Saison (Ausbildungsabgabe, Phase 0 Finanzsystem). Fehler dürfen
        # das Speichern nicht blockieren, werden aber geloggt.
        if advanced:
            try:
                from game.club_history import snapshot_season
                snapshot_season(self.current_season)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    'Vereinsstationen-Snapshot für Saison %s fehlgeschlagen',
                    self.current_season,
                )

        # Finanz-Saisonjobs (Spec Kap. 15): Beim Vorrücken der Saisonnummer
        # die alte Saison finanziell abschließen (Backstop, idempotent) und
        # die neue öffnen (Snapshot, TV-Töpfe, Sponsorangebote). Beim
        # offiziellen Saisonstart ebenfalls öffnen. Fehler dürfen das
        # Speichern nie blockieren.
        if is_transition:
            try:
                from game.economy.season_jobs import (
                    finance_season_close, finance_season_open,
                )
                if advanced and prev_season is not None:
                    finance_season_close(str(prev_season))
                finance_season_open(str(self.current_season))
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    'Finanz-Saisonjobs beim Saisonübergang auf %s fehlgeschlagen',
                    self.current_season,
                )

        # Fällige Zuschlagstermine beim Saisonübergang/-start auflösen. Läuft
        # in eigener Transaktion (innerhalb von resolve_due_windows) und darf
        # das Speichern des Saison-Status nie blockieren.
        if is_transition:
            try:
                from game.scouting import service as _scouting_service
                _scouting_service.resolve_due_windows()
            except Exception:
                pass


class LeagueSeasonState(models.Model):
    """Saisonfortschritt pro Liga — speichert den aktiven Spieltag.

    Verwaltet den Spieltag-Zyklus: Offen → Simuliert → Abgeschlossen → nächster Spieltag.
    Singleton pro (Liga, Saison).
    """

    league = models.ForeignKey(
        'League',
        on_delete=models.CASCADE,
        related_name='season_states',
        verbose_name='Liga',
    )
    season = models.CharField(max_length=20, default='0', verbose_name='Saison')
    current_matchday = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Aktiver Spieltag',
    )
    is_simulated = models.BooleanField(
        default=False,
        verbose_name='Simuliert',
        help_text='Alle Spiele des aktiven Spieltags wurden simuliert.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('league', 'season')]
        verbose_name = 'Liga-Saison-Status'
        verbose_name_plural = 'Liga-Saison-Status'

    def __str__(self):
        status = 'simuliert' if self.is_simulated else 'offen'
        return f'{self.league.name} | Saison {self.season} | ST{self.current_matchday} ({status})'


class PresidentSatisfaction(models.Model):
    """Präsident-Zufriedenheit — vereinsgebunden, pro Manager-Club-Kombination.

    Startet bei 100, wenn ein Manager einen Verein übernimmt (frischer Start).
    Sinkt um 50 bei verfehlem Saisonziel, steigt um 50 bei Zielerreichung.
    Wird beim Vereinswechsel NICHT übertragen — neuer Verein = Neustart bei 100.
    Bei 0 % erscheint der Manager in der Admin-Übersicht "Entlassungskandidaten".
    """

    manager = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        related_name='president_satisfactions',
        verbose_name='Manager',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.CASCADE,
        related_name='president_satisfactions',
        verbose_name='Verein',
    )
    value = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Zufriedenheit (0–100)',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('manager', 'club')]
        ordering = ['value', '-updated_at']
        verbose_name = 'Präsident-Zufriedenheit'
        verbose_name_plural = 'Präsident-Zufriedenheiten'

    def __str__(self):
        return f'{self.manager} @ {self.club} — {self.value} %'


class ManagerAtRisk(PresidentSatisfaction):
    """Proxy-Modell: zeigt nur Manager mit Zufriedenheit 0 % (Entlassungskandidaten)."""

    class Meta:
        proxy = True
        verbose_name = 'Entlassungskandidat'
        verbose_name_plural = 'Entlassungskandidaten (Zufriedenheit 0 %)'


# ── Sportgericht ───────────────────────────────────────────────────────────────

class InactivityRecord(models.Model):
    """Protokolliert jeden Spieltag, an dem ein Manager kein Team aufgestellt hat."""

    SQUAD_PRO_LABEL = 'pro'
    SQUAD_U21_LABEL = 'u21'
    SCOPE_CHOICES = [
        ('pro', 'Profis'),
        ('u21', 'U21'),
    ]

    manager = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        related_name='inactivity_records',
        verbose_name='Manager',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.SET_NULL,
        null=True,
        related_name='inactivity_records',
        verbose_name='Verein',
    )
    squad_scope = models.CharField(
        max_length=10,
        choices=SCOPE_CHOICES,
        default='pro',
        verbose_name='Mannschaft',
    )
    season = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Saison',
    )
    matchday_label = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='Spieltag',
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erfasst am',
    )

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = 'Inaktivitäts-Eintrag'
        verbose_name_plural = 'Inaktivitäts-Einträge'
        constraints = [
            models.UniqueConstraint(
                fields=['manager', 'club', 'squad_scope', 'season', 'matchday_label'],
                name='unique_inactivity_record_per_matchday',
            ),
        ]

    def __str__(self):
        return f'{self.manager} | {self.get_squad_scope_display()} | {self.matchday_label} ({self.season})'


class InactivityPenalty(models.Model):
    """Strafpunkt für Manager, die bereits einmal wegen Inaktivität entlassen wurden.

    Senkt die Toleranzschwelle: 3→2 hintereinander, 5→4 pro Saison.
    """

    manager = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        related_name='inactivity_penalties',
        verbose_name='Manager',
    )
    given_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erteilt am',
    )
    reason = models.TextField(
        blank=True,
        verbose_name='Begründung',
    )

    class Meta:
        ordering = ['-given_at']
        verbose_name = 'Inaktivitäts-Strafpunkt'
        verbose_name_plural = 'Inaktivitäts-Strafpunkte'

    def __str__(self):
        return f'Strafpunkt: {self.manager} ({self.given_at:%d.%m.%Y})'


class SupportTicket(models.Model):
    """Support-Ticket, das ein Manager einreichen kann."""

    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        ('open', 'Offen'),
        ('in_progress', 'In Bearbeitung'),
        ('closed', 'Abgeschlossen'),
    ]

    manager = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        related_name='support_tickets',
        verbose_name='Manager',
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Titel',
    )
    description = models.TextField(
        verbose_name='Beschreibung',
    )
    screenshot = models.FileField(
        upload_to='support_tickets/',
        blank=True,
        null=True,
        verbose_name='Screenshot',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name='Status',
    )
    admin_response = models.TextField(
        blank=True,
        verbose_name='Admin-Antwort',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erstellt am',
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Abgeschlossen am',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Support-Ticket'
        verbose_name_plural = 'Support-Tickets'

    def __str__(self):
        return f'#{self.pk} {self.title} ({self.get_status_display()}) — {self.manager}'


class ClubFinancialTransaction(models.Model):
    CATEGORY_CHOICES = [
        ('ticketverkauf',    'Ticketverkauf'),
        ('sponsor',          'Sponsoren'),
        ('tv_gelder',        'TV-Gelder'),
        ('transfer_einnahme','Transfer (Einnahme)'),
        ('leih_einnahme',    'Leiheinnahme'),
        ('praemie',          'Prämie'),
        ('sonstige_einnahme','Sonstige Einnahme'),
        ('transfer_ausgabe', 'Transfer (Ausgabe)'),
        ('profigehalt',      'Profigehalt'),
        ('jugendgehalt',     'Jugendgehalt'),
        ('stadionkosten',    'Stadionkosten'),
        ('stadionumfeld',    'Stadionumfeld'),
        ('sonstige_ausgabe', 'Sonstige Ausgabe'),
    ]

    INCOME_CATEGORIES = {
        'ticketverkauf', 'sponsor', 'tv_gelder',
        'transfer_einnahme', 'leih_einnahme', 'praemie', 'sonstige_einnahme',
    }

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='financial_transactions',
        verbose_name='Verein',
    )
    date = models.DateField(
        default=timezone.localdate,
        verbose_name='Datum',
    )
    season = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Saison',
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        verbose_name='Kategorie',
    )
    description = models.CharField(
        max_length=200,
        verbose_name='Verwendungszweck',
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Betrag (€)',
        help_text='Positiv = Einnahme, Negativ = Ausgabe.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Finanztransaktion'
        verbose_name_plural = 'Finanztransaktionen'

    @property
    def is_income(self):
        return self.amount >= 0

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f'{self.club} | {self.get_category_display()} | {sign}{self.amount:,.0f} € ({self.date})'


class ClubSponsor(models.Model):
    TYPE_CHOICES = [
        ('tv',       'TV-Vertrag'),
        ('trikot',   'Trikotsponsor'),
        ('haupt',    'Hauptsponsor'),
        ('ausrüster','Ausrüster'),
        ('sonstig',  'Sonstige Sponsoren'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='sponsors',
        verbose_name='Verein',
    )
    name = models.CharField(max_length=100, verbose_name='Sponsorname')
    sponsor_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name='Typ',
    )
    amount_per_season = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Betrag / Saison (€)',
    )
    season = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Saison',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    class Meta:
        ordering = ['sponsor_type', 'name']
        verbose_name = 'Vereinssponsor'
        verbose_name_plural = 'Vereinssponsoren'

    def __str__(self):
        return f'{self.club} — {self.get_sponsor_type_display()}: {self.name} ({self.amount_per_season:,.0f} €/Saison)'


class ManagerCareerEntry(models.Model):
    """Karriere-Historientabelle — eine Zeile pro Manager-Vereins-Amtszeit.

    Club.managed_by bleibt der schnelle Live-Pointer (DB-UNIQUE-Constraint).
    Diese Tabelle ist die Historienschicht darüber: Vereinswechsel, Entlassungen,
    Rücktritte, Amtszeiten, Hall of Fame, Saisonstatistiken.

    Ablauf:
    - Übernahme  → neuer Eintrag (active=True, ended_at=None)
    - Entlassung → ended_at setzen, end_reason='fired',  active=False
    - Rücktritt  → ended_at setzen, end_reason='resign', active=False
    - Saisonende → ended_at setzen, end_reason='season_end' (optional, wenn der
                   Manager trotzdem weitermacht: kein neuer Eintrag nötig)
    """

    END_REASONS = [
        ('resign',     'Rücktritt'),
        ('fired',      'Entlassung'),
        ('season_end', 'Saisonende'),
        ('mutual',     'Einvernehmliche Trennung'),
    ]

    manager = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        related_name='career_entries',
        verbose_name='Manager',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.CASCADE,
        related_name='manager_career_entries',
        verbose_name='Verein',
    )
    started_at = models.DateField(verbose_name='Amtsantritt')
    ended_at = models.DateField(null=True, blank=True, verbose_name='Amtsende')
    end_reason = models.CharField(
        max_length=20,
        choices=END_REASONS,
        null=True,
        blank=True,
        verbose_name='Abgangsgrund',
    )
    active = models.BooleanField(
        default=True,
        verbose_name='Aktiv',
        help_text='Genau ein aktiver Eintrag pro Manager erlaubt (App-Ebene).',
    )

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Manager-Karriereeintrag'
        verbose_name_plural = 'Manager-Karriereeinträge'
        indexes = [
            models.Index(fields=['manager', 'active'], name='mgr_career_active_idx'),
            models.Index(fields=['club', 'active'],    name='mgr_career_club_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['manager'],
                condition=models.Q(active=True),
                name='one_active_entry_per_manager',
                violation_error_message='Dieser Manager hat bereits einen aktiven Verein.',
            ),
            models.UniqueConstraint(
                fields=['club'],
                condition=models.Q(active=True),
                name='one_active_entry_per_club',
                violation_error_message='Dieser Verein hat bereits einen aktiven Manager.',
            ),
        ]

    def __str__(self):
        end = self.ended_at.strftime('%d.%m.%Y') if self.ended_at else 'heute'
        return f'{self.manager.name} @ {self.club.name} ({self.started_at:%d.%m.%Y} – {end})'


class Referee(models.Model):
    """Schiedsrichter-Datenbank — Profil + Tendenzen + Vorsaison-Statistiken."""

    # level: 5=Weltklasse, 4=International, 3=Erste Liga, 2=Zweite Liga, 1=Aufsteiger  (E-16)
    LEVEL_BADGE_MAP = {
        5: 'weltklasse',
        4: 'international',
        3: 'erste-liga',
        2: 'zweite-liga',
        1: 'aufsteiger',
    }
    LEVEL_LABEL_MAP = {
        5: 'Weltklasse',
        4: 'International',
        3: 'Erste Liga',
        2: 'Zweite Liga',
        1: 'Aufsteiger',
    }

    fm_uid = models.BigIntegerField(
        unique=True,
        null=True, blank=True,
        verbose_name='FM UID',
        help_text='Football-Manager interne UID (für Profilbild /assets/referees/face_{fm_uid}.png).',
    )
    name = models.CharField(max_length=120, verbose_name='Name')
    nationality = models.CharField(
        max_length=80, blank=True, verbose_name='Nationalität (DE)',
        help_text='z. B. "Schweiz", "Frankreich"',
    )
    nationality_code = models.CharField(
        max_length=10, blank=True, verbose_name='Flaggen-Code',
        help_text='Assetserver-Code für flag_url(), z. B. "771" oder ISO-2 "de".',
    )
    birth_date = models.DateField(
        null=True, blank=True, verbose_name='Geburtsdatum',
        help_text='Format DD.MM.YYYY; Alter wird zur Laufzeit berechnet.',
    )
    level = models.PositiveSmallIntegerField(
        default=3, verbose_name='Niveau (1–5)',
        help_text='5=Weltklasse, 4=International, 3=Erste Liga, 2=Zweite Liga, 1=Aufsteiger',
    )
    schlagwort = models.CharField(
        max_length=200, blank=True, verbose_name='Schlagwort/Kurzcharakter',
        help_text='Erscheint kursiv im Popup, z. B. „Souveräner Spielleiter".',
    )
    quote = models.PositiveSmallIntegerField(
        default=10, verbose_name='Entscheidungsqualität (1–20)',
        help_text='1=fehlerhaft, 20=makellos. P(Fehlentscheidung/Sp) = clamp((14−quote)×0.7; 1; 8)%.',
    )
    karten_tendenz = models.PositiveSmallIntegerField(
        default=10, verbose_name='Karten-Tendenz (1–20)',
        help_text='1=sehr nachsichtig, 20=sehr kartenfreudig. Invariante: karten+spielfluss=21.',
    )
    spielfluss_tendenz = models.PositiveSmallIntegerField(
        default=11, verbose_name='Spielfluss-Tendenz (1–20)',
        help_text='1=pfeift viel ab, 20=lässt laufen. Invariante: karten+spielfluss=21.',
    )
    vorsaison_spiele   = models.PositiveSmallIntegerField(default=0, verbose_name='Spiele (Vorsaison)')
    vorsaison_gelb_avg = models.DecimalField(
        max_digits=4, decimal_places=1, default=0,
        verbose_name='Ø Gelb/Spiel (Vorsaison)',
    )
    vorsaison_rot           = models.PositiveSmallIntegerField(default=0, verbose_name='Rote Karten (Vorsaison)')
    vorsaison_elfmeter      = models.PositiveSmallIntegerField(default=0, verbose_name='Elfmeter (Vorsaison)')
    vorsaison_umstritten    = models.PositiveSmallIntegerField(default=0, verbose_name='Umstrittene Ents. (Vorsaison)')
    vorsaison_competitions  = models.JSONField(
        default=list, blank=True,
        verbose_name='Wettbewerbe (Vorsaison)',
        help_text='Liste von Wettbewerbsnamen, z. B. ["1. Bundesliga", "DFB-Pokal"].',
    )

    class Meta:
        verbose_name = 'Schiedsrichter'
        verbose_name_plural = 'Schiedsrichter'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def age(self):
        """Berechnet Alter aus birth_date."""
        if not self.birth_date:
            return None
        from django.utils import timezone
        today = timezone.localdate()
        bd = self.birth_date
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))

    @property
    def spielfluss_bucket(self):
        """0=Pfeift viel ab, 1=Ausgewogen, 2=Lässt laufen."""
        v = self.spielfluss_tendenz or 11
        return 0 if v <= 7 else (1 if v <= 13 else 2)

    @property
    def karten_bucket(self):
        """0=Nachsichtig, 1=Ausgewogen, 2=Kartenfreudig."""
        return 2 - self.spielfluss_bucket

    def face_url(self):
        from .asset_urls import referee_face_url
        return referee_face_url(self.fm_uid)

    def flag_url(self):
        from .asset_urls import flag_url as _flag_url
        if self.nationality:
            asset = COUNTRY_FLAG_ASSETS.get(self.nationality)
            if asset and 'asset_id' in asset:
                return _flag_url(asset['asset_id'])
        return _flag_url(self.nationality_code) if self.nationality_code else ''

    def level_badge_class(self):
        return f'ref-badge--{self.LEVEL_BADGE_MAP.get(self.level, "international")}'

    def level_display_upper(self):
        return self.LEVEL_LABEL_MAP.get(self.level, str(self.level)).upper()

    def get_level_display(self):
        return self.LEVEL_LABEL_MAP.get(self.level, str(self.level))


class SimulatedMatch(models.Model):
    """Gespeichertes Ergebnis einer Match-Engine-Simulation (zum Testen)."""

    MATCH_TYPE_CHOICES = [
        ('liga',         'Ligaspiel'),
        ('freundschaft', 'Freundschaftsspiel'),
        ('pokal',        'Pokal'),
    ]

    home_club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='simulated_home_matches',
    )
    away_club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='simulated_away_matches',
    )
    home_goals = models.PositiveSmallIntegerField(default=0)
    away_goals = models.PositiveSmallIntegerField(default=0)
    report_data = models.JSONField(
        default=dict,
        help_text='Vollständiger Spielbericht als JSON (Tore, Stats, Spieler).',
    )
    match_type = models.CharField(
        max_length=20,
        choices=MATCH_TYPE_CHOICES,
        default='freundschaft',
        verbose_name='Spieltyp',
    )
    simulated_at = models.DateTimeField(auto_now_add=True)
    season = models.CharField(
        max_length=10,
        default='0',
        db_index=True,
        verbose_name='Saison',
        help_text='Saison, in der das Spiel stattfand (z. B. "0", "1").',
    )
    match_no = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Spiel-Nr. (Saison)',
        help_text='Laufende Spielnummer innerhalb der Saison, beginnt je Saison bei 1.',
    )
    referee = models.ForeignKey(
        'Referee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='matches',
        verbose_name='Schiedsrichter',
    )

    @classmethod
    def create_numbered(cls, season, match_no=None, **kwargs):
        """Erzeugt ein SimulatedMatch mit fortlaufender Spielnummer pro Saison.

        match_no: optional explizit vergeben (z. B. bei Re-Simulation die alte
        Nummer übernehmen). Ohne Angabe wird Max+1 mit Retry bei Kollision
        vergeben (UniqueConstraint schützt vor Doppelvergabe).
        """
        from django.db import IntegrityError, transaction as _tx

        season = str(season if season is not None else '0')
        if match_no is not None:
            return cls.objects.create(season=season, match_no=match_no, **kwargs)

        last_error = None
        for _ in range(5):
            last = cls.objects.filter(season=season).aggregate(
                m=models.Max('match_no')
            )['m'] or 0
            try:
                with _tx.atomic():
                    return cls.objects.create(
                        season=season, match_no=last + 1, **kwargs
                    )
            except IntegrityError as exc:
                last_error = exc
                continue
        raise last_error

    class Meta:
        ordering = ['-simulated_at']
        verbose_name = 'Simuliertes Spiel'
        verbose_name_plural = 'Simulierte Spiele'
        constraints = [
            models.UniqueConstraint(
                fields=['season', 'match_no'],
                name='uniq_simulatedmatch_season_match_no',
                condition=models.Q(match_no__isnull=False),
            ),
        ]

    def __str__(self):
        return (
            f"{self.home_club.short_name} {self.home_goals}:{self.away_goals} "
            f"{self.away_club.short_name}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DFB-POKAL / K.-O.-WETTBEWERB
# ═══════════════════════════════════════════════════════════════════════════════

class CupSeason(models.Model):
    """Pokalsaison — verbindet einen Pokalwettbewerb mit einer Saison.

    Speichert die Teilnehmer als M2M-Snapshot (Snapshot bei Saisonstart,
    spätere Tabellenänderungen verändern den laufenden Pokal nicht).
    """

    STATUS_SETUP = 'setup'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_SETUP, 'Vorbereitung'),
        (STATUS_RUNNING, 'Laufend'),
        (STATUS_COMPLETED, 'Abgeschlossen'),
    ]

    competition = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name='cup_seasons',
        limit_choices_to={'competition_type': 'cup'},
        verbose_name='Wettbewerb',
    )
    season = models.CharField(max_length=20, verbose_name='Saison')
    participants = models.ManyToManyField(
        'Club',
        blank=True,
        related_name='cup_participations',
        verbose_name='Teilnehmer (Snapshot)',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SETUP,
        verbose_name='Status',
    )
    winner_club = models.ForeignKey(
        'Club',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cup_titles',
        verbose_name='Pokalsieger',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['competition', 'season'],
                name='unique_cup_competition_season',
            )
        ]
        verbose_name = 'Pokalsaison'
        verbose_name_plural = 'Pokalsaisons'
        ordering = ['-season', 'competition']

    def __str__(self):
        return f'{self.competition.name} {self.season}'


class CupRound(models.Model):
    """Pokalrunde — konkrete Runde innerhalb einer Pokalsaison."""

    STATUS_PENDING = 'pending'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ausstehend'),
        (STATUS_SCHEDULED, 'Angesetzt'),
        (STATUS_COMPLETED, 'Abgeschlossen'),
    ]

    cup_season = models.ForeignKey(
        CupSeason,
        on_delete=models.CASCADE,
        related_name='rounds',
        verbose_name='Pokalsaison',
    )
    round_number = models.PositiveSmallIntegerField(verbose_name='Rundennummer')
    round_code = models.CharField(
        max_length=30,
        verbose_name='Rundencode',
        help_text='z. B. round_of_32, round_of_16, quarter_final, semi_final, final',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Status',
    )
    scheduled_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Spieltag',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cup_season', 'round_number'],
                name='unique_cup_round',
            )
        ]
        verbose_name = 'Pokalrunde'
        verbose_name_plural = 'Pokalrunden'
        ordering = ['cup_season', 'round_number']

    def __str__(self):
        return f'{self.cup_season} — {self.round_code} (R{self.round_number})'


class CupFixture(models.Model):
    """Pokalbegegnung — ein Spiel innerhalb einer Pokalrunde."""

    STATUS_SCHEDULED = 'scheduled'
    STATUS_PLAYED = 'played'
    STATUS_BYE = 'bye'
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Angesetzt'),
        (STATUS_PLAYED, 'Gespielt'),
        (STATUS_BYE, 'Freilos'),
    ]

    DECIDED_BY_REGULAR = 'regular_time'
    DECIDED_BY_ET = 'extra_time'
    DECIDED_BY_PENALTIES = 'penalties'
    DECIDED_BY_CHOICES = [
        (DECIDED_BY_REGULAR, 'Reguläre Spielzeit'),
        (DECIDED_BY_ET, 'Verlängerung'),
        (DECIDED_BY_PENALTIES, 'Elfmeterschießen'),
    ]

    cup_round = models.ForeignKey(
        CupRound,
        on_delete=models.CASCADE,
        related_name='fixtures',
        verbose_name='Pokalrunde',
    )
    bracket_position = models.PositiveSmallIntegerField(
        verbose_name='Bracket-Position',
        help_text='Aufsteigende Zahl pro Runde — bestimmt die Anzeigereihenfolge im Baum.',
    )
    home_club = models.ForeignKey(
        'Club',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cup_home_fixtures',
        verbose_name='Heimverein',
    )
    away_club = models.ForeignKey(
        'Club',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cup_away_fixtures',
        verbose_name='Auswärtsverein',
    )
    winner_club = models.ForeignKey(
        'Club',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cup_wins',
        verbose_name='Sieger',
    )
    simulated_match = models.OneToOneField(
        SimulatedMatch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cup_fixture',
        verbose_name='Spielbericht',
    )
    is_bye = models.BooleanField(default=False, verbose_name='Freilos')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
        verbose_name='Status',
    )

    # Ergebnisfelder — exakt entsprechend simulate_ko_match()-Output
    home_goals_90 = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Heimtore (90 min)')
    away_goals_90 = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Auswärtstore (90 min)')
    home_goals_et = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Heimtore (Verl.)')
    away_goals_et = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Auswärtstore (Verl.)')
    home_penalties = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Heim-Elfmeter')
    away_penalties = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Auswärts-Elfmeter')
    decided_by = models.CharField(
        max_length=20,
        choices=DECIDED_BY_CHOICES,
        null=True,
        blank=True,
        verbose_name='Entschieden durch',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cup_round', 'bracket_position'],
                name='unique_cup_round_bracket_position',
            )
        ]
        verbose_name = 'Pokalbegegnung'
        verbose_name_plural = 'Pokalbegegnungen'
        ordering = ['cup_round', 'bracket_position']

    @property
    def final_home_goals(self) -> int | None:
        """Gesamttore Heim (90 min + Verlängerung)."""
        if self.home_goals_90 is None:
            return None
        return (self.home_goals_90 or 0) + (self.home_goals_et or 0)

    @property
    def final_away_goals(self) -> int | None:
        """Gesamttore Auswärts (90 min + Verlängerung)."""
        if self.away_goals_90 is None:
            return None
        return (self.away_goals_90 or 0) + (self.away_goals_et or 0)

    @property
    def score_display(self) -> str:
        """Ergebnisanzeige für den Pokalbaum."""
        if self.is_bye:
            return 'Freilos'
        if self.status != self.STATUS_PLAYED:
            return '–'
        fh = self.final_home_goals
        fa = self.final_away_goals
        base = f'{fh}:{fa}' if fh is not None and fa is not None else '?:?'
        if self.decided_by == self.DECIDED_BY_ET:
            return f'{base} n. V.'
        if self.decided_by == self.DECIDED_BY_PENALTIES:
            return f'{base} i. E. ({self.home_penalties}:{self.away_penalties})'
        return base

    def __str__(self):
        if self.is_bye:
            club = self.home_club or self.winner_club
            return f'Freilos: {club}'
        home = self.home_club.short_name if self.home_club else '?'
        away = self.away_club.short_name if self.away_club else '?'
        return f'{self.cup_round} — {home} vs {away}'


class HistoricCoach(models.Model):
    """Historische Trainerentität für Seed-Rekorde der Ruhmeshalle."""

    fm_inside_id = models.CharField(
        max_length=80,
        unique=True,
        verbose_name='FM-Inside-ID',
    )
    name = models.CharField(max_length=160, verbose_name='Name')
    nationality = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Historischer Trainer'
        verbose_name_plural = 'Historische Trainer'

    def __str__(self):
        return self.name


class ClubRecord(models.Model):
    """Materialisierter Rekordstand je Verein, Rekord und Quelle.

    ``SEED`` wird ausschließlich durch die spätere Creator-Pflege geschrieben.
    Die Recompute-Engine arbeitet nur mit ``SIM`` und kann damit recherchierte
    Werte strukturell nicht überschreiben.
    """

    SOURCE_SEED = 'SEED'
    SOURCE_SIM = 'SIM'
    SOURCE_CHOICES = [
        (SOURCE_SEED, 'Echte Geschichte'),
        (SOURCE_SIM, 'Neue Geschichte'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='hall_of_fame_records',
    )
    record_key = models.CharField(max_length=60)
    source = models.CharField(max_length=4, choices=SOURCE_CHOICES)
    value_numeric = models.DecimalField(max_digits=15, decimal_places=2)
    value_display = models.CharField(max_length=160)
    holder_name = models.CharField(max_length=160)
    holder_player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    holder_coach = models.ForeignKey(
        HistoricCoach,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    holder_manager = models.ForeignKey(
        ManagerProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    opponent_name = models.CharField(max_length=160, blank=True)
    opponent_club = models.ForeignKey(
        Club,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    context_line = models.CharField(max_length=200, blank=True)
    record_date = models.DateField(null=True, blank=True)
    period_from = models.DateField(null=True, blank=True)
    period_to = models.DateField(null=True, blank=True)
    season = models.CharField(max_length=20, blank=True)
    competition = models.CharField(max_length=120, blank=True)
    source_note = models.TextField(blank=True)
    linked_match = models.ForeignKey(
        SimulatedMatch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='hall_of_fame_records',
    )
    is_anonymized = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'record_key', 'source'],
                name='unique_club_record_source',
            ),
        ]
        indexes = [
            models.Index(fields=['club', 'source']),
            models.Index(fields=['record_key', 'source']),
        ]
        verbose_name = 'Vereinsrekord'
        verbose_name_plural = 'Vereinsrekorde'

    def __str__(self):
        return f'{self.club} — {self.record_key} ({self.source})'


class ClubRecordBreak(models.Model):
    """Unveränderliches Ereignisprotokoll eines tatsächlichen Rekordwechsels."""

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='hall_of_fame_record_breaks',
    )
    record_key = models.CharField(max_length=60)
    old_value_numeric = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
    )
    old_value_display = models.CharField(max_length=160, blank=True)
    old_holder_name = models.CharField(max_length=160, blank=True)
    new_value_numeric = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
    )
    new_value_display = models.CharField(max_length=160, blank=True)
    new_holder_name = models.CharField(max_length=160, blank=True)
    broke_seed = models.BooleanField(default=False)
    season = models.CharField(max_length=20, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at', '-id']
        indexes = [
            models.Index(fields=['club', 'record_key', '-occurred_at']),
        ]
        verbose_name = 'Rekordwechsel'
        verbose_name_plural = 'Rekordwechsel'

    def __str__(self):
        return f'{self.club} — {self.record_key}: {self.old_value_display} → {self.new_value_display}'


class ClubRecordCorrectionRequest(models.Model):
    """Antragsschicht für spätere Creator-Pflege der Rekorddaten."""

    STATUS_OPEN = 'open'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Offen'),
        (STATUS_ACCEPTED, 'Angenommen'),
        (STATUS_REJECTED, 'Abgelehnt'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='hall_of_fame_correction_requests',
    )
    record_key = models.CharField(max_length=60)
    requester = models.ForeignKey(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='hall_of_fame_correction_requests',
    )
    old_value = models.CharField(max_length=160, blank=True)
    new_value = models.CharField(max_length=160)
    new_holder = models.CharField(max_length=160, blank=True)
    new_date = models.CharField(max_length=40, blank=True)
    source_reference = models.TextField()
    requester_note = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='decided_hall_of_fame_correction_requests',
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['status', '-created_at']
        verbose_name = 'Rekordkorrekturantrag'
        verbose_name_plural = 'Rekordkorrekturanträge'

    def __str__(self):
        return f'{self.club} — {self.record_key} ({self.status})'


class ClubPlayerImportJob(models.Model):
    """Importauftrag für den lokalen Vereins-/Spielerimporter (Creator-Mode).

    Der Auftrag verbindet einen WS-Verein mit einer Transfermarkt-Vereins-ID
    und einer (bei Erstellung eingefrorenen) Saison-ID. Der lokale Importer
    übernimmt den Auftrag per Lease-Token und füllt Kandidaten.
    """

    STATUS_PENDING = 'pending'
    STATUS_CLAIMED = 'claimed'
    STATUS_RUNNING = 'running'
    STATUS_REVIEW = 'review'
    STATUS_IMPORTING = 'importing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Wartet auf lokalen Importer'),
        (STATUS_CLAIMED, 'Vom lokalen Importer übernommen'),
        (STATUS_RUNNING, 'Import läuft'),
        (STATUS_REVIEW, 'Zur Kontrolle bereit'),
        (STATUS_IMPORTING, 'Datenbankimport läuft'),
        (STATUS_COMPLETED, 'Abgeschlossen'),
        (STATUS_FAILED, 'Fehlgeschlagen'),
        (STATUS_CANCELLED, 'Abgebrochen'),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='club_player_import_jobs',
    )
    ws_club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='player_import_jobs',
        help_text='Der bei Auftragserstellung gewählte WS-Verein.',
    )
    tm_club_id = models.PositiveBigIntegerField(
        help_text='Transfermarkt-Vereins-ID der zu importierenden Kaderseite.',
    )
    tm_club_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text=(
            'Vom lokalen Importer aus der Kaderseite erkannter Vereinsname. '
            'Dient zur Bestätigung/Aktualisierung neu angelegter Vereine.'
        ),
    )
    tm_season_id = models.PositiveIntegerField(
        help_text='Bei Erstellung eingefrorene Transfermarkt-Saison-ID.',
    )
    season_label = models.CharField(
        max_length=20,
        help_text='Anzeige der Saison, z. B. "2025/26".',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    progress_current = models.PositiveIntegerField(default=0)
    progress_total = models.PositiveIntegerField(default=0)
    current_step = models.CharField(max_length=200, blank=True)
    error_message = models.TextField(blank=True)
    validation_issues = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Validierungsprobleme aus dem letzten Import-Lauf '
            '(Liste von {level, code, message, ref}-Dicts).'
        ),
    )

    # Lease / Heartbeat — bindet genau einen lokalen Importer an den Auftrag.
    lease_token = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Pro Claim zufällig erzeugtes Geheimnis; bindet einen Importer.',
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Spielerimport-Auftrag'
        verbose_name_plural = 'Spielerimport-Aufträge'

    def __str__(self):
        return (
            f'Import #{self.pk} {self.ws_club_id} '
            f'(TM {self.tm_club_id}, {self.season_label}) — {self.status}'
        )

    @staticmethod
    def new_lease_token():
        """Erzeugt ein neues zufälliges Lease-Token für einen Claim."""
        return secrets.token_hex(32)


class PlayerImportCandidate(models.Model):
    """Temporärer Spielerkandidat eines Importauftrags.

    Hält die getrennten Rohdaten (Transfermarkt / FMInside / CMTracker) sowie das
    daraus normalisierte Ergebnis, bis der Administrator den Import bestätigt.
    """

    STATUS_NEW = 'new'
    STATUS_EXISTING_CHANGED = 'existing_changed'
    STATUS_EXISTING_UNCHANGED = 'existing_unchanged'
    STATUS_MISSING_FMI = 'missing_fmi'
    STATUS_MISSING_SOFIFA = 'missing_sofifa'
    STATUS_AMBIGUOUS_FMI = 'ambiguous_fmi'
    STATUS_AMBIGUOUS_SOFIFA = 'ambiguous_sofifa'
    STATUS_INVALID = 'invalid'
    STATUS_SOURCE_ERROR = 'source_error'
    STATUS_READY = 'ready'
    STATUS_IMPORTED = 'imported'
    STATUS_SKIPPED = 'skipped'

    STATUS_CHOICES = [
        (STATUS_NEW, 'Neuer Spieler'),
        (STATUS_EXISTING_CHANGED, 'Vorhanden — geändert'),
        (STATUS_EXISTING_UNCHANGED, 'Vorhanden — unverändert'),
        (STATUS_MISSING_FMI, 'FMInside fehlt'),
        (STATUS_MISSING_SOFIFA, 'CMTracker fehlt'),
        (STATUS_AMBIGUOUS_FMI, 'FMInside mehrdeutig'),
        (STATUS_AMBIGUOUS_SOFIFA, 'CMTracker mehrdeutig'),
        (STATUS_INVALID, 'Ungültig'),
        (STATUS_SOURCE_ERROR, 'Quellenfehler'),
        (STATUS_READY, 'Importbereit'),
        (STATUS_IMPORTED, 'Importiert'),
        (STATUS_SKIPPED, 'Übersprungen'),
    ]

    job = models.ForeignKey(
        ClubPlayerImportJob,
        related_name='candidates',
        on_delete=models.CASCADE,
    )

    tm_player_id = models.PositiveBigIntegerField()
    existing_player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='import_candidates',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
    )
    selected_for_import = models.BooleanField(default=False)
    overwrite_existing = models.BooleanField(default=False)

    # Getrennte Rohdaten je Quelle — keine finalen Attribute hier berechnen.
    tm_raw = models.JSONField(default=dict, blank=True)
    position_raw = models.JSONField(default=dict, blank=True)
    fmi_raw = models.JSONField(default=dict, blank=True)
    sofifa_raw = models.JSONField(default=dict, blank=True)

    normalized_data = models.JSONField(default=dict, blank=True)
    detected_changes = models.JSONField(default=dict, blank=True)
    validation_errors = models.JSONField(default=list, blank=True)
    source_warnings = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['job', 'tm_player_id']
        verbose_name = 'Spielerimport-Kandidat'
        verbose_name_plural = 'Spielerimport-Kandidaten'
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'tm_player_id'],
                name='unique_candidate_per_job_tm_player',
            ),
        ]

    def __str__(self):
        return f'Kandidat TM {self.tm_player_id} (Job #{self.job_id}) — {self.status}'


# ════════════════════════════════════════════════════════════════════════════
#  Scouting-System V1 (Task #594)
# ════════════════════════════════════════════════════════════════════════════


class ScoutingDepartment(models.Model):
    """Pro Verein: Ausbaustufe der Scoutingabteilung (0–3).

    Die Stufe beeinflusst nur Dauer, Auftragskosten und Trefferpräzision –
    niemals die Qualität der gefundenen Spieler.
    """
    club = models.OneToOneField(
        Club,
        on_delete=models.CASCADE,
        related_name='scouting_department',
        verbose_name='Verein',
    )
    level = models.PositiveSmallIntegerField(
        'Ausbaustufe',
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Scoutingbüro'
        verbose_name_plural = 'Scoutingbüros'

    def __str__(self):
        return f'{self.club} – Scouting Stufe {self.level}'


class ScoutingAssignment(models.Model):
    """Ein Scoutingauftrag. Es gibt pro Verein immer nur einen aktiven Auftrag."""

    SCOPE_COUNTRY = 'country'
    SCOPE_REGION = 'region'
    SCOPE_CHOICES = [
        (SCOPE_COUNTRY, 'Land'),
        (SCOPE_REGION, 'Region'),
    ]

    PROFILE_BACKUP = 'backup'
    PROFILE_ERGAENZUNG = 'ergaenzung'
    PROFILE_ROTATION = 'rotation'
    PROFILE_STAMMKRAFT = 'stammkraft'
    PROFILE_TALENT = 'talent'
    PROFILE_CHOICES = [
        (PROFILE_BACKUP, 'Back-up'),
        (PROFILE_ERGAENZUNG, 'Ergänzungsspieler'),
        (PROFILE_ROTATION, 'Rotationsspieler'),
        (PROFILE_STAMMKRAFT, 'Stammkraft'),
        (PROFILE_TALENT, 'Jugendspieler / Talent'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Aktiv'),
        (STATUS_COMPLETED, 'Abgeschlossen'),
        (STATUS_CANCELLED, 'Abgebrochen'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='scouting_assignments',
        verbose_name='Verein',
    )
    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scouting_assignments',
        verbose_name='Manager',
    )
    scope_type = models.CharField(max_length=10, choices=SCOPE_CHOICES, default=SCOPE_COUNTRY)
    scope_key = models.CharField(
        max_length=20,
        help_text='ISO2-Ländercode (Großbuchstaben) oder Regions-Schlüssel.',
    )
    position = models.CharField(
        max_length=80,
        blank=True,
        default='',
        help_text='Zielposition(en), kommagetrennt bei Mehrfachauswahl (leer = keine Vorgabe).',
    )
    profile = models.CharField(max_length=20, choices=PROFILE_CHOICES, default=PROFILE_ERGAENZUNG)
    department_level = models.PositiveSmallIntegerField(default=0)
    cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    duration_days = models.PositiveSmallIntegerField(default=0)
    started_on = models.DateField(default=timezone.localdate)
    completes_on = models.DateField()
    season_id = models.IntegerField(help_text='Eingefrorene Transfermarkt-Saison-ID bei Auftragsstart.')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    finds_generated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Scoutingauftrag'
        verbose_name_plural = 'Scoutingaufträge'
        constraints = [
            models.UniqueConstraint(
                fields=['club'],
                condition=models.Q(status='active'),
                name='unique_active_assignment_per_club',
            ),
        ]

    def __str__(self):
        return f'Scoutingauftrag {self.club} → {self.scope_key} ({self.get_status_display()})'

    @property
    def is_ready(self):
        return self.status == self.STATUS_ACTIVE and timezone.localdate() >= self.completes_on


class ScoutingFind(models.Model):
    """Ein anonymer Fund eines Auftrags. Pro Auftrag genau 3 Funde."""

    STATUS_OFFERED = 'offered'
    STATUS_CHOSEN = 'chosen'
    STATUS_REJECTED = 'rejected'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_OFFERED, 'Vorgeschlagen'),
        (STATUS_CHOSEN, 'Ausgewählt'),
        (STATUS_REJECTED, 'Abgelehnt'),
        (STATUS_EXPIRED, 'Verfallen'),
    ]

    assignment = models.ForeignKey(
        ScoutingAssignment,
        on_delete=models.CASCADE,
        related_name='finds',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='scouting_finds',
    )
    order = models.PositiveSmallIntegerField(default=0, help_text='Anzeigereihenfolge 0–2.')
    observer_count = models.PositiveIntegerField(default=0, help_text='Anzahl beobachtender Manager.')
    min_bid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_OFFERED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['assignment', 'order']
        verbose_name = 'Scouting-Fund'
        verbose_name_plural = 'Scouting-Funde'
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'order'],
                name='unique_find_order_per_assignment',
            ),
        ]

    def __str__(self):
        return f'Fund #{self.order} → {self.player} (Auftrag {self.assignment_id})'


class ScoutingBid(models.Model):
    """Verbindliches Gebot auf einen Poolspieler, gewertet zum Zuschlagstermin."""

    STATUS_ACTIVE = 'active'
    STATUS_WON = 'won'
    STATUS_LOST = 'lost'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Aktiv'),
        (STATUS_WON, 'Gewonnen'),
        (STATUS_LOST, 'Verloren'),
        (STATUS_CANCELLED, 'Zurückgezogen'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='scouting_bids',
        verbose_name='Verein',
    )
    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scouting_bids',
        verbose_name='Manager',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='scouting_bids',
    )
    find = models.ForeignKey(
        ScoutingFind,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bids',
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    min_bid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    window_date = models.DateField(help_text='Fester Zuschlagstermin, zu dem dieses Gebot gewertet wird.')
    season_id = models.IntegerField(help_text='Eingefrorene Saison-ID bei Gebotsabgabe.')
    coin_earmarked = models.BooleanField(
        default=False,
        help_text='Gebot benötigt einen Hoeneß-Coin-Slot (3.+ Verpflichtung). Coin wird erst bei Gewinn verbraucht.',
    )
    coin_used = models.BooleanField(
        default=False,
        help_text='True, wenn ein gewonnenes Gebot tatsächlich einen Coin verbraucht hat.',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Scouting-Gebot'
        verbose_name_plural = 'Scouting-Gebote'
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'player', 'window_date'],
                condition=models.Q(status='active'),
                name='unique_active_bid_per_club_player_window',
            ),
        ]

    def __str__(self):
        return f'Gebot {self.club} → {self.player} ({self.amount} €, {self.get_status_display()})'


class WatchlistEntry(models.Model):
    """Managergebundene Beobachtungsliste (bleibt bei Vereinswechsel bestehen)."""

    STATUS_WATCHED = 'watched'
    STATUS_BID = 'bid'
    STATUS_WON = 'won'
    STATUS_LOST = 'lost'
    STATUS_CHOICES = [
        (STATUS_WATCHED, 'Beobachtet'),
        (STATUS_BID, 'Gebot abgegeben'),
        (STATUS_WON, 'Gewonnen'),
        (STATUS_LOST, 'Verloren'),
    ]

    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='watchlist_entries',
        verbose_name='Manager',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='watchlist_entries',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_WATCHED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Beobachtungslisten-Eintrag'
        verbose_name_plural = 'Beobachtungslisten-Einträge'
        constraints = [
            models.UniqueConstraint(
                fields=['manager', 'player'],
                name='unique_watchlist_manager_player',
            ),
        ]

    def __str__(self):
        return f'{self.manager} beobachtet {self.player} ({self.get_status_display()})'


class CountryNetwork(models.Model):
    """Persistente Community-/Aktivitätsdaten je Land.

    Die echte Poolgröße wird NIE gespeichert oder ans Frontend gegeben –
    sie wird serverseitig live gezählt. ``coverage_percent`` wird nur aus
    Community- und Aktivitätspunkten abgeleitet, damit die verborgene
    Spielerzahl nicht rückgerechnet werden kann.
    """
    iso2 = models.CharField(max_length=2, unique=True, help_text='ISO2-Ländercode (Großbuchstaben).')
    name = models.CharField(max_length=100)
    continent = models.CharField(max_length=40, blank=True, default='')
    region = models.CharField(max_length=40, blank=True, default='')
    community_points = models.PositiveIntegerField(default=0)
    activity_points = models.PositiveIntegerField(default=0)
    is_paused = models.BooleanField(default=False, help_text='Admin-Sperre: Land wird als gesperrt angezeigt.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Länder-Netzwerk'
        verbose_name_plural = 'Länder-Netzwerke'

    def clean(self):
        super().clean()
        if self.iso2:
            normalized = self.iso2.strip().upper()
            self.iso2 = normalized
            if not (len(normalized) == 2 and normalized.isalpha() and normalized.isascii()):
                raise ValidationError(
                    {'iso2': 'Der ISO2-Code muss aus genau 2 Buchstaben (A–Z) bestehen.'}
                )
            qs = CountryNetwork.objects.filter(iso2=normalized)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {'iso2': f'Ein Land mit dem ISO2-Code „{normalized}" existiert bereits.'}
                )

    def save(self, *args, **kwargs):
        if self.iso2:
            self.iso2 = self.iso2.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.iso2})'


class CommunitySubmission(models.Model):
    """Community-Einreichung eines tm.de-Profils zur Erhöhung der Abdeckung."""

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Offen'),
        (STATUS_APPROVED, 'Angenommen'),
        (STATUS_REJECTED, 'Abgelehnt'),
    ]

    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='community_submissions',
        verbose_name='Manager',
    )
    iso2 = models.CharField(max_length=2, help_text='ISO2-Ländercode des eingereichten Spielers.')
    tm_url = models.URLField('Transfermarkt-URL')
    player_name = models.CharField(max_length=120, blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    week_key = models.CharField(
        max_length=8,
        help_text='ISO-Jahr-Woche (z. B. 2026-W26), eingefroren bei Einreichung – für das Wochenlimit.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Community-Einreichung'
        verbose_name_plural = 'Community-Einreichungen'

    def __str__(self):
        return f'{self.manager} → {self.iso2} ({self.get_status_display()})'


class StadionumfeldConfig(models.Model):
    """Globaler Einzelsatz (Singleton) für die Stadionumfeld-Szene.

    Speichert den kompletten Editor-Zustand aus dem Replit-Design-Export
    (heimspiel, tod, wetter, day, capacity, levels, building, positions,
    badgePos, selected). Nur Superuser dürfen schreiben; die Szene gilt
    global für ALLE Vereine. Kalibrierungs-Defaults (defPos/BAKED_POS/
    BAKED_BADGES) leben clientseitig — hier werden nur die Overrides und
    der Umgebungs-/Ausbauzustand persistiert.
    """

    state = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Stadionumfeld-Konfiguration'
        verbose_name_plural = 'Stadionumfeld-Konfiguration'

    def __str__(self):
        return f'Stadionumfeld-Konfiguration (aktualisiert {self.updated_at:%Y-%m-%d %H:%M})'

    @classmethod
    def get_solo(cls):
        obj = cls.objects.order_by('id').first()
        if obj is None:
            obj = cls.objects.create(state={})
        return obj


class ClubStadionumfeldState(models.Model):
    """Per-Verein-Zustand der Stadionumfeld-Szene (Spec Kap. 5, Phase 3).

    Hält die Ambiente-Keys (heimspiel, tod, wetter, day) je Verein — das
    Szenen-LAYOUT (positions, badgePos, selected) bleibt bewusst im globalen
    StadionumfeldConfig-Singleton (Kalibrierung durch Superuser, gilt für
    alle Vereine). Die Facility-Ausbaustufen liegen weiterhin auf Stadium,
    laufende Bauten in FacilityConstruction.
    """

    club = models.OneToOneField(
        Club,
        on_delete=models.CASCADE,
        related_name='stadionumfeld_state',
        verbose_name='Verein',
    )
    state = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Stadionumfeld-Zustand (Verein)'
        verbose_name_plural = 'Stadionumfeld-Zustände (Vereine)'

    def __str__(self):
        return f'Stadionumfeld-Zustand {self.club.name}'

    @classmethod
    def for_club(cls, club):
        obj, _ = cls.objects.get_or_create(club=club)
        return obj


class FacilityConstruction(models.Model):
    """Aktiver Ausbau einer Vereinseinrichtung mit echter Wanduhr-Bauzeit.

    Beim Start wird das Geld sofort abgebucht und dieser Auftrag angelegt; die
    Stufe der Einrichtung (Stadium.<facility>_level) wird ERST beim Ablauf von
    ``completes_at`` erhöht (lazy resolve über resolve_due_constructions()). So
    greifen Boni/Attribute erst NACH Ablauf der Bauzeit, nicht schon beim Start.

    Generisch gehalten: ``facility`` nimmt die serverseitigen Keys aus
    FACILITY_DATA (nlz/medizin/training/office). Weitere Einrichtungen
    (z. B. Scouting mit 3 Stufen) lassen sich später ohne Schemaänderung
    ergänzen.
    """
    STATUS_ACTIVE = 'active'
    STATUS_DONE = 'done'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Im Bau'),
        (STATUS_DONE, 'Abgeschlossen'),
        (STATUS_CANCELLED, 'Abgebrochen'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='facility_constructions',
        verbose_name='Verein',
    )
    facility = models.CharField(
        'Einrichtung',
        max_length=32,
        help_text='Serverseitiger Einrichtungs-Key (z. B. nlz, medizin, training, office).',
    )
    target_level = models.PositiveSmallIntegerField('Zielstufe')
    cost_paid = models.DecimalField(
        'Bezahlte Baukosten',
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
    )
    started_at = models.DateTimeField('Baubeginn', default=timezone.now)
    completes_at = models.DateTimeField('Fertigstellung')
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Einrichtungs-Ausbau'
        verbose_name_plural = 'Einrichtungs-Ausbauten'
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'facility'],
                condition=models.Q(status='active'),
                name='uniq_active_facility_construction_per_club',
            ),
        ]

    def __str__(self):
        return (
            f'{self.club} – {self.facility} → Stufe {self.target_level} '
            f'({self.status})'
        )


class MediaOutlet(models.Model):
    """Medienpartner für Vereinsnews (Logo unter ASSETS_ROOT/media/{slug}_media.png)."""

    name         = models.CharField(max_length=80, unique=True)
    slug         = models.SlugField(max_length=60, unique=True,
                                    help_text='Dateiname ohne _media.png, z.B. kicker')
    accent_color = models.CharField(max_length=7, default='#22e6ff',
                                    help_text='Hex-Akzentfarbe für Fallback-Badge')
    has_logo     = models.BooleanField(default=False,
                                       help_text='True wenn PNG unter ASSETS_ROOT/media/ vorhanden')
    sort_order   = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def logo_url(self):
        from .asset_urls import _base as _assets_base
        return f'{_assets_base()}media/{self.slug}_media.png'

    def to_vn_dict(self):
        return {
            'n':    self.name,
            'slug': self.slug if self.has_logo else None,
            'd':    self.accent_color,
        }


# ═══════════════════════════════════════════════════════════════════════════
#  Finanzsystem (Spec Kap. 2, 4, 12) — EconomyParameter, Ledger, Snapshot
# ═══════════════════════════════════════════════════════════════════════════

class EconomyParameter(models.Model):
    """Zentrale Balancing-Regler-Tabelle (Spec Kap. 2), pro Saison versioniert.

    Saison-Konvention: numerische Sim-Saison als String
    (GameSeasonState.current_season, z. B. "0", "1") — es gibt kein
    Season-Modell. Lookup mit Fallback auf die jüngste Saison ≤ angefragt
    (game.economy.params.get_param).
    """

    saison = models.CharField(max_length=20, verbose_name='Saison')
    key = models.CharField(max_length=64, verbose_name='Parameter-Key')
    value = models.JSONField(verbose_name='Wert')

    class Meta:
        unique_together = ('saison', 'key')
        ordering = ['key', 'saison']
        verbose_name = 'Economy-Parameter'
        verbose_name_plural = 'Economy-Parameter'

    def __str__(self):
        return f'{self.key} (Saison {self.saison}) = {self.value}'


class FinanceTransaction(models.Model):
    """Finanz-Ledger (Spec Kap. 12.1) — die einzige Wahrheit über Geld.

    Der Kontostand eines Vereins ist die Summe seiner Ledger-Zeilen;
    Club.budget ist nur ein Performance-Cache (Integritätsprüfung via
    finance_integrity_check). Buchungen laufen ausschließlich über
    game.economy.booking.book() — nie direkt Zeilen anlegen.
    """

    TYP_CHOICES = [
        # Einnahmen (Schöpfung)
        ('TICKET',            'Ticketverkauf'),
        ('UMFELD',            'Stadionumfeld-Umsatz'),
        ('SPONSOR_FIX',       'Sponsor (Fixrate)'),
        ('SPONSOR_VARIABEL',  'Sponsor (variabel)'),
        ('TV_SOCKEL',         'TV-Gelder (Sockel)'),
        ('TV_PLATZ',          'TV-Gelder (Platzierung)'),
        ('TV_KOEFF',          'TV-Gelder (Koeffizient)'),
        ('FALLSCHIRM',        'Fallschirmzahlung'),
        ('PRAEMIE_POKAL',     'Pokalprämie'),
        ('PRAEMIE_SUPERCUP',  'Supercup-Prämie'),
        ('PRAEMIE_INTL',      'Internationale Prämie'),
        ('ABFINDUNG',         'Abfindung (Todesfall)'),
        # Transfers (Zirkulation)
        ('TRANSFER_EIN',      'Transfer (Einnahme)'),
        ('TRANSFER_AUS',      'Transfer (Ausgabe)'),
        ('AUSBILDUNG_EIN',    'Ausbildungsabgabe (Einnahme)'),
        ('AUSBILDUNG_AUS',    'Ausbildungsabgabe (Ausgabe)'),
        # Senken (Vernichtung)
        ('GEHALT',            'Gehälter'),
        ('BETRIEB',           'Betriebskosten'),
        ('STADION_UNTERHALT', 'Stadionunterhalt'),
        ('STADION_SPIELTAG',  'Spieltagskosten'),
        ('AUSBAU',            'Stadionausbau'),
        ('UMFELD_AUSBAU',     'Stadionumfeld-Ausbau'),
        ('SCOUTING',          'Scouting'),
        ('AUKTION',           'Auktion'),
        ('STRAFE',            'Sportgericht-Strafe'),
        ('VERBANDSABGABE',    'Verbandsabgabe'),
        # Admin
        ('KORREKTUR_ADMIN',   'Admin-Korrektur'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.PROTECT,
        related_name='finance_transactions',
        verbose_name='Verein',
    )
    saison = models.CharField(max_length=20, blank=True, verbose_name='Saison')
    spieltag = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Spieltag',
    )
    typ = models.CharField(
        max_length=32, choices=TYP_CHOICES, verbose_name='Buchungstyp',
    )
    betrag = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Betrag (€)',
        help_text='Positiv = Einnahme, Negativ = Ausgabe.',
    )
    referenz_typ = models.CharField(max_length=32, blank=True, default='')
    referenz_id = models.PositiveIntegerField(null=True, blank=True)
    referenz_mw = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Marktwert-Snapshot (€)',
        help_text=(
            'Marktwert des Spielers zum Buchungszeitpunkt (Snapshot). '
            'Nur bei Transfer-Buchungen befüllt — ermöglicht historische '
            'Ablöse/MW-Auswertung ohne Rekonstruktion.'
        ),
    )
    beschreibung = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Verwendungszweck',
    )
    datum = models.DateField(default=timezone.localdate, verbose_name='Buchungsdatum')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['club', 'saison']),
            models.Index(fields=['saison', 'typ']),
            models.Index(fields=['club', 'created_at']),
        ]
        constraints = [
            # Idempotenz-Schutz Show-Auktion (Spec E25): die Referenz
            # showauction:{id}:settle darf nur EINMAL gebucht werden —
            # doppeltes Abwickeln (Beat- und Lazy-Pfad gleichzeitig)
            # ist damit strukturell unmöglich.
            models.UniqueConstraint(
                fields=['referenz_typ', 'referenz_id'],
                condition=models.Q(referenz_typ='showauction_settle'),
                name='unique_showauction_settle_booking',
            ),
        ]
        verbose_name = 'Finanzbuchung'
        verbose_name_plural = 'Finanzbuchungen'

    @property
    def is_income(self):
        return self.betrag >= 0

    def __str__(self):
        sign = '+' if self.betrag >= 0 else ''
        return (f'{self.club} | {self.get_typ_display()} | '
                f'{sign}{self.betrag:,.0f} € (S{self.saison}'
                + (f'/ST{self.spieltag}' if self.spieltag else '') + ')')


class FinanceReservation(models.Model):
    """Generische Geld-/Kaderplatz-Reservierung (Escrow-Fundament).

    Eine Reservierung ist KEINE Buchung: Ledger und Kontostand bleiben
    unberührt. Aktive Reservierungen reduzieren aber überall die
    "verfügbare" Sicht (Spec Show-Auktion §8.2):
    - booking._create_booking: Deckungsprüfung aktiver Ausgaben
    - transfers._check_kaderplatz: Kaderlimit-Prüfung
    - scouting.service: verfügbares Budget / freie Slots

    Verwaltung ausschließlich über game/economy/reservations.py
    (reserve / adjust / release / consume) — nie direkt Zeilen anlegen.
    """

    STATUS_ACTIVE = 'active'
    STATUS_RELEASED = 'released'
    STATUS_CONSUMED = 'consumed'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Aktiv'),
        (STATUS_RELEASED, 'Freigegeben'),
        (STATUS_CONSUMED, 'Verbraucht (gebucht)'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='finance_reservations',
        verbose_name='Verein',
    )
    zweck = models.CharField(
        max_length=32,
        help_text="Modul-Kennung, z. B. 'showauction'.",
    )
    referenz = models.CharField(
        max_length=64,
        help_text="Eindeutige Referenz, z. B. 'showauction:bid:42'.",
    )
    betrag = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text='Reservierter Geldbetrag (≥ 0).',
    )
    slots = models.PositiveSmallIntegerField(
        default=0,
        help_text='Reservierte Kaderplätze.',
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['referenz'],
                condition=models.Q(status='active'),
                name='unique_active_finance_reservation',
            ),
        ]
        indexes = [
            models.Index(fields=['club', 'status']),
        ]
        verbose_name = 'Finanz-Reservierung'
        verbose_name_plural = 'Finanz-Reservierungen'

    def __str__(self):
        return (f'{self.club} | {self.referenz} | {self.betrag:,.0f} € '
                f'+ {self.slots} Slot(s) [{self.get_status_display()}]')


class SeasonEconomySnapshot(models.Model):
    """Saison-Snapshot der Ökonomie-Basisdaten (Spec Kap. 4 + 14).

    gehalts_anker = gedämpfter MW-Median (max ±MEDIAN_DAEMPFUNG pro Saison
    gegenüber Vorsaison-Anker). Erste Saison ohne Vorgänger: roher Median.
    """

    saison = models.CharField(max_length=20, unique=True, verbose_name='Saison')
    mw_median = models.DecimalField(max_digits=15, decimal_places=2)
    staerke_median = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
    )
    potential_median = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
    )
    mw_kurve_json = models.JSONField(default=dict, blank=True)
    gehalts_anker = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-saison']
        verbose_name = 'Saison-Ökonomie-Snapshot'
        verbose_name_plural = 'Saison-Ökonomie-Snapshots'

    def __str__(self):
        return (f'Snapshot Saison {self.saison}: MW-Median {self.mw_median:,.0f} €, '
                f'Anker {self.gehalts_anker:,.0f} €')


class FinanceMatchdayRun(models.Model):
    """Idempotenz-Guard für finance_matchday_run (ein Marker je Verein+Spieltag+Typ).

    typ='' (leer) ist der Haupt-Zeitstempel-Anker: seine run_at-Zeit definiert
    das Betriebskosten-Fenster. Typ-Marker (TV_SOCKEL, SPONSOR, TICKET, GEHALT,
    STADION, BETRIEB) zeigen an, welche Buchungsschritte bereits abgeschlossen
    wurden. Ein Wiederholungsaufruf ergänzt nur fehlende Typen.
    """

    club = models.ForeignKey(
        Club, on_delete=models.CASCADE, related_name='finance_matchday_runs',
    )
    saison = models.CharField(max_length=20)
    spieltag = models.PositiveSmallIntegerField()
    typ = models.CharField(
        max_length=30, default='', blank=True,
        help_text=(
            "Buchungstyp-Guard (leer = Haupt-Zeitstempel-Anker; "
            "TV_SOCKEL / SPONSOR / TICKET / GEHALT / STADION / BETRIEB = Schritt-Marker)."
        ),
    )
    run_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('club', 'saison', 'spieltag', 'typ')
        ordering = ['-run_at']
        verbose_name = 'Finanz-Spieltagslauf'
        verbose_name_plural = 'Finanz-Spieltagsläufe'

    def __str__(self):
        label = f' [{self.typ}]' if self.typ else ''
        return f'{self.club} — Saison {self.saison}, ST {self.spieltag}{label} ({self.run_at:%d.%m.%Y %H:%M})'


class LandKoeffizient(models.Model):
    """Landes-5-Jahreswertung (Spec Kap. 7.1) — Punkte je Land und Saison.

    Der Koeffizienten-Rang eines Landes ergibt sich aus der Summe der
    Punkte der letzten 5 Saisons (game.economy.tv.land_rank_map). Beim
    Launch geseedet mit realen UEFA-Werten (eine Zeile pro Land in der
    Seed-Saison = komplette 5-Jahres-Summe). Sobald Europapokal-Ergebnisse
    simuliert werden, schreibt finance_season_close echte Saisonpunkte.
    """

    land = models.CharField(max_length=80, verbose_name='Land')
    saison = models.CharField(max_length=20, verbose_name='Saison')
    punkte = models.DecimalField(
        max_digits=8, decimal_places=3, verbose_name='Punkte',
    )

    class Meta:
        unique_together = ('land', 'saison')
        ordering = ['saison', '-punkte']
        verbose_name = 'Landeskoeffizient'
        verbose_name_plural = 'Landeskoeffizienten'

    def __str__(self):
        return f'{self.land} (Saison {self.saison}): {self.punkte}'


class VereinKoeffizient(models.Model):
    """Vereins-5-Jahreswertung (Spec Kap. 7.1) — Punkte je Verein und Saison.

    Bestimmt den Koeffizienten-Rang innerhalb der Liga für den 20-%-
    Koeffanteil der TV-Gelder (Kap. 7.3). Seed wie LandKoeffizient.
    """

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='koeffizienten',
        verbose_name='Verein',
    )
    saison = models.CharField(max_length=20, verbose_name='Saison')
    punkte = models.DecimalField(
        max_digits=8, decimal_places=3, verbose_name='Punkte',
    )

    class Meta:
        unique_together = ('club', 'saison')
        ordering = ['saison', '-punkte']
        verbose_name = 'Vereinskoeffizient'
        verbose_name_plural = 'Vereinskoeffizienten'

    def __str__(self):
        return f'{self.club} (Saison {self.saison}): {self.punkte}'


class TVPot(models.Model):
    """Ländertopf-Snapshot je Saison (Spec Kap. 7.2).

    Wird bei finance_season_open aus TV_TOEPFE × Koeffizienten-Rang
    eingefroren — der Rang bleibt damit saisonstabil, auch wenn sich die
    Koeffizienten unterjährig ändern würden.
    """

    saison = models.CharField(max_length=20, verbose_name='Saison')
    land = models.CharField(max_length=80, verbose_name='Land')
    rang = models.PositiveSmallIntegerField(verbose_name='Koeffizienten-Rang')
    gesamt = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='Gesamttopf (€)',
    )

    class Meta:
        unique_together = ('saison', 'land')
        ordering = ['saison', 'rang']
        verbose_name = 'TV-Ländertopf'
        verbose_name_plural = 'TV-Ländertöpfe'

    def __str__(self):
        return f'{self.land} Saison {self.saison}: Rang {self.rang}, {self.gesamt:,.0f} €'


class Sponsor(models.Model):
    """Reales Sponsoring-Unternehmen aus der Stammdatenbank (Spec Kap. 6 V2).

    slug: Eindeutiger Bezeichner (ASCII), dient als Dateiname-Stem für
    Logo-Assets (/var/www/assets/sponsors/{bereich}/{slug}.jpg).
    bereich: Slot-Typ des Sponsors — steuert, in welchem der 5 Slots
    ein Angebot generiert werden darf (Exclusivity-Regel).
    """

    BEREICH_HAUPTSPONSOR = 'hauptsponsor'
    BEREICH_TRIKOTSPONSOR = 'trikotsponsor'
    BEREICH_AUSRUESTER = 'ausruester'
    BEREICH_STADIONPARTNER = 'stadionpartner'
    BEREICH_TV_MEDIEN = 'tv_medien'
    BEREICH_CHOICES = [
        (BEREICH_HAUPTSPONSOR, 'Hauptsponsor'),
        (BEREICH_TRIKOTSPONSOR, 'Trikotsponsor'),
        (BEREICH_AUSRUESTER, 'Ausrüster'),
        (BEREICH_STADIONPARTNER, 'Stadionpartner'),
        (BEREICH_TV_MEDIEN, 'TV- & Medienpartner'),
    ]

    slug = models.SlugField(max_length=80, unique=True, verbose_name='Slug')
    name = models.CharField(max_length=120, verbose_name='Firmenname')
    display_name = models.CharField(
        max_length=120, blank=True, verbose_name='Anzeigename (Caps)',
    )
    bereich = models.CharField(
        max_length=20, choices=BEREICH_CHOICES,
        db_index=True, verbose_name='Bereich',
    )
    branche = models.CharField(max_length=60, blank=True, verbose_name='Branche')
    domain = models.CharField(
        max_length=120, blank=True, verbose_name='Domain (z.B. fritz-kola.de)',
    )
    aktiv = models.BooleanField(default=True, db_index=True, verbose_name='Aktiv')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['bereich', 'name']
        verbose_name = 'Sponsor'
        verbose_name_plural = 'Sponsoren'
        indexes = [models.Index(fields=['bereich', 'aktiv'])]

    def __str__(self):
        return f'{self.name} ({self.get_bereich_display()})'

    @property
    def logo_url(self):
        if self.domain:
            return (
                f'https://img.logo.dev/{self.domain}'
                '?token=pk_QmUpoNKUTByAKyVZIVYYVw&size=400&format=jpg'
            )
        from django.conf import settings
        base = getattr(settings, 'ASSETS_BASE_URL', '/assets/')
        return f'{base}sponsors/{self.bereich}/{self.slug}_sponsor.jpg'


class SponsorOffer(models.Model):
    """Sponsor-Jahresangebot (Spec Kap. 6.2) — Laufzeit genau 1 Saison.

    3–5 Angebote je Verein und Saison, alle mit demselben Erwartungswert
    ≈ Sponsorwert (kalibriert auf die Präsidenten-Erwartung, ±Streuung).
    Genau EIN Angebot pro (Verein, Saison) darf gewaehlt=True sein
    (DB-Constraint). variable_json beschreibt den variablen Anteil:
    {'einheit': 'sieg'|'besucher'|'ziel', 'betrag': float,
     'erwartete_events': float, 'ziel_label': str}.

    V2-Felder (Slot-Modell, Spec Kap. 6 V2):
    slot=haupt|trikot|ausruester|stadion|tv; fix_start/fix_aktuell in €
    (int) für Verhandlungs-Tracking; status-Zustandsmaschine.
    """

    TYP_SICHERHEIT = 'sicherheit'
    TYP_SIEGGELD = 'sieggeld'
    TYP_TORGELD = 'torgeld'
    TYP_ZIELJAEGER = 'zieljaeger'
    TYP_ZUSCHAUER = 'zuschauer'
    TYP_CHOICES = [
        (TYP_SICHERHEIT, 'Sicherheit (100 % fix)'),
        (TYP_SIEGGELD, 'Sieggeld (fix + €/Sieg)'),
        (TYP_TORGELD, 'Torgeld (fix + €/Tor)'),
        (TYP_ZIELJAEGER, 'Zieljäger (fix + Zielbonus)'),
        (TYP_ZUSCHAUER, 'Zuschauer (fix + €/Besucher)'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='sponsor_offers',
        verbose_name='Verein',
    )
    saison = models.CharField(max_length=20, verbose_name='Saison')
    typ = models.CharField(
        max_length=20, choices=TYP_CHOICES, verbose_name='Angebotstyp',
    )
    sponsor_name = models.CharField(max_length=100, verbose_name='Sponsorname')
    fix_betrag = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='Fixbetrag / Saison (€)',
    )
    variable_json = models.JSONField(
        default=dict, blank=True, verbose_name='Variabler Anteil',
    )
    erwartungswert = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='Erwartungswert (€)',
    )
    gewaehlt = models.BooleanField(default=False, verbose_name='Gewählt')
    angenommen_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Angenommen am',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # ── V2-Felder (Slot-Modell, Spec Kap. 6 V2) ──────────────────────────────
    STATUS_OFFEN = 'offen'
    STATUS_FIXIERT = 'fixiert'
    STATUS_VERPRELLT = 'verprellt'
    STATUS_ABGESAGT = 'abgesagt'
    STATUS_ANGENOMMEN = 'angenommen'  # V1-Legacy-Alias (=fixiert)
    STATUS_LEGACY = 'legacy'
    STATUS_CHOICES = [
        (STATUS_OFFEN,     'Offen'),
        (STATUS_FIXIERT,   'Fixiert (Vertrag abgeschlossen)'),
        (STATUS_VERPRELLT, 'Verprellt (Sponsor abgesprungen)'),
        (STATUS_ABGESAGT,  'Abgesagt (durch anderen Slot-Contract)'),
        (STATUS_ANGENOMMEN, 'Angenommen (V1-Legacy)'),
        (STATUS_LEGACY,    'Alt (V1)'),
    ]

    slot = models.CharField(
        max_length=20, default='haupt', db_index=True,
        verbose_name='Sponsoring-Slot',
    )
    sponsor = models.ForeignKey(
        'Sponsor', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='offers',
        verbose_name='Sponsor',
    )
    fix_start = models.BigIntegerField(
        null=True, blank=True,
        verbose_name='Fixbetrag Verhandlungsstart (€)',
    )
    fix_aktuell = models.BigIntegerField(
        null=True, blank=True,
        verbose_name='Fixbetrag aktuell (€)',
    )
    var_rate = models.BigIntegerField(
        default=0,
        verbose_name='Variabler Betrag je Event (€-Cent)',
    )
    var_ziel = models.CharField(
        max_length=32, blank=True,
        verbose_name='Zielstufe (goal_tier)',
    )
    mult = models.DecimalField(
        max_digits=6, decimal_places=4, default=1,
        verbose_name='Verhandlungs-Multiplikator',
    )
    runde = models.PositiveSmallIntegerField(
        default=0, verbose_name='Verhandlungsrunde',
    )
    status = models.CharField(
        max_length=12, default=STATUS_LEGACY, choices=STATUS_CHOICES,
        db_index=True, verbose_name='Status',
    )

    class Meta:
        ordering = ['club', 'saison', 'slot', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'saison'],
                condition=models.Q(gewaehlt=True),
                name='unique_chosen_sponsor_offer_per_season',
            ),
        ]
        indexes = [
            models.Index(fields=['club', 'saison']),
            models.Index(fields=['club', 'saison', 'slot']),
        ]
        verbose_name = 'Sponsorangebot'
        verbose_name_plural = 'Sponsorangebote'

    def __str__(self):
        v2_status = self.status if self.status != self.STATUS_LEGACY else (
            'gewählt' if self.gewaehlt else 'offen'
        )
        return (f'{self.club} S{self.saison}/{self.slot} — {self.get_typ_display()} '
                f'({self.sponsor_name}, {v2_status})')


class SponsorContract(models.Model):
    """Aktiver Sponsoring-Vertrag je Slot pro Saison (Spec Kap. 6 V2).

    Entsteht, wenn ein Manager (oder Auto-Pick) ein SponsorOffer annimmt.
    fix_saison = Gesamtfixbetrag der Saison in € (ganze Euros).
    Spieltagsrate = fix_saison / Anzahl_Spieltage (dynamisch aus Spielplan).
    Zieljäger-Bonus und Zuschauerbonus laufen weiterhin über das
    referenzierte offer (V1-Pfad bleibt rückwärtskompatibel).
    """

    saison = models.CharField(max_length=20, verbose_name='Saison')
    club = models.ForeignKey(
        Club, on_delete=models.CASCADE,
        related_name='sponsor_contracts', verbose_name='Verein',
    )
    slot = models.CharField(max_length=20, verbose_name='Slot')
    sponsor = models.ForeignKey(
        'Sponsor', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='contracts',
        verbose_name='Sponsor',
    )
    offer = models.OneToOneField(
        SponsorOffer, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='contract',
        verbose_name='Zugrundeliegendes Angebot',
    )
    fix_saison = models.BigIntegerField(verbose_name='Fixbetrag Saison (€)')
    auto = models.BooleanField(
        default=False, verbose_name='Automatisch gewählt',
    )
    abgelaufen = models.BooleanField(
        default=False, db_index=True, verbose_name='Abgelaufen',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('saison', 'club', 'slot')]
        ordering = ['saison', 'club', 'slot']
        indexes = [
            models.Index(fields=['saison', 'club']),
            models.Index(fields=['club', 'saison', 'abgelaufen']),
        ]
        verbose_name = 'Sponsoring-Vertrag'
        verbose_name_plural = 'Sponsoring-Verträge'

    def __str__(self):
        name = self.sponsor.name if self.sponsor_id else (
            self.offer.sponsor_name if self.offer_id else '—'
        )
        return (f'{self.club} S{self.saison}/{self.slot} — '
                f'{name}: {self.fix_saison:,} €')


class SeasonFinanceState(models.Model):
    """Idempotenz-Guard für die Saison-Finanzjobs (Spec Kap. 15).

    opened_at gesetzt = finance_season_open gelaufen (Snapshot, TV-Töpfe,
    Sponsorangebote); closed_at gesetzt = finance_season_close gelaufen
    (Platz-/Koeffausschüttung, Fallschirme, Koeffizienten-Update).
    report_json hält den Saison-Finanzreport des Close-Laufs.
    """

    saison = models.CharField(max_length=20, unique=True, verbose_name='Saison')
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    report_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-saison']
        verbose_name = 'Saison-Finanzstatus'
        verbose_name_plural = 'Saison-Finanzstatus'

    def __str__(self):
        o = 'offen' if self.opened_at else '—'
        c = 'geschlossen' if self.closed_at else '—'
        return f'Saison {self.saison}: open={o}, close={c}'


class TransferNegotiation(models.Model):
    """Verhandlung Manager → KI-Verein (reaktive Verkäufer, Spec Kap. 9.2/9.3).

    Zustandsmaschine mit max. 3 Manager-Geboten (runde). Die KI antwortet
    sofort: Deal, Gegenforderung oder Absage (+ Cooldown). noise_seed
    speist die deterministische ±STREUUNG je (Verhandlung, Runde) — stabil
    gegen Reload-Exploits, ohne Seed nicht reverse-engineerbar. Der Seed
    und die Schmerzgrenze werden NIE an Clients ausgeliefert.
    """

    STATUS_GEGENFORDERUNG = 'gegenforderung'
    STATUS_DEAL = 'deal'
    STATUS_ABGELEHNT = 'abgelehnt'
    STATUS_CHOICES = [
        (STATUS_GEGENFORDERUNG, 'Gegenforderung — Manager am Zug'),
        (STATUS_DEAL, 'Abgeschlossen'),
        (STATUS_ABGELEHNT, 'Abgelehnt'),
    ]

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='transfer_negotiations',
        verbose_name='Spieler',
    )
    bidder_club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='transfer_bids',
        verbose_name='Bietender Verein',
    )
    seller_club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='transfer_sales',
        verbose_name='Verkaufender Verein',
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, verbose_name='Status',
    )
    runde = models.PositiveSmallIntegerField(default=1, verbose_name='Runde')
    letztes_gebot = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name='Letztes Gebot (€)',
    )
    gegenforderung = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name='Gegenforderung (€)',
    )
    noise_seed = models.CharField(max_length=64, editable=False)
    cooldown_until = models.DateTimeField(
        null=True, blank=True, verbose_name='Cooldown bis',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'bidder_club'],
                condition=models.Q(status='gegenforderung'),
                name='unique_active_transfer_negotiation',
            ),
        ]
        ordering = ['-updated_at']
        verbose_name = 'Transferverhandlung'
        verbose_name_plural = 'Transferverhandlungen'

    def __str__(self):
        return (f'{self.bidder_club} → {self.player} '
                f'(Runde {self.runde}, {self.get_status_display()})')


# ── KI-Käufer Stufe 2 (Spec Kap. 9.3) ─────────────────────────────────────────

class AITransferOffer(models.Model):
    """Aktives KI-Kaufangebot (KI-Käufer Stufe 2, Spec Kap. 9.3).

    bewertung + max_gebot sind interne Rechnungsgrößen und werden NIE an
    Manager-Clients serialisiert — sichtbar sind nur aktuelles_gebot,
    stufe und gueltig_bis. Trockenlauf-Angebote tragen dry_run=True und
    bleiben im Status 'berechnet' (Admin-Review in der Transferzentrale).
    Fenster-Zähler und Talent-Cooldowns hängen an window_id.
    """

    KAUFTYP_BEDARF = 'bedarf'
    KAUFTYP_QUALITAET = 'qualitaet'
    KAUFTYP_TALENT = 'talent'
    KAUFTYP_CHOICES = [
        (KAUFTYP_BEDARF, 'Bedarfskauf'),
        (KAUFTYP_QUALITAET, 'Qualitätskauf'),
        (KAUFTYP_TALENT, 'Talentkauf'),
    ]

    STATUS_BERECHNET = 'berechnet'
    STATUS_VERSENDET = 'versendet'
    STATUS_ABGELEHNT = 'abgelehnt'
    STATUS_DEAL = 'deal'
    STATUS_STORNIERT = 'storniert'
    STATUS_ABGELAUFEN = 'abgelaufen'
    STATUS_CHOICES = [
        (STATUS_BERECHNET, 'Berechnet (Trockenlauf)'),
        (STATUS_VERSENDET, 'Versendet — Manager am Zug'),
        (STATUS_ABGELEHNT, 'Abgelehnt'),
        (STATUS_DEAL, 'Deal'),
        (STATUS_STORNIERT, 'Storniert'),
        (STATUS_ABGELAUFEN, 'Abgelaufen'),
    ]
    OFFENE_STATUS = (STATUS_BERECHNET, STATUS_VERSENDET)

    buyer_club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='ai_buy_offers',
        verbose_name='Bietender KI-Verein',
    )
    seller_club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='ai_incoming_offers',
        verbose_name='Besitzerverein',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ai_transfer_offers',
        verbose_name='Zielspieler',
    )
    kauftyp = models.CharField(
        max_length=12, choices=KAUFTYP_CHOICES, verbose_name='Kauftyp',
    )
    bewertung = models.DecimalField(
        max_digits=15, decimal_places=2, editable=False,
        verbose_name='Interne Bewertung (€)',
    )
    max_gebot = models.DecimalField(
        max_digits=15, decimal_places=2, editable=False,
        verbose_name='Käufer-Maximum (€)',
    )
    aktuelles_gebot = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name='Aktuelles Gebot (€)',
    )
    stufe = models.PositiveSmallIntegerField(
        default=1, verbose_name='Gebotsstufe (1–3)',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_BERECHNET,
        verbose_name='Status',
    )
    dry_run = models.BooleanField(default=False, verbose_name='Trockenlauf')
    window_id = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Fenster-ID',
    )
    noise_seed = models.CharField(max_length=64, editable=False)
    gueltig_bis = models.DateTimeField(
        null=True, blank=True, verbose_name='Gültig bis',
    )
    cooldown_until = models.DateTimeField(
        null=True, blank=True, verbose_name='Cooldown bis',
    )
    luecken_score = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Lückenscore',
    )
    ki_meta = models.JSONField(
        null=True, blank=True,
        verbose_name='KI-Bewertungsdetails',
        help_text=(
            'Nur bei KI-Angeboten gesetzt. Enthält: max_gebot (KI-Schmerzgrenzen-'
            'Maximum), schmerzgrenze, gegenwartswert, zukunftswert (alle in €), '
            'kernspieler (bool).'
        ),
    )
    begruendung = models.TextField(
        blank=True, default='', verbose_name='Begründung (Admin-Review)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['buyer_club', 'player'],
                condition=models.Q(status__in=('berechnet', 'versendet')),
                name='unique_open_ai_transfer_offer',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'window_id']),
            models.Index(fields=['seller_club', 'status']),
        ]
        ordering = ['-updated_at']
        verbose_name = 'KI-Kaufangebot'
        verbose_name_plural = 'KI-Kaufangebote'

    def __str__(self):
        return (f'{self.buyer_club} → {self.player} '
                f'({self.get_kauftyp_display()}, Stufe {self.stufe}, '
                f'{self.get_status_display()})')


class AIBuyerRun(models.Model):
    """Idempotenz-Guard für den KI-Käufer-Prüflauf (Spec Kap. 9.3).

    Spieltagsläufe (trigger='spieltag') sind je Verein+Saison+Spieltag
    eindeutig — Doppel-Hooks sind unschädlich. Trigger-Läufe (eigener
    Verkauf, Monatsupdate, Finanzlagenwechsel, manuell) dürfen zusätzlich
    laufen. report speichert das Prüflauf-Ergebnis fürs Admin-Review.
    """

    TRIGGER_SPIELTAG = 'spieltag'
    TRIGGER_VERKAUF = 'verkauf'
    TRIGGER_MONATSUPDATE = 'monatsupdate'
    TRIGGER_FINANZLAGE = 'finanzlage'
    TRIGGER_MANUELL = 'manuell'
    TRIGGER_CHOICES = [
        (TRIGGER_SPIELTAG, 'Spieltag'),
        (TRIGGER_VERKAUF, 'Eigener Verkauf'),
        (TRIGGER_MONATSUPDATE, 'Monats-Datenupdate'),
        (TRIGGER_FINANZLAGE, 'Finanzlagenwechsel'),
        (TRIGGER_MANUELL, 'Manuell'),
    ]

    club = models.ForeignKey(
        Club, on_delete=models.CASCADE, related_name='ai_buyer_runs',
    )
    saison = models.CharField(max_length=20)
    spieltag = models.PositiveSmallIntegerField()
    trigger = models.CharField(
        max_length=16, choices=TRIGGER_CHOICES, default=TRIGGER_SPIELTAG,
    )
    dry_run = models.BooleanField(default=False)
    window_id = models.CharField(max_length=20, blank=True, default='')
    report = models.JSONField(default=dict, blank=True)
    run_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'saison', 'spieltag'],
                condition=models.Q(trigger='spieltag'),
                name='unique_ai_buyer_matchday_run',
            ),
        ]
        ordering = ['-run_at']
        verbose_name = 'KI-Käufer-Prüflauf'
        verbose_name_plural = 'KI-Käufer-Prüfläufe'

    def __str__(self):
        return (f'{self.club} — Saison {self.saison}, ST {self.spieltag} '
                f'({self.get_trigger_display()}, {self.run_at:%d.%m.%Y %H:%M})')


# ── Zahlungsunfähigkeit & Zwangsversteigerung (Spec Kap. 12.3) ─────────────────

class InsolvencyCase(models.Model):
    """Sportgericht-Vermerk bei Zahlungsunfähigkeit (Spec Kap. 12.3).

    Wird automatisch geöffnet, wenn eine Pflichtbuchung das Konto ins Minus
    bucht (Hook in game.economy.booking → game.economy.insolvency). Der
    Manager hat 7 ECHTE Tage, den Kontostand zu bereinigen (deadline_at);
    kehrt das Konto auf ≥ 0 zurück, schließt der Fall automatisch.
    Andernfalls kann der Admin eine Zwangsversteigerung ausgewählter
    Spieler starten (ForcedAuction) — der Erlös geht an den Verein.
    Keine gesonderte Transfersperre: Aktive Ausgaben scheitern im Minus
    ohnehin an der Deckung (Grundregel 2).
    """

    STATUS_OPEN = 'open'
    STATUS_RESOLVED = 'resolved'
    STATUS_ENFORCED = 'enforced'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Offen'),
        (STATUS_RESOLVED, 'Bereinigt'),
        (STATUS_ENFORCED, 'Zwangsversteigerung eingeleitet'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='insolvency_cases',
        verbose_name='Verein',
    )
    opened_at = models.DateTimeField(auto_now_add=True, verbose_name='Eröffnet am')
    deadline_at = models.DateTimeField(verbose_name='Frist (7 echte Tage)')
    trigger_tx = models.ForeignKey(
        'FinanceTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Auslösende Buchung',
    )
    betrag_bei_eroeffnung = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Kontostand bei Eröffnung (€)',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='Bereinigt am')
    enforced_at = models.DateTimeField(null=True, blank=True, verbose_name='Vollstreckt am')
    reminder_sent = models.BooleanField(
        default=False,
        verbose_name='Erinnerung gesendet',
        help_text='Wird gesetzt, sobald die 1–2-Tage-Erinnerungs-News erzeugt wurde.',
    )

    class Meta:
        ordering = ['-opened_at']
        verbose_name = 'Zahlungsunfähigkeits-Vermerk'
        verbose_name_plural = 'Zahlungsunfähigkeits-Vermerke'
        constraints = [
            models.UniqueConstraint(
                fields=['club'],
                condition=models.Q(status='open'),
                name='unique_open_insolvency_case_per_club',
            ),
        ]

    def __str__(self):
        return (f'Vermerk {self.club} ({self.get_status_display()}, '
                f'eröffnet {self.opened_at:%d.%m.%Y})')


class ForcedAuction(models.Model):
    """Zwangsversteigerung eines Spielers (Spec Kap. 12.3).

    Vom Admin nach Fristablauf eines offenen Zahlungsunfähigkeits-Vermerks
    angesetzt. Anders als reguläre Auktionen (Scouting-Pool, Erlös
    vernichtet) geht der Erlös hier an den Verein: Das Settlement läuft
    über execute_money_transfer (TRANSFER_AUS/TRANSFER_EIN inkl.
    Ausbildungsabgabe). Höchstes Gebot gewinnt; fehlt dem Gewinner beim
    Zuschlag die Deckung, rückt das nächsthöhere Gebot nach.
    """

    STATUS_OPEN = 'open'
    STATUS_SETTLED = 'settled'
    STATUS_UNSOLD = 'unsold'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Laufend'),
        (STATUS_SETTLED, 'Zugeschlagen'),
        (STATUS_UNSOLD, 'Kein Zuschlag'),
        (STATUS_CANCELLED, 'Abgebrochen'),
    ]

    case = models.ForeignKey(
        InsolvencyCase,
        on_delete=models.PROTECT,
        related_name='forced_auctions',
        verbose_name='Vermerk',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.PROTECT,
        related_name='forced_auctions',
    )
    seller_club = models.ForeignKey(
        Club,
        on_delete=models.PROTECT,
        related_name='forced_auctions',
        verbose_name='Schuldner-Verein',
    )
    min_bid = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='Mindestgebot (€)',
    )
    ends_on = models.DateField(verbose_name='Zuschlagstermin')
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )
    winning_bid = models.ForeignKey(
        'ForcedAuctionBid',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Zuschlags-Gebot',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    settled_on = models.DateField(null=True, blank=True, verbose_name='Gewertet am')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Zwangsversteigerung'
        verbose_name_plural = 'Zwangsversteigerungen'
        constraints = [
            models.UniqueConstraint(
                fields=['player'],
                condition=models.Q(status='open'),
                name='unique_open_forced_auction_per_player',
            ),
        ]

    def __str__(self):
        return (f'Zwangsversteigerung {self.player} '
                f'({self.seller_club}, {self.get_status_display()})')


class ForcedAuctionBid(models.Model):
    """Gebot eines Vereins auf eine Zwangsversteigerung.

    Ein Verein hält je Auktion genau ein Gebot (Erhöhen = Update).
    Keine Budget-Reservierung beim Bieten — beim Bieten erfolgt nur eine
    Plausibilitätsprüfung gegen den aktuellen Kontostand; maßgeblich ist
    die erneute Deckungsprüfung beim Zuschlag (aktive Ausgabe,
    Grundregel 2); scheitert sie, rückt das nächsthöhere Gebot nach.
    """

    auction = models.ForeignKey(
        ForcedAuction,
        on_delete=models.CASCADE,
        related_name='bids',
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='forced_auction_bids',
        verbose_name='Bieter',
    )
    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forced_auction_bids',
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='Gebot (€)',
    )
    ki_meta = models.JSONField(
        null=True, blank=True,
        verbose_name='KI-Bewertungsdetails',
        help_text=(
            'Nur bei KI-Geboten gesetzt. Enthält: max_gebot (KI-Schmerzgrenzen-'
            'Maximum), schmerzgrenze, gegenwartswert, zukunftswert (alle in €), '
            'kernspieler (bool), akute_positionen (Liste von Positions-Codes).'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-amount', 'created_at']
        verbose_name = 'Zwangsversteigerungs-Gebot'
        verbose_name_plural = 'Zwangsversteigerungs-Gebote'
        constraints = [
            models.UniqueConstraint(
                fields=['auction', 'club'],
                name='unique_forced_auction_bid_per_club',
            ),
        ]

    def __str__(self):
        return f'{self.club} bietet {self.amount} € ({self.auction})'


# ── Wettersystem ──────────────────────────────────────────────────────────────

class DayWeather(models.Model):
    """Globales Tageswetter — ein Wurf pro Sim-Tag für alle Ligen/Wettbewerbe.

    Der Sim-Tag entspricht dem echten Kalenderdatum (der globale Kalender
    läuft auf date.today(), Fixtures haben scheduled_date). Einmal gewürfeltes
    Wetter ist unveränderlich — es wird nie nachgewürfelt (get_or_create,
    niemals update). Würfellogik: game/weather_service.py.
    """

    WEATHER_NORMAL = 'normal'
    WEATHER_REGEN  = 'regen'
    WEATHER_WIND   = 'wind'
    WEATHER_NEBEL  = 'nebel'
    WEATHER_HITZE  = 'hitze'
    WEATHER_SCHNEE = 'schnee'

    WEATHER_CHOICES = [
        (WEATHER_NORMAL, 'Normal'),
        (WEATHER_REGEN,  'Regen'),
        (WEATHER_WIND,   'Starker Wind'),
        (WEATHER_NEBEL,  'Nebel'),
        (WEATHER_HITZE,  'Hitze'),
        (WEATHER_SCHNEE, 'Schnee/Frost'),
    ]

    sim_day = models.DateField(
        primary_key=True,
        verbose_name='Sim-Tag',
        help_text='Kalenderdatum des Sim-Tags (globaler Kalender).',
    )
    weather_type = models.CharField(
        max_length=10,
        choices=WEATHER_CHOICES,
        verbose_name='Wetterart',
    )
    temperature = models.SmallIntegerField(
        verbose_name='Temperatur (°C)',
        help_text='Reiner Anzeigewert ohne Mechanik.',
    )

    class Meta:
        ordering = ['sim_day']
        verbose_name = 'Tageswetter'
        verbose_name_plural = 'Tageswetter'

    def __str__(self):
        return f'{self.sim_day}: {self.get_weather_type_display()} ({self.temperature} °C)'


# ── Transfersystem v2 (Task #819) ──────────────────────────────────────────
# Modelle liegen in game/transfer_v2/models.py (app_label='game'); hier
# importiert, damit sie im "game"-App-Register erscheinen und Migrationen
# erzeugt werden.
from game.transfer_v2.models import (  # noqa: E402,F401
    TransferListing, TransferBid, ListingPin, SquadOffer,
    DealRequest, DealRequestPlayer, LoanListing, Loan,
    TransferRecord, TransferRecordPlayer, YouthLevyPayment, TransferReport,
    TransferLock, PendingTransfer, ClubPartnership, RumorNews,
    PositionBarometer, SellOnClause, BuybackClause,
)
