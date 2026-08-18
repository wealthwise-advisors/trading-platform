"""
Every timeframe the UI offers must be loadable from every file/API provider.

Live Replay hid this: it fetches at a resolution that DIVIDES the selection and
resamples upward itself, so 45m worked there while the Backtest page -- which
asks the provider for "45m" directly -- raised ValueError and surfaced as a 500.
The two paths must agree on what is supported.
"""

import pytest

from src.backtesting.multi_replay import TF_MINUTES

#: What the selector offers, mirroring ALL_TIMEFRAMES in ReplayPage.tsx and the
#: list in ConfigForm.tsx.
UI_TIMEFRAMES = ["1m", "2m", "5m", "10m", "15m", "20m", "25m",
                 "30m", "35m", "45m", "1h"]


def test_every_selectable_timeframe_is_one_the_engine_knows():
    """
    Subset, not equality.

    Equality was right while the two lists were the same list. They are not any
    more: 40m was dropped from the selector but kept in the engine, because a saved
    session or a stored config on 40m still has to load. The invariant that matters
    is one-directional -- nothing may be offered that the engine cannot build.
    """
    missing = sorted(set(UI_TIMEFRAMES) - set(TF_MINUTES))
    assert not missing, (
        f"the selector offers {missing}, which the engine cannot build"
    )


def test_the_engine_may_know_more_than_the_selector_offers():
    """The reverse direction is allowed, and is stated so it is not read as drift."""
    retired = sorted(set(TF_MINUTES) - set(UI_TIMEFRAMES))
    assert retired == ["40m"], (
        f"unexpected engine-only timeframes {retired}; if one was retired from the "
        f"selector deliberately, name it here so the next reader knows it was a choice"
    )


@pytest.mark.parametrize("tf", UI_TIMEFRAMES)
def test_csv_provider_can_express_every_timeframe(tf):
    from src.data.external_csv_provider import _TF_ALIAS

    assert tf in _TF_ALIAS, f"{tf} has no pandas alias; a CSV backtest would fail"


@pytest.mark.parametrize("tf", UI_TIMEFRAMES)
def test_schwab_plans_a_fetch_for_every_timeframe(tf):
    from src.data.schwab_provider import _fetch_plan

    freq_type, freq, resample_to = _fetch_plan(tf)
    assert freq_type == "minute"
    assert freq in (1, 5, 10, 15, 30), f"{tf} would request an unsupported frequency"


@pytest.mark.parametrize("tf", UI_TIMEFRAMES)
def test_schwab_only_ever_resamples_from_a_divisor(tf):
    """
    Aggregating from a non-divisor puts the wrong amount of market time in a
    bar -- a 45m bar built from 30m data would hold 30 or 60 minutes. This is
    the same trap the replay's source-resolution rule exists to avoid.
    """
    from src.data.schwab_provider import _fetch_plan, _TF_MINUTES

    _, freq, resample_to = _fetch_plan(tf)
    if resample_to is None:
        return
    want = _TF_MINUTES[tf]
    assert int(resample_to.replace("min", "")) == want
    assert want % freq == 0, (
        f"{tf} would be aggregated from {freq}m bars, which do not divide it"
    )


def test_an_unknown_timeframe_still_says_so_clearly():
    from src.data.schwab_provider import _fetch_plan

    with pytest.raises(ValueError, match="Unsupported timeframe"):
        _fetch_plan("7m")
