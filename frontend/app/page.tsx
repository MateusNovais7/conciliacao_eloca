import Link from "next/link";
import { Building2, ChevronRight, Inbox } from "lucide-react";
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
        <h1 className="text-2xl font-semibold tracking-tight text-stone-900">Clientes</h1>
        <p className="mt-1 text-sm text-stone-500">
          Escolha um cliente para ver o histórico de conciliações, ou importe uma nova.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {!error && clients.length === 0 && (
        <div className="flex flex-col items-center rounded-2xl border border-dashed border-stone-300 px-6 py-14 text-center">
          <Inbox size={28} strokeWidth={1.5} className="mb-3 text-stone-300" />
          <p className="text-stone-600">Nenhum cliente cadastrado ainda.</p>
          <Link href="/nova-conciliacao" className="mt-2 inline-block text-sm font-medium text-teal-700 hover:underline">
            Comece criando a primeira conciliação →
          </Link>
        </div>
      )}

      {!error && clients.length > 0 && (
        <ul className="divide-y divide-stone-200 overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
          {clients.map((c) => (
            <li key={c.id}>
              <Link
                href={`/clientes/${c.id}`}
                className="flex items-center gap-3 px-5 py-4 transition-colors hover:bg-stone-50"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-teal-700">
                  <Building2 size={17} strokeWidth={2} />
                </span>
                <span className="flex-1 font-medium text-stone-900">{c.name}</span>
                <ChevronRight size={18} className="text-stone-300" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
