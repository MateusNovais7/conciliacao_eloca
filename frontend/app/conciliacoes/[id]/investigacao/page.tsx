"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { ReconciliationMatch, ReconciliationMatchDetail } from "@/types/api";
import { StatusBadge } from "@/components/StatusBadge";

const MANUAL_REASONS = [
  { value: "NUMERACAO_DIFERENTE", label: "Numeração diferente" },
  { value: "DIFERENCA_DE_DATA", label: "Diferença de data" },
  { value: "AGRUPAMENTO", label: "Agrupamento" },
  { value: "AJUSTE_CONTABIL", label: "Ajuste contábil" },
  { value: "CLASSIFICACAO", label: "Classificação" },
  { value: "OUTRO", label: "Outro" },
];

function formatBRL(v: number | null) {
  if (v === null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDate(d: string) {
  return new Date(d + "T00:00:00").toLocaleDateString("pt-BR");
}

export default function InvestigacaoPage({ params }: { params: { id: string } }) {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<ReconciliationMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const qs = new URLSearchParams();
    if (status) qs.set("status", status);
    if (search) qs.set("search", search);
    api.get<ReconciliationMatch[]>(`/conciliacoes/${params.id}/titulos?${qs.toString()}`)
      .then(setRows)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Não foi possível carregar os títulos."))
      .finally(() => setLoading(false));
  }, [params.id, status, search]);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">Investigação</h1>
      <p className="mt-1 text-sm text-slate-500">Pesquise título, cliente, valor, NF ou documento.</p>

      <div className="mt-6 flex gap-3">
        <input
          className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm"
          placeholder="Pesquisar título, cliente, valor, NF ou documento…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">Todos os status</option>
          {[
            "CONCILIADO", "CONCILIADO D+1", "CONCILIADO D+2", "CORTE DE COMPETÊNCIA",
            "CORTE DE COMPETÊNCIA (fim do período importado)", "POSSÍVEL CORRESPONDÊNCIA",
            "VALOR DIVERGENTE", "BANCO SEM ERP", "ERP SEM BANCO",
            "TÍTULO DESCONTADO (fora do escopo desta versão)",
          ].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {error && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Confiança</th>
              <th className="px-4 py-3 font-medium">Diagnóstico</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading && (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-400">Carregando…</td></tr>
            )}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-400">Nenhum título encontrado.</td></tr>
            )}
            {rows.map((r) => (
              <tr
                key={r.id}
                onClick={() => setSelectedId(r.id)}
                className="cursor-pointer hover:bg-slate-50"
              >
                <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                <td className="px-4 py-3 tabular-nums text-slate-600">{r.confidence}%</td>
                <td className="max-w-xl truncate px-4 py-3 text-slate-700">{r.diagnostic}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedId && (
        <DetailDrawer
          reconciliationId={params.id}
          matchId={selectedId}
          onClose={() => setSelectedId(null)}
          onAdjusted={() => {
            setSelectedId(null);
            setStatus((s) => s); // força re-fetch mantendo o filtro atual
          }}
        />
      )}
    </main>
  );
}

function DetailDrawer({
  reconciliationId, matchId, onClose, onAdjusted,
}: { reconciliationId: string; matchId: string; onClose: () => void; onAdjusted: () => void }) {
  const [detail, setDetail] = useState<ReconciliationMatchDetail | null>(null);
  const [showAdjustForm, setShowAdjustForm] = useState(false);
  const [reason, setReason] = useState("AJUSTE_CONTABIL");
  const [observation, setObservation] = useState("");
  const [performedBy, setPerformedBy] = useState("");
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    api.get<ReconciliationMatchDetail>(`/conciliacoes/${reconciliationId}/titulos/${matchId}`).then(setDetail);
  }, [reconciliationId, matchId]);

  async function handleManualReconcile() {
    if (!performedBy.trim()) {
      setErrorMsg("Informe seu usuário para registrar o ajuste.");
      return;
    }
    setSaving(true);
    setErrorMsg(null);
    try {
      await api.post(`/conciliacoes/${reconciliationId}/titulos/${matchId}/ajuste-manual`, {
        reason, observation: observation || null,
        new_status: "CONCILIADO MANUALMENTE", performed_by: performedBy,
      });
      onAdjusted();
    } catch (e) {
      setErrorMsg(e instanceof ApiError ? e.message : "Não foi possível salvar o ajuste.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-10 flex justify-end bg-slate-900/30" onClick={onClose}>
      <div className="h-full w-full max-w-2xl overflow-y-auto bg-white p-8 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-6 flex items-start justify-between">
          <h2 className="text-lg font-semibold">Detalhe do título</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">✕</button>
        </div>

        {!detail && <p className="text-slate-400">Carregando…</p>}

        {detail && (
          <>
            <StatusBadge status={detail.status} />

            {detail.bank_transaction && detail.erp_transaction && (
              <Timeline
                bankDate={detail.bank_transaction.movement_date}
                bankLabel={`Título ${detail.bank_transaction.seu_numero ?? detail.bank_transaction.nosso_numero}`}
                bankAmount={detail.bank_transaction.principal_amount}
                erpDate={detail.erp_transaction.transaction_date}
                erpLabel={`Título ${detail.erp_transaction.invoice_number_raw ?? "—"}`}
                erpAmount={detail.erp_transaction.incoming_amount}
                status={detail.status}
              />
            )}

            <div className="mt-6 grid grid-cols-2 gap-6">
              <div>
                <h3 className="text-sm font-semibold text-slate-500">BANCO</h3>
                {detail.bank_transaction ? (
                  <dl className="mt-2 space-y-1 text-sm">
                    <Row label="Data" value={formatDate(detail.bank_transaction.movement_date)} />
                    <Row label="Pagador" value={detail.bank_transaction.payer_name ?? "—"} />
                    <Row label="Seu Número" value={detail.bank_transaction.seu_numero ?? "—"} />
                    <Row label="Nosso Número" value={detail.bank_transaction.nosso_numero} />
                    <Row label="Principal" value={formatBRL(detail.bank_transaction.principal_amount)} />
                    <Row label="Juros" value={formatBRL(detail.bank_transaction.interest_amount)} />
                    <Row label="Tarifa" value={formatBRL(detail.bank_transaction.fee_amount)} />
                  </dl>
                ) : <p className="mt-2 text-sm text-slate-400">Sem correspondência no banco.</p>}
              </div>

              <div>
                <h3 className="text-sm font-semibold text-slate-500">ERP</h3>
                {detail.erp_transaction ? (
                  <dl className="mt-2 space-y-1 text-sm">
                    <Row label="Data" value={formatDate(detail.erp_transaction.transaction_date)} />
                    <Row label="Título" value={detail.erp_transaction.invoice_number_raw ?? "—"} />
                    <Row label="Nota Fiscal" value={detail.erp_transaction.nota_fiscal ?? "—"} />
                    <Row label="Valor" value={formatBRL(detail.erp_transaction.incoming_amount)} />
                  </dl>
                ) : <p className="mt-2 text-sm text-slate-400">Sem correspondência no ERP.</p>}
              </div>
            </div>

            <div className="mt-6 rounded-lg bg-slate-50 p-4">
              <h3 className="text-sm font-semibold text-slate-500">DIAGNÓSTICO</h3>
              <p className="mt-1 text-sm text-slate-700">{detail.diagnostic}</p>
            </div>

            {!detail.is_manual_override && (
              <div className="mt-6">
                {!showAdjustForm ? (
                  <button
                    onClick={() => setShowAdjustForm(true)}
                    className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50"
                  >
                    Conciliar manualmente
                  </button>
                ) : (
                  <div className="space-y-3 rounded-lg border border-slate-200 p-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700">Motivo</label>
                      <select
                        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                      >
                        {MANUAL_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700">Observação</label>
                      <textarea
                        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                        rows={2}
                        value={observation}
                        onChange={(e) => setObservation(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700">Seu usuário</label>
                      <input
                        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                        value={performedBy}
                        onChange={(e) => setPerformedBy(e.target.value)}
                        placeholder="voce@empresa.com"
                      />
                    </div>
                    {errorMsg && <p className="text-sm text-red-700">{errorMsg}</p>}
                    <div className="flex gap-2">
                      <button
                        onClick={handleManualReconcile}
                        disabled={saving}
                        className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50"
                      >
                        {saving ? "Salvando…" : "Confirmar conciliação manual"}
                      </button>
                      <button onClick={() => setShowAdjustForm(false)} className="text-sm text-slate-500 hover:underline">
                        Cancelar
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-1">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium tabular-nums text-slate-900">{value}</dd>
    </div>
  );
}

function Timeline({
  bankDate, bankLabel, bankAmount, erpDate, erpLabel, erpAmount, status,
}: {
  bankDate: string; bankLabel: string; bankAmount: number | null;
  erpDate: string; erpLabel: string; erpAmount: number | null; status: string;
}) {
  return (
    <div className="mt-6 rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-3">
        <span className="h-2 w-2 rounded-full bg-slate-400" />
        <div className="flex-1 text-sm">
          <span className="font-medium">{formatDate(bankDate)}</span>
          <span className="ml-2 text-slate-500">BANCO · {bankLabel}</span>
          <span className="ml-2 font-medium tabular-nums">{formatBRL(bankAmount)}</span>
        </div>
      </div>
      <div className="ml-1 h-4 w-px bg-slate-300" />
      <div className="flex items-center gap-3">
        <span className="h-2 w-2 rounded-full bg-slate-400" />
        <div className="flex-1 text-sm">
          <span className="font-medium">{formatDate(erpDate)}</span>
          <span className="ml-2 text-slate-500">ERP · {erpLabel}</span>
          <span className="ml-2 font-medium tabular-nums">{formatBRL(erpAmount)}</span>
        </div>
      </div>
      <div className="ml-1 h-4 w-px bg-slate-300" />
      <div className="flex items-center gap-3">
        <span className="h-2 w-2 rounded-full bg-teal-600" />
        <StatusBadge status={status} />
      </div>
    </div>
  );
}
