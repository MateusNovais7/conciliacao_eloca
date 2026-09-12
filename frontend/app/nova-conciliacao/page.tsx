"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { BankAccount, Client, ImportFile } from "@/types/api";

const MONTHS = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

type StepState = "idle" | "loading" | "done" | "error";

function StepStatus({ state, doneLabel, idleLabel }: { state: StepState; doneLabel: string; idleLabel: string }) {
  if (state === "done") return <p className="text-sm text-teal-700">✓ {doneLabel}</p>;
  if (state === "loading") return <p className="text-sm text-slate-500">Processando…</p>;
  if (state === "error") return null;
  return <p className="text-sm text-slate-400">{idleLabel}</p>;
}

export default function NovaConciliacaoPage() {
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [clientId, setClientId] = useState("");
  const [newClientName, setNewClientName] = useState("");
  const [accountId, setAccountId] = useState("");
  const [newAccount, setNewAccount] = useState({ bank: "Itaú", agency: "", account_number: "" });
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [importedBy, setImportedBy] = useState("");

  const [erpFile, setErpFile] = useState<File | null>(null);
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [erpState, setErpState] = useState<StepState>("idle");
  const [bankState, setBankState] = useState<StepState>("idle");
  const [erpResult, setErpResult] = useState<ImportFile | null>(null);
  const [bankResult, setBankResult] = useState<ImportFile | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<Client[]>("/clientes").then(setClients).catch(() => {});
  }, []);

  useEffect(() => {
    if (!clientId) { setAccounts([]); return; }
    api.get<BankAccount[]>(`/contas?client_id=${clientId}`).then(setAccounts).catch(() => {});
  }, [clientId]);

  async function ensureClientAndAccount(): Promise<{ clientId: string; accountId: string }> {
    let cid = clientId;
    if (!cid && newClientName.trim()) {
      const created = await api.post<Client>("/clientes", { name: newClientName.trim() });
      cid = created.id;
    }
    if (!cid) throw new ApiError(422, "Selecione ou crie um cliente.");

    let aid = accountId;
    if (!aid && newAccount.account_number.trim()) {
      const created = await api.post<BankAccount>("/contas", {
        client_id: cid, bank: newAccount.bank, agency: newAccount.agency || null,
        account_number: newAccount.account_number.trim(),
      });
      aid = created.id;
    }
    if (!aid) throw new ApiError(422, "Selecione ou crie uma conta.");

    return { clientId: cid, accountId: aid };
  }

  async function handleSubmit() {
    setErrorMsg(null);
    if (!erpFile || !bankFile) {
      setErrorMsg("Envie os dois arquivos: relatório do ERP e extrato do banco.");
      return;
    }
    if (!importedBy.trim()) {
      setErrorMsg("Informe seu e-mail ou nome de usuário.");
      return;
    }

    setSubmitting(true);
    try {
      const { accountId: aid } = await ensureClientAndAccount();

      setErpState("loading");
      const erpForm = new FormData();
      erpForm.append("bank_account_id", aid);
      erpForm.append("competencia_year", String(year));
      erpForm.append("competencia_month", String(month));
      erpForm.append("imported_by", importedBy);
      erpForm.append("file", erpFile);
      const erp = await api.postForm<ImportFile>("/importacoes/erp", erpForm);
      setErpResult(erp);
      setErpState("done");

      setBankState("loading");
      const bankForm = new FormData();
      bankForm.append("bank_account_id", aid);
      bankForm.append("competencia_year", String(year));
      bankForm.append("competencia_month", String(month));
      bankForm.append("imported_by", importedBy);
      bankForm.append("file", bankFile);
      const bank = await api.postForm<ImportFile>("/importacoes/banco", bankForm);
      setBankResult(bank);
      setBankState("done");

      const reconciliation = await api.post<{ id: string }>("/conciliacoes", {
        bank_account_id: aid, competencia_year: year, competencia_month: month,
        erp_import_file_id: erp.id, bank_import_file_id: bank.id,
      });
      await api.post(`/conciliacoes/${reconciliation.id}/executar`);

      router.push(`/conciliacoes/${reconciliation.id}`);
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Não foi possível concluir a importação.";
      setErrorMsg(message);
      if (erpState === "loading") setErpState("error");
      if (bankState === "loading") setBankState("error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">Nova conciliação</h1>
      <p className="mt-1 text-sm text-slate-500">Importe o relatório do ERP e o extrato do banco para esta competência.</p>

      <section className="mt-8 space-y-6 rounded-xl border border-slate-200 bg-white p-6">
        <div>
          <label className="block text-sm font-medium text-slate-700">Cliente</label>
          <select
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={clientId}
            onChange={(e) => { setClientId(e.target.value); setAccountId(""); }}
          >
            <option value="">— criar novo abaixo —</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          {!clientId && (
            <input
              className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Nome do novo cliente"
              value={newClientName}
              onChange={(e) => setNewClientName(e.target.value)}
            />
          )}
        </div>

        {clientId && (
          <div>
            <label className="block text-sm font-medium text-slate-700">Conta</label>
            <select
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
            >
              <option value="">— criar nova abaixo —</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.bank} · {a.account_number}</option>
              ))}
            </select>
            {!accountId && (
              <div className="mt-2 grid grid-cols-3 gap-2">
                <input
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Banco (ex: Itaú)"
                  value={newAccount.bank}
                  onChange={(e) => setNewAccount({ ...newAccount, bank: e.target.value })}
                />
                <input
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Agência"
                  value={newAccount.agency}
                  onChange={(e) => setNewAccount({ ...newAccount, agency: e.target.value })}
                />
                <input
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Conta (ex: 98967-1)"
                  value={newAccount.account_number}
                  onChange={(e) => setNewAccount({ ...newAccount, account_number: e.target.value })}
                />
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-700">Competência</label>
            <select
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            >
              {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Ano</label>
            <input
              type="number"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Seu e-mail ou usuário</label>
          <input
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            placeholder="voce@empresa.com"
            value={importedBy}
            onChange={(e) => setImportedBy(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <FileDrop
            label="ERP"
            file={erpFile}
            onFile={setErpFile}
            status={<StepStatus state={erpState} idleLabel="arraste o relatório FFP045A2" doneLabel={`${erpResult?.row_count ?? "?"} registros encontrados`} />}
          />
          <FileDrop
            label="Banco"
            file={bankFile}
            onFile={setBankFile}
            status={<StepStatus state={bankState} idleLabel="arraste a Francesinha / extrato de cobrança" doneLabel={`${bankResult?.row_count ?? "?"} títulos encontrados`} />}
          />
        </div>

        {errorMsg && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {errorMsg}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50"
        >
          {submitting ? "Importando e conciliando…" : "Importar e conciliar"}
        </button>
      </section>
    </main>
  );
}

function FileDrop({
  label, file, onFile, status,
}: { label: string; file: File | null; onFile: (f: File) => void; status: React.ReactNode }) {
  const [dragOver, setDragOver] = useState(false);
  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors ${
        dragOver ? "border-teal-500 bg-teal-50" : "border-slate-300 bg-slate-50"
      }`}
    >
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <span className="mt-1 text-xs text-slate-500">{file ? file.name : "arraste o arquivo ou clique"}</span>
      <div className="mt-2">{status}</div>
      <input
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
      />
    </label>
  );
}
