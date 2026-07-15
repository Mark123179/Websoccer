"""Regressions-Tests für _NATIONALITY_CONFEDERATION in competition_assets.py.

Sicherstellt, dass alle pflichtgemäßen englischen Aliasnamen (inkl. Sonderfälle
wie 'Korea Republic', "Côte d'Ivoire", 'DR Congo', 'UAE') den korrekten
Konföderation-Code liefern.  Ein fehlendes Alias-Eintrag im Dict lässt den
jeweiligen subTest fehlschlagen.
"""

from django.test import SimpleTestCase

from game.competition_assets import _NATIONALITY_CONFEDERATION


REQUIRED_ALIASES = [
    # Deutsche Namen, die mit englischen identisch sind
    ('England',             'uefa'),
    ('Scotland',            'uefa'),
    ('Wales',               'uefa'),
    # UEFA-Englisch
    ('Germany',             'uefa'),
    ('France',              'uefa'),
    ('Italy',               'uefa'),
    ('Spain',               'uefa'),
    ('Netherlands',         'uefa'),
    ('Portugal',            'uefa'),
    ('Belgium',             'uefa'),
    ('Austria',             'uefa'),
    ('Switzerland',         'uefa'),
    ('Poland',              'uefa'),
    ('Russia',              'uefa'),
    ('Turkey',              'uefa'),
    ('Greece',              'uefa'),
    ('Czech Republic',      'uefa'),
    ('Czechia',             'uefa'),
    ('Hungary',             'uefa'),
    ('Croatia',             'uefa'),
    ('Serbia',              'uefa'),
    ('Romania',             'uefa'),
    ('Denmark',             'uefa'),
    ('Sweden',              'uefa'),
    ('Norway',              'uefa'),
    ('Finland',             'uefa'),
    ('Slovakia',            'uefa'),
    ('Slovenia',            'uefa'),
    ('Bulgaria',            'uefa'),
    ('Georgia',             'uefa'),
    ('Albania',             'uefa'),
    ('Armenia',             'uefa'),
    ('Azerbaijan',          'uefa'),
    ('Bosnia and Herzegovina', 'uefa'),
    ('Bosnia & Herzegovina', 'uefa'),
    ('Latvia',              'uefa'),
    ('Lithuania',           'uefa'),
    ('Luxembourg',          'uefa'),
    ('Moldova',             'uefa'),
    ('North Macedonia',     'uefa'),
    ('Estonia',             'uefa'),
    ('Iceland',             'uefa'),
    ('Republic of Ireland', 'uefa'),
    ('Northern Ireland',    'uefa'),
    ('Kazakhstan',          'uefa'),
    ('Cyprus',              'uefa'),
    ('United Kingdom',      'uefa'),
    # CONMEBOL
    ('Argentina',           'conmebol'),
    ('Brazil',              'conmebol'),
    ('Colombia',            'conmebol'),
    ('Bolivia',             'conmebol'),
    # CAF
    ('Egypt',               'caf'),
    ('Morocco',             'caf'),
    ('Tunisia',             'caf'),
    ('Algeria',             'caf'),
    ('Cameroon',            'caf'),
    ('South Africa',        'caf'),
    ('Kenya',               'caf'),
    ('Rwanda',              'caf'),
    ('Tanzania',            'caf'),
    ('Zimbabwe',            'caf'),
    ('Zambia',              'caf'),
    ('South Sudan',         'caf'),
    ('Chad',                'caf'),
    # CAF Sonderfälle
    ("Côte d'Ivoire",       'caf'),
    ('Ivory Coast',         'caf'),
    ('DR Congo',            'caf'),
    ('Democratic Republic of Congo', 'caf'),
    ('Congo DR',            'caf'),
    ('Equatorial Guinea',   'caf'),
    ('Ethiopia',            'caf'),
    ('Djibouti',            'caf'),
    ('Gabon',               'caf'),
    ('Cape Verde',          'caf'),
    ('Comoros',             'caf'),
    ('Republic of Congo',   'caf'),
    ('Libya',               'caf'),
    ('Madagascar',          'caf'),
    ('Mauritania',          'caf'),
    ('Mozambique',          'caf'),
    ('Seychelles',          'caf'),
    ('Central African Republic', 'caf'),
    ('São Tomé and Príncipe', 'caf'),
    # AFC
    ('Australia',           'afc'),
    ('Japan',               'afc'),
    ('South Korea',         'afc'),
    # AFC Sonderfälle
    ('Korea Republic',      'afc'),
    ('North Korea',         'afc'),
    ('Korea DPR',           'afc'),
    ('United Arab Emirates', 'afc'),
    ('UAE',                 'afc'),
    ('Saudi Arabia',        'afc'),
    ('Iran',                'afc'),
    ('Iraq',                'afc'),
    ('China PR',            'afc'),
    ('India',               'afc'),
    ('Indonesia',           'afc'),
    ('Bangladesh',          'afc'),
    ('Jordan',              'afc'),
    ('Lebanon',             'afc'),
    ('Palestine',           'afc'),
    ('Philippines',         'afc'),
    ('Singapore',           'afc'),
    ('Syria',               'afc'),
    ('Tajikistan',          'afc'),
    ('Uzbekistan',          'afc'),
    ('Kyrgyzstan',          'afc'),
    ('Mongolia',            'afc'),
    ('Maldives',            'afc'),
    ('Cambodia',            'afc'),
    ('Yemen',               'afc'),
    # CONCACAF
    ('Mexico',              'concacaf'),
    ('Canada',              'concacaf'),
    ('United States',       'concacaf'),
    ('USA',                 'concacaf'),
    ('Jamaica',             'concacaf'),
    ('Cuba',                'concacaf'),
    ('Dominican Republic',  'concacaf'),
    ('Trinidad and Tobago', 'concacaf'),
    ('Antigua and Barbuda', 'concacaf'),
    ('Saint Kitts and Nevis', 'concacaf'),
    ('St. Kitts and Nevis', 'concacaf'),
    ('Saint Lucia',         'concacaf'),
    ('St. Vincent and the Grenadines', 'concacaf'),
    ('Curaçao',             'concacaf'),
    # OFC
    ('New Zealand',         'ofc'),
    ('Fiji',                'ofc'),
    ('Papua New Guinea',    'ofc'),
    ('Solomon Islands',     'ofc'),
    ('Marshall Islands',    'ofc'),
    ('Micronesia',          'ofc'),
]


class NationalityConfederationAliasTests(SimpleTestCase):
    """Jeder Pflicht-Alias muss auf den korrekten Konföderation-Code zeigen."""

    def test_all_required_aliases(self):
        for nationality, expected_conf in REQUIRED_ALIASES:
            with self.subTest(nationality=nationality):
                result = _NATIONALITY_CONFEDERATION.get(nationality)
                self.assertEqual(
                    result,
                    expected_conf,
                    msg=(
                        f"'{nationality}' → got {result!r}, expected {expected_conf!r}. "
                        f"Eintrag fehlt oder ist falsch in _NATIONALITY_CONFEDERATION."
                    ),
                )

    def test_special_case_cote_divoire(self):
        """Côte d'Ivoire muss 'caf' liefern."""
        self.assertEqual(_NATIONALITY_CONFEDERATION.get("Côte d'Ivoire"), 'caf')

    def test_special_case_dr_congo(self):
        """DR Congo muss 'caf' liefern."""
        self.assertEqual(_NATIONALITY_CONFEDERATION.get('DR Congo'), 'caf')

    def test_special_case_korea_republic(self):
        """Korea Republic muss 'afc' liefern."""
        self.assertEqual(_NATIONALITY_CONFEDERATION.get('Korea Republic'), 'afc')

    def test_special_case_uae(self):
        """UAE muss 'afc' liefern."""
        self.assertEqual(_NATIONALITY_CONFEDERATION.get('UAE'), 'afc')

    def test_no_unknown_confederation_codes(self):
        """Alle Werte im Dict müssen gültige Konföderation-Codes sein."""
        valid_codes = {'uefa', 'conmebol', 'caf', 'afc', 'concacaf', 'ofc'}
        invalid = {
            k: v
            for k, v in _NATIONALITY_CONFEDERATION.items()
            if v not in valid_codes
        }
        self.assertFalse(
            invalid,
            msg=f"Unbekannte Konföderation-Codes in _NATIONALITY_CONFEDERATION: {invalid}",
        )
