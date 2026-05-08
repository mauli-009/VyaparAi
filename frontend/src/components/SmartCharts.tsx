"use client";

import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";

const COLORS = ["#4a8aff", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899"];

const chartWrap: React.CSSProperties = {
  width: "100%",
  height: 300,
  marginTop: 10,
  background: "var(--surface)",
  padding: "16px 12px 12px",
  borderRadius: 12,
  border: "1px solid var(--border)",
  boxShadow: "var(--shadow-xs)",
};

const tooltipStyle = {
  borderRadius: 8,
  border: "1px solid var(--border)",
  boxShadow: "var(--shadow)",
  fontSize: 12,
};

const axisStyle = { fontSize: 11, fill: "var(--text-3)" };

/** Find the best X key (first string-ish column) and Y key (first numeric column). */
function detectAxes(data: any[]): { xKey: string; yKey: string } {
  const keys = Object.keys(data[0]);
  const sample = data[0];
  const yKey = keys.find((k) => typeof sample[k] === "number") ?? keys[keys.length - 1];
  const xKey = keys.find((k) => k !== yKey && k !== "period_type") ?? keys[0];
  return { xKey, yKey };
}

export function SmartBarChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const { xKey, yKey } = detectAxes(data);

  return (
    <div style={chartWrap}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
          <XAxis dataKey={xKey} tick={axisStyle} axisLine={false} tickLine={false} />
          <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--brand-subtle)" }} />
          <Bar dataKey={yKey} fill="var(--brand)" radius={[5, 5, 0, 0]} barSize={42} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const RADIAN = Math.PI / 180;

/** Render percentage labels INSIDE the pie slice — no clipping. */
function PieLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) {
  if (percent < 0.04) return null; // Skip labels on tiny slices
  const r = innerRadius + (outerRadius - innerRadius) * 0.55;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central"
      style={{ fontSize: 10, fontWeight: 700, pointerEvents: "none" }}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

export function SmartPieChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const { xKey, yKey } = detectAxes(data);

  // Cap at 8 slices — merge the tail into "Others" so the chart stays readable
  const sorted = [...data].sort((a, b) => (b[yKey] ?? 0) - (a[yKey] ?? 0));
  const top     = sorted.slice(0, 8);
  const tail    = sorted.slice(8);
  const chartData = tail.length > 0
    ? [...top, { [xKey]: "Others", [yKey]: tail.reduce((s, r) => s + (r[yKey] ?? 0), 0) }]
    : top;

  const truncate = (s: string) => s.length > 18 ? s.slice(0, 17) + "…" : s;

  return (
    <div style={chartWrap}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={chartData}
            dataKey={yKey}
            nameKey={xKey}
            cx="50%"
            cy="42%"
            outerRadius={85}
            innerRadius={32}
            paddingAngle={2}
            labelLine={false}
            label={PieLabel}
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(val: any, _name: any, props: any) => [
              Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 }),
              props?.payload?.[xKey] ?? yKey,
            ]}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 6 }}
            formatter={(value: string) => truncate(String(value))}
            iconType="circle"
            iconSize={8}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SmartLineChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const { xKey, yKey } = detectAxes(data);

  return (
    <div style={chartWrap}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
          <XAxis dataKey={xKey} tick={axisStyle} axisLine={false} tickLine={false} />
          <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line
            type="monotone"
            dataKey={yKey}
            stroke="var(--brand)"
            strokeWidth={2.5}
            dot={{ r: 3.5, fill: "var(--brand)", strokeWidth: 0 }}
            activeDot={{ r: 5.5, fill: "var(--brand)", strokeWidth: 2, stroke: "var(--surface)" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SmartScatterChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const { xKey, yKey } = detectAxes(data);

  return (
    <div style={chartWrap}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey={xKey} type="number" name={xKey} tick={axisStyle} axisLine={false} tickLine={false} />
          <YAxis dataKey={yKey} type="number" name={yKey} tick={axisStyle} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={tooltipStyle} />
          <Scatter name="Data Points" data={data} fill="var(--brand)" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}