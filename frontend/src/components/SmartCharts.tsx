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

export function SmartBarChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const keys      = Object.keys(data[0]);
  const xAxisKey  = keys[0];
  const yAxisKey  = keys[1] || keys[0];

  return (
    <div style={chartWrap}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
          <XAxis dataKey={xAxisKey} tick={axisStyle} axisLine={false} tickLine={false} />
          <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--brand-subtle)" }} />
          <Bar dataKey={yAxisKey} fill="var(--brand)" radius={[5, 5, 0, 0]} barSize={42} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SmartPieChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const keys     = Object.keys(data[0]);
  const nameKey  = keys[0];
  const valueKey = keys[1] || keys[0];

  return (
    <div style={chartWrap}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey={valueKey}
            nameKey={nameKey}
            cx="50%"
            cy="50%"
            outerRadius={95}
            innerRadius={40}
            paddingAngle={2}
            label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SmartLineChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const keys     = Object.keys(data[0]);
  const xAxisKey = keys[0];
  const yAxisKey = keys[1] || keys[0];

  return (
    <div style={chartWrap}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
          <XAxis dataKey={xAxisKey} tick={axisStyle} axisLine={false} tickLine={false} />
          <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line
            type="monotone"
            dataKey={yAxisKey}
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
  const keys     = Object.keys(data[0]);
  const xAxisKey = keys[0];
  const yAxisKey = keys[1] || keys[0];

  return (
    <div style={chartWrap}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey={xAxisKey} type="number" name={xAxisKey} tick={axisStyle} axisLine={false} tickLine={false} />
          <YAxis dataKey={yAxisKey} type="number" name={yAxisKey} tick={axisStyle} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={tooltipStyle} />
          <Scatter name="Data Points" data={data} fill="var(--brand)" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}