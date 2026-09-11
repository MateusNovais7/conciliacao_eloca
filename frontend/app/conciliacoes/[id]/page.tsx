import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { Dashboard } from "@/types/api";
import { StatusBadge } from "@/components/StatusBadge";

function formatBRL(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default async function DashboardPage({ params }: { params: { id: string } }) {
  let dashboard: Dashboard | null = null;
  let error: string | null = null;
  try {
    dashboard = await api.get<Dashboard>(`/conciliacoes/${params.id}/dashboard`);
  } catch (e) {
    error = e instanceof ApiError ? e.message : "Não foi possível carregar o dashboard.";
  }

  if (error || !dashboard) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      </main>
    );
  }

  const sortedByStatus = [...dashboard.by_status].sort((a, b) => b.count - a.count);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <p className="text-sm text-slate-500">Conciliação</p>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/conciliacoes/${params.id}/diaria`}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
          >
            Conciliação diária
          </Link>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/exports/${params.id}/excel`}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
          >
            Exportar Excel
          </a>
          <Link
            href={`/conciliacoes/${params.id}/investigacao`}
            className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800"
          >
            Investigar
          </Link>
        </div>
      </div>

      <div className="mb-8 rounded-xl border border-slate-200 bg-white p-8">
        <p className="text-sm text-slate-500">Percentual conciliado</p>
        <p className="mt-1 text-5xl font-semibold tabular-nums text-teal-700">
          {dashboard.reconciled_pct.toFixed(1)}%
        </p>
        <div className="mt-4 grid grid-cols-3 gap-6 text-sm">
          <div>
            <p className="text-slate-500">Títulos banco</p>
            <p className="text-lg font-medium tabular-nums">{dashboard.bank_titles_count}</p>
          </div>
          <div>
            <p className="text-slate-500">Títulos ERP</p>
            <p className="text-lg font-medium tabular-nums">{dashboard.erp_titles_count}</p>
          </div>
          <div>
            <p className="text-slate-500">Valor divergente</p>
            <p className="text-lg font-medium tabular-nums text-red-700">{formatBRL(dashboard.divergent_amount)}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {sortedByStatus.map((s) => (
          <Link
            key={s.status}
            href={`/conciliacoes/${params.id}/investigacao?status=${encodeURIComponent(s.status)}`}
            className="rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-teal-300 hover:bg-teal-50/40"
          >
            <StatusBadge status={s.status} />
            <p className="mt-2 text-2xl font-semibold tabular-nums">{s.count}</p>
            <p className="text-xs text-slate-500">{formatBRL(s.total_amount)}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
