"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function BalanceChart({
  data,
}: {
  data: { date: string; balance: number }[];
}) {
  if (!data.length) {
    return (
      <div className="text-center text-lavender py-8 text-sm">
        Not enough history to plot a chart.
      </div>
    );
  }

  const formatXTick = (d: string) => {
    if (d.includes(" ")) {
      const [datePart, timePart] = d.split(" ");
      if (timePart === "00:00") {
        return datePart.slice(5);
      }
      return timePart;
    }
    return d.slice(5);
  };

  const formatYAxis = (v: number) => {
    if (v >= 10000000) return `${(v / 10000000).toFixed(1)}Cr`;
    if (v >= 100000) return `${(v / 100000).toFixed(1)}L`;
    if (v >= 1000) return `${(v / 1000).toFixed(0)}k`;
    return String(v);
  };

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -4, bottom: 0 }}>
          <defs>
            <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f0a585" stopOpacity={0.55} />
              <stop offset="100%" stopColor="#f0a585" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tickFormatter={formatXTick}
            tick={{ fill: "#cec2ce", fontSize: 12, fontWeight: 500 }}
            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            tickLine={false}
            minTickGap={28}
          />
          <YAxis
            tick={{ fill: "#cec2ce", fontSize: 12, fontWeight: 500 }}
            axisLine={false}
            tickLine={false}
            width={58}
            tickFormatter={formatYAxis}
          />
          <Tooltip
            contentStyle={{
              background: "rgba(45, 35, 48, 0.95)",
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 8,
              color: "#f7f0eb",
              fontSize: 13,
              boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
            }}
            formatter={(v: number) => [`৳${Number(v).toLocaleString("en-IN")}`, "Balance"]}
            labelFormatter={(d: string) => {
              if (d.includes(" ")) {
                const [datePart, timePart] = d.split(" ");
                if (timePart === "00:00") return `${datePart} (Opening)`;
                return `${datePart} · ${timePart}`;
              }
              return d;
            }}
          />
          <Area
            type="monotone"
            dataKey="balance"
            stroke="#f0a585"
            strokeWidth={2.5}
            fill="url(#balGrad)"
            isAnimationActive={true}
            animationDuration={500}
            dot={{ r: 2.5, fill: "#f0a585", stroke: "#2d2330", strokeWidth: 1.5 }}
            activeDot={{ r: 5, fill: "#f0a585", stroke: "#ffffff", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}