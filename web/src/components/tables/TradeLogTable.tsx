import type { TradeRecord } from "@/lib/types"

function fmtTime(iso: string | null) {
  if (!iso) return "—"
  return iso.replace("T", " ").slice(0, 16)
}

export function TradeLogTable({ trades }: { trades: TradeRecord[] }) {
  if (!trades.length) {
    return <p className="text-muted-foreground p-4">No completed trades in this period.</p>
  }

  const avgQuality = trades
    .filter((t) => t.quality_score != null)
    .reduce((acc, t, _, arr) => acc + (t.quality_score ?? 0) / arr.length, 0)

  return (
    <div>
      {avgQuality > 0 && (
        <p className="text-xs text-muted-foreground mb-2 px-1">
          Quality Score (0-100) reflects the entry SETUP — trend alignment, momentum, volume, and
          proximity to a support/resistance zone — not the trade's outcome. Average: {avgQuality.toFixed(0)}/100
        </p>
      )}
      <div className="overflow-x-auto rounded-lg border border-white/6">
        <table className="w-full text-sm">
          <thead className="bg-[#0e1424] text-muted-foreground">
            <tr>
              <th className="text-left p-2 font-medium">#</th>
              <th className="text-left p-2 font-medium">Direction</th>
              <th className="text-left p-2 font-medium">Entry Time</th>
              <th className="text-right p-2 font-medium">Entry $</th>
              <th className="text-left p-2 font-medium">Exit Time</th>
              <th className="text-right p-2 font-medium">Exit $</th>
              <th className="text-right p-2 font-medium">Duration</th>
              <th className="text-right p-2 font-medium">P&L</th>
              <th className="text-right p-2 font-medium">Quality</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => (
              <tr key={i} className="border-t border-white/6"
                  style={{ background: t.pnl >= 0 ? "rgba(27,67,50,0.35)" : "rgba(74,16,16,0.35)" }}>
                <td className="p-2">{i + 1}</td>
                <td className={`p-2 ${t.direction === "LONG" ? "text-green-400" : "text-red-400"}`}>{t.direction}</td>
                <td className="p-2">{fmtTime(t.entry_time)}</td>
                <td className="p-2 text-right">{t.entry_price.toFixed(2)}</td>
                <td className="p-2">{fmtTime(t.exit_time)}</td>
                <td className="p-2 text-right">{t.exit_price?.toFixed(2) ?? "—"}</td>
                <td className="p-2 text-right">{t.duration_min ? `${t.duration_min.toFixed(0)}m` : "—"}</td>
                <td className={`p-2 text-right font-semibold ${t.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {t.pnl >= 0 ? "+" : ""}${t.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </td>
                <td className="p-2 text-right">
                  {t.quality_score != null ? `${t.quality_score.toFixed(0)} (${t.quality_grade})` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
