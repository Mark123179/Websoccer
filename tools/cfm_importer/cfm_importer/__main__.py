"""Einstiegspunkt: ``python -m cfm_importer``.

Lädt die Konfiguration, richtet Logging (ohne Secrets) ein und startet die
Ablaufsteuerung. Beendet sich mit einem aussagekräftigen Exit-Code:
    0 = erfolgreich / nichts zu tun
    1 = Lauf abgebrochen (z. B. Blockade, Spielerfehler-Abbruch)
    2 = Konfigurations-/Verbindungs-/Auth-Fehler
"""

import argparse
import sys

from . import __version__
from .config import ConfigError, load_config
from .logging_setup import setup_logging
from .runner import Runner


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='cfm_importer',
        description='Lokaler Vereins-/Spielerimporter (Transfermarkt/FMInside).')
    parser.add_argument('--yes', action='store_true',
                        help='Rückfrage überspringen und Auftrag direkt starten.')
    parser.add_argument('--version', action='version',
                        version=f'CFM-Importer {__version__}')
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except ConfigError as exc:
        # Logging ist hier noch nicht konfiguriert — direkt ausgeben.
        print(f'[KONFIGURATIONSFEHLER] {exc}', file=sys.stderr)
        return 2

    logger = setup_logging(secrets=[config.api_token])
    logger.info('CFM-Importer %s gestartet.', __version__)

    try:
        return Runner(config, logger).run(auto_yes=args.yes)
    except KeyboardInterrupt:
        logger.warning('Abbruch durch Benutzer (Strg+C).')
        return 1


if __name__ == '__main__':
    sys.exit(main())
