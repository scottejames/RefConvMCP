import pytest

from refconv_mcp import gridref
from refconv_mcp.streetview import bearing


def test_square_origin_su():
    e, n, precision, norm = gridref.parse("SU", centre=False)
    assert (e, n, precision, norm) == (400_000, 100_000, 100_000, "SU")


@pytest.mark.parametrize("ref", ["SU 123 456", "su123456", " SU123 456 "])
def test_six_figure_centre(ref):
    e, n, precision, norm = gridref.parse(ref)
    assert precision == 100
    assert norm == "SU 123 456"
    assert (e, n) == (412_350, 145_650)


def test_ben_nevis():
    # Ben Nevis summit: published as NN 166 712 and 56.79685 N, 5.00360 W.
    # A 6-figure ref is a 100 m square, so allow ~100 m of slack.
    p = gridref.to_wgs84("NN 166 712")
    assert p.lat == pytest.approx(56.79685, abs=1e-3)
    assert p.lon == pytest.approx(-5.00360, abs=1.5e-3)


def test_numeric_input():
    e, n, precision, _ = gridref.parse("412300,145600")
    assert (e, n, precision) == (412_300, 145_600, 1)


@pytest.mark.parametrize("bad", ["XX123456", "SU12345", "hello", "SI123456", "9999999,9999999"])
def test_rejects_bad(bad):
    with pytest.raises(gridref.GridRefError):
        gridref.to_wgs84(bad)


@pytest.mark.parametrize("ref", ["SU 123 456", "NN 166 712", "TQ 300 800", "HU 400 400", "SV 900 100"])
def test_roundtrip(ref):
    p = gridref.to_wgs84(ref)
    assert gridref.from_wgs84(p.lat, p.lon, 6)["grid_ref"] == ref


def test_bearing():
    assert bearing(50, 0, 51, 0) == pytest.approx(0, abs=0.1)
    assert bearing(50, 0, 50, 1) == pytest.approx(90, abs=0.5)
