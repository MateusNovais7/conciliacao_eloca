/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // Sem isso, o Next guarda a versão de páginas dinâmicas (como o
    // histórico do cliente) em cache no navegador por até 30s — voltar
    // pra tela logo depois de criar uma conciliação mostrava a versão
    // antiga até um hard refresh. Zerando isso, toda navegação busca os
    // dados de novo.
    staleTimes: {
      dynamic: 0,
    },
  },
};
module.exports = nextConfig;
