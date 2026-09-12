"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FileCheck2, FileSpreadsheet, UploadCloud } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { BankAccount, Client, ImportFile } from "@/types/api";
import { BackButton } from "@/components/BackButton";

const MONTHS = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

type StepState = "idle" | "loading" | "done" | "error";

function StepStatus({ state, doneLabel, idleLabel }: { state: StepState; doneLabel: string; idleLabel: string }) {
  if (state === "done") return <p className="text-sm text-teal-700">✓ {doneLabel}</p>;
  if (state === "loading") return <p className="text-sm text-stone-500">Processando…</p>;
  if (state === "error") return null;
  return <p className="text-sm text-stone-400">{idleLabel}</p>;
}

export default function NovaConciliacaoPage() {
  return (
    <Suspense>
      <NovaConciliacaoForm />
    </Suspense>
  );
}

function NovaConciliacaoForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [clients, setClients] = useState<Client[]>([]);
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [clientId, setClientId] = useState(searchParams.get("client_id") ?? "");
  const [newClientName, setNewClientName] = useState("");
  const [accountId, setAccountId] = useState(searchParams.get("bank_account_id") ?? "");
  const [newAccount, setNewAccount] = useState({ bank: "Itaú", agency: "", account_number: "" });
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [importedBy, setImportedBy] = useState("");

  const [erpFile, setErpFile] = useState<File | null>(null);
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [crpFile, setCrpFile] = useState<File | null>(null);
  const [erpState, setErpState] = useState<StepState>("idle");
  const [bankState, setBankState] = useState<StepState>("idle");
  const [crpState, setCrpState] = useState<StepState>("idle");
  const [erpResult, setErpResult] = useState<ImportFile | null>(null);
  const [bankResult, setBankResult] = useState<ImportFile | null>(null);
  const [crpResult, setCrpResult] = useState<ImportFile | null>(null);
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

      let crpId: string | undefined;
      if (crpFile) {
        setCrpState("loading");
        const crpForm = new FormData();
        crpForm.append("bank_account_id", aid);
        crpForm.append("competencia_year", String(year));
        crpForm.append("competencia_month", String(month));
        crpForm.append("imported_by", importedBy);
        crpForm.append("file", crpFile);
        const crp = await api.postForm<ImportFile>("/importacoes/crp032a1", crpForm);
        setCrpResult(crp);
        setCrpState("done");
        crpId = crp.id;
      }

      const reconciliation = await api.post<{ id: string }>("/conciliacoes", {
        bank_account_id: aid, competencia_year: year, competencia_month: month,
        erp_import_file_id: erp.id, bank_import_file_id: bank.id,
        crp032a1_import_file_id: crpId,
      });
      await api.post(`/conciliacoes/${reconciliation.id}/executar`);

      router.push(`/conciliacoes/${reconciliation.id}`);
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Não foi possível concluir a importação.";
      setErrorMsg(message);
      if (erpState === "loading") setErpState("error");
      if (bankState === "loading") setBankState("error");
      if (crpState === "loading") setCrpState("error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <BackButton fallbackHref="/" />
      <h1 className="text-2xl font-semibold tracking-tight text-stone-900">Nova conciliação</h1>
      <p className="mt-1 text-sm text-stone-500">Importe o relatório do ERP e o extrato do banco para esta competência.</p>

      <section className="mt-8 space-y-6 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
        <div>
          <label className="block text-sm font-medium text-stone-700">Cliente</label>
          <select
            className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
            value={clientId}
            onChange={(e) => { setClientId(e.target.value); setAccountId(""); }}
          >
            <option value="">— criar novo abaixo —</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          {!clientId && (
            <input
              className="mt-2 w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
              placeholder="Nome do novo cliente"
              value={newClientName}
              onChange={(e) => setNewClientName(e.target.value)}
            />
          )}
        </div>

        {clientId && (
          <div>
            <label className="block text-sm font-medium text-stone-700">Conta</label>
            <select
              className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
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
                  className="rounded-md border border-stone-300 px-3 py-2 text-sm"
                  placeholder="Banco (ex: Itaú)"
                  value={newAccount.bank}
                  onChange={(e) => setNewAccount({ ...newAccount, bank: e.target.value })}
                />
                <input
                  className="rounded-md border border-stone-300 px-3 py-2 text-sm"
                  placeholder="Agência"
                  value={newAccount.agency}
                  onChange={(e) => setNewAccount({ ...newAccount, agency: e.target.value })}
                />
                <input
                  className="rounded-md border border-stone-300 px-3 py-2 text-sm"
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
            <label className="block text-sm font-medium text-stone-700">Competência</label>
            <select
              className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            >
              {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700">Ano</label>
            <input
              type="number"
              className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-stone-700">Seu e-mail ou usuário</label>
          <input
            className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
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

        <div>
          <FileDrop
            label="CRP032A1 (opcional)"
            file={crpFile}
            onFile={setCrpFile}
            status={<StepStatus state={crpState} idleLabel="arraste a Relação de Documentos Recebidos, se tiver" doneLabel={`${crpResult?.row_count ?? "?"} documentos encontrados`} />}
          />
          <p className="mt-1.5 text-xs text-stone-400">
            Usado só para explicar desconto comercial em valores divergentes. Pode pular se não tiver esse relatório.
          </p>
        </div>

        {errorMsg && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {errorMsg}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-teal-800 disabled:opacity-50"
        >
          <UploadCloud size={16} strokeWidth={2.25} />
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
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-7 text-center transition-colors ${
        dragOver ? "border-teal-500 bg-teal-50" : file ? "border-teal-300 bg-teal-50/30" : "border-stone-300 bg-stone-50 hover:border-stone-400"
      }`}
    >
      {file ? (
        <FileCheck2 size={22} strokeWidth={1.75} className="text-teal-600" />
      ) : (
        <FileSpreadsheet size={22} strokeWidth={1.75} className="text-stone-400" />
      )}
      <span className="mt-2 text-sm font-medium text-stone-700">{label}</span>
      <span className="mt-1 text-xs text-stone-500">{file ? file.name : "arraste o arquivo ou clique"}</span>
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
