# Plano — visão gerencial de relatórios

Data: 08/10/2026. Status: implementado e validado localmente. Critérios de métricas e acesso confirmados pelo usuário.

## Definições confirmadas

- Contagem diária: deslocamentos por data de saída, incluindo retorno, e série separada de viagens comerciais iniciadas. Não multiplicar pelos veículos ou pelo consumo de franquia.
- Ocupação: máxima simultânea de passageiros confirmados em cada veículo/deslocamento, respeitando embarques e desembarques nas paradas. Bloqueios temporários ficam separados.
- Acesso à visão gerencial, inclusive valores de reservas e pagamentos: administradores e atendentes da empresa. Franquia continua respeitando a permissão de administrador existente. Motorista, guia e passageiro não acessam o painel gerencial; o painel Nexus de consumo atual permanece separado.

## Objetivo

Acrescentar uma aba Visão gerencial aos relatórios da empresa, com gráficos e cartões de indicadores, preservando os relatórios detalhados e a exportação CSV existentes. Respeitar Turismo/Regular e o isolamento entre empresas.

## Gráficos solicitados

1. Quantidade de deslocamentos por dia e viagens comerciais iniciadas, usando a data de saída no fuso America/Sao_Paulo. Um pacote é uma viagem comercial com vários deslocamentos, e consumo de franquia é outra medida. Vários veículos não multiplicam a contagem. Preencher dias sem movimento com zero e identificar situações das viagens.
2. Percentual de ocupação dos veículos, com nome/placa, capacidade e quantidade ocupada. Proposta: maior ocupação simultânea confirmada por veículo/deslocamento, considerando intervalos entre paradas. Separar bloqueios temporários ainda válidos. Para consolidar, somar quantidades ocupadas e capacidades das observações; não calcular média simples de percentuais de veículos de tamanhos distintos. Excluir viagens canceladas da ocupação e apresentar ausência de dados sem transformar em zero.

## Gráficos e KPIs propostos

- Viagens por situação: agendadas, em andamento, concluídas e canceladas.
- Passageiros confirmados e reservas/famílias confirmadas, sem repetir passageiros pela quantidade de destinos ou veículos do pacote.
- Valor das reservas confirmadas das viagens do período; valor marcado PAGO e valor confirmado ainda não pago. São indicadores baseados no cadastro e pagamento manual, não conciliação bancária ou fluxo de caixa.
- Ticket médio por passageiro confirmado: valor confirmado dividido pela quantidade de passageiros confirmados.
- Destinos mais vendidos por passageiros confirmados e valor reservado. Para pacotes, utilizar o produto/roteiro comercial, sem distribuir artificialmente o preço entre seus destinos.
- Saídas próximas com baixa ocupação, com taxa e lugares disponíveis para apoiar vendas.
- Reservas por situação: confirmadas, pendentes válidas, expiradas e canceladas.
- Administrador: consumo da franquia no ciclo atual, unidades restantes e extras, aproveitando os dados atuais de assinatura. Separar explicitamente franquia de contagem operacional de viagens.

Recomendação de primeira entrega: os dois gráficos solicitados, distribuição por situação, ranking de destinos/produtos e cartões de passageiros confirmados, valor confirmado, PAGO, não pago e ticket médio. Franquia permanece indicador adicional do administrador; baixa ocupação pode ser uma lista com links às viagens.

## Filtros e apresentação

- Período, situação, veículo e viagem/produto, com atalhos de período e indicação clara dos filtros aplicados.
- Período inicial sugerido: mês atual. Datas locais no fuso de São Paulo.
- Gráfico diário operacional por saída; valores/reservas pela saída inicial da viagem comercial no período, com legenda explicando o critério para pacotes. Não duplicar vendas em cada deslocamento.
- Destacar totais no topo e gráficos abaixo; detalhes e CSV continuam acessíveis.
- Interface responsiva, valores em reais, percentuais com legenda, tooltips e alternativa textual/tabela para os gráficos.
- Mensagens claras de vazio, carregamento e falha. Sem dados parciais apresentados como totais completos.

## Backend

- Criar endpoint agregado próprio para a visão gerencial. O relatório operacional atual limita a consulta a 50 viagens e 5.000 linhas; não reutilizar esse limite para um painel mensal com mais saídas.
- Agregar no banco e retornar séries resumidas, sem contatos, CPF ou credenciais dos passageiros.
- Usar alocações por deslocamento e capacidade registrada na viagem, incluindo troca de veículo em pacotes.
- Evitar multiplicação de valores e passageiros ao combinar reservas, paradas e veículos.
- Respeitar permissões definidas para a visão gerencial e RLS em todas as consultas.
- Manter limites de período e filtros para custo previsível; avaliar índices conforme as consultas finais.
- Não incluir lucro, margem, custo por quilômetro, taxa de pontualidade ou fluxo de caixa nesta etapa: faltam dados/custos ou bases adequadas para esses indicadores.

## Ordem de execução e aceite

1. Aplicar as definições confirmadas de métricas e permissões.
2. Implementar consultas agregadas, contrato da API e validação de filtros.
3. Acrescentar aba gerencial, gráficos e cartões.
4. Testar dias vazios, cancelamento, reservas expiradas, capacidade de veículos diferentes, paradas, pacotes, troca de veículo, filtros e isolamento entre empresas.
5. Validar desktop/celular, desempenho com mais de 50 viagens e regressão dos relatórios/CSV atuais.
6. Documentar fórmulas, validar no ambiente local e entregar atualização para a VPS.

## Entrega

Implementado `GET /api/v1/reports/management`, com agregação no PostgreSQL e isolamento por empresa. A aba Visão gerencial abre por padrão para administradores e atendentes. Inclui nove indicadores, os dois gráficos solicitados, situações das viagens/reservas, dez destinos/produtos e até trinta próximas saídas com ocupação inferior a 50%. O administrador pode abrir a consulta de franquia existente.

O período inicial inclui o mês atual inteiro. O filtro de veículo considera o valor integral da reserva comercial atendida por esse veículo, sem repartir preços entre destinos. Lugares disponíveis consideram o maior total simultâneo de confirmados e bloqueios válidos. Canceladas permanecem na contagem diária e na distribuição de situações, mas são excluídas da ocupação e dos valores confirmados.

As fórmulas e limites estão em [RELATORIOS.md](RELATORIOS.md). Pendências anteriores estão em [PENDENCIAS_FUTURAS.md](PENDENCIAS_FUTURAS.md). Não há nova migração nem alteração no aplicativo Android nesta entrega.

Validação: 205 testes do backend e 18 testes Chromium passaram: três da visão gerencial, quatorze de rotas/pacotes/viagens/perfis e um dos relatórios detalhados com CSV usando o backend local. A compilação Docker e a atualização local de API/web também passaram. Os testes incluem pacotes, troca de veículo, ocupação entre paradas, expiração, cancelamento, permissões, isolamento e agregação acima de cinquenta viagens. A publicação na VPS deve ser feita pelo script de implantação existente.
