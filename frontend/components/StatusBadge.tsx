const STATUS_STYLES: Record<string, { badge: string; dot: string }> = {
  "CONCILIADO": { badge: "bg-teal-50 text-teal-800 border-teal-200", dot: "bg-teal-600" },
  "CONCILIADO D+1": { badge: "bg-teal-50 text-teal-800 border-teal-200", dot: "bg-teal-600" },
  "CONCILIADO D+2": { badge: "bg-teal-50 text-teal-800 border-teal-200", dot: "bg-teal-600" },
  "CONCILIADO MANUALMENTE": { badge: "bg-teal-50 text-teal-800 border-teal-200", dot: "bg-teal-600" },
  "CORTE DE COMPETÊNCIA": { badge: "bg-stone-100 text-stone-700 border-stone-300", dot: "bg-stone-500" },
  "CORTE DE COMPETÊNCIA (fim do período importado)": { badge: "bg-stone-100 text-stone-700 border-stone-300", dot: "bg-stone-500" },
  "POSSÍVEL CORRESPONDÊNCIA": { badge: "bg-amber-50 text-amber-800 border-amber-200", dot: "bg-amber-500" },
  "VALOR DIVERGENTE": { badge: "bg-red-50 text-red-800 border-red-200", dot: "bg-red-600" },
  "BANCO SEM ERP": { badge: "bg-red-50 text-red-800 border-red-200", dot: "bg-red-600" },
  "ERP SEM BANCO": { badge: "bg-red-50 text-red-800 border-red-200", dot: "bg-red-600" },
  "TÍTULO DESCONTADO (fora do escopo desta versão)": { badge: "bg-stone-100 text-stone-500 border-stone-200", dot: "bg-stone-400" },
  "IGNORADO": { badge: "bg-stone-100 text-stone-400 border-stone-200", dot: "bg-stone-300" },
  // Status de ciclo de vida da competência (item 20) — distintos dos
  // status por título acima.
  "RASCUNHO": { badge: "bg-stone-100 text-stone-600 border-stone-300", dot: "bg-stone-400" },
  "EM_ANALISE": { badge: "bg-amber-50 text-amber-800 border-amber-200", dot: "bg-amber-500" },
  "CONCILIADA": { badge: "bg-teal-50 text-teal-800 border-teal-200", dot: "bg-teal-600" },
  "FECHADA": { badge: "bg-stone-800 text-white border-stone-800", dot: "bg-white" },
  "REABERTA": { badge: "bg-amber-50 text-amber-800 border-amber-200", dot: "bg-amber-500" },
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? { badge: "bg-stone-100 text-stone-700 border-stone-300", dot: "bg-stone-400" };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium ${style.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {status}
    </span>
  );
}
