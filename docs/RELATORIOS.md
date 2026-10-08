# Relatórios da Nexus Rotafy

Abra **Relatórios** no painel. Administradores e atendentes consultam os dados operacionais da própria agência. O administrador também consulta o consumo da franquia. A Nexus consulta consumo por empresa; guia, motorista e passageiro não acessam relatórios administrativos.

## Filtros e interpretação

### Visão gerencial

Esta é a aba inicial da empresa, disponível para administradores e atendentes. Filtre período, situação, veículo e viagem. O mês atual inclui todas as datas até o último dia; o atalho de trinta dias termina hoje. Datas inicial e final são inclusivas em America/Sao_Paulo, com limite de 366 dias.

- **Gráfico diário:** cada deslocamento conta na própria data de saída, incluindo retorno. A segunda série conta viagens comerciais pela primeira saída. Vários veículos não multiplicam essas contagens. Canceladas aparecem, podendo ser excluídas pelo filtro de situação. Não são medidas de consumo da franquia.
- **Ocupação:** para cada veículo/deslocamento, calcula o maior número simultâneo de passageiros confirmados entre paradas. A taxa consolidada é a soma desses picos dividida pela soma das capacidades registradas nas alocações. Não é média simples dos percentuais. Canceladas são excluídas; ausência de observações aparece como Sem dados. Bloqueios temporários válidos ficam separados.
- **Valores e passageiros:** somente reservas confirmadas de viagens comerciais iniciadas no período, excluindo viagens canceladas. Uma família e seus passageiros não são repetidos por destino, retorno ou veículo. São participações nas reservas, não pessoas únicas entre viagens distintas. Pacotes iniciados antes do período podem ter deslocamentos no gráfico sem gerar novas vendas nos indicadores.
- **PAGO e não pago:** valor nominal confirmado com marcação manual. O ticket médio divide o valor confirmado pelos passageiros confirmados. Não representam conciliação bancária, lucro ou fluxo de caixa.
- **Filtro de veículo:** valores e passageiros incluem a reserva inteira quando o veículo atende um dos seus deslocamentos; não dividem o preço do pacote entre veículos ou destinos.
- **Destinos/produtos:** até dez itens por passageiros confirmados; pacotes usam seu produto comercial, sem ratear o preço pelos destinos.
- **Baixa ocupação:** até trinta alocações/deslocamentos futuros, dentro do período aplicado, com ocupação confirmada inferior a 50%, incluindo acesso aos detalhes. Lugares disponíveis usam capacidade menos o maior total simultâneo de confirmados e bloqueios válidos, respeitando paradas.

Os totais gerenciais são agregados no banco e não usam o limite de cinquenta viagens das tabelas detalhadas. Os limites de dez e trinta itens afetam apenas as listas indicadas, não os totais. Os gráficos também possuem valores textuais; o gráfico diário permite selecionar um dia e consultar sua tabela.

### Relatórios detalhados

- **Ocupação:** cada linha representa um segmento entre pontos de um trecho de um veículo. Mostra capacidade atribuída à viagem, passageiros confirmados, bloqueios ainda válidos e lugares disponíveis. Bloqueios vencidos não ocupam vagas, mesmo antes da execução do worker. Família que embarca numa parada só ocupa os segmentos seguintes até seu desembarque.
- **Reservas e pagamentos:** uma linha por reserva familiar, com responsável, veículo, quantidade de passageiros, situação da reserva, PAGO/NÃO PAGO e valor nominal. Ida e volta não duplicam a família. O pagamento é uma marcação manual, independente de confirmação/cancelamento; este relatório não é um extrato bancário nem processa estornos financeiros.
- **Presença:** contagens do manifesto atual por veículo e trecho, somente de reservas confirmadas. Estado aceito pelo servidor: aguardando, a bordo ou desembarcado. Ações offline pendentes não entram nas contagens. Eventos históricos continuam no histórico de embarque/auditoria.
- **Consumo da franquia:** ciclos iniciados no intervalo selecionado, com plano/valores históricos, franquia, uso líquido, restantes, extras e valor estimado. Cancelamentos estornam o ciclo original. Uma viagem simples consome uma unidade; pacotes consomem por destino comercial, sem acréscimo por retorno, paradas ou vários veículos. Valores são demonstrativos, sem emissão de fatura ou cobrança integrada.

Datas inicial e final são inclusivas em **America/Sao_Paulo**. Os relatórios operacionais selecionam pela partida da viagem, inclusive as canceladas; não pela data de cadastro da reserva nem por cada partida da volta. O relatório de consumo seleciona pelo início do ciclo. Intervalo máximo: 366 dias.

Use **Aplicar filtros** após alterar datas, viagem ou empresa. **Atualizar relatório** consulta novamente o servidor. A tela informa o horário da consulta. O filtro PAGO/NÃO PAGO afeta apenas a tabela; **Exportar CSV completo** usa todo o período e a viagem/empresa aplicados, como indicado na tela.

Para preservar o tempo de resposta, cada consulta operacional aceita até 50 viagens e 5.000 linhas por seção; consumo aceita até 5.000 ciclos. Quando o limite é atingido, o sistema pede reduzir o período ou selecionar uma viagem/empresa. Não entrega totais parciais silenciosamente.

## Exportação e privacidade

CSV em UTF-8 com BOM, separador `;`, títulos em português, datas com fuso de Brasília e valores em reais com vírgula decimal. Textos que poderiam virar fórmula numa planilha recebem um apóstrofo de proteção. O CSV pode conter o código da reserva para conferência, mas exclui CPF, telefone, tokens, chaves, senhas e nomes individuais de passageiros.

Os endpoints são autenticados, sujeitos ao perfil e ao RLS do PostgreSQL:

| Endpoint | Consulta |
| --- | --- |
| `GET /api/v1/reports/management?start=YYYY-MM-DD&end=YYYY-MM-DD` | Visão gerencial; `trip_id`, `vehicle_id` e `status` opcionais |
| `GET /api/v1/reports/operations?start=YYYY-MM-DD&end=YYYY-MM-DD` | Ocupação, reservas e presença; `trip_id` opcional |
| `GET /api/v1/reports/consumption?start=YYYY-MM-DD&end=YYYY-MM-DD` | Consumo; `company_id` opcional para Nexus |
| `GET /api/v1/reports/export?start=...&end=...&category=...` | CSV de `occupancy`, `reservations`, `presence` ou `consumption` |

Migração `0011_report_indexes` adiciona índices de partida da viagem e passageiros por reserva. Interface em `frontend/src/Reports.tsx`; regras em `backend/app/reports.py`.

A visão gerencial usa `frontend/src/ManagementDashboard.tsx` e `backend/app/management_reports.py`. Esta atualização não exige nova migração ou APK. Referências visuais: [desktop](screenshots/visao-gerencial-desktop.png) e [celular](screenshots/visao-gerencial-mobile.png).

## Validação

Testes cobrem isolamento, papéis, ida/volta sem duplicação da reserva, presença por trecho, família parcial entre paradas, bloqueio vencido, cancelamento/estorno, fronteira do dia em Brasília, limites de consulta e proteção de fórmulas. Jornada Chromium cobre painel da agência e Nexus, filtros, PAGO, presença, consumo, CSV e viewport mobile.

Referência de carga local em [LOAD_TEST_RESULT.json](LOAD_TEST_RESULT.json): duas empresas, dez veículos por empresa, 800 passageiros únicos e cem consultas com dez leitores simultâneos. Ambiente Windows/TestClient com PostgreSQL Docker, não VPS, sem simular gravação simultânea, GPS ou WhatsApp. A medição deve ser repetida na infraestrutura de produção; não estabelece SLA.
