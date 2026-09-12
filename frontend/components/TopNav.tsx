import Link from "next/link";
import { Landmark, Plus } from "lucide-react";

export function TopNav() {
  return (
    <header className="sticky top-0 z-20 border-b border-stone-200 bg-stone-50/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight text-stone-900">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-700 text-white shadow-sm">
            <Landmark size={16} strokeWidth={2.25} />
          </span>
          <span className="text-[15px]">Conciliação Bancária</span>
        </Link>
        <Link
          href="/nova-conciliacao"
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-teal-800 transition-colors hover:bg-teal-50"
        >
          <Plus size={16} strokeWidth={2.25} />
          Nova conciliação
        </Link>
      </div>
    </header>
  );
}
