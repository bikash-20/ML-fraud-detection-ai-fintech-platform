"use client";

import React from "react";
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface TimelineDataPoint {
  date: string;
  volume_bdt: number;
}

export interface RiskDistributionItem {
  name: string;
  count: number;
  color: string;
}

export function AdminVolumeChart({ data }: { data: TimelineDataPoint[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-xs text-secondary">
        No transaction volume recorded in this period.
      </div>
    );
  }

  const formatYAxis = (v: number) => {
    if (v >= 10000000) return `৳${(v / 10000000).toFixed(1)}Cr`;
    if (v >= 100000) return `৳${(v / 100000).toFixed(1)}L`;
    if (v >= 1000) return `৳${(v / 1000).toFixed(0)}k`;
    return `৳${v}`;
  };

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 8, right: 10, left: -4, bottom: 0 }}>
        <defs>
          <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f0a585" stopOpacity={0.6} />
            <stop offset="100%" stopColor="#f0a585" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tick={{ fill: "#cec2ce", fontSize: 12, fontWeight: 500 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#cec2ce", fontSize: 12, fontWeight: 500 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={formatYAxis}
          width={60}
        />
        <Tooltip
          contentStyle={{
            background: "rgba(45, 35, 48, 0.95)",
            border: "1px solid rgba(255,255,255,0.15)",
            borderRadius: 12,
            color: "#f7f0eb",
            fontSize: 14,
          }}
          formatter={(val: any) => [`৳${Number(val).toLocaleString("en-IN")}`, "Volume"]}
        />
        <Area
          type="monotone"
          dataKey="volume_bdt"
          stroke="#f0a585"
          strokeWidth={2.5}
          fill="url(#volGrad)"
          dot={{ r: 3, fill: "#f0a585", stroke: "#2d2330", strokeWidth: 1.5 }}
          activeDot={{ r: 6, fill: "#f0a585", stroke: "#ffffff", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function AdminRiskPieChart({ data }: { data: RiskDistributionItem[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-xs text-secondary">
        No risk distribution telemetry.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="count"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={48}
          outerRadius={72}
          paddingAngle={4}
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "rgba(45, 35, 48, 0.95)",
            border: "1px solid rgba(255,255,255,0.15)",
            borderRadius: 12,
            color: "#f7f0eb",
            fontSize: 14,
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
