"use client";

import { useState } from "react";

const PRIORITY = {
  high:   { color: "#dc2626", bg: "#fef2f2", border: "#fecaca",   label: "High" },
  medium: { color: "#d97706", bg: "#fffbeb", border: "#fde68a",   label: "Medium" },
  low:    { color: "#059669", bg: "#ecfdf5", border: "#6ee7b7",   label: "Low" },
};

const PRIORITY_DARK = {
  high:   { color: "#f87171", bg: "rgba(248,113,113,0.1)", border: "rgba(248,113,113,0.2)" },
  medium: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)",  border: "rgba(251,191,36,0.2)" },
  low:    { color: "#34d399", bg: "rgba(52,211,153,0.1)",  border: "rgba(52,211,153,0.2)" },
};

function SuggestionCard({ s, index }: { s: any; index: number }) {
  const [open, setOpen] = useState(false);
  const p = PRIORITY[s.priority as keyof typeof PRIORITY] || PRIORITY.medium;

  return (
    <div className="suggestion-card" style={{ animationDelay: `${index * 0.07}s` }}>
      <div className="suggestion-card-header">
        <div className="suggestion-num">{index + 1}</div>
        <div className="suggestion-title-row">
          <span className="suggestion-title">{s.title}</span>
          <div className="suggestion-badges">
            <span
              className="priority-badge"
              style={{ background: p.bg, color: p.color, border: `1px solid ${p.border}` }}
            >
              {p.label} Priority
            </span>
          </div>
        </div>
        <button className="expand-btn" onClick={() => setOpen(!open)}>
          <svg
            width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
            style={{ transform: open ? "rotate(180deg)" : "rotate(0)", transition: "transform 0.2s ease" }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>

      <p className="suggestion-insight">{s.insight}</p>

      <div className="action-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--brand)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 2 }}>
          <polyline points="9 18 15 12 9 6" />
        </svg>
        {s.action}
      </div>

      {open && (
        <div className="expanded-section">
          <div>
            <div className="section-label">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
              </svg>
              Execution Plan
            </div>
            <div className="steps-list">
              {s.execution_plan?.map((step: string, i: number) => (
                <div key={i} className="step-row">
                  <div className="step-num">{i + 1}</div>
                  <span>{step}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="impact-box">
            <div className="section-label" style={{ marginBottom: 6 }}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" /><polyline points="17 6 23 6 23 12" />
              </svg>
              Expected Impact
            </div>
            <p className="impact-text">{s.expected_impact}</p>
          </div>
        </div>
      )}

      {!open && (
        <button className="show-more-btn" onClick={() => setOpen(true)}>
          View execution plan →
        </button>
      )}
    </div>
  );
}

export default function SuggestionCards({ suggestions }: { suggestions: any[] }) {
  if (!suggestions?.length) return null;
  return (
    <div className="suggestions-wrapper">
      <div className="suggestions-header">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
        AI Business Recommendations
      </div>
      {suggestions.map((s, i) => (
        <SuggestionCard key={i} s={s} index={i} />
      ))}
    </div>
  );
}