"use client";

import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,ScatterChart, Scatter,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts';

// Matching your UI theme colors
const COLORS = ['#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

export function SmartBarChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const keys = Object.keys(data[0]);
  const xAxisKey = keys[0]; 
  const yAxisKey = keys[1] || keys[0]; 

  return (
    <div style={{ width: '100%', height: 320, marginTop: 16, background: "var(--surface)", padding: 16, borderRadius: 12, border: "1px solid var(--border)" }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
          <XAxis dataKey={xAxisKey} tick={{ fontSize: 12, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 12, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ borderRadius: 8, border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }} />
          <Bar dataKey={yAxisKey} fill="var(--accent)" radius={[4, 4, 0, 0]} barSize={45} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SmartPieChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const keys = Object.keys(data[0]);
  const nameKey = keys[0];
  const valueKey = keys[1] || keys[0];

  return (
    <div style={{ width: '100%', height: 320, marginTop: 16, background: "var(--surface)", padding: 16, borderRadius: 12, border: "1px solid var(--border)" }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey={valueKey} nameKey={nameKey} cx="50%" cy="50%" outerRadius={100} label>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ borderRadius: 8, border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SmartLineChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const keys = Object.keys(data[0]);
  const xAxisKey = keys[0];
  const yAxisKey = keys[1] || keys[0];

  return (
    <div style={{ width: '100%', height: 320, marginTop: 16, background: "var(--surface)", padding: 16, borderRadius: 12, border: "1px solid var(--border)" }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
          <XAxis dataKey={xAxisKey} tick={{ fontSize: 12, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 12, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ borderRadius: 8, border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }} />
          <Line type="monotone" dataKey={yAxisKey} stroke="var(--accent)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SmartScatterChart({ data }: { data: any[] }) {
    if (!data || data.length === 0) return null;
    
    const keys = Object.keys(data[0]);
    // The first requested column is X, the second is Y
    const xAxisKey = keys[0];
    const yAxisKey = keys[1] || keys[0];
  
    return (
      <div style={{ width: '100%', height: 320, marginTop: 16, background: "var(--surface)", padding: 16, borderRadius: 12, border: "1px solid var(--border)" }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 20, bottom: 10, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            {/* For Scatter plots, type="number" is required for both axes */}
            <XAxis dataKey={xAxisKey} type="number" name={xAxisKey} tick={{ fontSize: 12, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
            <YAxis dataKey={yAxisKey} type="number" name={yAxisKey} tick={{ fontSize: 12, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
            
            <Tooltip 
              cursor={{ strokeDasharray: '3 3' }} 
              contentStyle={{ borderRadius: 8, border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }} 
            />
            <Scatter name="Data Points" data={data} fill="var(--accent)" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  }