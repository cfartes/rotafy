# Financeiro: próxima fatura e avisos individuais

## Comportamento

- O administrador vê cinco cards: valor a vencer, parcela X/12, valor do plano, próximo vencimento e situação da assinatura.
- A previsão usa os preços contratados e os excedentes líquidos do livro de consumo, incluindo estornos. Setup é separado nos contratos pós-pagos de 30 dias; contratos antigos preservam seu modo de cobrança.
- Faturas definitivas prevalecem sobre previsões. Faturas pagas ou canceladas não reaparecem como previsão da mesma cobrança. O cálculo não emite fatura, link ou mensagem.
- Vencimento é o prazo para pagamento calculado pela regra existente de dois dias úteis, com feriados nacionais. O aviso usa datas de São Paulo e aparece entre cinco dias antes e o próprio vencimento.
- X/12 é um contador circular dos ciclos da mensalidade, sem alterar o contrato. Setup não entra na contagem.
- Desativar o aviso salva a preferência do próprio usuário no banco. É possível reativá-lo pelo Financeiro; os cards continuam visíveis. A preferência não altera e-mails ou WhatsApp de cobrança.

## Bloqueio e pagamento

O administrador bloqueado por pendência financeira acessa somente o Financeiro. O backend também recusa consultas e alterações operacionais desse perfil, além de ocultar os menus. Motorista e guia preservam o acesso operacional às viagens já vendidas. A baixa ou confirmação de pagamento retira a restrição quando não houver outras dívidas; a sessão e os menus são reavaliados automaticamente.

O cliente pode solicitar o link de uma fatura definitiva, aberta, positiva e da própria empresa com pagamento online. O pedido reutiliza a referência e o recebedor já registrados, sem criar outra fatura ou duplicar o trabalho de geração. Não permite gerar links para previsões, faturas pagas, canceladas ou pagamentos em conferência. Se já existe link, ele é reaproveitado. A confirmação segue a verificação do provedor já existente.

## API e persistência

- `GET /api/v1/company/billing/upcoming`: previsão ou próxima fatura, cinco indicadores e preferência individual; somente administrador da empresa.
- `PUT /api/v1/company/billing/reminder`: recebe `{ "enabled": false }` ou `true`, alterando somente o usuário autenticado.
- `POST /api/v1/company/invoices/{id}/payment-link`: agenda ou reaproveita o link da própria fatura. Continua acessível ao administrador sob bloqueio financeiro, com CSRF, validação de propriedade e limitação de tentativas.

A migração incremental `0033_billing_reminder` adiciona apenas `users.billing_reminder_enabled`, com valor inicial verdadeiro. Nenhum banco é recriado e nenhum valor de fatura existente é alterado.

## Aplicação na VPS

```bash
cd /opt/rotafy-tech
git pull --ff-only origin main
bash scripts/update_vps.sh
```

Não exige novo APK. Os testes simulam o pagamento externo e não enviam cobranças reais.

## Validação

Suíte completa: 406 testes backend aprovados. Após o ajuste de pagamentos antecipados, 15 testes direcionados verificaram previsão, valores definitivos, estornos, contratos antigos, preferência entre usuários, permissões e link de pagamento. Nove testes de navegador verificaram cards, aviso, menus restritos, pagamento e documentação. Build web e Ruff aprovados.
