"""The Export Data page's Excel file, laid out and coloured like the app.

Four sheets: the bars with every study ("Price & Studies"), the swing points, the
Volume Profile levels ("Levels") and a key. The dark theme, the fonts and every
colour are the app's own -- each constant names the file it was read from -- so a
column looks in Excel the way its line looks on the chart. Sheet names avoid the
app's page names (Market Grid, Volume Profile, Volume Average): sharing them
confused readers of the earlier workbooks.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ── the app's dark theme (web/src/index.css) ─────────────────────────────────
TITLE_BG, BG, ZEBRA, HEAD_BG = "0B0F19", "0F1420", "141A28", "161C2B"
HEAD, TEXT, DIM, LILAC, GOLD = "C7CBE0", "E6E9F0", "8B93A7", "C9B8FF", "F5CF7A"
ARIAL, MONO = "Arial", "Consolas"

# ── the chart's colours (CandlestickChart.tsx, vwapLevels.ts, volumeAverage.ts) ─
CANDLE_UP, CANDLE_DOWN = "2DD4BF", "F0576B"                    # GREEN / RED
VOL_UP, VOL_DOWN, VOL_FLAT = "00C853", "FF6B6B", "22D3EE"      # volumeBarColors
VOLUME_AVG = "E040FB"                                          # VOLUME_AVG_COLOR
BUYERS, SELLERS = "26A69A", "EF5350"
EMA9, EMA20, EMA50 = "FFAB40", "A3E635", "C4B5FD"
VWAP = "E879F9"                                                # vwapStyle.vwap
BB_BASIS, BB_BAND = "6B7FA8", "8B9DC3"
CVD = "22D3EE"                                                 # CandlestickChart.tsx CVD_LINE
#: Volume Delta bars (CandlestickChart.tsx): green / red, blue / orange past ±60 %.
DELTA_UP, DELTA_DOWN, DELTA_BIG_UP, DELTA_BIG_DOWN = "00C853", "FF5252", "2979FF", "FF9100"
OSC_LINE, STOCH_K, STOCH_D, MFI_LINE = "FFFFFF", "FF6B6B", "E040FB", "E0A800"
ZONE_ABOVE, ZONE_BELOW = "FF5252", "00C853"                    # past overbought / oversold
HIGH_TAG, LOW_TAG = "22C55E", "EF4444"                         # HH/LH and HL/LL tags
#: Band colours per level (vwapLevels.ts LEVEL_COLORS; 2 uses the chart style's own pair).
BAND_COLORS = {0.5: ("D8C9A0", "E0A800"), 1: ("22D3EE", "22D3EE"), 1.5: ("D8C9A0", "D8C9A0"),
               2: ("FDE047", "F472B6")}
OTHER_BAND = ("CBD5E1", "94A3B8")
#: Overbought / oversold, from web/src/lib/oscillatorStudies.ts.
OSC_LEVELS = {"RSI(2)": (94, 5), "FullK": (80, 20), "FullD": (80, 20), "RSI(13)": (55, 45), "MFI": (80, 20)}

PRICE_FMT, OSC_FMT, VOL_FMT, PCT_FMT = "#,##0.00", "0.00", "#,##0", '0.0"%"'
WHEN = "ddd dd-mmm-yyyy  h:mm AM/PM"


@dataclass
class ExportMeta:
    symbol: str
    timeframe: str
    start: date
    end: date
    source: str
    zone: str
    session: str
    dev_3: float
    dev_10: float


def _fill(c: str) -> PatternFill:
    return PatternFill("solid", start_color=c, end_color=c)


def _column_style(name: str, vwap_levels) -> tuple[str, str]:
    """(text colour, number format) for a column of the bars sheet."""
    if name in ("Open", "High", "Low", "Close"):
        return TEXT, PRICE_FMT
    fixed = {"Volume": (TEXT, VOL_FMT), "VolumeAvg (20)": (VOLUME_AVG, "#,##0.0"), "Buyers %": (TEXT, PCT_FMT),
             "Buyers": (BUYERS, VOL_FMT), "Sellers": (SELLERS, VOL_FMT), "EMA 9": (EMA9, PRICE_FMT),
             "EMA 20": (EMA20, PRICE_FMT), "EMA 50": (EMA50, PRICE_FMT), "VWAP": (VWAP, PRICE_FMT),
             "BB 20 2 basis": (BB_BASIS, PRICE_FMT), "BB Upper": (BB_BAND, PRICE_FMT),
             "BB Lower": (BB_BAND, PRICE_FMT), "RSI(2)": (OSC_LINE, OSC_FMT), "FullK": (STOCH_K, OSC_FMT),
             "FullD": (STOCH_D, OSC_FMT), "RSI(13)": (OSC_LINE, OSC_FMT), "MFI": (MFI_LINE, OSC_FMT),
             "Volume Delta": (TEXT, '+#,##0;-#,##0;0'), "Delta %": (TEXT, '+0.0"%";-0.0"%";0.0"%"'),
             "CVD": (CVD, '+#,##0;-#,##0;0')}
    if name in fixed:
        return fixed[name]
    for lv in vwap_levels:
        up, dn = BAND_COLORS.get(lv, OTHER_BAND)
        if name == f"VWAP Upper +{lv:.1f}σ":
            return up, PRICE_FMT
        if name == f"VWAP Lower -{lv:.1f}σ":
            return dn, PRICE_FMT
    return TEXT, "General"                                    # swing columns


def _title(ws, title: str, line: str, ncols: int) -> None:
    for r in (1, 2):
        for c in range(1, ncols + 1):
            ws.cell(row=r, column=c).fill = _fill(TITLE_BG)
    a = ws.cell(row=1, column=1, value=title)
    a.font, a.alignment = Font(name=ARIAL, size=16, bold=True, color=LILAC), Alignment(vertical="center", indent=1)
    b = ws.cell(row=2, column=1, value=line)
    b.font, b.alignment = Font(name=ARIAL, size=10.5, bold=True, color=GOLD), Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height, ws.row_dimensions[2].height = 26, 18


def _header(ws, row: int, names: list[str], colors: list[str]) -> None:
    for i, (name, color) in enumerate(zip(names, colors), start=1):
        c = ws.cell(row=row, column=i, value=name)
        c.font = Font(name=ARIAL, size=9.5, bold=True, color=color)
        c.fill, c.alignment = _fill(HEAD_BG), Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(bottom=Side(style="medium", color="3B4560"))
    ws.row_dimensions[row].height = 30


def _body(ws, first: int, rows: list[list], fonts: list[Font], fmts: list[str]) -> None:
    for k, values in enumerate(rows):
        shade = _fill(ZEBRA if k % 2 else BG)
        for j, v in enumerate(values, start=1):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = None
            c = ws.cell(row=first + k, column=j, value=v)
            c.font, c.fill, c.number_format = fonts[j - 1], shade, fmts[j - 1]
            # Short labels (swing letter, leg number) centred, so they don't sit against the next column.
            align = ("center" if len(v) <= 4 else "left") if isinstance(v, str) else "right"
            c.alignment = Alignment(horizontal=align, vertical="center")


def _widths(ws, widths: list[float]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _bars_sheet(ws, table: pd.DataFrame, meta: ExportMeta, vwap_levels) -> None:
    names = [table.index.name] + list(table.columns)
    styles = [(TEXT, WHEN)] + [_column_style(n, vwap_levels) for n in table.columns]
    _title(ws, f"{meta.symbol} {meta.timeframe}  ·  {meta.start:%d %b %Y} to {meta.end:%d %b %Y}",
           f"Every study on the chart, one row per candle  ·  Times in {meta.zone}  ·  Session {meta.session}  ·  "
           f"Source {meta.source}", len(names))
    _header(ws, 4, names, [HEAD] + [color for color, _ in styles[1:]])
    rows = [[ts.to_pydatetime()] + list(r) for ts, r in zip(table.index, table.itertuples(index=False))]
    fonts = [Font(name=MONO, size=10, color=c, bold=n in ("Close", "Swing", "10 Leg")) for n, (c, _) in
             zip(names, styles)]
    _body(ws, 5, rows, fonts, [f for _, f in styles])
    last = 4 + len(rows)

    col = {n: get_column_letter(i) for i, n in enumerate(names, start=1)}
    # Close in the candle's colour, Volume in its bar's colour (volumeBarColors: against the previous close).
    closes, opens = table["Close"].tolist(), table["Open"].tolist()
    for k in range(len(rows)):
        r = 5 + k
        ws[f"{col['Close']}{r}"].font = Font(name=MONO, size=10, bold=True,
                                             color=CANDLE_UP if closes[k] >= opens[k] else CANDLE_DOWN)
        if "Volume" in col:
            vc = VOL_FLAT if k == 0 or closes[k] == closes[k - 1] else VOL_UP if closes[k] > closes[k - 1] else VOL_DOWN
            ws[f"{col['Volume']}{r}"].font = Font(name=MONO, size=10, color=vc)
        if "Volume Delta" in col:
            # The chart's Delta bar colours: green / red, blue / orange past ±60 %.
            d, p = table["Volume Delta"].iloc[k], table["Delta %"].iloc[k]
            if pd.notna(d):
                dc = (DELTA_BIG_UP if p > 60 else DELTA_UP) if d >= 0 else (DELTA_BIG_DOWN if p < -60 else DELTA_DOWN)
                for c in ("Volume Delta", "Delta %"):
                    ws[f"{col[c]}{r}"].font = Font(name=MONO, size=10, bold=abs(p) > 60, color=dc)
        for tag in ("10 Leg Tag", "3 Leg Tag"):
            v = ws[f"{col[tag]}{r}"].value
            if v in ("HH", "LH", "H", "EH"):
                ws[f"{col[tag]}{r}"].fill = _fill(HIGH_TAG)
            elif v in ("HL", "LL", "L", "EL"):
                ws[f"{col[tag]}{r}"].fill = _fill(LOW_TAG)
            if v:
                ws[f"{col[tag]}{r}"].font = Font(name=ARIAL, size=10, bold=True, color="FFFFFF")
                ws[f"{col[tag]}{r}"].alignment = Alignment(horizontal="center", vertical="center")
    # The chart's zone colours: red at or past overbought, green at or past oversold.
    for name, (ob, os_) in OSC_LEVELS.items():
        if name in col and rows:
            ref = f"{col[name]}5:{col[name]}{last}"
            ws.conditional_formatting.add(ref, CellIsRule(operator="greaterThanOrEqual", formula=[str(ob)],
                                                          font=Font(color=ZONE_ABOVE, bold=True)))
            ws.conditional_formatting.add(ref, CellIsRule(operator="lessThanOrEqual", formula=[str(os_)],
                                                          font=Font(color=ZONE_BELOW, bold=True)))
    # Room for the header and its filter arrow; VWAP band names wrap onto two lines instead.
    _widths(ws, [27] + [12 if n.startswith("VWAP ") else max(10.5, len(n) + 4) for n in names[1:]])
    ws.freeze_panes = "B5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(names))}{max(last, 5)}"


def _list_sheet(ws, df: pd.DataFrame, title: str, line: str, fmts: dict[str, str], widths: list[float]) -> None:
    names = list(df.columns)
    _title(ws, title, line, len(names))
    _header(ws, 4, names, [HEAD] * len(names))
    fonts = [Font(name=MONO, size=10, color=TEXT, bold=n in ("Number", "POC")) for n in names]
    rows = [[v.to_pydatetime() if isinstance(v, pd.Timestamp) else v for v in r] for r in df.itertuples(index=False)]
    _body(ws, 5, rows, fonts, [fmts.get(n, "General") for n in names])
    if "High/Low" in names:                                    # a high's row reads green, a low's red
        hl, tag = names.index("High/Low") + 1, names.index("Tag") + 1
        for k, r in enumerate(rows):
            color = HIGH_TAG if r[hl - 1] == "High" else LOW_TAG
            ws.cell(row=5 + k, column=hl).font = Font(name=MONO, size=10, bold=True, color=color)
            t = ws.cell(row=5 + k, column=tag)
            t.fill, t.font = _fill(color), Font(name=ARIAL, size=10, bold=True, color="FFFFFF")
            t.alignment = Alignment(horizontal="center", vertical="center")
    _widths(ws, widths)
    ws.freeze_panes = "A5"


def _key_sheet(ws, meta: ExportMeta, columns: list[str], vwap_levels) -> None:
    about = {
        "Open / High / Low / Close": "The candle. Close is green when it closed at or above its open, red below.",
        "Volume": "Contracts traded. Coloured like the chart's volume bars: green above the last close, red below.",
        "VolumeAvg (20)": "Average volume of the last 20 candles.",
        "Buyers % / Buyers / Sellers": "The candle's volume split by where it closed in its range (sir's formula).",
        "EMA 9 / 20 / 50": "Exponential moving averages of the close.",
        "VWAP": "Volume-weighted average price, starting again at each session open.",
        "VWAP Upper / Lower": "VWAP plus / minus that many standard deviations; every level the chart offers.",
        "BB 20 2 basis / Upper / Lower": "Bollinger Bands: 20-candle average with a 2 standard deviation band.",
        "RSI(2), RSI(13)": "RSI, Wilder's. Red at or above overbought (94 / 55), green at or below oversold (5 / 45).",
        "FullK / FullD": "StochRSI(14, 14, 3, 1). Red at or above 80, green at or below 20.",
        "MFI": "Money Flow Index(9), as thinkorswim. Red at or above 80, green at or below 20.",
        "Volume Delta / Delta %": "Buyers minus sellers on the candle (estimated from where it closed in its range: "
                                  "Schwab gives no bid/ask volume), and that as % of its volume. Green / red; "
                                  "blue / orange past ±60 %.",
        "CVD": "Cumulative Volume Delta: the running total of Volume Delta, restarting at 6 PM, midnight and 8 AM ET.",
        "Swing": "The swing letter (A, B, C ...) on the candle of each big swing point.",
        "10 Leg / 10 Leg Tag": "Big swing number (starts again at 1 each swing) and its tag: HH / LH on green, HL / LL on red.",
        "3 Leg / 3 Leg Tag": "Small swing numeral (i, ii, iii ...), counted inside each big move, and its tag.",
        "Swing Points sheet": "Every swing point in time order, with its price.",
        "Levels sheet": "Volume Profile POC, VAHigh, VALow, ProfileHigh, ProfileLow: whole range and each day.",
    }
    settings = [("Symbol / timeframe", f"{meta.symbol} {meta.timeframe}"),
                ("Dates", f"{meta.start:%d %b %Y} to {meta.end:%d %b %Y}"),
                ("Times shown in", meta.zone), ("Session", meta.session), ("Data source", meta.source),
                ("10 Leg deviation", f"{meta.dev_10 * 100:.2f}%"), ("3 Leg deviation", f"{meta.dev_3 * 100:.2f}%"),
                ("VWAP levels", ", ".join(f"{lv:g}" for lv in vwap_levels))]
    _title(ws, "Key", "What each column is, and the settings this file was made with", 2)
    _header(ws, 4, ["Setting", "Value"], [HEAD, HEAD])
    _body(ws, 5, [list(s) for s in settings], [Font(name=ARIAL, size=10, bold=True, color=GOLD),
                                               Font(name=ARIAL, size=10, color=TEXT)], ["General"] * 2)
    r = 6 + len(settings)
    _header(ws, r, ["Column", "What it is"], [HEAD, HEAD])
    _body(ws, r + 1, [[k, v] for k, v in about.items()],
          [Font(name=ARIAL, size=10, bold=True, color=LILAC), Font(name=ARIAL, size=10, color=TEXT)],
          ["General"] * 2)
    _widths(ws, [30, 110])


def workbook_bytes(table: pd.DataFrame, swings: pd.DataFrame, levels: pd.DataFrame,
                   meta: ExportMeta, vwap_levels) -> bytes:
    wb = Workbook()
    bars = wb.active
    bars.title = "Price & Studies"
    _bars_sheet(bars, table, meta, vwap_levels)
    sw = swings.rename(columns={"Time": f"Time ({meta.zone})"})
    _list_sheet(wb.create_sheet("Swing Points"), sw, f"Swing points  ·  {meta.symbol} {meta.timeframe}",
                f"10 Leg (big) and 3 Leg (small) points in time order  ·  Times in {meta.zone}",
                {sw.columns[0]: WHEN, "Price": PRICE_FMT}, [27, 8, 9, 9, 10, 12, 8])
    lv = levels.rename(columns={"From": f"From ({meta.zone})", "To": f"To ({meta.zone})"})
    _list_sheet(wb.create_sheet("Levels"), lv, f"Volume Profile levels  ·  {meta.symbol} {meta.timeframe}",
                "48 rows, 70% value area (the chart's defaults)  ·  whole range, then each day",
                {lv.columns[1]: WHEN, lv.columns[2]: WHEN, **{c: PRICE_FMT for c in lv.columns[3:]}},
                [18, 27, 27, 12, 12, 12, 13, 13])
    _key_sheet(wb.create_sheet("Key"), meta, list(table.columns), vwap_levels)
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.tabColor = LILAC if ws.title == "Price & Studies" else "3B4560"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
