import type { Metadata } from "next";
import { TopNav } from "@/components/TopNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Conciliação Bancária",
  description: "ERP × extrato de cobrança, explicado — não só comparado.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen antialiased font-sans bg-stone-50 text-stone-900">
        <TopNav />
        {children}
      </body>
    </html>
  );
}
