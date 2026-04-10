"use client";

import { useState, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
  fileId: string | null;
  fileName: string | null;
  mappingDone: boolean;
  onFileUploaded: (id: string, name: string) => void;
  onMappingDone: () => void;
}

export default function Sidebar({
  fileId,
  fileName,
  mappingDone,
  onFileUploaded,
  onMappingDone,
}: Props) {
  const [uploading, setUploading] = useState(false);
  const [mapping, setMapping] = useState(false);
  const [mappingData, setMappingData] = useState<Record<string, string> | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (!file.name.endsWith(".csv")) {
      setError("Only CSV files are supported.");
      return;
    }
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

  async function handleMapping() {
    if (!fileId) return;
    setMapping(true);
    setError(null);
    try {
      const res = await fetch(`${API}/mapping`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fileId }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Mapping failed");
      const data = await res.json();
      setMappingData(data.semantic_mapping);
      onMappingDone();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setMapping(false);
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">Q</div>
          <span className="sidebar-logo-name">QueryMind</span>
        </div>
        <div className="sidebar-tagline">Natural language analytics</div>
      </div>

      <div className="sidebar-body">

        {/* Upload Section */}
        <div>
          <div className="sidebar-section-label">Data Source</div>

          {!fileId ? (
            <div
              className={`upload-zone ${dragOver ? "drag-over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const file = e.dataTransfer.files[0];
                if (file) handleFile(file);
              }}
              onClick={() => inputRef.current?.click()}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFile(file);
                }}
              />
              <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              {uploading ? (
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <div className="spinner spinner-dark" />
                </div>
              ) : (
                <>
                  <div className="upload-text">
                    <strong>Click to upload</strong> or drag & drop
                  </div>
                  <div className="upload-hint">CSV files only</div>
                </>
              )}
            </div>
          ) : (
            <div className="file-card">
              <div className="file-card-header">
                <div className="file-card-icon">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <div className="file-card-info">
                  <div className="file-card-name">{fileName}</div>
                  <div className="file-card-id">{fileId?.slice(0, 16)}…</div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span className={`status-badge ${mappingDone ? "success" : "pending"}`}>
                  <span className="status-dot" />
                  {mappingDone ? "Mapped" : "Needs mapping"}
                </span>
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => window.location.reload()}
                >
                  Change
                </button>
              </div>

              {!mappingDone && (
                <button
                  className="btn btn-primary btn-full btn-sm"
                  onClick={handleMapping}
                  disabled={mapping}
                >
                  {mapping ? (
                    <><div className="spinner" /> Mapping columns…</>
                  ) : (
                    <>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      Generate Mapping
                    </>
                  )}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Mapping Preview */}
        {mappingDone && mappingData && (
          <div>
            <div className="sidebar-section-label">Column Mapping</div>
            <div className="mapping-grid">
              {Object.entries(mappingData).slice(0, 8).map(([col, key]) => (
                <div key={col} className="mapping-row">
                  <span className="mapping-col" title={col}>{col}</span>
                  <span className="mapping-arrow">→</span>
                  <span className="mapping-key" title={key}>{key}</span>
                </div>
              ))}
              {Object.keys(mappingData).length > 8 && (
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textAlign: "center", marginTop: 4 }}>
                  +{Object.keys(mappingData).length - 8} more columns
                </div>
              )}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="error-banner">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, marginTop: 1 }}>
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            {error}
          </div>
        )}

      </div>
    </aside>
  );
}
