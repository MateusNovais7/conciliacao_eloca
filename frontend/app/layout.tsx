import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Conciliação Bancária",
  description: "ERP × extrato de cobrança, explicado — não só comparado.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen antialiased font-sans bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
