"""Kalibrierungs-Report (Finanzsystem Phase 7, Spec Kap. 16).

Dokumentierter Kalibrierungs-Durchlauf: stellt die Live-Kennzahlen aus
dem Ledger gegen die Zielkorridore der Spec und benennt je Abweichung
den zuständigen EconomyParameter-Regler. Reine Anzeige — Anpassungen
bleiben bewusste Admin-Entscheidungen (Creator → Kalibrierung).
"""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('Kalibrierungs-Report: Live-Kennzahlen vs. Zielkorridore '
            '(Spec Kap. 16), mit Regler-Verweisen.')

    def add_arguments(self, parser):
        parser.add_argument('--saison', default=None,
                            help='Sim-Saison (Standard: aktuelle Saison).')
        parser.add_argument('--json', action='store_true', dest='as_json',
                            help='Report als JSON ausgeben.')

    def handle(self, *args, **opts):
        from game.economy import kalibrierung

        report = kalibrierung.kalibrierungs_report(opts['saison'])

        if opts['as_json']:
            self.stdout.write(json.dumps(report, indent=2, default=str,
                                         ensure_ascii=False))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Kalibrierungs-Report — Saison {report['saison']} "
            f"(Spec Kap. 16)"))
        self.stdout.write(
            f"Status: {report['alarm_count']} Alarm · "
            f"{report['warn_count']} außerhalb Korridor · "
            f"{report['nicht_messbar_count']} nicht messbar\n")

        style_map = {
            kalibrierung.STATUS_OK: self.style.SUCCESS,
            kalibrierung.STATUS_WARN: self.style.WARNING,
            kalibrierung.STATUS_ALARM: self.style.ERROR,
            kalibrierung.STATUS_NICHT_MESSBAR: self.style.NOTICE,
        }

        def _pct(v, signed=True):
            if v is None:
                return '—'
            fmt = f'{v * 100:+.1f} %' if signed else f'{v * 100:.1f} %'
            return fmt.replace('.', ',')

        for k in report['kennzahlen']:
            mark = style_map[k['status']](
                f"[{kalibrierung.STATUS_LABELS[k['status']].upper()}]")
            self.stdout.write(f"{mark} {k['titel']}")
            self.stdout.write(f"    Korridor: {k['korridor']}")

            if k['id'] == 'geldmenge':
                self.stdout.write(
                    f"    Ist: Wachstum {_pct(k['wachstum'])} · "
                    f"MW-Drift {_pct(k['mw_drift'])}")
            elif k['id'] == 'abloese_mw':
                med = (f"{k['median']:.2f}".replace('.', ',')
                       if k['median'] is not None else '—')
                self.stdout.write(
                    f"    Ist: Median {med} ({k['count']} Transfers)")
            elif k['id'] == 'gehaltslasten':
                self.stdout.write(
                    f"    Ist: klein {_pct(k['quote_klein'], signed=False)} · "
                    f"top {_pct(k['quote_top'], signed=False)} "
                    f"({k['clubs_gesamt']} Vereine, Gruppen je "
                    f"{k['gruppen_groesse']})"
                    + (' — anteilig, laufende Saison' if k['laufend'] else ''))
            elif k['id'] == 'zuschauer':
                med = (f"{k['median']:.2f}".replace('.', ',')
                       if k['median'] is not None else '—')
                ausl = (f"{k['auslastung_median']:.1f} %".replace('.', ',')
                        if k['auslastung_median'] is not None else '—')
                self.stdout.write(
                    f"    Ist: Median-Ratio {med} · Auslastung {ausl} "
                    f"({k['spiele']} Heimspiele)")
                for a in k['ausreisser']:
                    self.stdout.write(
                        f"      Ausreißer: {a['club']} — Ratio "
                        f"{a['ratio']:.2f} ({a['attendance']} Zuschauer)")
            elif k['id'] == 'ki_anteil':
                self.stdout.write(
                    f"    Ist: {k['anteil']:.0%} von "
                    f"{float(k['gesamt_volumen']):,.0f} € Transfervolumen "
                    f"(Limit {k['limit']:.0%})".replace(',', '.'))

            if k['hinweis']:
                self.stdout.write(f"    Hinweis: {k['hinweis']}")
            self.stdout.write(f"    Regler: {', '.join(k['regler'])}\n")
