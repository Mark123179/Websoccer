"""Acceptance of the supplied v4.1 package, without relaxing source diagnostics."""
import hashlib
import json
from pathlib import Path
import zipfile

from django.test import SimpleTestCase

from game.match_story import narrate


ROOT = Path(__file__).resolve().parents[2]


def text_hash(result):
    return hashlib.sha256(json.dumps(
        [line.text for line in result['lines']], ensure_ascii=False,
        separators=(',', ':'),
    ).encode()).hexdigest()


class NarratorV41Tests(SimpleTestCase):
    def test_approved_reference_texts_timing_counts_and_determinism(self):
        # 114/179 are v4 text hashes; 6 is the explicitly approved v4.1 text.
        references = {
            114: (140, 900, 1, '41ca64578c312c6470610d7201b4cebed119e3c6c8a6789f49d17baf226d68e8'),
            179: (108, 900, 0, 'e30898becf67905a393a084918bfd491197af226cbab3ca32c1f6a6ad0296ed1'),
            6: (123, 1310, 5, 'e460d0b2fa9c1fea2e721dad000079a7b9c07d90155bdfc44a5da08d663c1d84'),
        }
        with zipfile.ZipFile(ROOT / 'attached_assets/0_files_1791022230871.zip') as z:
            for ident, (count, duration, issues, digest) in references.items():
                with self.subTest(match=ident):
                    export = json.loads(z.read(f'match_{ident}.json'))
                    first = narrate(export)
                    second = narrate(export)
                    self.assertEqual(len(first['lines']), count)
                    self.assertEqual(len(first['issues']), issues)
                    self.assertFalse(any('Kernzahlen' in issue for issue in first['issues']))
                    self.assertEqual(text_hash(first), digest)
                    serialize = lambda r: [
                        (line.text, line.offset_s, line.duration_s) for line in r['lines']
                    ]
                    self.assertEqual(serialize(first), serialize(second))
                    self.assertEqual(first['issues'], second['issues'])
                    self.assertAlmostEqual(
                        first['lines'][-1].offset_s + first['lines'][-1].duration_s,
                        duration, places=2,
                    )

    def test_corner_near_misses_cannot_consume_on_target_capacity(self):
        with zipfile.ZipFile(ROOT / 'reports/live-ticker-pruefbelege.zip') as z:
            for ident in (237, 239, 242, 244):
                with self.subTest(match=ident):
                    export = json.loads(z.read(
                        f'consistent-input-cases/match_{ident}.json'))['export']
                    original = json.dumps(export, sort_keys=True)
                    result = narrate(export)
                    self.assertEqual(result['issues'], [])
                    for side in ('home', 'away'):
                        beats = [b for b in result['beats'] if b.team == side]
                        got = sum(
                            b.cls == 'goal' or
                            (b.cls == 'shot' and bool(b.payload.get('on_target')))
                            for b in beats
                        )
                        self.assertEqual(
                            got, export['report_data']['match_stats'][f'{side}_shots_on_target'])
                    self.assertEqual(json.dumps(export, sort_keys=True), original)