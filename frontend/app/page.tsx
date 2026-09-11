import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { Client } from "@/types/api";

export default async function HomePage() {
  let clients: Client[] = [];
  let error: string | null = null;
  try {
    clients = await api.get<Client[]>("/clientes");
  } catch (e) {
    error = e instanceof ApiError ? e.message : "Não foi possível carregar os clientes.";
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-10 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Conciliação Bancária</h1>
          <p className="mt-1 text-sm text-slate-500">
            Importe o ERP e o extrato do banco — o resto a gente explica.
          </p>
        </div>
        <Link
          href="/nova-conciliacao"
          className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800"
        >
          Nova conciliação
        </Link>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {!error && clients.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 px-6 py-12 text-center">
          <p className="text-slate-600">Nenhum cliente cadastrado ainda.</p>
          <Link href="/nova-conciliacao" className="mt-2 inline-block text-sm font-medium text-teal-700 hover:underline">
            Comece criando a primeira conciliação →
          </Link>
        </div>
      )}

      {!error && clients.length > 0 && (
        <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white">
          {clients.map((c) => (
            <li key={c.id} className="px-5 py-4">
              <span className="font-medium">{c.name}</span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
