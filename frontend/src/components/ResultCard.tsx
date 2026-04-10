"use client";

function formatValue(val: number): string {
  if (Math.abs(val) >= 1_000_000)
    return "$" + (val / 1_000_000).toFixed(2) + "M";
  if (Math.abs(val) >= 1_000)
    return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function SingleValue({ value, intent }: { value: number; intent: any }) {
  const field  = intent?.field?.replace(/_/g, " ") || "value";
  const metric = intent?.metric || "";
  const filters = intent?.filters || [];

  return (
    <div className="result-card" style={{ maxWidth: 340 }}>
      <div className="result-card-header">
        <span className="result-card-label">{metric} · {field}</span>
      </div>
      <div className="result-card-body">
        <div className="result-value">{formatValue(value)}</div>
        <div className="result-meta">
          {filters.length > 0
            ? filters.map((f: any) =>
                `${f.field}: ${Array.isArray(f.value) ? f.value.join(" – ") : f.value}`
              ).join(" · ")
            : "All records"}
        </div>
      </div>
    </div>
  );
}

function TableResult({ rows, intent }: { rows: any[]; intent: any }) {
  const field  = intent?.field?.replace(/_/g, " ") || "value";
  const metric = intent?.metric || "value";
  const max    = Math.max(...rows.map((r) => r.value || 0));

  const getLabel = (row: any) =>
    row.month || row.category || row.region || row.group ||
    Object.values(row).find((v) => typeof v === "string") || "—";

  const keyLabel =
    "month"    in rows[0] ? "Month"    :
    "category" in rows[0] ? "Category" :
    "region"   in rows[0] ? "Region"   :
    "group"    in rows[0] ? "Group"    : "Item";

  return (
    <div className="result-card" style={{ maxWidth: 540 }}>
      <div className="result-card-header">
        <span className="result-card-label">{metric} of {field} · by {keyLabel}</span>
        <span style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 600 }}>
          {rows.length} rows
        </span>
      </div>
      <div style={{ maxHeight: 340, overflowY: "auto" }}>
        <table className="result-table">
          <thead>
            <tr>
              <th>{keyLabel}</th>
              <th style={{ textAlign: "right" }}>{field}</th>
              <th className="td-bar" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const pct = max > 0 ? (row.value / max) * 100 : 0;
              return (
                <tr key={i}>
                  <td style={{ fontWeight: 500 }}>{String(getLabel(row))}</td>
                  <td className="td-value">{formatValue(row.value)}</td>
                  <td className="td-bar">
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${pct}%` }} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ResultCard({ result, intent }: { result: any; intent: any }) {
  if (!result) return null;

  const rows = result.results || [];

  if (result.error)
    return <div className="error-banner">❌ {result.error}</div>;

  if (result.message && rows.length === 0)
    return (
      <div className="error-banner" style={{ background: "var(--warning-light)", borderColor: "#f5d98b", color: "var(--warning)" }}>
        ⚠️ {result.message}
      </div>
    );

  if (rows.length === 1 && "value" in rows[0] && !("month" in rows[0]) && !("category" in rows[0]) && !("region" in rows[0]))
    return <SingleValue value={rows[0].value} intent={intent} />;

  if (rows.length > 0)
    return <TableResult rows={rows} intent={intent} />;

  return null;
}