"use client";

import { useState } from "react";
import { SmartBarChart, SmartPieChart, SmartLineChart, SmartScatterChart } from "./SmartCharts";
import ResultCard from "./ResultCard";

function SimpleTable({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  const keys = Object.keys(data[0]);
  return (
    <div style={{ maxHeight: 340, overflowY: "auto", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 }}>
      <table style={{ width: "100%", textAlign: "left", borderCollapse: "collapse", fontSize: 13 }}>
        <thead style={{ position: "sticky", top: 0, background: "var(--surface-2)", zIndex: 10 }}>
          <tr>
            {keys.map((k) => (
              <th key={k} style={{
                padding: "9px 12px", borderBottom: "1px solid var(--border)",
                fontSize: 10, fontWeight: 700, textTransform: "capitalize",
                letterSpacing: "0.06em", color: "var(--text-3)",
              }}>
                {k.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
              {keys.map((k) => (
                <td key={k} style={{ padding: "9px 12px", color: "var(--text-2)" }}>
                  {String(row[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DynamicRenderer({ msg }: { msg: any }) {
  const intent  = msg.intent || {};
  const rawData = msg.result?.results || msg.records || [];

  // Infer chart type from data shape when the LLM didn't suggest one
  function inferCharts(): string[] {
    if (rawData.length === 0) return [];
    const first = rawData[0];
    if ("period" in first)   return ["line_chart", "bar_chart"];  // time-series
    if ("group" in first ||
        "category" in first ||
        "region" in first)   return ["bar_chart", "pie_chart"];   // categorical
    return [];
  }

  const suggestedCharts: string[] =
    intent.suggested_charts?.length > 0 ? intent.suggested_charts : inferCharts();

  // Auto-show chart for all grouped data (multiple rows)
  const hasMultipleRows      = rawData.length > 1;
  const shouldDefaultToChart = suggestedCharts.length > 0 && hasMultipleRows;

  const [selectedChart, setSelectedChart] = useState<string | null>(
    shouldDefaultToChart ? suggestedCharts[0] : null
  );
  const [showData, setShowData] = useState<boolean>(!shouldDefaultToChart);

  if (!rawData || rawData.length === 0) return null;

  const chartLabels: Record<string, string> = {
    bar_chart:     "📊 Bar",
    pie_chart:     "🥧 Pie",
    line_chart:    "📈 Line",
    scatter_chart: "🔵 Scatter",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", gap: 10, marginTop: 8 }}>
      {suggestedCharts.length > 0 && (
        <div className="view-toggle-bar">
          <button
            className={`view-toggle-btn${showData ? " is-active" : ""}`}
            onClick={() => { setShowData(true); setSelectedChart(null); }}
          >
            📋 Table
          </button>
          {suggestedCharts.map((chart: string) => (
            <button
              key={chart}
              className={`view-toggle-btn${selectedChart === chart ? " is-active" : ""}`}
              onClick={() => { setShowData(false); setSelectedChart(chart); }}
            >
              {chartLabels[chart] || chart.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      )}

      {showData && (
        msg.queryType === "aggregation" || msg.queryType === "both"
          ? <ResultCard result={msg.result} intent={intent} />
          : <SimpleTable data={rawData} />
      )}

      {!showData && selectedChart === "bar_chart"     && <SmartBarChart data={rawData} />}
      {!showData && selectedChart === "pie_chart"     && <SmartPieChart data={rawData} />}
      {!showData && selectedChart === "line_chart"    && <SmartLineChart data={rawData} />}
      {!showData && selectedChart === "scatter_chart" && <SmartScatterChart data={rawData} />}
    </div>
  );
}