"use client";

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, FileSpreadsheet, Terminal, UploadCloud } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Reconciliation, RecoveredTitle } from "@/types/api";
import { BackButton } from "@/components/BackButton";
import { DownloadButton } from "@/components/DownloadButton";

function formatBRL(v: number | null) {
  if (v === null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function RecuperacaoPage({ params }: { params: { id: string } }) {
  const [reconciliation, setReconciliation] = useState<Reconciliation | null>(null);
  const [titulos, setTitulos] = useState<RecoveredTitle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [importedBy, setImportedBy] = useState("");

  async function carregar() {
    setLoading(true);
    setError(null);
    try {
      const rec = await api.get<Reconciliation>(`/conciliacoes/${params.id}`);
      setReconciliation(rec);
      const lista = await api.get<RecoveredTitle[]>(`/conciliacoes/${params.id}/recuperacao`);
      setTitulos(lista);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível carregar a recuperação.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  async function handleUploadFtp050(file: File) {
    if (!reconciliation) return;
    if (!importedBy.trim()) {
      setError("Informe seu e-mail ou usuário antes de subir o arquivo.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("bank_account_id", reconciliation.bank_account_id);
      form.append("competencia_year", String(reconciliation.competencia_year));
      form.append("competencia_month", String(reconciliation.competencia_month));
      form.append("imported_by", importedBy);
      form.append("file", file);
      await api.postForm("/importacoes/ftp050", form);
      await carregar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível importar o FTP050.");
    } finally {
      setUploading(false);
    }
  }

  const resolvidos = titulos.filter((t) => t.resolved).length;

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <BackButton fallbackHref={`/conciliacoes/${params.id}`} />
      <h1 className="text-2xl font-semibold tracking-tight text-stone-900">Recuperação de documentos apagados</h1>
      <p className="mt-1 text-sm text-stone-500">
        Cruza os títulos "sem correspondência" com o FTP050 (Relação de NF Emitidas) para descobrir
        Local e Cliente e permitir reimputar o documento no ERP.
      </p>

      {error && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}

      <section className="mt-6 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-stone-700">Enviar FTP050</h2>
        <p className="mt-1 text-xs text-stone-500">
          O ERP limita a exportação a 6 meses por consulta — pode enviar quantos arquivos precisar, um de cada vez;
          eles se somam ao acervo sem duplicar.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <input
            className="w-64 rounded-md border border-stone-300 px-3 py-2 text-sm"
            placeholder="Seu e-mail ou usuário"
            value={importedBy}
            onChange={(e) => setImportedBy(e.target.value)}
          />
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-stone-300 bg-stone-50 px-4 py-2 text-sm text-stone-600 hover:border-teal-400">
            <UploadCloud size={16} strokeWidth={2.25} />
            {uploading ? "Enviando…" : "Escolher arquivo FTP050"}
            <input
              type="file"
              accept=".xlsx,.xls"
              className="hidden"
              disabled={uploading}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUploadFtp050(f); }}
            />
          </label>
        </div>
      </section>

      {!loading && titulos.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
          <div>
            <p className="text-sm text-stone-500">Títulos sem correspondência</p>
            <p className="text-2xl font-semibold tabular-nums text-stone-900">
              {titulos.length} <span className="text-base font-normal text-stone-400">({resolvidos} resolvidos)</span>
            </p>
          </div>
          <div className="flex gap-2">
            <DownloadButton
              path={`/conciliacoes/${params.id}/recuperacao/excel`}
              filename={`reimputacao_${reconciliation?.competencia_year}_${String(reconciliation?.competencia_month).padStart(2, "0")}.xlsx`}
              className="flex items-center gap-1.5 rounded-lg border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-50"
            >
              <FileSpreadsheet size={15} strokeWidth={2.25} />
              Baixar planilha
            </DownloadButton>
            <DownloadButton
              path={`/conciliacoes/${params.id}/recuperacao/script`}
              filename="reimputacao.js"
              className="flex items-center gap-1.5 rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50"
            >
              <Terminal size={15} strokeWidth={2.25} />
              Baixar script de console
            </DownloadButton>
          </div>
        </div>
      )}

      {!loading && titulos.length === 0 && !error && (
        <p className="mt-6 text-sm text-stone-400">Nenhum título sem correspondência nesta competência.</p>
      )}

      {!loading && titulos.length > 0 && (
        <div className="mt-4 overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead className="border-b border-stone-200 bg-stone-50 text-left text-xs uppercase tracking-wide text-stone-500">
              <tr>
                <th className="px-4 py-3 font-medium">NF / Seq</th>
                <th className="px-4 py-3 font-medium">Pagador (banco)</th>
                <th className="px-4 py-3 text-right font-medium">Valor</th>
                <th className="px-4 py-3 font-medium">Local</th>
                <th className="px-4 py-3 font-medium">Cliente (FTP050)</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {titulos.map((t) => (
                <tr key={t.match_id} className={t.resolved ? "" : "bg-amber-50/40"}>
                  <td className="px-4 py-2.5 tabular-nums">{t.nota_fiscal}/{t.sequencia}</td>
                  <td className="px-4 py-2.5 text-stone-700">{t.payer_name ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{formatBRL(t.principal_amount)}</td>
                  <td className="px-4 py-2.5">{t.resolved ? `${t.local_nome} [${t.local_id}]` : "—"}</td>
                  <td className="px-4 py-2.5 text-stone-700">{t.resolved ? `${t.razao_social} (${t.cliente_id})` : "—"}</td>
                  <td className="px-4 py-2.5">
                    {t.resolved ? (
                      <span className="inline-flex items-center gap-1.5 rounded-md border border-teal-200 bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-800">
                        <CheckCircle2 size={13} /> Resolvido
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
                        <AlertCircle size={13} /> Revisar manualmente
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
