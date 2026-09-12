import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { BankAccount, Client, ReconciliationHistoryItem } from "@/types/api";
import { StatusBadge } from "@/components/StatusBadge";
import { BackButton } from "@/components/BackButton";

const MONTHS_ABBR = [
  "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez",
];

export default async function ClientDetailPage({ params }: { params: { id: string } }) {
  let client: Client | null = null;
  let accounts: BankAccount[] = [];
  let error: string | null = null;

  try {
    client = await api.get<Client>(`/clientes/${params.id}`);
    accounts = await api.get<BankAccount[]>(`/contas?client_id=${params.id}`);
  } catch (e) {
    error = e instanceof ApiError ? e.message : "Não foi possível carregar este cliente.";
  }

  const histories = await Promise.all(
    accounts.map((a) =>
      api.get<ReconciliationHistoryItem[]>(`/conciliacoes?bank_account_id=${a.id}`).catch(() => [])
    )
  );

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <BackButton fallbackHref="/" />

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}

      {client && (
        <>
          <h1 className="text-2xl font-semibold tracking-tight">{client.name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {accounts.length} conta{accounts.length !== 1 ? "s" : ""} bancária{accounts.length !== 1 ? "s" : ""}
          </p>

          <div className="mt-8 space-y-8">
            {accounts.map((account, idx) => {
              const history = histories[idx];
              return (
                <section key={account.id} className="rounded-xl border border-slate-200 bg-white">
                  <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                    <div>
                      <p className="font-medium">{account.bank} · {account.account_number}</p>
                      {account.agency && <p className="text-xs text-slate-500">Agência {account.agency}</p>}
                    </div>
                    <Link
                      href={`/nova-conciliacao?client_id=${client!.id}&bank_account_id=${account.id}`}
                      className="text-sm font-medium text-teal-700 hover:underline"
                    >
                      + Nova competência
                    </Link>
                  </div>

                  {history.length === 0 ? (
                    <p className="px-5 py-6 text-sm text-slate-400">Nenhuma conciliação importada ainda para esta conta.</p>
                  ) : (
                    <ul className="divide-y divide-slate-100">
                      {history.map((h) => (
                        <li key={h.id}>
                          <Link
                            href={`/conciliacoes/${h.id}`}
                            className="flex items-center justify-between px-5 py-3 transition-colors hover:bg-slate-50"
                          >
                            <span className="text-sm font-medium">
                              {MONTHS_ABBR[h.competencia_month - 1]}/{h.competencia_year}
                            </span>
                            <div className="flex items-center gap-3">
                              <span className="text-sm tabular-nums text-slate-600">{h.reconciled_pct.toFixed(1)}%</span>
                              <StatusBadge status={h.status} />
                            </div>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}

            {accounts.length === 0 && (
              <div className="rounded-xl border border-dashed border-slate-300 px-6 py-10 text-center">
                <p className="text-slate-600">Nenhuma conta cadastrada para este cliente ainda.</p>
                <Link
                  href={`/nova-conciliacao?client_id=${client.id}`}
                  className="mt-2 inline-block text-sm font-medium text-teal-700 hover:underline"
                >
                  Criar a primeira conciliação →
                </Link>
              </div>
            )}
          </div>
        </>
      )}
    </main>
  );
}
