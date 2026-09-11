const STATUS_STYLES: Record<string, string> = {
  "CONCILIADO": "bg-teal-50 text-teal-800 border-teal-200",
  "CONCILIADO D+1": "bg-teal-50 text-teal-800 border-teal-200",
  "CONCILIADO D+2": "bg-teal-50 text-teal-800 border-teal-200",
  "CONCILIADO MANUALMENTE": "bg-teal-50 text-teal-800 border-teal-200",
  "CORTE DE COMPETÊNCIA": "bg-slate-100 text-slate-700 border-slate-300",
  "CORTE DE COMPETÊNCIA (fim do período importado)": "bg-slate-100 text-slate-700 border-slate-300",
  "POSSÍVEL CORRESPONDÊNCIA": "bg-amber-50 text-amber-800 border-amber-200",
  "VALOR DIVERGENTE": "bg-red-50 text-red-800 border-red-200",
  "BANCO SEM ERP": "bg-red-50 text-red-800 border-red-200",
  "ERP SEM BANCO": "bg-red-50 text-red-800 border-red-200",
  "TÍTULO DESCONTADO (fora do escopo desta versão)": "bg-slate-100 text-slate-500 border-slate-200",
  "IGNORADO": "bg-slate-100 text-slate-400 border-slate-200",
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700 border-slate-300";
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${style}`}>
      {status}
    </span>
  );
}
