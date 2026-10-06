# Nexus Rotafy — decisões iniciais

Data: 2026-10-03. Este registro complementa NEXUS_ROTAFY_DEV_SPEC.md; em caso de conflito, as decisões confirmadas abaixo prevalecem sobre a especificação original.

Atualização: 2026-10-05. Plano detalhado em PLANO_DESENVOLVIMENTO.md.

## Confirmado pelo cliente

- Primeira entrega: módulos administrativos, viagens, reservas, passageiros, bilhetes e embarque. Rastreamento e integração WhatsApp ficam para uma etapa posterior.
- Web multiempresa em banco compartilhado. Futuramente, um aplicativo Android/iOS por empresa cliente.
- Rastreamento futuro: dispositivo GPS/OBD2 ou celular do motorista, inclusive com tela desligada.
- Guia e motorista terão login e cadastro independente em cada empresa em que trabalham.
- Painel Nexus para administrar empresas e planos.
- Reservas cadastradas manualmente pelo atendente e originadas de página pública de compra/integrada.
- Planos iniciais: Basic, Professional e Enterprise. Cadastro configurável de nome, quantidade de viagens, valor do plano e valor por viagem extra.
- Cobrança por viagem, independente do número de veículos da mesma rota/dia; ida e volta compõem uma viagem comercial. Franquia mensal consumida ao criar a viagem e estornada ao cancelar.
- Viagens com ida e volta, vários veículos e pontos diferentes de embarque e desembarque.
- CPF opcional. Reserva familiar com um único telefone e passageiros individuais.
- Distribuição por capacidade, sem escolha de poltrona numerada. O sistema sugere o melhor veículo para a família; se não houver capacidade suficiente, informa o comprador e a agência.
- Página própria de compra de pacotes e suporte a integrações com sites externos.
- Operação de agências com ida e volta; modelagem preparada para venda por trechos de transporte, como Blumenau–Aeroporto de Navegantes.
- Vários guias podem operar simultaneamente; devem poder desfazer embarques e registrar desembarques.
- Apps futuros atenderão passageiros, guias e motoristas.
- Cada empresa terá seu próprio número de WhatsApp na etapa de integração.
- Infraestrutura disponível: VPS Hostinger com Docker, 4 CPUs, 24 GB RAM e 100 GB de armazenamento. Estimativa inicial: duas empresas, dez veículos por empresa.
- Domínio definido: frotafy.nexusdataanalytics.com.br. Nome público confirmado: Nexus Rotafy.
- Pagamentos dos passageiros serão recebidos diretamente por cada agência, fora do Nexus Rotafy.
- Correção do cliente: sem integração com sistemas de pagamento no escopo atual. Somente opção administrativa para marcar a reserva do pacote/viagem como PAGO. Integração futura não é compromisso da segunda fase e depende de nova definição de escopo.

## Arquitetura proposta, ainda não confirmada

- Web: React, TypeScript e Vite, com Tailwind e persistência offline via IndexedDB.
- Backend: FastAPI, SQLAlchemy e Alembic; API versionada compartilhada pelos clientes web e mobile.
- Banco: PostgreSQL com PostGIS, company_id, políticas de isolamento por linha e restrições de relacionamento entre entidades da mesma empresa.
- Redis e workers para tarefas assíncronas conforme necessário.
- Docker Compose e proxy HTTPS na VPS; backups fora da VPS.
- Mobile futuro: React Native com Expo development builds, configurações de marca por empresa e recursos nativos de localização.
- Monólito modular inicialmente, com módulos de identidade, empresas, planos, viagens, reservas, alocação, bilhetes e embarque.
- Nenhum cliente web/mobile terá acesso direto ao banco.
- Credenciais operacionais separadas dos bilhetes públicos. Bilhete não autoriza acesso ao manifesto completo.
- Rastreamento com tela desligada será tratado como recurso nativo/hardware; não dependerá do Wake Lock do navegador.

## Mudanças necessárias na modelagem original

- Separar viagem comercial, trechos de ida/volta e alocação de veículos por trecho.
- Separar reserva familiar, passageiros e bilhetes/alocações.
- Modelar capacidade e ocupação por veículo e trecho, incluindo concorrência entre reservas.
- Acrescentar contas por empresa, perfis, permissões e atribuições de guia/motorista.
- Acrescentar catálogo de planos, assinaturas, histórico de preços e eventos idempotentes de consumo de viagens.
- Acrescentar eventos de embarque idempotentes e política para conflitos offline.
- Preservar registros históricos ao alterar planos, veículos e reservas.

## Questões pendentes

Não há dúvida impeditiva para elaborar o plano da primeira versão. Não há provedor ou integração de pagamento a definir no escopo atual. As regras propostas abaixo são premissas do plano, não novas confirmações do cliente.

## Regras propostas para fechar o plano

- Uma viagem comercial tem identificador próprio; não agrupar automaticamente apenas por destino/data. Adicionar veículos e trechos à mesma viagem não gera novos consumos.
- Reserva familiar deve caber integralmente no mesmo veículo em cada trecho; se não couber, não dividir nem confirmar silenciosamente.
- Ocupação calculada por segmento entre paradas para permitir venda de trechos com embarques/desembarques diferentes.
- Reservas concorrentes e integrações usam a mesma validação transacional de disponibilidade.
- Ciclo mensal segue o aniversário da assinatura; franquia não acumula. Cancelamento estorna o lançamento original, sem criar crédito de viagens no mês seguinte. Valores faturados precisam de política própria.
- Cobrança da assinatura Nexus inicialmente manual; pagamento do passageiro é uma decisão independente.
- Reservas pendentes de pagamento têm bloqueio temporário de capacidade, com prazo configurável.
- Alterações e reversões de embarque ficam auditadas; conflitos offline não serão resolvidos silenciosamente.

## Referências técnicas consultadas

- https://docs.expo.dev/versions/latest/sdk/location/
- https://www.postgresql.org/docs/17/ddl-rowsecurity.html
- https://fastapi.tiangolo.com/deployment/docker/
- https://developer.apple.com/app-store/review/guidelines/

Desenvolvimento autorizado e iniciado em 2026-10-05. Progresso em docs/PROGRESSO.md.
