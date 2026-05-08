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
  "Which product should I choose long-term?",
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
  queryType?: "aggregation" | "suggestion" | "recommendation" | "list_records" | "both" | "text"; // <-- ADDED "text" HERE
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
  const [showControls, setShowControls] = useState(false);
  const [language, setLanguage] = useState("English");
  const [complexity, setComplexity] = useState("Simple (Explain like I'm 5)");
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);

  const bottomRef      = useRef<HTMLDivElement>(null);
  const textareaRef    = useRef<HTMLTextAreaElement>(null);
  const isNewChatRef   = useRef(false);
  const recognitionRef = useRef<any>(null);
  // Ref tracks intended listening state — needed because Chrome fires onend
  // spuriously with continuous:true, requiring a restart from inside the handler.
  const shouldListenRef = useRef(false);

  useEffect(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    setVoiceSupported(!!SR);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!chatId) { setMessages([]); return; }
    if (isNewChatRef.current) { isNewChatRef.current = false; return; }
    setMessages([]);
    async function loadPastChat() {
      const token = localStorage.getItem("token");
      if (!token) return;
      try {
        const res = await fetch(`${API}/auth/chats/${chatId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (data.messages) {
          const restored: Message[] = [];
          data.messages.forEach((m: any, i: number) => {
            restored.push({ id: `h-${i}-u`, role: "user", text: m.question });
            const rd = m.response || {};
            const qt = rd.query_type || "aggregation";
            restored.push({
              id: `h-${i}-a`,
              role: "assistant",
              text: buildSummaryText(qt, rd),
              intent: rd.intent,
              result: rd.result,
              suggestions: rd.suggestions,
              recommendation: rd.recommendation,
              queryType: qt,
            });
          });
          setMessages(restored);
        }
      } catch {
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
    const activeChatId = chatId || (Math.random().toString(36).substring(2, 15) + Date.now().toString(36));
    if (!chatId) { isNewChatRef.current = true; onChatStarted(activeChatId); }

    setMessages((p) => [
      ...p,
      { id: Date.now() + "u", role: "user",      text: question },
      { id: Date.now() + "a", role: "assistant",  text: "", loading: true },
    ]);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setLoading(true);

    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`${API}/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          file_id: fileId,
          question,
          chat_id: activeChatId,
          language,
          complexity: complexity.split(" ")[0],
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessages((p) => p.map((m) => m.loading ? { ...m, loading: false, error: data.detail || "Query failed" } : m));
        return;
      }

      const queryType = data.query_type || "aggregation";
      // Use backend's natural language summary if available, else build one
      const summaryText = data.summary || buildSummaryText(queryType, data);
      setMessages((p) =>
        p.map((m) =>
          m.loading
            ? { ...m, loading: false, text: summaryText,
                intent: data.intent, result: data.result,
                suggestions: data.suggestions, recommendation: data.recommendation,
                records: data.records, queryType }
            : m
        )
      );
      const t2 = localStorage.getItem("token");
      if (t2) onQueryDone?.();
    } catch {
      setMessages((p) => p.map((m) => m.loading ? { ...m, loading: false, error: "Network error. Is the server running?" } : m));
    } finally {
      setLoading(false);
    }
  }

  function buildSummaryText(queryType: string, data: any): string {
    if (queryType === "recommendation") {
      const top = data.recommendation?.top_pick;
      return top ? `Here are your product recommendations. Top pick: **${top}**.` : "Here are your product recommendations ranked by performance:";
    }
    if (queryType === "list_records") return `Here are the top ${data.records?.length || 0} records matching your criteria:`;
    const intent = data.intent;
    const result = data.result;
    if (!intent || !result) return "Here are the results:";
    const metric = intent.metric;
    const field  = intent.field?.replace(/_/g, " ");
    const rows   = result?.results || [];
    if (rows.length === 1 && "value" in rows[0]) {
      const val = rows[0].value;
      const formatted = typeof val === "number" ? val.toLocaleString(undefined, { maximumFractionDigits: 2 }) : val;
      return `The ${metric} of ${field} is **${formatted}**.`;
    }
    if (rows.length > 1) return `Here's the ${metric} of ${field} breakdown:`;
    if (result?.message) return result.message;
    return "Here are the results:";
  }

  function startVoice() {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;

    shouldListenRef.current = true;
    setIsListening(true);

    function createAndStart() {
      const rec = new SR();
      rec.continuous      = true;
      rec.interimResults  = true;
      rec.lang            = "en-US";
      rec.maxAlternatives = 1;

      rec.onstart = () => setIsListening(true);

      // Chrome often fires onend after ~1s even with continuous:true.
      // Auto-restart if we still intend to listen.
      rec.onend = () => {
        if (shouldListenRef.current) {
          try { createAndStart(); } catch {}
        } else {
          setIsListening(false);
        }
      };

      rec.onerror = (e: any) => {
        if (e.error === "not-allowed" || e.error === "permission-denied") {
          shouldListenRef.current = false;
          setIsListening(false);
          alert("Microphone access denied. Please enable microphone access in your browser settings and try again.");
        } else if (e.error === "aborted") {
          // Expected when we call .stop() ourselves — ignore
        } else {
          console.warn("Speech recognition error:", e.error);
        }
      };

      rec.onresult = (e: any) => {
        // Rebuild full transcript from all accumulated results each time
        let transcript = "";
        for (let i = 0; i < e.results.length; i++) {
          transcript += e.results[i][0].transcript;
        }
        setInput(transcript);
        autoResize();
      };

      recognitionRef.current = rec;
      try { rec.start(); } catch (err) {
        console.error("SpeechRecognition start failed:", err);
        shouldListenRef.current = false;
        setIsListening(false);
      }
    }

    createAndStart();
  }

  function stopVoice() {
    shouldListenRef.current = false;
    try { recognitionRef.current?.stop(); } catch {}
    setIsListening(false);
  }

  /* ── No file uploaded ── */
  if (!fileId) {
    return (
      <div className="chat-root">
        <EmptyState icon="📊" title={<>Ask anything about<br />your data</>} subtitle="Upload a CSV file from the sidebar to get started." />
      </div>
    );
  }

  return (
    <div className="chat-root">

      {messages.length === 0 ? (
        <div className="chat-empty">
          <EmptyState
            icon="✨"
            title={<>Ready to answer<br />your questions</>}
            subtitle="Ask for numbers, trends, product recommendations, or business advice."
          />
          <div className="suggestion-grid">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="suggestion-chip" onClick={() => sendQuery(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="messages-area">
          {messages.map((msg) => <MessageRow key={msg.id} msg={msg} />)}
          <div ref={bottomRef} style={{ height: 12 }} />
        </div>
      )}

      {/* ── Input ── */}
      <div className="input-area">
        <div>
          <button
            className="controls-toggle"
            onClick={() => setShowControls((v) => !v)}
            title="Response settings"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="4" y1="6" x2="20" y2="6" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="18" x2="20" y2="18" />
              <circle cx="8" cy="6" r="2" style={{ fill: "var(--surface)" }} /><circle cx="16" cy="12" r="2" style={{ fill: "var(--surface)" }} /><circle cx="10" cy="18" r="2" style={{ fill: "var(--surface)" }} />
            </svg>
            {language} · {complexity.split(" ")[0]}
            <span style={{ opacity: 0.45, fontSize: 9 }}>{showControls ? "▲" : "▼"}</span>
          </button>
        </div>

        {showControls && (
          <div className="controls-panel">
            <div className="control-group">
              <label className="control-label">Language</label>
              <select className="control-select" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="English">🇬🇧 English</option>
                <option value="Marathi">🇮🇳 Marathi</option>
                <option value="Hindi">🇮🇳 Hindi</option>
                <option value="Spanish">🇪🇸 Spanish</option>
                <option value="French">🇫🇷 French</option>
                <option value="German">🇩🇪 German</option>
              </select>
            </div>
            <div className="control-group">
              <label className="control-label">Response Style</label>
              <select className="control-select" value={complexity} onChange={(e) => setComplexity(e.target.value)}>
                <option value="Simple (Explain like I'm 5)">Simple (ELI5)</option>
                <option value="Normal">Normal</option>
                <option value="Technical (Expert-level)">Technical</option>
              </select>
            </div>
          </div>
        )}

        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => { setInput(e.target.value); autoResize(); }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendQuery(input);
              }
            }}
            placeholder={isListening ? "🎤 Listening…" : "Ask anything about your data…"}
            disabled={loading}
          />

          {/* Mic button — Web Speech API, no API key, completely free */}
          {voiceSupported && (
            <button
              onClick={isListening ? stopVoice : startVoice}
              disabled={loading}
              title={isListening ? "Click to stop recording and send" : "Click to speak your question"}
              style={{
                width: 34, height: 34, borderRadius: "var(--r-md)", border: "none",
                flexShrink: 0, cursor: loading ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
                background: isListening ? "var(--error)" : "var(--surface-2)",
                color: isListening ? "white" : "var(--text-2)",
                transition: "all 0.15s",
                boxShadow: isListening ? "0 0 0 4px rgba(239,68,68,0.2)" : "none",
              }}
            >
              {isListening ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="6" width="12" height="12" rx="2"/>
                </svg>
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" y1="19" x2="12" y2="23"/>
                  <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
              )}
            </button>
          )}

          <button
            className="send-btn"
            onClick={() => sendQuery(input)}
            disabled={!input.trim() || loading}
          >
            {loading ? (
              <span style={{
                display: "inline-block", width: 12, height: 12,
                border: "2px solid rgba(255,255,255,0.35)",
                borderTopColor: "#fff", borderRadius: "50%",
                animation: "spin 0.7s linear infinite",
              }} />
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>

        <p className="input-hint">
          Enter to send · Shift+Enter for new line
          {voiceSupported && " · 🎤 Click mic to speak"}
        </p>
      </div>
    </div>
  );
}

/* ── MessageRow ── */
function MessageRow({ msg }: { msg: Message }) {
  if (msg.role === "user") {
    return (
      <div className="message user">
        <div className="msg-avatar user-av">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <div className="msg-body">
          <div className="msg-bubble">{msg.text}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="message assistant">
      <div className="msg-avatar ai-av">QM</div>
      <div className="msg-body">
        {msg.loading ? (
          <div className="msg-bubble">
            <div className="loading-dots">
              <span /><span /><span />
            </div>
          </div>
        ) : msg.error ? (
          <div className="msg-bubble" style={{ background: "var(--error-dim)", borderColor: "rgba(220,38,38,0.2)", color: "var(--error)" }}>
            ⚠ {msg.error}
          </div>
        ) : (
          <>
            <div className="msg-bubble">
              <FormattedText text={msg.text} />
            </div>
            {/* Intent pills only make sense for data queries, not general answers */}
            {msg.intent && msg.queryType !== "text" && <IntentPills intent={msg.intent} />}
            {(msg.queryType === "aggregation" || msg.queryType === "both") && msg.result && (
              <DynamicRenderer msg={msg} />
            )}
            {msg.queryType === "list_records" && (
              <DynamicRenderer msg={msg} />
            )}
            {(msg.queryType === "suggestion" || msg.queryType === "both") && msg.suggestions && (
              <SuggestionCards suggestions={msg.suggestions} />
            )}
            {msg.queryType === "recommendation" && msg.recommendation && (
              <RecommendationCard recommendation={msg.recommendation} />
            )}
            {/* general: just the text bubble — no data cards needed */}
          </>
        )}
      </div>
    </div>
  );
}

function FormattedText({ text }: { text: string }) {
  const parts = text.split(/\*\*(.*?)\*\*/g);
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1
          ? <strong key={i} style={{ fontWeight: 700, color: "var(--text-1)" }}>{p}</strong>
          : <span key={i}>{p}</span>
      )}
    </>
  );
}

function IntentPills({ intent }: { intent: any }) {
  // Don't show pills for suggestion/general responses — they're not field-specific queries
  const skipTypes = ["suggestion", "both", "recommendation", "general"];
  if (!intent || skipTypes.includes(intent.action)) return null;

  const pills: string[] = [];
  // Only show metric if there's also a real field — avoids orphaned "sum" pills
  const hasRealField = intent.field && intent.field !== "None" && intent.field !== "unknown";
  if (intent.metric && hasRealField) pills.push(intent.metric);
  if (hasRealField) pills.push(intent.field.replace(/_/g, " "));
  if (intent.group_by) pills.push(`by ${String(intent.group_by).replace(/_/g, " ").replace(/\w+\((.+)\)/, "$1")}`);
  if (!pills.length) return null;

  return (
    <div className="intent-pills">
      {pills.map((p) => (
        <span key={p} className="intent-pill">{p}</span>
      ))}
    </div>
  );
}

function EmptyState({ icon, title, subtitle }: { icon: string; title: React.ReactNode; subtitle: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, paddingBottom: 8 }}>
      <div className="empty-icon-wrap">{icon}</div>
      <h2 className="empty-title">{title}</h2>
      <p className="empty-subtitle">{subtitle}</p>
    </div>
  );
}