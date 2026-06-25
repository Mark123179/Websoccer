"""Read-only Simulation-Diagnose (Creator Mode).

Öffentlicher Einstieg: ``build_simulation_diagnostics_report()`` liefert ein
Kontext-Dict mit IMMER genau acht Abschnitts-Keys. Das Paket schreibt nichts
in die Datenbank und importiert KEINE Management Commands zur Laufzeit.
"""
from .report import build_simulation_diagnostics_report, SECTION_KEYS

__all__ = ['build_simulation_diagnostics_report', 'SECTION_KEYS']
