"use client";

import { useState } from "react";
import QueryChat from "@/components/QueryChat";
import Sidebar from "@/components/Sidebar";

export default function Home() {
  const [fileId, setFileId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null); // NEW
  const [historyTrigger, setHistoryTrigger] = useState(0);

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
          setCurrentChatId(null); // Clear chat on new upload
        }}
        onChatSelect={(chatId, fId) => {
          setCurrentChatId(chatId);
          setFileId(fId);
          setFileName("Historical Dataset"); // Fallback name for past chats
        }}
        onNewChat={() => {
          setCurrentChatId(null);
          setFileId(null);
          setFileName(null);
        }}
      />
      <main className="main-area">
        <QueryChat
          fileId={fileId}
          chatId={currentChatId}
          onChatStarted={(id) => setCurrentChatId(id)}
          onQueryDone={() => setHistoryTrigger((n) => n + 1)}
        />
      </main>
    </div>
  );
}