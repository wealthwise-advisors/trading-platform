import { PieChart, Pie, Cell, Legend, Tooltip, ResponsiveContainer } from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CYAN, CRITICAL } from "@/components/cards/StatCard"

interface WinLossDonutProps {
  wins: number
  losses: number
  winRate: number
}

export function WinLossDonut({ wins, losses, winRate }: WinLossDonutProps) {
  const data = wins + losses > 0
    ? [{ name: "Wins", value: wins }, { name: "Losses", value: losses }]
    : [{ name: "No trades", value: 1 }]
  const colors = wins + losses > 0 ? [CYAN, CRITICAL] : ["#45475a"]

  return (
    <Card className="h-full border border-white/6">
      <CardHeader className="pb-0">
        <CardTitle className="text-sm">Win / Loss</CardTitle>
      </CardHeader>
      <CardContent className="relative">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="65%"
              outerRadius="90%"
              stroke="#0b1120"
              strokeWidth={3}
              isAnimationActive
            >
              {data.map((_, i) => <Cell key={i} fill={colors[i]} />)}
            </Pie>
            <Tooltip
              contentStyle={{ background: "#0b1120", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }}
              formatter={(value, name) => [`${value} trades`, name] as [string, string]}
            />
            <Legend verticalAlign="bottom" height={24} />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
             style={{ transform: "translateY(-14px)" }}>
          <span className="text-2xl font-extrabold">{winRate.toFixed(0)}%</span>
          <span className="text-xs text-muted-foreground">Win Rate</span>
        </div>
      </CardContent>
    </Card>
  )
}
