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
      <header className="mb-10">
        <h1 className="text-2xl font-semibold tracking-tight">Clientes</h1>
        <p className="mt-1 text-sm text-slate-500">
          Escolha um cliente para ver o histórico de conciliações, ou importe uma nova.
        </p>
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
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {clients.map((c) => (
            <li key={c.id}>
              <Link
                href={`/clientes/${c.id}`}
                className="flex items-center justify-between px-5 py-4 transition-colors hover:bg-slate-50"
              >
                <span className="font-medium">{c.name}</span>
                <span className="text-slate-400">→</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
