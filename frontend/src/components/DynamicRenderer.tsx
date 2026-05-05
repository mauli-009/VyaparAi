"use client";

import { useState } from 'react';
import { SmartBarChart, SmartPieChart, SmartLineChart, SmartScatterChart } from './SmartCharts';
import ResultCard from './ResultCard';

// A clean, compact table for raw list records (like scatter plot data)
function SimpleTable({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const keys = Object.keys(data[0]);

  return (
    <div style={{ maxHeight: "340px", overflowY: "auto", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "10px" }}>
      <table style={{ width: "100%", textAlign: "left", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead style={{ position: "sticky", top: 0, background: "var(--surface-hover)", zIndex: 10 }}>
          <tr>
            {keys.map(k => (
              <th key={k} style={{ padding: "10px", borderBottom: "1px solid var(--border)", textTransform: "capitalize", color: "var(--text-primary)" }}>
                {k.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
              {keys.map(k => (
                <td key={k} style={{ padding: "10px", color: "var(--text-secondary)" }}>{String(row[k])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DynamicRenderer({ msg }: { msg: any }) {
  const intent = msg.intent || {};
  const suggestedCharts = intent.suggested_charts || [];
  const rawData = msg.result?.results || msg.records || [];

  // 🔥 THE MAGIC: Auto-hide massive tables for Scatter Charts OR any explicit chart on a list query
  const shouldDefaultToChart = suggestedCharts.includes("scatter_chart") || (msg.queryType === "list_records" && suggestedCharts.length > 0);
  
  const defaultChart = suggestedCharts.length > 0 ? suggestedCharts[0] : null;
  const [selectedChart, setSelectedChart] = useState<string | null>(shouldDefaultToChart ? defaultChart : null);
  const [showData, setShowData] = useState<boolean>(!shouldDefaultToChart);

  if (!rawData || rawData.length === 0) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", gap: "12px", marginTop: "10px" }}>

      {/* 1. View Toggles (Tabs) */}
      {suggestedCharts.length > 0 && (
        <div style={{ display: "flex", gap: "6px", background: "var(--surface)", padding: "6px", borderRadius: "8px", border: "1px solid var(--border)", width: "fit-content" }}>
          <button
            onClick={() => { setShowData(true); setSelectedChart(null); }}
            style={{ 
              padding: "6px 12px", borderRadius: "6px", fontSize: "12px", fontWeight: 600, border: "none", cursor: "pointer", transition: "0.2s",
              background: showData ? "var(--accent)" : "transparent", color: showData ? "#fff" : "var(--text-secondary)" 
            }}
          >
            📋 Data Table
          </button>

          {suggestedCharts.map((chart: string) => (
            <button
              key={chart}
              onClick={() => { setShowData(false); setSelectedChart(chart); }}
              style={{ 
                padding: "6px 12px", borderRadius: "6px", fontSize: "12px", fontWeight: 600, border: "none", cursor: "pointer", transition: "0.2s",
                background: selectedChart === chart ? "var(--accent)" : "transparent", color: selectedChart === chart ? "#fff" : "var(--text-secondary)" 
              }}
            >
              📊 {chart.replace('_', ' ').toUpperCase()}
            </button>
          ))}
        </div>
      )}

      {/* 2. Render Data Table (Auto-hidden if chart is active) */}
      {showData && (
        msg.queryType === "aggregation" || msg.queryType === "both"
          ? <ResultCard result={msg.result} intent={intent} />
          : <SimpleTable data={rawData} />
      )}

      {/* 3. Render Chart */}
      {!showData && selectedChart === "bar_chart" && <SmartBarChart data={rawData} />}
      {!showData && selectedChart === "pie_chart" && <SmartPieChart data={rawData} />}
      {!showData && selectedChart === "line_chart" && <SmartLineChart data={rawData} />}
      {!showData && selectedChart === "scatter_chart" && <SmartScatterChart data={rawData} />}
    </div>
  );
}