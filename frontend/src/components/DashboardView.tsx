"use client";

import { useEffect, useState, useRef } from "react";
import ResultCard from "./ResultCard";
import { SmartBarChart, SmartPieChart, SmartLineChart } from "./SmartCharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/* ── Skeleton ── */
function SkeletonCard() {
  return (
    <div className="dash-card">
      <div className="dash-card-accent" />
      <div className="skeleton-line" style={{ height: 10, width: "45%", marginBottom: 14 }} />
      <div className="skeleton-line" style={{ height: 34, width: "35%", borderRadius: 7, marginBottom: 10 }} />
      <div className="skeleton-line" style={{ height: 9, width: "60%" }} />
    </div>
  );
}

/* ── DragHandle ── */
function DragHandleIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
      <circle cx="3.5" cy="2.5" r="1.2" />
      <circle cx="8.5" cy="2.5" r="1.2" />
      <circle cx="3.5" cy="6" r="1.2" />
      <circle cx="8.5" cy="6" r="1.2" />
      <circle cx="3.5" cy="9.5" r="1.2" />
      <circle cx="8.5" cy="9.5" r="1.2" />
    </svg>
  );
}

/* ── Widget Content ── */
function DashboardWidget({ widget, fileId }: { widget: any; fileId: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const token = localStorage.getItem("token");
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const res = await fetch(`${API}/query`, {
          method: "POST",
          headers,
          body: JSON.stringify({ file_id: fileId, question: "", intent_override: widget.intent }),
        });
        setData(await res.json());
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [widget, fileId]);

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 80 }}>
        <div className="dash-mini-spinner" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
        <span style={{ fontSize: 12, color: "var(--text-3)" }}>Failed to load widget</span>
      </div>
    );
  }

  const rows = data.result?.results || [];

  return (
    <div style={{ marginTop: 8, flex: 1, overflow: "hidden" }}>
      {widget.type === "metric"     && <ResultCard result={data.result} intent={widget.intent} />}
      {widget.type === "bar_chart"  && <SmartBarChart data={rows} />}
      {widget.type === "pie_chart"  && <SmartPieChart data={rows} />}
      {widget.type === "line_chart" && <SmartLineChart data={rows} />}

      {widget.type === "list" && data.records && (
        <div style={{ maxHeight: 240, overflowY: "auto", borderRadius: 8, border: "1px solid var(--border)", marginTop: 6 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr>
                {Object.keys(data.records[0] || {}).map((k) => (
                  <th key={k} style={{
                    padding: "7px 10px", textAlign: "left", fontWeight: 700,
                    fontSize: 9.5, letterSpacing: "0.08em", textTransform: "uppercase",
                    color: "var(--text-3)", background: "var(--surface-2)",
                    borderBottom: "1px solid var(--border)",
                    position: "sticky", top: 0, zIndex: 1,
                  }}>
                    {k.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.records.map((row: any, i: number) => (
                <tr key={i} style={i % 2 !== 0 ? { background: "var(--surface-2)" } : {}}>
                  {Object.keys(row).map((k) => (
                    <td key={k} style={{
                      padding: "7px 10px", color: "var(--text-2)",
                      borderBottom: "1px solid var(--border)",
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 160,
                    }}>
                      {String(row[k])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ── Main ── */
export default function DashboardView({ fileId }: { fileId: string | null }) {
  const [layout, setLayout] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  /* Drag state */
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);
  const dragCounter = useRef(0);

  useEffect(() => {
    if (!fileId) { setLayout([]); return; }
    async function fetchDashboard() {
      setLoading(true);
      try {
        const res = await fetch(`${API}/dashboards/${fileId}`);
        if (res.ok) {
          const data = await res.json();
          setLayout(data.layout || []);
        }
      } catch {} finally {
        setLoading(false);
      }
    }
    fetchDashboard();
  }, [fileId]);

  /* ── Drag handlers ── */
  function handleDragStart(e: React.DragEvent, id: string) {
    setDragId(id);
    e.dataTransfer.effectAllowed = "move";
    // Ghost image transparency
    const el = e.currentTarget as HTMLElement;
    e.dataTransfer.setDragImage(el, el.offsetWidth / 2, 20);
  }

  function handleDragEnter(e: React.DragEvent, id: string) {
    e.preventDefault();
    dragCounter.current++;
    if (id !== dragId) setDragOverId(id);
  }

  function handleDragLeave() {
    dragCounter.current--;
    if (dragCounter.current === 0) setDragOverId(null);
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }

  function handleDrop(e: React.DragEvent, targetId: string) {
    e.preventDefault();
    dragCounter.current = 0;
    if (!dragId || dragId === targetId) {
      setDragId(null);
      setDragOverId(null);
      return;
    }
    setLayout((prev) => {
      const next = [...prev];
      const fromIdx = next.findIndex((w) => w.id === dragId);
      const toIdx   = next.findIndex((w) => w.id === targetId);
      if (fromIdx < 0 || toIdx < 0) return prev;
      const [removed] = next.splice(fromIdx, 1);
      next.splice(toIdx, 0, removed);
      return next;
    });
    setDragId(null);
    setDragOverId(null);
  }

  function handleDragEnd() {
    setDragId(null);
    setDragOverId(null);
    dragCounter.current = 0;
  }

  /* ── Render ── */
  if (!fileId) {
    return (
      <DashEmpty
        icon="📊"
        title="No dataset selected"
        subtitle="Upload a CSV file to generate your executive dashboard."
      />
    );
  }

  if (loading) {
    return (
      <div className="dashboard-root">
        <DashboardHeader />
        <div className="dashboard-grid">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    );
  }

  if (layout.length === 0) {
    return (
      <DashEmpty
        icon="🗂️"
        title="No dashboard layout found"
        subtitle="Re-upload your dataset to generate a fresh dashboard."
      />
    );
  }

  return (
    <div className="dashboard-root">
      <DashboardHeader />
      <p style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 16, display: "flex", alignItems: "center", gap: 5 }}>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="5 9 2 12 5 15" /><polyline points="9 5 12 2 15 5" />
          <polyline points="15 19 12 22 9 19" /><polyline points="19 9 22 12 19 15" />
          <line x1="2" y1="12" x2="22" y2="12" /><line x1="12" y1="2" x2="12" y2="22" />
        </svg>
        Drag cards to reorder
      </p>
      <div className="dashboard-grid">
        {layout.map((widget) => {
          const isDragging  = widget.id === dragId;
          const isDragTarget = widget.id === dragOverId;
          const spanTwo = widget.grid_position?.w === 2;

          return (
            <div
              key={widget.id}
              className={[
                "dash-card",
                isDragging   ? "is-dragging"  : "",
                isDragTarget ? "drag-target"  : "",
              ].join(" ")}
              style={{ gridColumn: spanTwo ? "span 2" : "span 1" }}
              draggable
              onDragStart={(e) => handleDragStart(e, widget.id)}
              onDragEnter={(e) => handleDragEnter(e, widget.id)}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, widget.id)}
              onDragEnd={handleDragEnd}
            >
              <div className="dash-card-accent" />
              <div className="dash-card-handle" title="Drag to reorder">
                <DragHandleIcon />
              </div>
              <p className="dash-card-label">{widget.title}</p>
              <DashboardWidget widget={widget} fileId={fileId} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DashboardHeader() {
  return (
    <div className="dashboard-header">
      <div>
        <h1 className="dashboard-title">Executive Overview</h1>
        <p className="dashboard-subtitle">Auto-generated insights from your dataset</p>
      </div>
      <div className="live-badge">
        <span className="live-dot" />
        Live
      </div>
    </div>
  );
}

function DashEmpty({ icon, title, subtitle }: { icon: string; title: string; subtitle: string }) {
  return (
    <div className="dash-empty">
      <div className="dash-empty-icon">{icon}</div>
      <p className="dash-empty-title">{title}</p>
      <p className="dash-empty-sub">{subtitle}</p>
    </div>
  );
}