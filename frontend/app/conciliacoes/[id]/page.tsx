import Link from "next/link";
import { CalendarDays, Download, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Dashboard } from "@/types/api";
import { StatusBadge } from "@/components/StatusBadge";
import { BackButton } from "@/components/BackButton";
import { ProgressRing } from "@/components/ProgressRing";

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
        <BackButton fallbackHref="/" />
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      </main>
    );
  }

  const sortedByStatus = [...dashboard.by_status].sort((a, b) => b.count - a.count);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <BackButton fallbackHref="/" />
      <div className="mb-8 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-stone-500">Conciliação</p>
          <h1 className="text-2xl font-semibold tracking-tight text-stone-900">Dashboard</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/conciliacoes/${params.id}/diaria`}
            className="flex items-center gap-1.5 rounded-lg border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition-colors hover:bg-stone-50"
          >
            <CalendarDays size={15} strokeWidth={2.25} />
            Conciliação diária
          </Link>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/exports/${params.id}/excel`}
            className="flex items-center gap-1.5 rounded-lg border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition-colors hover:bg-stone-50"
          >
            <Download size={15} strokeWidth={2.25} />
            Exportar Excel
          </a>
          <Link
            href={`/conciliacoes/${params.id}/investigacao`}
            className="flex items-center gap-1.5 rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-teal-800"
          >
            <Search size={15} strokeWidth={2.25} />
            Investigar
          </Link>
        </div>
      </div>

      <div className="mb-8 flex flex-wrap items-center gap-8 rounded-2xl border border-stone-200 bg-white p-8 shadow-sm">
        <ProgressRing pct={dashboard.reconciled_pct} />
        <div className="grid flex-1 grid-cols-2 gap-6 text-sm sm:grid-cols-3">
          <div>
            <p className="text-stone-500">Títulos banco</p>
            <p className="mt-0.5 text-xl font-semibold tabular-nums text-stone-900">{dashboard.bank_titles_count}</p>
          </div>
          <div>
            <p className="text-stone-500">Títulos ERP</p>
            <p className="mt-0.5 text-xl font-semibold tabular-nums text-stone-900">{dashboard.erp_titles_count}</p>
          </div>
          <div>
            <p className="text-stone-500">Valor conciliado</p>
            <p className="mt-0.5 text-xl font-semibold tabular-nums text-teal-700">{formatBRL(dashboard.reconciled_amount)}</p>
          </div>
          <div>
            <p className="text-stone-500">Valor divergente</p>
            <p className="mt-0.5 text-xl font-semibold tabular-nums text-red-700">{formatBRL(dashboard.divergent_amount)}</p>
          </div>
        </div>
      </div>

      <p className="mb-3 text-sm font-medium text-stone-500">Clique num status para investigar só esses registros</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {sortedByStatus.map((s) => (
          <Link
            key={s.status}
            href={`/conciliacoes/${params.id}/investigacao?status=${encodeURIComponent(s.status)}`}
            className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-md"
          >
            <StatusBadge status={s.status} />
            <p className="mt-2.5 text-2xl font-semibold tabular-nums text-stone-900">{s.count}</p>
            <p className="text-xs text-stone-500">{formatBRL(s.total_amount)}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
