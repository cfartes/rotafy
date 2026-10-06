# Nexus Rotafy — plano de desenvolvimento

Data: 2026-10-05.
Status: desenvolvimento iniciado em 2026-10-05; etapas 1 a 6 implementadas, incluindo bilhetes e embarque online. Progresso, validação e limites em docs/PROGRESSO.md. Próxima etapa: PWA/offline e sincronização.
Fontes: NEXUS_ROTAFY_DEV_SPEC.md e DECISOES_INICIAIS.md. As decisões posteriores do cliente prevalecem sobre a especificação original.

## 1. Objetivo e escopo

Entregar uma plataforma web SaaS multiempresa para administração de viagens, venda/reserva pública de pacotes, cadastro de famílias, distribuição de passageiros entre veículos, bilhetes e embarque offline. Um banco compartilhado com isolamento por empresa. Piloto com duas empresas e aproximadamente vinte veículos.

Primeira versão: painel Nexus, planos e consumo mensal, painel da agência, usuários, frota, viagens de ida/volta, reservas manuais e públicas, integrações externas, importação de passageiros, bilhetes QR, modo guia offline e modo motorista com consulta à operação atribuída.

Etapas posteriores: rastreamento, WhatsApp e aplicativos próprios Android/iOS por empresa. A página pública permite reservar o pacote. Pagamento ocorre fora da plataforma; haverá somente marcação administrativa PAGO na reserva. Integrações financeiras não fazem parte do plano atual nem estão assumidas para a segunda fase.

## 2. Stack proposta

| Camada | Escolha | Finalidade |
|---|---|---|
| Web | React, TypeScript, Vite, Tailwind | Painéis e interfaces responsivas |
| Dados web | TanStack Query | Consulta, atualização e estados de carregamento |
| Offline | Dexie/IndexedDB e service worker | Manifesto local, interface disponível e fila de eventos |
| API | FastAPI, Pydantic, SQLAlchemy, Alembic | Contratos versionados, regras e migrações |
| Banco | PostgreSQL com PostGIS | Dados transacionais e preparação geográfica |
| Assíncrono | Redis e Celery, conforme necessidade | Importações, expiração e notificações futuras |
| Infraestrutura | Docker Compose e Traefik | Serviços isolados e HTTPS na VPS |
| Mobile futuro | React Native com builds próprios Expo | Apps por empresa e localização nativa |

Versões estáveis e compatíveis serão fixadas nos arquivos de dependências durante a fundação. Backend como monólito modular. API /api/v1 compartilhada pelo web e mobile; nenhum cliente acessa diretamente o banco. Não serão criados serviços de telemetria ou envio WhatsApp na primeira versão.

Estrutura prevista: frontend/, backend/, infra/, docs/. Dados de exemplo somente para desenvolvimento e homologação.

## 3. Regras do produto e premissas

### Confirmadas

- Cadastro independente de funcionários por empresa, incluindo guia e motorista; login associado à empresa.
- Planos iniciais Basic, Professional e Enterprise, com nome, preço, franquia mensal e preço de viagem extra configuráveis pela Nexus. Sem preços fictícios em produção.
- Criar uma viagem consome uma unidade; cancelar estorna. Vários veículos e ida/volta na mesma viagem comercial não multiplicam o consumo.
- CPF opcional; reserva familiar com contato único e passageiros identificados individualmente.
- Distribuição por quantidade, sem poltronas numeradas. Sugestão de veículo para manter a família junta, respeitando capacidade.
- Pontos de embarque e desembarque distintos; preparação para transporte vendido por trechos.
- Vários guias simultâneos, reversão de embarque e registro de desembarque.
- Pagamentos recebidos pela agência; número de WhatsApp próprio de cada empresa na etapa futura.

### Premissas adotadas para desenvolver

- Viagem comercial identificada por registro próprio: não mesclar registros automaticamente apenas por destino/data.
- Franquia por aniversário mensal da assinatura, sem acumulação. Estorno vinculado ao período original. Reativação consome novamente e não permite duplicar estornos.
- Catálogo de pacotes e rascunhos não consomem franquia; conversão explícita em viagem operacional criada consome. Cancelar exige confirmação das consequências sobre reservas.
- Cobrança da assinatura Nexus inicialmente manual, com demonstrativo mensal e extras. Histórico de preço preservado; mudança de plano vale para o próximo ciclo por padrão.
- Família deve caber junta em cada trecho. Selecionar, entre veículos compatíveis, aquele com menor sobra de capacidade; desempate determinístico. A agência pode alterar a alocação respeitando lotação.
- Capacidade por segmento entre paradas, permitindo reutilizar vagas após desembarque. Ida e volta podem ter alocações diferentes, mantendo o grupo junto em cada trecho.
- Reserva pendente bloqueia vagas durante prazo configurável. Expiração ou cancelamento libera vagas uma única vez. Confirmação da reserva e pagamento são independentes: uma reserva confirmada pode estar NÃO PAGO. A agência terá uma ação manual Marcar como PAGO por reserva familiar do pacote/viagem, com registro de funcionário e data/hora. Não haverá processamento de pagamento, credenciais bancárias ou gateway.
- Sem vagas suficientes: não confirmar nem dividir a família silenciosamente; mostrar indisponibilidade e registrar aviso no painel da agência. Aviso não depende do WhatsApp futuro.
- Solicitação pública de contato após indisponibilidade exige ação explícita do comprador. Lista de espera automática não faz parte da primeira versão.
- Troca de veículo por outro menor bloqueada quando inviabilizar reservas existentes; realocação deve ser resolvida antes da troca.
- Papel motorista permite consultar viagens atribuídas e manifesto mínimo necessário; GPS entra posteriormente.
- Política inicial proposta: remover cache operacional após sincronização e encerramento da viagem; oferecer limpeza explícita no dispositivo e explicar pendências antes do logout. Retenção em servidor configurável, com padrão a definir na homologação.

Essas premissas são propostas documentadas e podem ser ajustadas antes da execução dos respectivos módulos.

## 4. Modelo de dados

| Grupo | Entidades e responsabilidades |
|---|---|
| Nexus | Administradores da plataforma, empresas, planos, versões de preço, assinaturas, períodos e lançamentos de consumo/estorno |
| Identidade | Contas por empresa, perfis, sessões, convites/recuperação e auditoria |
| Frota | Veículos, capacidade, situação e equipe |
| Comercial | Pacotes, preços, conteúdo público e publicação |
| Operação | Viagens comerciais, trechos, paradas ordenadas e veículos/equipe por trecho |
| Reservas | Responsável, passageiros, itens por trecho, alocações e bloqueios temporários |
| Bilhetes | Credenciais públicas individuais, validade e revogação |
| Embarque | Eventos de embarque/desembarque/reversão, origem, dispositivo e versão |
| Integrações | Chaves por empresa, idempotência, identificadores externos e notificações internas |

Entidades de cada empresa terão company_id; vínculos compostos impedem relacionamentos entre empresas. Restrições, índices e transações garantem integridade além dos filtros da API. Usuário operacional do banco não poderá contornar políticas de isolamento; jobs terão contexto de empresa explícito. Administração Nexus terá acesso separado e auditado.

Reservas e pagamentos serão estados independentes. Datas operacionais com fuso explícito, armazenadas em UTC quando representarem instantes. Valores monetários em centavos/decimal, nunca ponto flutuante.

## 5. Ordem de implementação

### Etapa 1 — Fundação, isolamento e autenticação

Entregas: estrutura do projeto, Docker local, migrações, empresas, contas, perfis, sessões, recuperação de acesso, auditoria, API documentada e interface base. Perfis: Nexus, administrador da empresa, atendente, guia e motorista. Branding por empresa e identificador de empresa no login/página pública.

Aceite: duas empresas de exemplo; acesso a dados de outra empresa negado em leituras e alterações; cadastros independentes com mesmo e-mail em empresas distintas; logout e recuperação de acesso funcionais. Segredos fora do código.

### Etapa 2 — Painel Nexus, planos e consumo

Entregas: CRUD de planos, empresas e assinaturas; situação de acesso; ciclo mensal; histórico de preços; demonstrativo de franquia e extras. Serviço de consumo integrado à criação/cancelamento implementado na etapa seguinte.

Aceite: parâmetros editáveis para os três planos; mudança de preço não altera períodos anteriores; fronteiras do ciclo mensal cobertas; suspensão impede novas operações comerciais sem apagar histórico.

### Etapa 3 — Frota, pacotes e viagens com vários veículos

Entregas: veículos e capacidade, funcionários, pacotes, viagens, ida/volta, paradas e atribuição de veículos/equipe. Agenda administrativa e status de viagem. Modelagem suporta trechos únicos, sem exigir lançamento completo da venda segmentada nessa etapa.

Aceite: uma viagem com dois veículos e ida/volta consome uma unidade; duplicação cria viagem distinta; cancelamento estorna uma vez; repetição de requisição não duplica consumo; conflitos de agenda de veículo/equipe identificados.

### Etapa 4 — Reservas familiares e disponibilidade

Entregas: cadastro manual, família, passageiros com CPF opcional, sugestão de veículo, bloqueio temporário, confirmação/cancelamento, realocação e importação CSV/XLSX com prévia e relatório de erros. Limites de arquivo e normalização de telefone sem pressupor que todos os clientes sejam brasileiros.

Aceite: duas compras simultâneas pela última vaga não ultrapassam capacidade; ida e volta validadas na mesma reserva; família não é dividida automaticamente; vagas liberadas corretamente; importação repetida não cria duplicações silenciosas; troca de veículo respeita ocupação.

### Etapa 5 — Página pública e integrações externas

Entregas: catálogo/página de pacote com marca da agência, datas/preços, seleção de pontos, formulário familiar, resumo e solicitação de reserva. Link de acompanhamento para o responsável. Confirmação manual pela agência, opção Marcar como PAGO na reserva e avisos de indisponibilidade. API externa com chaves por empresa e idempotência; contrato para sistemas de venda externos. Integração de reservas não inclui integração financeira nem autoriza uma chamada pública a marcar uma reserva como paga.

Aceite: página pública não expõe outros passageiros; repetição de formulário ou chamada externa não duplica reserva; reserva pendente expira e libera capacidade; comprador vê confirmação e situação reais. Somente funcionário autorizado da empresa pode marcar PAGO; ação auditada e isolada por empresa. Marcação não altera a cobrança de viagens da Nexus nem confirma silenciosamente uma reserva cancelada/expirada.

### Etapa 6 — Bilhetes e interfaces operacionais

Entregas: bilhete individual com QR, marca, viagem, pontos e status; links revogáveis; download/impressão e compartilhamento manual. Modo motorista com agenda e detalhes autorizados. Modo guia com busca, contagem e embarque/desembarque/reversão online.

Aceite: QR válido apenas para viagem/trecho autorizado; bilhete cancelado não embarca; credencial pública não dá acesso ao manifesto; dois guias não duplicam embarque; CPF não aparece integralmente em telas públicas.

### Etapa 7 — Embarque offline e sincronização

Situação em 2026-10-06: implementação local e testes automatizados entregues. Uso e limites em [docs/OFFLINE_E_SINCRONIZACAO.md](docs/OFFLINE_E_SINCRONIZACAO.md). Aceite em iPhone/Android físicos permanece pendente antes da liberação operacional.

Entregas: instalação PWA, cache de interface e manifesto mínimo por viagem/veículo, scanner e confirmação manual offline, fila local com identificadores únicos e versões. Servidor registra eventos idempotentes e devolve aceitos/rejeitados/conflitantes. Interface distingue estado local pendente do estado confirmado.

Aceite: após preparação online, abrir/reabrir a interface e operar em modo avião; sincronizar sem duplicação; lidar com reconexão parcial, token revogado, cancelamento e alterações de manifesto. Conflito entre reversão e embarque em aparelhos diferentes fica visível para resolução autorizada. Validar em iPhone e Android reais; offline não promete visibilidade instantânea de eventos de outro aparelho.

### Etapa 8 — Relatórios, homologação e implantação

Situação em 2026-10-06: relatórios, logs/métricas, configuração de produção, serviço de backup externo e documentação entregues localmente. Ensaio de restauração e carga de leitura aprovados. Publicação na VPS, envio/recuperação pelo storage externo e aceite em aparelhos físicos permanecem pendentes. Evidências e roteiro em [docs/HOMOLOGACAO.md](docs/HOMOLOGACAO.md).

Entregas: ocupação por veículo/trecho, reservas com status PAGO/NÃO PAGO, presença e consumo por empresa; estados vazios/erros e acessibilidade; logs estruturados, métricas básicas, backup externo e restauração ensaiada. Compose de produção e procedimento de atualização/rollback no domínio definido.

Aceite: fluxo completo com duas empresas, testes de isolamento e concorrência aprovados, jornadas de atendente/guia/motorista/passageiro homologadas, HTTPS, backups restauráveis e carga representativa medida. Implantação após resultado revisável; este plano não autoriza alterações imediatas na VPS.

## 6. Etapas posteriores

Integrações com sistemas de pagamento ficam fora deste plano. Só serão planejadas mediante solicitação futura do cliente.
2. Rastreamento: API de ingestão autenticada, vínculo dispositivo/veículo, normalização de GPS, tempo de coleta/recepção, qualidade e retenção; Redis/WebSocket, mapa e estado de localização desatualizada. ETA exige serviço de roteamento próprio/contratado; distância geográfica não será apresentada como tempo garantido.
3. WhatsApp: conta/número por agência, templates e credenciais protegidas, fila, tentativas e histórico de entrega. Alertas de proximidade deduplicados.
4. Apps Android/iOS por empresa: base compartilhada, builds e identidade por cliente, fluxos dos três públicos, login operacional e passageiro por credencial apropriada. Localização em segundo plano exige recurso nativo e validação de bateria/permissões; encerramento forçado não terá promessa de rastreamento contínuo. Publicação por empresa planejada conforme regras das lojas. Um piloto nativo do motorista deve preceder a liberação do rastreamento por celular com tela desligada.

## 7. Verificação e riscos concretos

- Testes prioritários: isolamento por empresa, permissões, consumo/estorno, disponibilidade concorrente, família e segmentos, expiração, idempotência e conflito offline.
- Testes ponta a ponta das jornadas de reserva pública, cadastro manual, marcação PAGO, bilhete e embarque. Testes de GPS somente na etapa correspondente.
- Capacidade da VPS será validada por medição; quatro CPUs e 24 GB não substituem conhecer conexões, tráfego e serviços existentes. Reservar espaço para banco, arquivos, logs e crescimento; backups fora dos 100 GB locais.
- API e banco não publicados indiscriminadamente; somente proxy HTTPS exposto. Rotação de logs e segredos, armazenamento persistente e verificação de saúde.
- Antes do deploy: inventariar containers/portas existentes, confirmar DNS, acesso administrativo e destino dos backups. Esses dados não impedem desenvolvimento local.
- Armazenamento de marca/arquivos em volume persistente atrás de interface compatível com futura migração para storage externo; upload SVG não será renderizado sem tratamento seguro.
- Token de bilhete e QR, sessão operacional e API key são credenciais com finalidades distintas. Logs e analytics não devem registrar tokens ou manifestos completos.

## 8. Conclusão do planejamento

Não há dúvida de produto impeditiva para iniciar a fundação. As premissas estão explícitas; dados de infraestrutura são necessários antes da implantação. Cada etapa termina com entrega demonstrável e seus critérios de aceite. Não fixar prazo fechado antes de concluir a fundação e medir a execução.
