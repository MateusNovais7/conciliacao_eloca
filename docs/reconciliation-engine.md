# Motor de Conciliação — documentação de regras

Última validação: arquivos reais MEATHUNTER / Itaú 98967-1 / janeiro-2026.

## Regras implementadas

| # | Regra | Confiança | Observação |
|---|---|---|---|
| 1 | Match exato (título + valor + mesma data) | 100 | |
| 2 | D+1 / D+2 em dias úteis | 98 / 95 | Sexta→segunda com valor batendo é tratado como Corte de Competência, não D+1 |
| 3 | Juros | — | `valor_cliente = principal + juros` (tarifa não desconta) |
| 4 | Valor divergente | 60/50 | Nunca força conciliação |
| 5 | Corte de competência | 98 | Também cobre borda do período importado (`CORTE_FIM_PERIODO`) |
| 6 | Antecipação (ERP) | — | Identificada via `ANTECIPAÇÃO RECEBIVEIS` na descrição do ERP; usada pela Regra 13 |
| 7/8 | Sem correspondência | 0 | |
| 9 | Possível correspondência | 80/70 | Busca por valor±R$0,05 + janela de 5 dias úteis + nome semelhante |
| 12 | Desconto comercial (CRP032A1) | 96 | Fonte opcional — explica valor divergente quando `Valor Emissão − Desconto − Abatimento − Impostos + Juros + Multa` bate exatamente com a baixa do ERP |
| 13 | Título descontado (carteira de antecipação bancária) | 95 / 90 | Casa `liquidação de título descontado` do banco com `ANTECIPAÇÃO RECEBIVEIS` do ERP (95) ou, na ausência dessa, com o CRP032A1 (90) |

## Não implementado (sem evidência real ainda)

- **Regra 10/11 (agrupamento um-para-vários / vários-para-um):** investigado contra os 4 casos residuais de janeiro/2026 — nenhuma combinação de 2 lançamentos do ERP somou exatamente o valor de nenhum banco-sem-ERP. Sem evidência, não implementado (ver item 31 do escopo original).
- **Calendário de feriados:** hoje só considera sábado/domingo como não-úteis.

## Achados de dados reais que viraram regra/escopo

1. **`liquidação de título descontado`** (carteira de antecipação bancária do Itaú) e **`ANTECIPAÇÃO RECEBIVEIS`** no ERP são A MESMA operação — cada sistema só usa um nome diferente. Confirmado em escala: dos 94 títulos descontados de janeiro/2026, os 44 lançamentos de antecipação do ERP bateram 1:1 com valor exato (bijeção completa). Mais 4 bateram exato com o CRP032A1 (documentos que nem aparecem no FFP045A2). Os 46 restantes ficam como `TITULO_DESCONTADO` (sem correspondência) — resíduo genuíno, não mais tratado como "fora de escopo".
2. **PIX / Depósito em Conta no ERP** nunca aparecem na Francesinha de cobrança (que só cobre a carteira de boleto) — escopado via `TipoDocumento`, não contados como `ERP SEM BANCO`.
3. **Bug conhecido do exportador ERP:** o `.xlsx` do FFP045A2 (e também o CRP032A1 — mesmo exportador) sai com stylesheet corrompida (`TypeError: expected <class Fill>`). O importador detecta e repara automaticamente via LibreOffice headless antes de processar.
4. **Desconto comercial não aparece no FFP045A2** — a baixa já vem líquida, sem explicar por que é menor que o principal do banco. O CRP032A1 (Relação de Documentos Recebidos) tem a resposta no campo `Valor Desconto`. Testado contra os 6 casos de `VALOR DIVERGENTE` de janeiro/2026: os 6 batem exatamente. Fonte opcional — sem o CRP032A1, o comportamento continua sendo `VALOR DIVERGENTE` sem forçar nada.

## Resultado no Golden Test (jan/2026)

- 3.047 registros bancários, 1.203 recebimentos de duplicata no ERP, 3.034 documentos no CRP032A1 (24 com desconto).
- 6/6 casos de valor divergente resolvidos pela Regra 12 — zero `VALOR DIVERGENTE` sem explicação.
- 48/94 títulos descontados resolvidos pela Regra 13 (44 via antecipação do ERP + 4 via CRP032A1).
- Residual genuíno: 4 banco-sem-ERP, 6 ERP-sem-banco, 46 título-descontado-sem-correspondência — nenhum candidato encontrado em nenhuma das 3 fontes, mesmo com busca fuzzy. Ficam para investigação humana; não foram forçados.

## Recuperação de documentos apagados (FTP050)

Cenário real: o time do ERP apagou documentos a receber a pedido do cliente,
e esses títulos passaram a aparecer como `TÍTULO DESCONTADO SEM
CORRESPONDÊNCIA`. O relatório FTP050 (Relação de NF Emitidas) permite
recuperar de qual **Local** e para qual **Cliente** cada documento deveria
ser recriado, cruzando pelo número da NF extraído do `Seu Número` do banco
(últimos 2 dígitos = Sequência, resto = número da NF), com desempate por
nome do cliente quando a NF se repete.

- `POST /importacoes/ftp050` — aceita múltiplos arquivos (o ERP limita a
  6 meses por exportação); não participa da conciliação mensal normal.
- `GET /conciliacoes/{id}/recuperacao` — lista cruzada, com `resolved=false`
  para os casos sem candidato confiável (nunca escolhido às cegas).
- `GET /conciliacoes/{id}/recuperacao/excel` — planilha pronta para
  reimputação manual ou repasse ao time de desenvolvimento.
- `GET /conciliacoes/{id}/recuperacao/script` — script para colar no
  console (F12) da tela de cadastro do documento. Preenche com segurança
  os campos de texto simples; os 4 campos de busca customizados (Local,
  Status, Tipo Documento, Forma Pagamento) exigem confirmação manual —
  o HTML fornecido não expõe um seletor confiável para esses widgets.

Mapeamento de Local é específico do cliente MEATHUNTER (informado por
eles, não inferido): 0=MEAT HUNTER, 2=MEAT HUNTER SP, 4=MEAT BARRA,
5=MEAT HUNTER RJ2 (ver `app/importers/erp/ftp050.py`).
