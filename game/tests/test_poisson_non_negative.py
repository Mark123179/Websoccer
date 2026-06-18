"""Unit-Tests für _poisson — stellt sicher dass 0.0 und Grenzwerte nie negativ zurückgeben."""
from game.match_engine import _poisson


def test_poisson_zero_returns_zero():
    assert _poisson(0.0) == 0


def test_poisson_zero_int_returns_zero():
    assert _poisson(0) == 0


def test_poisson_negative_returns_zero():
    assert _poisson(-1.0) == 0
    assert _poisson(-0.5) == 0


def test_poisson_small_positive_non_negative():
    for lam in [0.001, 0.01, 0.1]:
        for _ in range(200):
            assert _poisson(lam) >= 0, f"_poisson({lam}) returned negative value"


def test_poisson_normal_values_non_negative():
    for lam in [0.5, 1.0, 2.0, 5.0]:
        for _ in range(200):
            assert _poisson(lam) >= 0, f"_poisson({lam}) returned negative value"
