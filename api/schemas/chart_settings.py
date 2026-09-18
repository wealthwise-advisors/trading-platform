"""The live chart's display settings, as the Export Report request carries them.

The dashboard chart (web/src/components/charts/CandlestickChart.tsx) and the
exported HTML report (api/report/report.py) are drawn by separate code. The
report used to draw fixed defaults of its own, so someone who had switched MFI
off or recoloured the POC exported a report that disagreed with the chart in
front of them. The chart now sends its current settings with the download, in
this shape, and the report draws with them.

Field names are the web's own camelCase, so the JSON the browser sends is
validated as it arrives. Defaults are the chart's factory defaults: a request
with no settings gets the report the chart shows before anything is changed.
tests/fixtures/chart_settings_factory.json pins those defaults, and both this
model and web/src/lib/chartExportSettings.ts are tested against that one file.

Anything the chart could not have sent -- an unknown field, a colour that is
not six-digit hex, a draw style the dialog does not offer -- is refused rather
than quietly replaced, because a report drawn with a guessed setting is exactly
the disagreement this exists to prevent.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

_CONFIG = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

#: Row order, top to bottom -- web/src/lib/oscillatorStudies.ts's OSC_ORDER.
OSC_ORDER = ("rsi2", "stochrsi", "rsi13", "mfi")


class OscillatorToggles(BaseModel):
    """Which oscillator rows are switched on under the price chart."""
    model_config = _CONFIG

    rsi2: bool = True
    stochrsi: bool = True
    rsi13: bool = True
    mfi: bool = False


class PlotStyle(BaseModel):
    """One Volume Profile plot tab: web/src/lib/vpPlotStyles.ts's PlotStyle."""
    model_config = _CONFIG

    show: bool
    values: Literal["numerical"] = "numerical"
    draw_as: Literal["line", "points", "squares", "triangles"] = "line"
    style: Literal["solid", "longdash", "dash", "dot"]
    width: Literal[1, 2, 3, 4, 5] = 1
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    bubble: bool = True
    title: bool = True


def _plot(show: bool, style: str, color: str) -> PlotStyle:
    return PlotStyle(show=show, style=style, color=color)


class PlotStyles(BaseModel):
    model_config = _CONFIG

    poc: PlotStyle = Field(default_factory=lambda: _plot(True, "solid", "#38bdf8"))
    profile_high: PlotStyle = Field(default_factory=lambda: _plot(False, "dot", "#94a3b8"))
    profile_low: PlotStyle = Field(default_factory=lambda: _plot(False, "dot", "#94a3b8"))
    vah: PlotStyle = Field(default_factory=lambda: _plot(True, "dash", "#7dd3fc"))
    val: PlotStyle = Field(default_factory=lambda: _plot(True, "dash", "#7dd3fc"))

    @model_validator(mode="after")
    def _value_area_is_one_thing(self) -> "PlotStyles":
        # VAHigh and VALow are the two edges of the value area and show together
        # -- the same reconciliation normalizePlotStyles() does on the web.
        on = self.vah.show or self.val.show
        self.vah.show = on
        self.val.show = on
        return self


class VolumeProfileSettings(BaseModel):
    """The Volume Profile toggle and its dialog, as CandlestickChart.tsx holds them.

    The bounds are the widest values the chart itself can draw with, not the
    dialog's spinner steps: a typed-in value outside the steps still draws.
    """
    model_config = _CONFIG

    on: bool = True
    bins: int = Field(48, ge=1, le=2000)
    value_area: float = Field(70, ge=0, le=100)
    opacity: float = Field(50, ge=0, le=100)
    row_mode: Literal["AUTOMATIC", "MANUAL"] = "AUTOMATIC"
    row_height: float = Field(1, gt=0)
    time_per: Literal["CHART", "DAY", "WEEK"] = "CHART"
    multiplier: float = Field(1, ge=1)
    max_profiles: int = Field(1000, ge=1)
    on_expansion: bool = True
    plots: PlotStyles = Field(default_factory=PlotStyles)
    show_study: bool = True
    show_plot_names: bool = True
    show_input_names: bool = True
    left_axis: bool = False


class ChartSettings(BaseModel):
    model_config = _CONFIG

    oscillators: OscillatorToggles = Field(default_factory=OscillatorToggles)
    volume_profile: VolumeProfileSettings = Field(default_factory=VolumeProfileSettings)
