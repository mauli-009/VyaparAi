"use client";

import { useState } from "react";

const PRIORITY = {
  high:   { color: "#dc2626", bg: "#fef2f2", border: "#fecaca", label: "High" },
  medium: { color: "#b45309", bg: "#fffbeb", border: "#fde68a", label: "Medium" },
  low:    { color: "#0a7c4e", bg: "#f0fdf4", border: "#bbf7d0", label: "Low" },
};

const RANK_COLORS = ["var(--accent)", "#6b7280", "#b45309"];

function ProductCard({ p, isTop, index }: { p: any; isTop: boolean; index: number }) {
  const [open, setOpen] = useState(isTop);
  const priority = PRIORITY[p.priority as keyof typeof PRIORITY] || PRIORITY.medium;

  return (
    <div className={`rec-product-card ${isTop ? "is-top" : ""}`} style={{ animationDelay: `${index * 0.07}s` }}>

      <div className="rec-product-header">
        <div className="rec-rank-badge" style={{ background: RANK_COLORS[index] || "#6b7280" }}>
          #{p.rank}
        </div>

        <div className="rec-product-info">
          <div className="rec-product-name-row">
            <span className="rec-product-name">{p.product}</span>
            {isTop && <span className="top-pick-badge">⭐ Top Pick</span>}
            <span className="priority-badge" style={{
              background: priority.bg,
              color: priority.color,
              border: `1px solid ${priority.border}`
            }}>
              {priority.label}
            </span>
          </div>
          <div className="score-bar-row">
            <div className="score-bar-track">
              <div
                className="score-bar-fill"
                style={{
                  width: `${p.score ?? 0}%`,
                  background: isTop ? "var(--accent)" : "#6b7280"
                }}
              />
            </div>
            <span className="score-label">{(p.score ?? 0).toFixed(0)} / 100</span>
          </div>
        </div>

        <button className="expand-btn" onClick={() => setOpen(!open)}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
            style={{ transform: open ? "rotate(180deg)" : "rotate(0)", transition: "transform 0.2s ease" }}>
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>

      <p className="rec-why">{p.why}</p>

      {open && (
        <div className="expanded-section">
          <div className="outlook-box">
            <div className="section-label" style={{ marginBottom: 6 }}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
              Long-term Outlook
            </div>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 }}>
              {p.long_term_outlook}
            </p>
          </div>

          <div className="action-box">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
              style={{ flexShrink: 0, color: "var(--accent)", marginTop: 1 }}>
              <polyline points="9 18 15 12 9 6" />
            </svg>
            {p.suggested_action}
          </div>

          <div>
            <div className="section-label">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
              </svg>
              Execution Plan
            </div>
            <div className="steps-list">
              {p.execution_plan?.map((step: string, i: number) => (
                <div key={i} className="step-row">
                  <div className="step-num">{i + 1}</div>
                  <span>{step}</span>
                </div>
              ))}
            </div>
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

export default function RecommendationCard({ recommendation }: { recommendation: any }) {
  if (!recommendation) return null;
  if (recommendation.error)
    return <div className="error-banner">❌ {recommendation.error}</div>;

  const products = recommendation.ranked_products || [];

  return (
    <div className="rec-wrapper">
      {recommendation.top_pick && (
        <div className="top-pick-banner">
          <div className="top-pick-banner-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
            Best Long-term Choice: <strong style={{ marginLeft: 3 }}>{recommendation.top_pick}</strong>
          </div>
          <p className="top-pick-reason">{recommendation.top_pick_reason}</p>
        </div>
      )}

      <div className="rec-products-list">
        {products.map((p: any, i: number) => (
          <ProductCard
            key={i}
            p={p}
            isTop={p.product === recommendation.top_pick}
            index={i}
          />
        ))}
      </div>
    </div>
  );
}