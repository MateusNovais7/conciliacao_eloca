import Link from "next/link";
import { CalendarPlus, Landmark } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { BankAccount, Client, ReconciliationHistoryItem } from "@/types/api";
import { StatusBadge } from "@/components/StatusBadge";
import { BackButton } from "@/components/BackButton";
import { DeleteReconciliationButton } from "@/components/DeleteReconciliationButton";

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
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
              <Landmark size={20} strokeWidth={2} />
            </span>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-stone-900">{client.name}</h1>
              <p className="text-sm text-stone-500">
                {accounts.length} conta{accounts.length !== 1 ? "s" : ""} bancária{accounts.length !== 1 ? "s" : ""}
              </p>
            </div>
          </div>

          <div className="mt-8 space-y-6">
            {accounts.map((account, idx) => {
              const history = histories[idx];
              return (
                <section key={account.id} className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
                  <div className="flex items-center justify-between border-b border-stone-100 bg-stone-50/60 px-5 py-4">
                    <div>
                      <p className="font-medium text-stone-900">{account.bank} · {account.account_number}</p>
                      {account.agency && <p className="text-xs text-stone-500">Agência {account.agency}</p>}
                    </div>
                    <Link
                      href={`/nova-conciliacao?client_id=${client!.id}&bank_account_id=${account.id}`}
                      className="flex items-center gap-1.5 text-sm font-medium text-teal-700 hover:underline"
                    >
                      <CalendarPlus size={15} strokeWidth={2.25} />
                      Nova competência
                    </Link>
                  </div>

                  {history.length === 0 ? (
                    <p className="px-5 py-6 text-sm text-stone-400">Nenhuma conciliação importada ainda para esta conta.</p>
                  ) : (
                    <ul className="divide-y divide-stone-100">
                      {history.map((h) => (
                        <li key={h.id} className="group flex items-center">
                          <Link
                            href={`/conciliacoes/${h.id}`}
                            className="flex flex-1 items-center justify-between px-5 py-3.5 transition-colors hover:bg-stone-50"
                          >
                            <span className="text-sm font-medium text-stone-800">
                              {MONTHS_ABBR[h.competencia_month - 1]}/{h.competencia_year}
                            </span>
                            <div className="flex items-center gap-3">
                              <span className="text-sm tabular-nums text-stone-600">{h.reconciled_pct.toFixed(1)}%</span>
                              <StatusBadge status={h.status} />
                            </div>
                          </Link>
                          <div className="pr-3">
                            <DeleteReconciliationButton
                              reconciliationId={h.id}
                              label={`${MONTHS_ABBR[h.competencia_month - 1]}/${h.competencia_year}`}
                            />
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}

            {accounts.length === 0 && (
              <div className="rounded-2xl border border-dashed border-stone-300 px-6 py-10 text-center">
                <p className="text-stone-600">Nenhuma conta cadastrada para este cliente ainda.</p>
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
