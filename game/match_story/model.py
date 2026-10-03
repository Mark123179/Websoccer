from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Player:
    id: int
    name: str
    position: str          # TW, LV, IV, RV, DM, ZM, LM, RM, OM, LF, RF, ST
    team: str              # 'home' | 'away'
    rating: float = 3.5
    on_minute: int = 0
    off_minute: int = 90
    is_sub: bool = False
    load: int = 0          # wie oft schon Hauptakteur im Bindegewebe
    subbed_off: bool = False

    @property
    def group(self) -> str:
        p = self.position
        if p == 'TW': return 'GK'
        if p in ('LV', 'IV', 'RV'): return 'DEF'
        if p in ('DM', 'ZM'): return 'MID'
        if p in ('LM', 'RM', 'OM'): return 'AMID'
        return 'ATT'

    @property
    def side(self) -> str:
        if self.position in ('LV', 'LM', 'LF'): return 'left'
        if self.position in ('RV', 'RM', 'RF'): return 'right'
        return 'center'

    def on_pitch(self, minute: int) -> bool:
        if minute < self.on_minute:
            return False
        if minute < self.off_minute:
            return True
        # Minute == Auswechsel-/Schlussminute: nur zählen, wenn der Spieler bis zum Ende blieb
        return minute == self.off_minute and self.off_minute in (90, 120) and not self.subbed_off

@dataclass
class Line:
    seq: int
    beat: int
    minute: int
    added: int = 0                 # Nachspielzeit-Minute (90+2 -> minute=90, added=2)
    team: Optional[str] = None
    kind: str = ''                 # Beat-Typ (Pool-Schlüssel)
    cls: str = 'flow'              # Planer-Klasse
    visible: bool = True
    actors: dict = field(default_factory=dict)   # rolle -> Player
    text: str = ''
    payload: dict = field(default_factory=dict)  # Rohdaten für 2D
    offset_s: float = 0.0
    duration_s: float = 0.0
    tags: list = field(default_factory=list)

    @property
    def clock(self) -> str:
        return f"{self.minute}+{self.added}'" if self.added else f"{self.minute}'"
