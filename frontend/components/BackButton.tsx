"use client";

import { useRouter } from "next/navigation";

export function BackButton({ fallbackHref, label = "Voltar" }: { fallbackHref: string; label?: string }) {
  const router = useRouter();
  return (
    <button
      onClick={() => {
        if (window.history.length > 1) router.back();
        else router.push(fallbackHref);
      }}
      className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-800"
    >
      ← {label}
    </button>
  );
}
