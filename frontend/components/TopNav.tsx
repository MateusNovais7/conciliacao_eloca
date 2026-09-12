import Link from "next/link";

export function TopNav() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight text-slate-900">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-teal-700 text-sm text-white">C</span>
          Conciliação Bancária
        </Link>
        <Link href="/nova-conciliacao" className="text-sm font-medium text-teal-700 hover:underline">
          Nova conciliação
        </Link>
      </div>
    </header>
  );
}
