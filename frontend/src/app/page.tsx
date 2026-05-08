"use client";

import { useState, useEffect } from "react";
import QueryChat from "@/components/QueryChat";
import Sidebar from "@/components/Sidebar";
import DashboardView from "@/components/DashboardView";

type Tab = "chat" | "dashboard";

/* ── Sun icon ── */
function SunIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

/* ── Moon icon ── */
function MoonIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

export default function Home() {
  const [fileId, setFileId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [historyTrigger, setHistoryTrigger] = useState(0);
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [isDark, setIsDark] = useState(false);

  /* Sync with whatever the anti-flash script set */
  useEffect(() => {
    const stored = localStorage.getItem("qm-theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dark = stored === "dark" || (!stored && prefersDark);
    setIsDark(dark);
  }, []);

  function toggleTheme() {
    const next = !isDark;
    setIsDark(next);
    if (next) {
      document.documentElement.classList.add("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-theme", "light");
    }
    localStorage.setItem("qm-theme", next ? "dark" : "light");
  }

  return (
    <div className="app-shell">
      <Sidebar
        fileId={fileId}
        fileName={fileName}
        currentChatId={currentChatId}
        historyTrigger={historyTrigger}
        onFileUploaded={(id, name) => {
          setFileId(id);
          setFileName(name);
          setCurrentChatId(null);
          setActiveTab("chat");
        }}
        onChatSelect={(chatId, fId) => {
          setCurrentChatId(chatId);
          setFileId(fId);
          setFileName("Historical Dataset");
          setActiveTab("chat");
        }}
        onNewChat={() => {
          setCurrentChatId(null);
          setFileId(null);
          setFileName(null);
          setActiveTab("chat");
        }}
      />

      <main className="main-area">
        {/* ── Header ── */}
        <header className="main-header">
          {/* Left: spacer so tabs are truly centered */}
          <div style={{ width: 34 }} />

          {/* Center: Tab switcher */}
          <div className="tab-switcher">
            <button
              className={`tab-btn${activeTab === "chat" ? " is-active" : ""}`}
              onClick={() => setActiveTab("chat")}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              Query Chat
            </button>
            <button
              className={`tab-btn${activeTab === "dashboard" ? " is-active" : ""}${!fileId ? " " : ""}`}
              onClick={() => { if (fileId) setActiveTab("dashboard"); }}
              disabled={!fileId}
              title={!fileId ? "Upload a dataset first" : undefined}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
                <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
              </svg>
              Dashboard
            </button>
          </div>

          {/* Right: Dark mode toggle */}
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
          >
            {isDark ? <SunIcon /> : <MoonIcon />}
          </button>
        </header>

        {/* ── Tab panels ── */}
        <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
          <div
            style={{
              position: "absolute",
              inset: 0,
              opacity: activeTab === "chat" ? 1 : 0,
              pointerEvents: activeTab === "chat" ? "auto" : "none",
              transition: "opacity 0.18s ease",
            }}
          >
            <QueryChat
              fileId={fileId}
              chatId={currentChatId}
              onChatStarted={(id) => setCurrentChatId(id)}
              onQueryDone={() => setHistoryTrigger((n) => n + 1)}
            />
          </div>

          <div
            style={{
              position: "absolute",
              inset: 0,
              overflowY: "auto",
              opacity: activeTab === "dashboard" ? 1 : 0,
              pointerEvents: activeTab === "dashboard" ? "auto" : "none",
              transition: "opacity 0.18s ease",
            }}
          >
            <DashboardView fileId={fileId} />
          </div>
        </div>
      </main>
    </div>
  );
}