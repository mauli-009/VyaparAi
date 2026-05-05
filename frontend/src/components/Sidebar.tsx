"use client";

import { useState, useRef, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
  fileId: string | null;
  fileName: string | null;
  currentChatId: string | null;
  historyTrigger: number;
  onFileUploaded: (id: string, name: string) => void;
  onChatSelect: (chatId: string, fileId: string) => void;
  onNewChat: () => void;
}

export default function Sidebar({
  fileId,
  fileName,
  currentChatId,
  historyTrigger,
  onFileUploaded,
  onChatSelect,
  onNewChat
}: Props) {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auth & History states
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [history, setHistory] = useState<any[]>([]);

  // Modals & Menus
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [isLogin, setIsLogin] = useState(true);

  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  // Load token on mount
  useEffect(() => {
    const t = localStorage.getItem("token");
    const e = localStorage.getItem("email");
    if (t) {
      setToken(t);
      setEmail(e);
      fetchHistory(t);
    }
  }, []);

  // Re-fetch history whenever a new query is made
  useEffect(() => {
    if (historyTrigger > 0 && token) {
      fetchHistory(token);
    }
  }, [historyTrigger, token]);

  async function fetchHistory(jwt: string) {
    try {
      const res = await fetch(`${API}/auth/chats`, {
        headers: { Authorization: `Bearer ${jwt}` },
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data.chats || []);
      }
    } catch (e) {
      console.error("Failed to fetch chats", e);
    }
  }

  async function handleAuth(e: React.FormEvent) {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const endpoint = isLogin ? "/auth/login" : "/auth/register";
      const res = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: authEmail, password: authPassword }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Authentication failed");

      localStorage.setItem("token", data.token);
      localStorage.setItem("email", data.email);
      setToken(data.token);
      setEmail(data.email);
      setShowAuthModal(false);
      setAuthEmail("");
      setAuthPassword("");
      fetchHistory(data.token);
    } catch (err: any) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    setToken(null);
    setEmail(null);
    setHistory([]);
    setShowProfileMenu(false);
    onNewChat(); // Clear screen on logout
  }

  async function handleFile(file: File) {
    // Extra safety check just in case
    if (!token) {
      setShowAuthModal(true);
      return;
    }
    
    if (!file.name.endsWith(".csv")) return setError("Only CSV files are supported.");
    setError(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
      const data = await res.json();
      onFileUploaded(data.file_id, file.name);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  function formatDate(dateStr: string) {
    // FIX 1: Ensure the browser treats the string as UTC by appending "Z"
    const safeDateStr = dateStr.endsWith("Z") ? dateStr : `${dateStr}Z`;
    const d = new Date(safeDateStr);
    const now = new Date();
    
    const diff = now.getTime() - d.getTime();
    const mins = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days === 1) return "yesterday";
    return d.toLocaleDateString();
  }

  return (
    <aside className="sidebar">
      {/* ── Auth Modal ── */}
      {showAuthModal && (
        <div className="modal-overlay" onClick={() => setShowAuthModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowAuthModal(false)}>✕</button>
            <h2 className="modal-title">{isLogin ? "Welcome back" : "Create account"}</h2>

            <form onSubmit={handleAuth}>
              <div className="form-group">
                <label>Email address</label>
                <input
                  type="email"
                  required
                  className="form-input"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  required
                  className="form-input"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                />
              </div>

              {authError && (
                <div className="error-banner" style={{ marginBottom: 12 }}>
                  {authError}
                </div>
              )}

              <button type="submit" className="btn btn-primary btn-full" disabled={authLoading}>
                {authLoading ? <div className="spinner" /> : isLogin ? "Sign In" : "Sign Up"}
              </button>
            </form>

            <div className="auth-switch">
              {isLogin ? "Don't have an account? " : "Already have an account? "}
              <button type="button" onClick={() => { setIsLogin(!isLogin); setAuthError(null); }}>
                {isLogin ? "Sign up" : "Sign in"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Header ── */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">Q</div>
          <span className="sidebar-logo-name">QueryMind</span>
        </div>
        <div className="sidebar-tagline">Natural language analytics</div>
      </div>

      <div className="sidebar-body">
        {/* ── Upload Section ── */}
        <div>
          <div className="sidebar-section-label">Active Dataset</div>
          {!fileId ? (
            <div
              className={`upload-zone ${dragOver ? "drag-over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                // FIX 2: Block drop if not logged in
                if (!token) {
                  setShowAuthModal(true);
                  return;
                }
                const file = e.dataTransfer.files[0];
                if (file) handleFile(file);
              }}
              onClick={(e) => {
                // FIX 2: Block click if not logged in
                if (!token) {
                  e.preventDefault();
                  setShowAuthModal(true);
                } else {
                  inputRef.current?.click();
                }
              }}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv"
                onChange={(e) => {
                  if (!token) {
                    setShowAuthModal(true);
                    return;
                  }
                  const file = e.target.files?.[0];
                  if (file) handleFile(file);
                }}
              />
              <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {uploading ? (
                <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text-secondary)" }}>
                  <div className="spinner spinner-dark" /> Analyzing columns...
                </div>
              ) : (
                <>
                  <div className="upload-text"><strong>Click to upload</strong> or drag & drop</div>
                  <div className="upload-hint">CSV files only</div>
                </>
              )}
            </div>
          ) : (
            <div className="file-card">
              <div className="file-card-header">
                <div className="file-card-icon">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <div className="file-card-info">
                  <div className="file-card-name">{fileName}</div>
                  <div className="file-card-id" style={{ color: "var(--success)" }}>Ready to analyze</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Upload Error ── */}
        {error && (
          <div className="error-banner">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            {error}
          </div>
        )}

        {/* ── History Section ── */}
        {token && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div className="sidebar-section-label" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 10 }}>
              <span>Recent Chats</span>
              <button 
                onClick={onNewChat}
                style={{ background: "none", border: "none", color: "var(--accent)", cursor: "pointer", fontSize: 11, fontWeight: 700 }}
              >
                + New Chat
              </button>
            </div>

            {history.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--text-muted)", padding: "10px 4px", lineHeight: 1.5 }}>
                No history yet. Ask a question to get started.
              </div>
            ) : (
              <div className="history-list" style={{ overflowY: "auto", flex: 1, paddingRight: 4 }}>
                {history.map((h) => {
                  const isActive = h.chat_id === currentChatId;
                  return (
                    <div 
                      key={h.chat_id} 
                      className="history-item"
                      onClick={() => onChatSelect(h.chat_id, h.file_id)}
                      style={{ 
                        background: isActive ? "var(--surface-hover)" : "transparent",
                        borderLeft: isActive ? "3px solid var(--accent)" : "3px solid transparent",
                        paddingLeft: isActive ? "9px" : "12px"
                      }}
                    >
                      <div className="history-question" style={{ color: isActive ? "var(--accent)" : "var(--text-primary)" }}>
                        {h.title}
                      </div>
                      <div className="history-meta">{formatDate(h.updated_at)}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── Profile / Auth Footer ── */}
        <div className="auth-footer">
          {token ? (
            <div className="profile-container">
              {showProfileMenu && (
                <>
                  <div style={{ position: "fixed", inset: 0, zIndex: 99 }} onClick={() => setShowProfileMenu(false)} />
                  <div className="profile-popover">
                    <button className="popover-item">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
                      </svg>
                      My Account
                    </button>
                    <div className="popover-divider" />
                    <button className="popover-item danger" onClick={logout}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
                      </svg>
                      Sign Out
                    </button>
                  </div>
                </>
              )}
              <button className="profile-btn" onClick={() => setShowProfileMenu(!showProfileMenu)}>
                <div className="profile-avatar">{email?.charAt(0).toUpperCase()}</div>
                <div className="profile-info">
                  <div className="profile-email">{email}</div>
                  <div className="profile-action">Free Plan</div>
                </div>
              </button>
            </div>
          ) : (
            <button className="profile-btn" onClick={() => setShowAuthModal(true)}>
              <div className="profile-avatar" style={{ background: "var(--surface-hover)", color: "var(--text-muted)" }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
                </svg>
              </div>
              <div className="profile-info">
                <div className="profile-email" style={{ color: "var(--text-secondary)" }}>Not signed in</div>
                <div className="profile-action" style={{ color: "var(--accent)" }}>Sign in to upload data</div>
              </div>
            </button>
          )}
        </div>

      </div>
    </aside>
  );
}