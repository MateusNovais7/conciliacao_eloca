import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { BackButton } from "@/components/BackButton";

type DailyRow = {
  date: string;
  bank_total: number;
  erp_total: number;
  difference: number;
  status: "OK" | "DIVERGENTE";
  match_ids: string[];
};

function formatBRL(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDate(d: string) {
  return new Date(d + "T00:00:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" });
}

export default async function ConciliacaoDiariaPage({ params }: { params: { id: string } }) {
  let rows: DailyRow[] = [];
  let error: string | null = null;
  try {
    rows = await api.get<DailyRow[]>(`/conciliacoes/${params.id}/diaria`);
  } catch (e) {
    error = e instanceof ApiError ? e.message : "Não foi possível carregar a conciliação diária.";
  }

  const firstDivergentDay = rows.find((r) => r.status === "DIVERGENTE");

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <BackButton fallbackHref={`/conciliacoes/${params.id}`} />
      <h1 className="text-2xl font-semibold tracking-tight">Conciliação diária</h1>
      <p className="mt-1 text-sm text-slate-500">
        Compara o total liquidado no banco com o total baixado no ERP, dia a dia.
      </p>

      {error && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}

      {firstDivergentDay && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          O banco e o ERP deixaram de fechar em <strong>{formatDate(firstDivergentDay.date)}</strong> — veja abaixo os
          lançamentos responsáveis por essa diferença.
        </div>
      )}

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Data</th>
              <th className="px-4 py-3 text-right font-medium">Banco</th>
              <th className="px-4 py-3 text-right font-medium">ERP</th>
              <th className="px-4 py-3 text-right font-medium">Diferença</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => (
              <tr key={r.date} className={r.status === "DIVERGENTE" ? "bg-red-50/40" : undefined}>
                <td className="px-4 py-2.5 font-medium">{formatDate(r.date)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatBRL(r.bank_total)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{formatBRL(r.erp_total)}</td>
                <td className={`px-4 py-2.5 text-right tabular-nums font-medium ${r.status === "DIVERGENTE" ? "text-red-700" : "text-slate-400"}`}>
                  {formatBRL(r.difference)}
                </td>
                <td className="px-4 py-2.5">
                  <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${
                    r.status === "OK" ? "border-teal-200 bg-teal-50 text-teal-800" : "border-red-200 bg-red-50 text-red-800"
                  }`}>
                    {r.status}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  {r.status === "DIVERGENTE" && r.match_ids.length > 0 && (
                    <Link
                      href={`/conciliacoes/${params.id}/investigacao`}
                      className="text-xs font-medium text-teal-700 hover:underline"
                    >
                      ver lançamentos →
                    </Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
