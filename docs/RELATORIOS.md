# Relatórios da Nexus Rotafy

Abra **Relatórios** no painel. Administradores e atendentes consultam os dados operacionais da própria agência. O administrador também consulta o consumo da franquia. A Nexus consulta consumo por empresa; guia, motorista e passageiro não acessam relatórios administrativos.

## Filtros e interpretação

- **Ocupação:** cada linha representa um segmento entre pontos de um trecho de um veículo. Mostra capacidade atribuída à viagem, passageiros confirmados, bloqueios ainda válidos e lugares disponíveis. Bloqueios vencidos não ocupam vagas, mesmo antes da execução do worker. Família que embarca numa parada só ocupa os segmentos seguintes até seu desembarque.
- **Reservas e pagamentos:** uma linha por reserva familiar, com responsável, veículo, quantidade de passageiros, situação da reserva, PAGO/NÃO PAGO e valor nominal. Ida e volta não duplicam a família. O pagamento é uma marcação manual, independente de confirmação/cancelamento; este relatório não é um extrato bancário nem processa estornos financeiros.
- **Presença:** contagens do manifesto atual por veículo e trecho, somente de reservas confirmadas. Estado aceito pelo servidor: aguardando, a bordo ou desembarcado. Ações offline pendentes não entram nas contagens. Eventos históricos continuam no histórico de embarque/auditoria.
- **Consumo da franquia:** ciclos iniciados no intervalo selecionado, com plano/valores históricos, franquia, uso líquido, restantes, extras e valor estimado. Cancelamentos estornam o ciclo original. Uma viagem com vários ônibus e ida/volta continua consumindo uma unidade. Valores são demonstrativos, sem emissão de fatura ou cobrança integrada.

Datas inicial e final são inclusivas em **America/Sao_Paulo**. Os relatórios operacionais selecionam pela partida da viagem, inclusive as canceladas; não pela data de cadastro da reserva nem por cada partida da volta. O relatório de consumo seleciona pelo início do ciclo. Intervalo máximo: 366 dias.

Use **Aplicar filtros** após alterar datas, viagem ou empresa. **Atualizar relatório** consulta novamente o servidor. A tela informa o horário da consulta. O filtro PAGO/NÃO PAGO afeta apenas a tabela; **Exportar CSV completo** usa todo o período e a viagem/empresa aplicados, como indicado na tela.

Para preservar o tempo de resposta, cada consulta operacional aceita até 50 viagens e 5.000 linhas por seção; consumo aceita até 5.000 ciclos. Quando o limite é atingido, o sistema pede reduzir o período ou selecionar uma viagem/empresa. Não entrega totais parciais silenciosamente.

## Exportação e privacidade

CSV em UTF-8 com BOM, separador `;`, títulos em português, datas com fuso de Brasília e valores em reais com vírgula decimal. Textos que poderiam virar fórmula numa planilha recebem um apóstrofo de proteção. O CSV pode conter o código da reserva para conferência, mas exclui CPF, telefone, tokens, chaves, senhas e nomes individuais de passageiros.

Os endpoints são autenticados, sujeitos ao perfil e ao RLS do PostgreSQL:

| Endpoint | Consulta |
| --- | --- |
| `GET /api/v1/reports/operations?start=YYYY-MM-DD&end=YYYY-MM-DD` | Ocupação, reservas e presença; `trip_id` opcional |
| `GET /api/v1/reports/consumption?start=YYYY-MM-DD&end=YYYY-MM-DD` | Consumo; `company_id` opcional para Nexus |
| `GET /api/v1/reports/export?start=...&end=...&category=...` | CSV de `occupancy`, `reservations`, `presence` ou `consumption` |

Migração `0011_report_indexes` adiciona índices de partida da viagem e passageiros por reserva. Interface em `frontend/src/Reports.tsx`; regras em `backend/app/reports.py`.

## Validação

Testes cobrem isolamento, papéis, ida/volta sem duplicação da reserva, presença por trecho, família parcial entre paradas, bloqueio vencido, cancelamento/estorno, fronteira do dia em Brasília, limites de consulta e proteção de fórmulas. Jornada Chromium cobre painel da agência e Nexus, filtros, PAGO, presença, consumo, CSV e viewport mobile.

Referência de carga local em [LOAD_TEST_RESULT.json](LOAD_TEST_RESULT.json): duas empresas, dez veículos por empresa, 800 passageiros únicos e cem consultas com dez leitores simultâneos. Ambiente Windows/TestClient com PostgreSQL Docker, não VPS, sem simular gravação simultânea, GPS ou WhatsApp. A medição deve ser repetida na infraestrutura de produção; não estabelece SLA.
