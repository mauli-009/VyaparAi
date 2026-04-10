"use client";

import { useState, useRef, useEffect } from "react";
import ResultCard from "./ResultCard";
import SuggestionCards from "./SuggestionCards";
import RecommendationCard from "./RecommendationCard";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SUGGESTIONS = [
  "What is the total revenue?",
  "Show revenue by region",
  "Monthly revenue trend",
  "Which product should I choose for long term?",
  "Average profit per order",
  "Give me business recommendations",
];

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  intent?: any;
  result?: any;
  suggestions?: any[];
  recommendation?: any;
  queryType?: "aggregation" | "suggestion" | "recommendation" | "both";
  error?: string;
  loading?: boolean;
}

interface Props {
  fileId: string | null;
  mappingDone: boolean;
}

export default function QueryChat({ fileId, mappingDone }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function autoResize() {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
  }

  async function sendQuery(question: string) {
    if (!question.trim() || !fileId || !mappingDone || loading) return;

    const userMsg: Message = { id: Date.now() + "u", role: "user", text: question };
    const loadingMsg: Message = { id: Date.now() + "a", role: "assistant", text: "", loading: true };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setLoading(true);

    try {
      const res = await fetch(`${API}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fileId, question }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessages((prev) =>
          prev.map((m) => m.loading ? { ...m, loading: false, error: data.detail || "Query failed" } : m)
        );
        return;
      }

      const queryType = data.query_type || "aggregation";

      setMessages((prev) =>
        prev.map((m) =>
          m.loading ? {
            ...m,
            loading: false,
            text: buildSummaryText(queryType, data),
            intent: data.intent,
            result: data.result,
            suggestions: data.suggestions,
            recommendation: data.recommendation,
            queryType,
          } : m
        )
      );
    } catch (e: any) {
      setMessages((prev) =>
        prev.map((m) => m.loading
          ? { ...m, loading: false, error: "Network error. Is the server running?" }
          : m
        )
      );
    } finally {
      setLoading(false);
    }
  }

  function buildSummaryText(queryType: string, data: any): string {
    if (queryType === "recommendation") {
      const top = data.recommendation?.top_pick;
      return top
        ? `Here are your product recommendations. Top pick: **${top}**.`
        : "Here are your product recommendations ranked by performance:";
    }
    if (queryType === "suggestion") {
      return `Here are ${data.suggestions?.length || 0} business recommendations based on your data:`;
    }

    const intent = data.intent;
    const result = data.result;
    if (!intent || !result) return "Here are the results:";

    const metric = intent.metric;
    const field = intent.field?.replace(/_/g, " ");
    const results = result?.results || [];

    if (results.length === 1 && "value" in results[0]) {
      const val = results[0].value;
      const formatted = typeof val === "number"
        ? val.toLocaleString(undefined, { maximumFractionDigits: 2 })
        : val;
      return `The ${metric} of ${field} is **${formatted}**.`;
    }
    if (results.length > 1) return `Here's the ${metric} of ${field} breakdown:`;
    if (result?.message) return result.message;
    return "Here are the results:";
  }

  const canQuery = fileId && mappingDone;

  if (!fileId) {
    return (
      <div className="chat-container">
        <div className="empty-state">
          <div className="empty-state-icon">📊</div>
          <div className="empty-state-title">Ask anything about<br />your data</div>
          <div className="empty-state-subtitle">Upload a CSV file from the sidebar to get started.</div>
        </div>
      </div>
    );
  }

  if (fileId && !mappingDone) {
    return (
      <div className="chat-container">
        <div className="empty-state">
          <div className="empty-state-icon">🗂️</div>
          <div className="empty-state-title">One more step</div>
          <div className="empty-state-subtitle">
            Click <strong>Generate Mapping</strong> in the sidebar to let the AI understand your column structure.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-container">
      {messages.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">✨</div>
          <div className="empty-state-title">Ready to answer<br />your questions</div>
          <div className="empty-state-subtitle">
            Ask for numbers, trends, product recommendations, or business advice.
          </div>
          <div className="empty-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="suggestion-chip" onClick={() => sendQuery(s)}>{s}</button>
            ))}
          </div>
        </div>
      ) : (
        <div className="messages-area">
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="message-avatar">
                {msg.role === "user" ? "U" : "AI"}
              </div>
              <div className="message-content">
                {msg.loading ? (
                  <div className="message-bubble">
                    <div className="loading-dots"><span /><span /><span /></div>
                  </div>
                ) : msg.error ? (
                  <div className="error-banner">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
                      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    {msg.error}
                  </div>
                ) : (
                  <>
                    <div className="message-bubble">
                      {msg.text.split(/\*\*(.+?)\*\*/).map((part, i) =>
                        i % 2 === 1 ? <strong key={i}>{part}</strong> : part
                      )}
                    </div>

                    {/* Intent pills — aggregation only */}
                    {msg.intent && msg.queryType === "aggregation" && (
                      <div className="intent-pills">
                        <span className="intent-pill">⚡ {msg.intent.metric}</span>
                        <span className="intent-pill">📌 {msg.intent.field}</span>
                        {msg.intent.group_by && <span className="intent-pill">📅 {msg.intent.group_by}</span>}
                        {msg.intent.filters?.map((f: any, i: number) => (
                          <span key={i} className="intent-pill">
                            🔍 {f.field} {f.operator} {Array.isArray(f.value) ? f.value.join(" – ") : f.value}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Result card */}
                    {msg.result && (msg.queryType === "aggregation" || msg.queryType === "both") && (
                      <ResultCard result={msg.result} intent={msg.intent} />
                    )}

                    {/* Suggestion cards */}
                    {msg.suggestions && msg.suggestions.length > 0 &&
                      (msg.queryType === "suggestion" || msg.queryType === "both") && (
                      <SuggestionCards suggestions={msg.suggestions} />
                    )}

                    {/* Recommendation card */}
                    {msg.recommendation && msg.queryType === "recommendation" && (
                      <RecommendationCard recommendation={msg.recommendation} />
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder={canQuery ? "Ask a question, request analysis, or get product recommendations…" : "Upload and map a file first"}
            value={input}
            disabled={!canQuery || loading}
            onChange={(e) => { setInput(e.target.value); autoResize(); }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendQuery(input); }
            }}
          />
          <button className="send-btn" disabled={!input.trim() || !canQuery || loading} onClick={() => sendQuery(input)}>
            {loading ? (
              <div className="spinner" style={{ width: 12, height: 12 }} />
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            )}
          </button>
        </div>
        <div className="input-hint">Press Enter to send · Shift+Enter for new line</div>
      </div>
    </div>
  );
}