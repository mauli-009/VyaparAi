"use client";

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────

function cleanFieldName(raw: string): string {
  return (raw || "value")
    .replace(/_(numeric|num|value|val|col|field|data|clean|processed|raw)$/i, "")
    .replace(/_/g, " ")
    .trim();
}

function formatValue(val: number, field?: string): string {
  const abs = Math.abs(val);
  const isFinancial = /revenue|profit|earning|income|sale|cost|expense|price|spend/i.test(field || "");
  if (abs >= 1_000_000) {
    const s = (val / 1_000_000).toFixed(2) + "M";
    return isFinancial ? "$" + s : s;
  }
  if (abs >= 1_000) {
    const s = val.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return isFinancial ? "$" + s : s;
  }
  return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function getRowLabel(row: any): string {
  return (
    row.period ?? row.group ?? row.month ??
    row.category ?? row.region ?? row.country ??
    row.product ?? row.item ??
    (Object.values(row).find((v) => typeof v === "string") as string | undefined) ?? "—"
  );
}

function getKeyLabel(row: any): string {
  if ("period"   in row) {
    const pt = row.period_type as string | undefined;
    return pt ? pt.charAt(0).toUpperCase() + pt.slice(1) : "Period";
  }
  if ("month"    in row) return "Month";
  if ("category" in row) return "Category";
  if ("region"   in row) return "Region";
  if ("group"    in row) return "Group";
  if ("country"  in row) return "Country";
  if ("product"  in row) return "Product";
  if ("item"     in row) return "Item";
  return "Item";
}

function buildFilterLabel(filters: any[]): string {
  if (!filters || filters.length === 0) return "";
  return filters
    .map((f: any) => {
      const field = cleanFieldName(f.field || "");
      const val   = Array.isArray(f.value) ? f.value.join(" – ") : String(f.value);
      return `${field}: ${val}`;
    })
    .join("  ·  ");
}

// ─────────────────────────────────────────────────────────────────
// Single value  (e.g. total revenue = $7.98M)
// ─────────────────────────────────────────────────────────────────
function SingleValue({ value, intent }: { value: number; intent: any }) {
  const field        = intent?.field  || "value";
  const metric       = intent?.metric || "";
  const filters      = intent?.filters || [];
  const filterLabel  = buildFilterLabel(filters);
  const displayField = cleanFieldName(field);

  return (
    <div className="result-card" style={{ maxWidth: 360 }}>
      <div className="result-card-header">
        <span className="result-card-label">
          {metric && <>{metric} · </>}{displayField}
        </span>
        {filterLabel && (
          <span style={{
            fontSize: 10, color: "var(--brand)", fontWeight: 600,
            background: "var(--brand-dim)", padding: "2px 8px",
            borderRadius: "var(--r-full)", border: "1px solid rgba(37,99,235,0.15)",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 180,
          }}>
            {filterLabel}
          </span>
        )}
      </div>
      <div className="result-card-body">
        <div className="result-value">{formatValue(value, field)}</div>
        <div className="result-meta">
          {filterLabel ? `Filtered · ${filterLabel}` : "All records"}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Grouped table  (e.g. revenue by region)
// ─────────────────────────────────────────────────────────────────
function TableResult({ rows, intent }: { rows: any[]; intent: any }) {
  const field        = intent?.field  || "value";
  const metric       = intent?.metric || "value";
  const filters      = intent?.filters || [];
  const filterLabel  = buildFilterLabel(filters);
  const displayField = cleanFieldName(field);
  const keyLabel     = getKeyLabel(rows[0]);
  const max          = Math.max(...rows.map((r) => r.value || 0), 0.001);

  return (
    <div className="result-card" style={{ maxWidth: 560 }}>
      <div className="result-card-header">
        <span className="result-card-label">
          {metric} of {displayField} · by {keyLabel}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {filterLabel && (
            <span style={{
              fontSize: 10, color: "var(--brand)", fontWeight: 600,
              background: "var(--brand-dim)", padding: "2px 7px",
              borderRadius: "var(--r-full)", border: "1px solid rgba(37,99,235,0.15)",
            }}>
              {filterLabel}
            </span>
          )}
          <span style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 700 }}>
            {rows.length} rows
          </span>
        </div>
      </div>
      <div style={{ maxHeight: 340, overflowY: "auto" }}>
        <table className="result-table">
          <thead>
            <tr>
              <th>{keyLabel}</th>
              <th style={{ textAlign: "right" }}>{displayField}</th>
              <th className="td-bar" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const pct = max > 0 ? (row.value / max) * 100 : 0;
              return (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{String(getRowLabel(row))}</td>
                  <td className="td-value">{formatValue(row.value, field)}</td>
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

// ─────────────────────────────────────────────────────────────────
// Metadata / schema view
// ─────────────────────────────────────────────────────────────────
function MetadataResult({ result }: { result: any }) {
  const columns = result?.columns || [];
  const types   = result?.column_types || {};
  return (
    <div className="result-card" style={{ maxWidth: 560 }}>
      <div className="result-card-header">
        <span className="result-card-label">Dataset Schema — {columns.length} columns</span>
      </div>
      <div style={{ maxHeight: 340, overflowY: "auto" }}>
        <table className="result-table">
          <thead><tr><th>Column</th><th>Type</th></tr></thead>
          <tbody>
            {columns.map((col: string) => (
              <tr key={col}>
                <td style={{ fontWeight: 500 }}>{col}</td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--brand)" }}>
                  {types[col] || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Main export
// ─────────────────────────────────────────────────────────────────
export default function ResultCard({ result, intent }: { result: any; intent: any }) {
  if (!result) return null;

  // Error
  if (result.error) {
    return (
      <div className="error-banner">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <div>
          <strong>Query error:</strong> {result.error}
          {result.available_fields && (
            <div style={{ marginTop: 4, fontSize: 11.5, opacity: 0.8 }}>
              Available: {(result.available_fields as string[]).join(", ")}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Metadata
  if (intent?.action === "metadata" || result.columns) {
    return <MetadataResult result={result} />;
  }

  const rows = result.results || [];

  // No data after filter
  if (result.message && rows.length === 0) {
    const filterLabel = buildFilterLabel(intent?.filters || []);
    return (
      <div className="error-banner" style={{
        background: "var(--warning-dim)",
        borderColor: "rgba(217,119,6,0.2)",
        color: "var(--warning)",
      }}>
        ⚠️ {result.message}
        {filterLabel && (
          <span style={{ marginLeft: 6, opacity: 0.8 }}>(filter: {filterLabel})</span>
        )}
      </div>
    );
  }

  if (rows.length === 0) return null;

  // Single aggregated value
  const isSingle =
    rows.length === 1 && "value" in rows[0] &&
    !("period" in rows[0]) && !("group" in rows[0]) &&
    !("category" in rows[0]) && !("region" in rows[0]) &&
    !("month" in rows[0]) && !("country" in rows[0]);

  if (isSingle) return <SingleValue value={rows[0].value} intent={intent} />;

  return <TableResult rows={rows} intent={intent} />;
}