"use client";

import { useState } from "react";
import { ApiError, api } from "@/lib/api";

export function DownloadButton({
  path, filename, children, className,
}: { path: string; filename: string; children: React.ReactNode; className?: string }) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    setLoading(true);
    try {
      const blob = await api.getBlob(path);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Não foi possível baixar o arquivo.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <button onClick={handleClick} disabled={loading} className={className}>
      {children}
    </button>
  );
}
