// The single Plotly build the app ships.
//
// `react-plotly.js`'s default export pulls in `plotly.js/dist/plotly` -- the
// full 10.7 MB bundle, which carries every trace type including the map ones,
// and with them a compiled-in copy of maplibre-gl. That copy is what
// GHSA-jrc7-96c5-q579 (critical, XSS sanitiser bypass) lives in, and no
// version bump of the `maplibre-gl` package can reach it: it is baked into
// plotly's dist, not resolved from node_modules.
//
// This app draws three trace types -- candlestick, scatter and bar -- all of
// which are in `plotly-finance`, together with the rangeslider, shapes and
// annotations the charts rely on. That bundle contains no maplibre code at
// all (only its CSS class names, which come from plotly's stylesheet), so
// swapping to it removes the vulnerable code from what users download rather
// than merely quieting the alert about it.
//
// Adding a map, 3D, or WebGL (`scattergl`) trace means changing this import.
// The build will not warn you -- Plotly reports an unknown trace type at run
// time, on the chart, as "Invalid value ... type".
import Plotly from "plotly.js/dist/plotly-finance"
import createPlotlyComponent from "react-plotly.js/factory"

const Plot = createPlotlyComponent(Plotly)

export default Plot
