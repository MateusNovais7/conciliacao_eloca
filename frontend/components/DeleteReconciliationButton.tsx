"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { api, ApiError } from "@/lib/api";

export function DeleteReconciliationButton({ reconciliationId, label }: { reconciliationId: string; label: string }) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();

    if (!window.confirm(`Excluir a conciliação de ${label}? Os arquivos importados continuam salvos — só o resultado da conciliação é apagado.`)) {
      return;
    }
    const performedBy = window.prompt("Seu e-mail ou usuário (fica registrado na auditoria):");
    if (!performedBy?.trim()) return;

    setDeleting(true);
    try {
      await api.delete(`/conciliacoes/${reconciliationId}?performed_by=${encodeURIComponent(performedBy.trim())}`);
      router.refresh();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Não foi possível excluir esta conciliação.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <button
      onClick={handleDelete}
      disabled={deleting}
      title="Excluir esta conciliação"
      className="rounded-md p-1.5 text-stone-300 transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
    >
      <X size={16} strokeWidth={2.25} />
    </button>
  );
}
