"use client";

import { useState, useRef, useEffect } from "react";
import QueryChat from "@/components/QueryChat";
import Sidebar from "@/components/Sidebar";

export default function Home() {
  const [fileId, setFileId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [mappingDone, setMappingDone] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar
        fileId={fileId}
        fileName={fileName}
        mappingDone={mappingDone}
        onFileUploaded={(id, name) => {
          setFileId(id);
          setFileName(name);
          setMappingDone(false);
        }}
        onMappingDone={() => setMappingDone(true)}
      />
      <main className="main-area">
        <QueryChat fileId={fileId} mappingDone={mappingDone} />
      </main>
    </div>
  );
}
