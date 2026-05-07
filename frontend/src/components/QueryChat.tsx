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
  queryType?: "aggregation" | "suggestion" | "recommendation" | "list_records" | "both" | "text";
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
  
  // Track the last checked file to prevent race conditions on the health check
  const [lastCheckedFile, setLastCheckedFile] = useState<string | null>(null);
  
  const [language, setLanguage] = useState("English");
  const [complexity, setComplexity] = useState("Simple (Explain like I'm 5)");

// 🎙️ Voice Recognition State
const [isListening, setIsListening] = useState(false);
const recognitionRef = useRef<any>(null);
const isListeningRef = useRef(false); // mirrors isListening for use inside callbacks

// Auto-resize textarea whenever 'input' changes
useEffect(() => {
  if (textareaRef.current) {
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + "px";
  }
}, [input]);

// Initialize Speech Recognition
useEffect(() => {
  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  
  if (!SpeechRecognition) return;

  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  recognition.onresult = (event: any) => {
    // Only collect results from the current session start (resultIndex),
    // not the full accumulated list — prevents duplicate/overwritten text.
    let finalTranscript = "";
    let interimTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcript;
      } else {
        interimTranscript += transcript;
      }
    }

    setInput((prev) => {
      // Append final words; show interim as a preview suffix
      const base = prev + finalTranscript;
      return interimTranscript ? base + interimTranscript : base;
    });
  };

  recognition.onerror = (event: any) => {
    console.error("Microphone error:", event.error);
    if (event.error === "not-allowed") {
      alert("Microphone blocked! Click the mic/camera icon in your browser's address bar and choose 'Allow'.");
    }
    isListeningRef.current = false;
    setIsListening(false);
  };

  recognition.onend = () => {
    // If the user hasn't manually stopped, restart to keep listening continuously.
    // (Browsers auto-stop recognition after silence; this resumes it.)
    if (isListeningRef.current) {
      try {
        recognition.start();
      } catch {
        // already started — ignore
      }
    } else {
      setIsListening(false);
    }
  };

  recognitionRef.current = recognition;
}, []);

// Update microphone language when user changes the dropdown
useEffect(() => {
  if (recognitionRef.current) {
    const langMap: Record<string, string> = {
      "English": "en-US",
      "Marathi": "mr-IN",
      "Hindi": "hi-IN",
      "Spanish": "es-ES"
    };
    recognitionRef.current.lang = langMap[language] || "en-US";
  }
}, [language]);


const toggleListening = () => {
  if (!recognitionRef.current) {
    alert("Your browser does not support voice recognition. Try Google Chrome or Edge.");
    return;
  }

  if (isListeningRef.current) {
    // User wants to stop — flip ref first so onend doesn't restart
    isListeningRef.current = false;
    recognitionRef.current.stop();
    setIsListening(false);
  } else {
    setInput("");
    isListeningRef.current = true;
    setIsListening(true);
    try {
      recognitionRef.current.start();
    } catch (err) {
      console.error("Failed to start mic:", err);
      isListeningRef.current = false;
      setIsListening(false);
    }
  }
};

// (You can DELETE your old `function autoResize() { ... }` completely, 
// because FIX 1 handles it perfectly now!)
  function autoResize() {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
  }

  async function sendQuery(question: string, isHidden: boolean = false) {
    if (!question.trim() || !fileId || loading) return;

    const activeChatId = chatId || (Math.random().toString(36).substring(2, 15) + Date.now().toString(36));
    
    if (!chatId) {
      isNewChatRef.current = true;
      onChatStarted(activeChatId);
    }

    const userMsg: Message = { id: Date.now() + "u", role: "user", text: question };
    const loadingMsg: Message = { id: Date.now() + "a", role: "assistant", text: "", loading: true };
    
    if (isHidden) {
      setMessages((prev) => [...prev, loadingMsg]);
    } else {
      setMessages((prev) => [...prev, userMsg, loadingMsg]);
      setInput("");
      if (textareaRef.current) textareaRef.current.style.height = "auto";
    }
    
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
        body: JSON.stringify({ 
          file_id: fileId, 
          question, 
          chat_id: activeChatId, 
          language: language, 
          complexity: complexity.split(' ')[0] 
        }),
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
    if (queryType === "text") {
      return data.result?.message || "Request processed.";
    }
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
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    {msg.error}
                  </div>
                ) : (
                  <>
                    <div className="message-bubble" style={{ whiteSpace: "pre-wrap" }}>
                      {msg.text.split(/\*\*(.+?)\*\*/).map((part, i) =>
                        i % 2 === 1 ? <strong key={i}>{part}</strong> : part
                      )}
                    </div>

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

                    {(msg.result || msg.records) &&
                      (msg.queryType === "aggregation" || msg.queryType === "both" || msg.queryType === "list_records") && (
                        <DynamicRenderer msg={msg} />
                    )}

                    {msg.suggestions &&
                      msg.suggestions.length > 0 &&
                      (msg.queryType === "suggestion" || msg.queryType === "both") && (
                        <SuggestionCards suggestions={msg.suggestions} />
                      )}

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
        
        <div className="input-wrapper" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder={
              isListening ? "Listening... speak now" :
              canQuery ? "Ask a question, request analysis..." : "Upload a file first"
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
            style={{ flex: 1 }}
          />

          {/* 🎙️ Microphone Button */}
          <button
            onClick={toggleListening}
            disabled={!canQuery || loading}
            style={{
              background: "transparent",
              border: "none",
              cursor: (!canQuery || loading) ? "not-allowed" : "pointer",
              padding: "8px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: isListening ? "#ef4444" : "var(--text-muted)",
              transition: "0.2s"
            }}
            title="Voice Command"
          >
            {isListening ? (
              <div style={{ width: 14, height: 14, background: "#ef4444", borderRadius: 3, animation: "pulse 1.5s infinite" }} />
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
            )}
          </button>

          {/* Send Button */}
          <button
            className="send-btn"
            disabled={!input.trim() || !canQuery || loading}
            onClick={() => sendQuery(input)}
          >
            {loading ? (
              <div className="spinner" style={{ width: 12, height: 12 }} />
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
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