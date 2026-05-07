"use client";

import { useState, useRef, useEffect } from "react";
import ResultCard from "./ResultCard";
import SuggestionCards from "./SuggestionCards";
import RecommendationCard from "./RecommendationCard";
import DynamicRenderer from "./DynamicRenderer";

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
  records?: any[];
  queryType?: "aggregation" | "suggestion" | "recommendation" | "list_records" | "both";
  error?: string;
  loading?: boolean;
}

interface Props {
  fileId: string | null;
  chatId: string | null;
  onChatStarted: (id: string) => void;
  onQueryDone?: () => void;
}

export default function QueryChat({ fileId, chatId, onChatStarted, onQueryDone }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isNewChatRef = useRef(false);
  const [language, setLanguage] = useState("English");
  const [complexity, setComplexity] = useState("Simple (Explain like I'm 5)");

  // Auto scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load Past Messages when a chat from the sidebar is clicked
  useEffect(() => {
    if (!chatId) {
      setMessages([]);
      return;
    }

    if (isNewChatRef.current) {
      isNewChatRef.current = false;
      return; 
    }

    setMessages([]);

    async function loadPastChat() {
      const token = localStorage.getItem("token");
      if (!token) return;
      
      try {
        const res = await fetch(`${API}/auth/chats/${chatId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const data = await res.json();
        
        if (data.messages) {
          const restoredMessages: Message[] = [];
          data.messages.forEach((m: any, i: number) => {
            // User Message
            restoredMessages.push({ id: `hist-${i}-u`, role: "user", text: m.question });
            
            // AI Message
            const resData = m.response || {};
            const qType = resData.query_type || "aggregation";
            restoredMessages.push({
              id: `hist-${i}-a`,
              role: "assistant",
              text: buildSummaryText(qType, resData),
              intent: resData.intent,
              result: resData.result,
              suggestions: resData.suggestions,
              recommendation: resData.recommendation,
              queryType: qType,
            });
          });
          setMessages(restoredMessages);
        }
      } catch (e) {
        console.error("Failed to load past messages");
      }
    }
    
    loadPastChat();
  }, [chatId]);

  function autoResize() {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
  }

  async function sendQuery(question: string) {
    if (!question.trim() || !fileId || loading) return;

    // Determine active Chat ID or create a new one
    const activeChatId = chatId || (Math.random().toString(36).substring(2, 15) + Date.now().toString(36));
    
    if (!chatId) {
      isNewChatRef.current = true;
      onChatStarted(activeChatId);
    }

    const userMsg: Message = { id: Date.now() + "u", role: "user", text: question };
    const loadingMsg: Message = { id: Date.now() + "a", role: "assistant", text: "", loading: true };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setLoading(true);

    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`${API}/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({ file_id: fileId, question, chat_id: activeChatId, language: language, complexity: complexity.split(' ')[0] }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessages((prev) =>
          prev.map((m) =>
            m.loading ? { ...m, loading: false, error: data.detail || "Query failed" } : m
          )
        );
        return;
      }

      const queryType = data.query_type || "aggregation";
      setMessages((prev) =>
        prev.map((m) =>
          m.loading
            ? {
                ...m,
                loading: false,
                text: buildSummaryText(queryType, data),
                intent: data.intent,
                result: data.result,
                suggestions: data.suggestions,
                recommendation: data.recommendation,
                records: data.records, 
                queryType,
              }
            : m
        )
      );

      // Tell sidebar to refresh history
      if (token) onQueryDone?.();

    } catch (e: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.loading
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
    if (queryType === "list_records") {
      return `Here are the top ${data.records?.length || 0} records matching your criteria:`;
    }

    const intent = data.intent;
    const result = data.result;
    if (!intent || !result) return "Here are the results:";

    const metric = intent.metric;
    const field = intent.field?.replace(/_/g, " ");
    const results = result?.results || [];

    if (results.length === 1 && "value" in results[0]) {
      const val = results[0].value;
      const formatted =
        typeof val === "number"
          ? val.toLocaleString(undefined, { maximumFractionDigits: 2 })
          : val;
      return `The ${metric} of ${field} is **${formatted}**.`;
    }
    if (results.length > 1) return `Here's the ${metric} of ${field} breakdown:`;
    if (result?.message) return result.message;
    return "Here are the results:";
  }

  const canQuery = !!fileId;

  if (!fileId) {
    return (
      <div className="chat-container">
        <div className="empty-state">
          <div className="empty-state-icon">📊</div>
          <div className="empty-state-title">
            Ask anything about
            <br />
            your data
          </div>
          <div className="empty-state-subtitle">
            Upload a CSV file from the sidebar to get started.
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
          <div className="empty-state-title">
            Ready to answer
            <br />
            your questions
          </div>
          <div className="empty-state-subtitle">
            Ask for numbers, trends, product recommendations, or business advice.
          </div>
          <div className="empty-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="suggestion-chip" onClick={() => sendQuery(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="messages-area">
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="message-avatar">{msg.role === "user" ? "U" : "AI"}</div>
              <div className="message-content">
                {msg.loading ? (
                  <div className="message-bubble">
                    <div className="loading-dots">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                ) : msg.error ? (
                  <div className="error-banner">
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      style={{ flexShrink: 0 }}
                    >
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
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

                    {/* Intent pills */}
                    {msg.intent && msg.queryType === "aggregation" && (
                      <div className="intent-pills">
                        <span className="intent-pill">⚡ {msg.intent.metric}</span>
                        <span className="intent-pill">📌 {msg.intent.field}</span>
                        {msg.intent.group_by && (
                          <span className="intent-pill">📅 {msg.intent.group_by}</span>
                        )}
                        {msg.intent.filters?.map((f: any, i: number) => (
                          <span key={i} className="intent-pill">
                            🔍 {f.field} {f.operator}{" "}
                            {Array.isArray(f.value) ? f.value.join(" – ") : f.value}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Unified Data & Visualization Renderer */}
                    {(msg.result || msg.records) &&
                      (msg.queryType === "aggregation" || msg.queryType === "both" || msg.queryType === "list_records") && (
                        <DynamicRenderer msg={msg} />
                    )}

                    {/* Suggestion cards */}
                    {msg.suggestions &&
                      msg.suggestions.length > 0 &&
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
        {/* 👇 NEW CONTROLS */}
        {canQuery && (
          <div style={{ display: "flex", gap: "10px", marginBottom: "8px", padding: "0 4px" }}>
            <select 
              value={language} 
              onChange={(e) => setLanguage(e.target.value)}
              style={{ padding: "4px 8px", borderRadius: "6px", fontSize: "12px", background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
            >
              <option value="English">🇬🇧 English</option>
              <option value="Marathi">🇮🇳 Marathi</option>
              <option value="Hindi">🇮🇳 Hindi</option>
              <option value="Spanish">🇪🇸 Spanish</option>
            </select>

            <select 
              value={complexity} 
              onChange={(e) => setComplexity(e.target.value)}
              style={{ padding: "4px 8px", borderRadius: "6px", fontSize: "12px", background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
            >
              <option value="Simple (Explain like I'm 5)">🧸 Simple (Explain like I'm 5)</option>
              <option value="Executive (Professional)">👔 Executive (Professional)</option>
              <option value="Technical (Data focused)">💻 Technical</option>
            </select>
          </div>
        )}
        {/* 👆 END NEW CONTROLS */}
        
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder={
              canQuery
                ? "Ask a question, request analysis, or get product recommendations…"
                : "Upload a file first"
            }
            value={input}
            disabled={!canQuery || loading}
            onChange={(e) => {
              setInput(e.target.value);
              autoResize();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendQuery(input);
              }
            }}
          />
          <button
            className="send-btn"
            disabled={!input.trim() || !canQuery || loading}
            onClick={() => sendQuery(input)}
          >
            {loading ? (
              <div className="spinner" style={{ width: 12, height: 12 }} />
            ) : (
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <div className="input-hint">Press Enter to send · Shift+Enter for new line</div>
      </div>
    </div>
  );
}