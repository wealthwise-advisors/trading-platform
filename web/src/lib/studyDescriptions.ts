// What each study is, in one or two plain sentences, shown at the top of its page in
// the settings window (user, 2026-11-27: "Economic events -- I don't know why it is
// there"). Keyed by the study's key in the Studies and Market Grid settings trees.
export const STUDY_DESCRIPTIONS: Record<string, string> = {
  range: "How much history each bar interval loads: 1m and 5m load 2 days, 1h loads 25 days, and so on. Pick an interval to switch the chart to it.",
  events: "Marks official US economic releases (FOMC, CPI, PCE, GDP, jobs reports) as dotted lines at their release time, so a sudden move can be read against the news behind it. Amber is high impact, sky is medium.",
  vwap: "Volume-Weighted Average Price: the average price paid in the session, weighted by volume, restarting at the session open. The bands are standard deviations around it.",
  vp: "Volume Profile: how much volume traded at each price. POC is the busiest price, VA High and VA Low bound the value area (70% of volume by default).",
  count: "Sir's swing count: 10 Leg swings (A, B, C), the 3 Leg moves inside them (1, 2, 3) and the 1 Leg moves inside those (i, ii, iii), with HH / HL / LH / LL tags.",
  levels: "Each swing's Volume Breakeven, 50% Equilibrium and Buyer Control, shown in the Data Window when the cursor is on the swing.",
  rsi: "Relative Strength Index, two lengths: RSI(2) for very short-term extremes, RSI(13) for the trend's momentum.",
  rsi2: "RSI over 2 bars, Wilder's smoothing. Past overbought it is drawn red, past oversold green.",
  rsi13: "RSI over 13 bars, Wilder's smoothing, with its own overbought / oversold lines.",
  stochrsi: "Stochastic RSI: where RSI sits within its own recent range. FullK is the fast line, FullD its average.",
  mfi: "Money Flow Index: RSI that weighs each bar by its volume, from the typical price (H+L+C)/3. Needs volume.",
  vol: "Volume bars with their moving average, and each bar's buyers and sellers estimated from where the candle closed in its range.",
  flow: "Sir's order-flow studies: Volume Delta, Cumulative Volume Delta and CVD Divergence.",
  delta: "Buyers minus sellers on each candle, estimated from where it closed in its range (Schwab gives bars, not bid / ask). Past the filter, a bar is drawn in the strong colour.",
  cvd: "Cumulative Volume Delta: the running total of Volume Delta, restarting at 6 PM, midnight and 8 AM Eastern.",
  div: "Where price and CVD disagree between two swing highs or two swing lows. Strength is the CVD change divided by VolumeAvg; weak ones are skipped.",
  // Market Grid
  volume: "Volume, its average over the VolumeAvg length, and buyers / sellers for each timeframe's newest bar.",
  swing: "Each timeframe's newest swing and its levels, counted with the same deviations as the chart.",
  gdelta: "The newest bar's Volume Delta and Delta %, coloured past the filter.",
  gcvd: "The running CVD for each timeframe, restarting at 6 PM, midnight and 8 AM Eastern.",
  gdiv: "The newest CVD divergence between each timeframe's recent 10 Leg swing points.",
}
