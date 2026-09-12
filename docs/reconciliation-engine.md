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
| 6 | Antecipação | — | Separada na importação via `ANTECIPAÇÃO RECEBIVEIS` na descrição do ERP |
| 7/8 | Sem correspondência | 0 | |
| 9 | Possível correspondência | 80/70 | Busca por valor±R$0,05 + janela de 5 dias úteis + nome semelhante |
| 12 | Desconto comercial (CRP032A1) | 96 | Fonte opcional — explica valor divergente quando `Valor Emissão − Desconto − Abatimento − Impostos + Juros + Multa` bate exatamente com a baixa do ERP |

## Não implementado (sem evidência real ainda)

- **Regra 10/11 (agrupamento um-para-vários / vários-para-um):** investigado contra os 4 casos residuais de janeiro/2026 — nenhuma combinação de 2 lançamentos do ERP somou exatamente o valor de nenhum banco-sem-ERP. Sem evidência, não implementado (ver item 31 do escopo original).
- **Calendário de feriados:** hoje só considera sábado/domingo como não-úteis.

## Achados de dados reais que viraram regra/escopo

1. **`liquidação de título descontado`** (carteira de antecipação bancária do Itaú) tem `Valor Final = 0` sempre — comparar contra o ERP gera falso positivo de divergência. Separado em status próprio `TITULO_DESCONTADO`, fora do matching por título+valor até haver evidência de como o ERP registra essa baixa.
2. **PIX / Depósito em Conta no ERP** nunca aparecem na Francesinha de cobrança (que só cobre a carteira de boleto) — escopado via `TipoDocumento`, não contados como `ERP SEM BANCO`.
3. **Bug conhecido do exportador ERP:** o `.xlsx` do FFP045A2 (e também o CRP032A1 — mesmo exportador) sai com stylesheet corrompida (`TypeError: expected <class Fill>`). O importador detecta e repara automaticamente via LibreOffice headless antes de processar.
4. **Desconto comercial não aparece no FFP045A2** — a baixa já vem líquida, sem explicar por que é menor que o principal do banco. O CRP032A1 (Relação de Documentos Recebidos) tem a resposta no campo `Valor Desconto`. Testado contra os 6 casos de `VALOR DIVERGENTE` de janeiro/2026: os 6 batem exatamente. Fonte opcional — sem o CRP032A1, o comportamento continua sendo `VALOR DIVERGENTE` sem forçar nada.

## Resultado no Golden Test (jan/2026)

- 3.047 registros bancários, 1.203 recebimentos de duplicata no ERP, 3.034 documentos no CRP032A1 (24 com desconto).
- 6/6 casos de valor divergente resolvidos pela Regra 12 — zero `VALOR DIVERGENTE` sem explicação.
- 4 banco-sem-ERP e 6 ERP-sem-banco genuinamente sem explicação (nenhum candidato mesmo com busca fuzzy) — ficam para investigação humana, não foram forçados.
