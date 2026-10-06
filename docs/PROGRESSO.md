# Progresso do desenvolvimento

Atualizado em 2026-10-06.

## Entrega inicial — fundação

- React/TypeScript/Vite/Tailwind e API FastAPI em execução local com Docker.
- PostgreSQL/PostGIS, migrações Alembic e papéis separados para plataforma e empresas.
- Login Nexus e login com identificador da empresa; contas independentes por empresa.
- Perfis administrador, atendente, guia e motorista.
- Cadastro de empresa com administrador inicial; suspensão e ativação.
- Cadastro de equipe, suspensão/ativação e proteção do acesso administrativo.
- Marca por empresa: nome comercial, razão social e cores editáveis pelo administrador.
- Sessões persistidas, cookies HttpOnly, CSRF, logout e revogação.
- Troca de senha; link manual de recuperação individual e de uso único, com expiração.
- Auditoria de ações, telas responsivas e estados de erro/carregamento.

## Verificação

- 19 testes de backend aprovados com PostgreSQL real: isolamento entre empresas, privilégios, vínculos compostos, CSRF, limite de tentativas, expiração/revogação, recuperação, marca e validações.
- 2 testes de navegador Chromium aprovados: cadastro completo de empresa/equipe, edição de identidade, sessão após recarga, logout, navegação mobile e credenciais inválidas.
- Build TypeScript/Vite aprovado; Ruff e verificação de formatação Prettier aprovados.
- Imagens Docker construídas; migrações 0001_identity e 0002_branding executadas; API e banco saudáveis.
- Screenshots desktop/mobile disponíveis em docs/screenshots/.
- Corrigida uma condição de corrida de gravação: transações autenticadas agora terminam antes de a resposta ser enviada ao cliente.
- Há um aviso de depreciação do transporte httpx no TestClient da versão atual de Starlette, sem falhas nos testes.

## Etapa 2 — planos e assinaturas

- Catálogo inicial Basic, Professional e Enterprise sem valores fictícios; configuração de nome, preço, franquia e viagem extra.
- Cadastro de planos adicionais, ativação/arquivamento e histórico imutável de condições.
- Assinatura por empresa, data inicial e alteração de plano no próximo ciclo.
- Ciclos mensais por aniversário no fuso America/Sao_Paulo, inclusive dias 29/30/31 e anos bissextos.
- Períodos preservam suas versões de preço; manutenção periódica recupera ciclos pendentes.
- Demonstrativos de consumo, franquia disponível, viagens extras e valor total; consulta da agência em Meu plano.
- Serviço interno de consumo/estorno idempotente, com reversão no mês original e proteção contra duplicação concorrente.
- Isolamento por empresa e históricos de preços, períodos e eventos protegidos contra edição/exclusão pelos papéis de runtime.
- Migração 0003_billing aplicada preservando empresas existentes; container billing com verificação de saúde.
- Regras documentadas em docs/PLANOS_E_ASSINATURAS.md.

### Validação da etapa 2

- 42 testes de backend aprovados, incluindo regressões da fundação, fronteiras de ciclos, preços históricos, isolamento, consumo/estorno e operações concorrentes de renovação e consumo.
- 3 testes de navegador aprovados, incluindo catálogo/assinatura/histórico, mudança agendada, consulta da agência no celular e regressões de cadastro/login.
- Build TypeScript/Vite, Ruff e formatação Prettier aprovados.
- API, PostgreSQL e worker de ciclos saudáveis; migração aplicada em Docker.
- Screenshots em docs/screenshots/planos-nexus.png e docs/screenshots/meu-plano-mobile.png.

## Etapa 3 — frota, pacotes e viagens

- Cadastro e edição de veículos, placa normalizada, capacidade e arquivamento.
- Catálogo de pacotes com destino, descrição, preço por passageiro e arquivamento.
- Viagem avulsa ou vinculada a pacote, com ida/volta ou trecho único e paradas de embarque/desembarque por trecho.
- Múltiplos veículos por viagem, motorista e vários guias por veículo; capacidade preservada na atribuição.
- Lista administrativa de viagens e detalhes do itinerário/equipe; iniciar, concluir, cancelar e duplicar com novos horários.
- Guias e motoristas consultam somente as viagens atribuídas, sem permissões administrativas.
- Bloqueio de sobreposição de agenda durante todo o intervalo da viagem, com serialização de comandos por empresa.
- Criação e consumo da franquia na mesma transação; cancelamento e estorno atômicos; idempotência e histórico preservados.
- RLS forçado nos novos cadastros, inclusive para a conexão de comandos; vínculos compostos e referência do consumo à viagem real.
- Migrações 0004_operations e 0005_trip_usage; regras documentadas em docs/FROTA_E_VIAGENS.md.

### Validação da etapa 3

- 60 testes de backend aprovados: regressões das etapas anteriores e 18 casos de operações, incluindo concorrência, idempotência, isolamento, permissões, agendas, validações, capacidade histórica e reversão integral de operações sem assinatura.
- 4 testes Chromium aprovados: regressões das etapas anteriores e jornada de frota/pacote, dois veículos com ida/volta e parada, duplicação em outra data, cancelamento e conferência de consumo; visualização desktop/mobile.
- Build TypeScript/Vite, Ruff e formatação Prettier aprovados; containers e migrações atualizados, API/banco/worker saudáveis.
- Execução de navegador com conta Nexus temporária exclusiva, revogada no encerramento, preserva o limite de login da conta administrativa habitual. Comando: `.venv/Scripts/python.exe scripts/test_e2e.py`.
- Screenshots em docs/screenshots/viagens-desktop.png e docs/screenshots/viagens-mobile.png.

## Etapa 4 — reservas familiares e disponibilidade

- Cadastro manual de responsável/telefone e passageiros, com CPF opcional e validação quando informado.
- Normalização de telefone com país explícito ou código internacional, inclusive números curtos válidos de outros países.
- Itinerário da família por trecho e pontos de embarque/desembarque; ida e volta verificadas na mesma reserva.
- Ocupação por segmento e sugestão de veículo que mantenha toda a família junta, sem divisão automática.
- Reservas confirmadas ou bloqueios pendentes de 15 minutos; confirmação, cancelamento e expiração automática.
- Realocação de toda a família com verificação da capacidade nos trechos e preservação de passageiros/valor.
- Cancelar viagem também cancela suas reservas ativas na mesma transação. Reservas não alteram a franquia de viagens.
- Importação CSV/XLSX com modelo, limites, prévia, erros por linha e confirmação atômica do lote. Repetições e referências já importadas não duplicam reservas.
- Dados e prévias isolados por empresa com RLS/vínculos compostos; operação reservada a administrador e atendente.
- Migrações 0006_reservations e 0007_international_phones; instruções em docs/RESERVAS_E_DISPONIBILIDADE.md.
- Screenshots em docs/screenshots/reservas-desktop.png e docs/screenshots/reservas-mobile.png.

### Validação da etapa 4

- 82 testes de backend aprovados: regressões e 22 casos de reservas/importação. Incluem disputa pela última vaga, confirmação após expiração, ocupação por segmento/ida-volta, realocação, cancelamento da viagem, CPF opcional/repetido, telefones internacionais, RLS/CSRF e importação idempotente/atômica com limites e erros por linha.
- 5 testes Chromium aprovados: regressões e jornada de reserva familiar, bloqueio/confirmação, realocação, indisponibilidade sem divisão da família, importação com erro/prévia/repetição e layout desktop/mobile.
- Corrigida uma condição de corrida na tela: seleção de veículo não é apagada ao terminar uma confirmação; o seletor fica desabilitado durante a operação.
- Build TypeScript/Vite, Ruff e formatação Prettier aprovados. Containers locais e migrações atualizados; API, banco e worker saudáveis.

## Etapa 5 — página pública e integrações

- Catálogo e oferta por agência, com viagens privadas por padrão e publicação manual por administrador/atendente.
- Formulário público familiar com CPF opcional, pontos de embarque/desembarque, sugestão de veículo e bloqueio pendente por 15 minutos.
- Acompanhamento privado da família por token aleatório; geração, rotação e revogação pelo painel. Dados públicos excluem CPF, telefone, placas e equipe.
- Marcação e remoção manual PAGO, independente da confirmação da reserva e sem alterar franquia. Nenhum pagamento é processado.
- Alertas no painel quando não cabem todos os passageiros no mesmo veículo; botão do comprador para avisar a agência e reconhecimento do aviso no painel.
- Chaves de integração nomeadas, com validade, exibição única e revogação; criação idempotente e consulta restrita às reservas da mesma chave.
- Upload administrativo de PNG/JPEG com limites, redução e remoção de metadados; marca e botões públicos com contraste de texto adequado.
- Migração 0008_public_sales; documentação em [PAGINA_PUBLICA_E_INTEGRACOES.md](PAGINA_PUBLICA_E_INTEGRACOES.md).

### Validação da etapa 5

- 90 testes de backend aprovados: 82 regressões anteriores e 8 casos específicos de privacidade, isolamento, idempotência, PAGO, alertas, chaves, expiração/revogação, papéis, origem e logo.
- 6 testes Chromium aprovados, incluindo publicação e chave no painel, reserva pública, confirmação/PAGO, acompanhamento, aviso de indisponibilidade e revogação do link. Layout mobile sem rolagem horizontal.
- Build TypeScript/Vite, Ruff e Prettier aprovados. Migração aplicada no Docker local; API, banco e worker saudáveis. Contratos temporários da homologação encerrados, preservando o histórico.
- Capturas em docs/screenshots/pagina-publica-desktop.png, pagina-publica-mobile.png e acompanhamento-mobile.png.

## Etapa 6 — bilhetes e interfaces operacionais

- Bilhete individual por passageiro e trecho, com marca, pontos/horários e QR de credencial aleatória. Emissão após confirmação, reemissão e revogação no painel.
- Página privada do bilhete com compartilhamento manual, download do QR e impressão/salvamento em PDF pelo navegador. Sem CPF, telefone ou dados de outros passageiros.
- Manifesto restrito ao veículo atribuído, com busca por nome, contagens e presença independente de ida/volta. Motorista consulta; guia, administrador e atendente registram presença.
- Leitura online pela câmera, imagem QR ou código/link; conferência do passageiro antes do embarque. Leitor carregado sob demanda.
- Embarque, desembarque e reversão com versão obrigatória, operação idempotente, auditoria e histórico de eventos sem permissão de edição/exclusão pelos papéis da aplicação.
- Encerramento/cancelamento bloqueado enquanto houver passageiros a bordo. Realocação de família bloqueada após qualquer registro de presença.
- Migração 0009_boarding e instruções em [BILHETES_E_EMBARQUE.md](BILHETES_E_EMBARQUE.md).

### Validação da etapa 6

- 100 testes de backend aprovados: 90 regressões anteriores e 10 testes de bilhetes, privacidade, atribuições, papéis, versões, idempotência por funcionário, concorrência, revogação, estados por trecho, encerramento e RLS/histórico imutável.
- 7 testes Chromium aprovados: regressões e jornada de QR real com emissão, bilhete mobile, leitura da imagem, embarque/reversão/desembarque, trecho incorreto e motorista somente leitura. Perda de resposta após commit simulada: repetição recupera resultado sem duplicar evento.
- Executor de homologação usa contas Nexus separadas por arquivo de cenário, revogadas no encerramento; limite de login da aplicação preservado. Contratos temporários encerrados sem apagar histórico.
- Build TypeScript/Vite, Ruff e Prettier aprovados. Docker local atualizado; API, banco e worker saudáveis.
- Capturas em docs/screenshots/bilhete-mobile.png, embarque-desktop.png e embarque-mobile.png. Câmera em aparelhos físicos ainda exige homologação.

## Etapa 7 — PWA, embarque offline e sincronização

- PWA com interface e leitor QR disponíveis sem rede; preparação autenticada do manifesto por usuário, veículo e trecho, limitada a oito horas ou à validade da sessão.
- IndexedDB/Dexie com manifesto mínimo, hashes de bilhetes e fila durável. Estados locais pendentes distinguem-se dos confirmados; operações sobrevivem à recarga e reabertura no mesmo navegador.
- QR por câmera, imagem ou código/link, confirmação manual, desembarque e reversão offline. Motorista mantém acesso somente para consulta.
- Sincronização automática enquanto a tela está aberta e botão manual; identificação única e versão por ação, recuperação após resposta perdida e bloqueio de ações dependentes em conflito/rejeição.
- Resolução explícita de conflitos: manter servidor ou reaplicar após consultar o estado atual. Proteção da fila ao sair, trocar acesso e remover dados; armazenamento compartilhado entre abas com bloqueio de sincronização.
- Revalidação de operador original, atribuição, viagem, reserva, QR e versão no servidor. Horários de captura e recepção separados; migração 0010_offline_events.
- Instruções e limites em [OFFLINE_E_SINCRONIZACAO.md](OFFLINE_E_SINCRONIZACAO.md).

### Validação da etapa 7

- 108 testes de backend aprovados, incluindo oito casos específicos de preparação, privacidade, perfis/empresas, validade da sessão, metadados, identidade, cancelamento, revogação, idempotência e conflitos. Casos offline repetidos após o ajuste final do código de erro.
- 8 testes Chromium aprovados, com todas as jornadas anteriores e operação offline: oito máscaras QR reais, recarga e nova aba sem rede, fila persistente, perda de resposta após commit sem duplicação, conflito entre operadores, revisão/reaplicação, bilhete revogado e logout bloqueado com fila.
- Leitor de imagem recebeu uma alternativa para decodificar QR exportado quando a detecção de uma foto falha. Testes aguardam o término do logout antes de navegar; cenário concorrente de consumo corrigido para tolerar todos os índices únicos na preparação da mesma viagem.
- Build TypeScript/Vite, Ruff e Prettier aprovados; Docker local atualizado. Capturas em docs/screenshots/offline-pendentes-mobile.png e offline-conflito-desktop.png.
- Instalação, câmera e modo avião em iPhone/Android físicos ainda precisam de homologação em HTTPS. Os testes Chromium não substituem esses aparelhos.

## Etapa 8 — relatórios e preparação operacional

- Relatórios restritos à empresa/perfil: ocupação por segmento, reservas familiares com PAGO/NÃO PAGO, presença por veículo/trecho e consumo por ciclo. Nexus consulta consumo por empresa; atendente não acessa condições da assinatura.
- Datas inclusivas no fuso de Brasília, limites de período/volume, filtros, CSV em português e reais, proteção contra fórmulas e ausência de CPF/telefone/credenciais. Contagens por segmento não são apresentadas como passageiros únicos.
- Índices de relatórios na migração 0011_report_indexes. Interface responsiva com estados de carregamento, vazio e erro; legenda distingue presença confirmada das ações offline pendentes.
- Logs JSON com rota normalizada, identificador da requisição, status, duração e classe de erro; sem URL bruta/query/corpo. Métricas somente para Nexus, em memória por processo. Worker registra conclusão/falha em JSON.
- Compose de produção independente: HTTPS/Caddy, cookies Secure, banco/API sem portas publicadas, confiança no IP do proxy, tags de entrega, imagens de infraestrutura fixadas e rotação de logs.
- Serviço de backup custom PostgreSQL/restic para S3 externo, configuração separada e agenda systemd preparadas. O envio externo não foi executado: destino e credenciais ainda faltam.
- Ensaio de backup/restauração com snapshot consistente, container novo sem rede/portas, banco criado de template0, conferência das contagens/revisão/papéis/RLS e histórico imutável. Arquivo em RESTORE_DRILL_RESULT.json; banco de origem não alterado.
- Carga local: duas empresas, 20 veículos, 800 passageiros e 100 consultas com dez leitores simultâneos, sem erros ou mistura de dados. Latências em LOAD_TEST_RESULT.json; não representam SLA da VPS nem carga de escrita.
- Instruções em [RELATORIOS.md](RELATORIOS.md), [IMPLANTACAO_E_OPERACAO.md](IMPLANTACAO_E_OPERACAO.md) e [HOMOLOGACAO.md](HOMOLOGACAO.md).

### Validação da etapa 8

- 118 testes de backend aprovados: regressões e dez novos casos de relatórios, isolamento/papéis, segmentos parciais, expiração, presença, estorno, datas/limites, CSV, privacidade dos logs, métricas e carga concorrente. Relatórios/observabilidade repetidos após os ajustes finais de exportação/logs.
- 9 jornadas Chromium aprovadas, incluindo relatório da agência/Nexus, filtros, PAGO, presença, consumo, CSV e viewport mobile. Menu lateral corrigido para permitir rolagem/logout em janelas baixas; atalho para pular ao conteúdo.
- Build TypeScript/Vite, Ruff e Prettier aprovados. Configuração de produção e Caddy validados sem publicação; imagem de backup construída, versão restic e sintaxe do script conferidas. Docker local saudável.
- Capturas em docs/screenshots/relatorios-desktop.png e relatorios-mobile.png. Contratos temporários dos cenários encerrados, preservando histórico.
- Aceite operacional ainda depende de aparelhos físicos, inventário/DNS/HTTPS na VPS, destino de backup externo, recuperação a partir desse destino e piloto/carga no servidor.

## Complemento — edição, realocação e acesso por e-mail

- Editor de viagens agendadas sem eventos de embarque: nomes, pacote, preço futuro, pontos/horários e equipe, com conflitos de agenda, versões de edição e preservação dos IDs/franquia/valores vendidos.
- Editor de reservas ativas: responsável, telefone, nomes/CPF e pontos dos trechos sem histórico, com capacidade por segmento, duplicidades e preservação de passageiros/bilhetes/PAGO.
- Realocação após desembarque ou reversão, inclusive em viagem em andamento, sem passageiros a bordo; estados em espera acompanham o veículo e o histórico concluído fica preservado.
- Convites, reenvio e recuperação por e-mail de agência/Nexus via Resend, fila persistente com retentativas/idempotência e painel de status por empresa. Links de uso único, expiração e revogação de sessões.
- Migração 0012 aplicada no Docker local. Serviço `email` preparado nos dois Composes; sem chave/remetente configurados, nenhum envio real é realizado.
- Regras e configuração em [EDICAO_E_EMAILS.md](EDICAO_E_EMAILS.md).
- Validação final: 130 testes de backend e 10 jornadas Chromium aprovados, incluindo edição, convites/recuperação com transporte simulado e regressão offline. Ruff, Prettier, TypeScript/Vite e os dois Composes aprovados; serviços locais saudáveis.
- Restauração da revisão 0012 aprovada em container isolado, com contagens de 18 tabelas, duas empresas e histórico protegido; resultado atualizado em RESTORE_DRILL_RESULT.json. Envio Resend real e publicação na VPS permanecem pendentes de configuração.

## Próxima entrega

### Correção da validação de formulários

Erros 422 agora identificam o campo e explicam o ajuste, inclusive CNPJ opcional e senha do administrador, sem exibir os valores enviados. Cadastro da empresa preserva os dados após erro e trata CNPJ com espaços como vazio. Cenário Chromium reproduziu o CNPJ de 13 dígitos, conferiu a mensagem específica e concluiu o cadastro ao limpar o campo opcional. Três jornadas de fundação, TypeScript/Vite e Prettier aprovados; Docker web atualizado localmente.

VPS identificada como `187.77.58.10`, acesso `root`. SSH respondeu, mas recusou as chaves disponíveis; chave pública exclusiva preparada em `infra/nexus-rotafy-deploy.pub`, com instruções de cadastro no guia de implantação. Consulta DNS em 06/10/2026 retornou domínio inexistente. Inventário remoto, configuração DNS e escolha do storage externo continuam pendentes; nenhuma alteração foi feita no servidor.

Homologação física e preparação da publicação na Hostinger com os dados do servidor e do storage externo. A implementação local das oito etapas está disponível; o aceite final e a publicação ainda não foram concluídos.

## Limites atuais

- Sem implantação na Hostinger; os serviços estão somente na máquina local.
- Envio real de convites/recuperação depende da chave Resend, remetente verificado e homologação da caixa de destino.
- Edição de viagens preserva os veículos/trechos e protege itinerário/equipe após eventos de embarque. Editor de reservas preserva passageiros/trechos e protege pontos com histórico; detalhes no guia complementar.
- Consumos não têm endpoint de edição manual. Não há emissão automática de faturas nem pró-rata de assinatura.
- Sem pagamento integrado, rastreamento ou WhatsApp.
- Uso offline exige preparar cada veículo/trecho com conexão. Eventos de outros aparelhos, cancelamentos e revogações só são conhecidos após reconectar; filas locais não sincronizam com a tela fechada.
- Realocação exige família sem passageiros a bordo; o histórico de trechos concluídos permanece no veículo original.
- Homologação do offline em aparelhos reais está pendente; screenshots mobile são em viewport Chromium. Limpeza do armazenamento pelo navegador ou pelo usuário pode perder ações ainda não sincronizadas.

## Ajustes do cadastro e acesso da empresa — 06/10/2026

- CPF/CNPJ opcional com máscara, preservação de zeros iniciais e validação de dígitos verificadores, incluindo CNPJ alfanumérico. Mensagens específicas para documento inválido e documento/identificador já cadastrado.
- Aplicativo instalado inicia no painel. Acesso online ao offline sem manifesto nem fila encaminha administradores e atendentes ao painel; operação preparada e ações pendentes são preservadas.
- Atalhos para Veículos, Viagens, Alocar veículos e Passageiros; passageiros são cadastrados nas reservas da viagem.
- Inclusão de veículos em viagens agendadas antes dos embarques, com conflitos de agenda/equipe validados, preservando reservas existentes e consumo da franquia.
- Validação: 145 testes de backend e 10 jornadas Chromium aprovados, incluindo máscaras, duplicidades, entrada no painel, atalhos e inclusão de terceiro veículo sem novo consumo. Build e verificações de código aprovados; Docker local atualizado.

## Gerenciamento da empresa e acesso ao plano — 06/10/2026

- Nexus pode editar nome comercial, razão social, identificador e CPF/CNPJ pela ação **Editar dados** na empresa. Validação de documento e duplicidades, permissão exclusiva Nexus e registro de auditoria; usuários, marca, status e assinatura preservados.
- A ação **Gerenciar plano** abre Planos e assinaturas com a empresa selecionada, para vincular o plano ou agendar sua troca. O cadastro informa onde definir a assinatura após salvar.
- Validação: 57 testes de backend de documentos, identidade e cobrança; quatro jornadas Chromium de assinatura/cadastro/acesso aprovadas. Build TypeScript/Vite aprovado e Docker local atualizado. Nenhuma migração necessária.

- Ajuste de navegação: **Gerenciar plano** agora abre somente a assinatura da empresa, com seleção do plano no primeiro conteúdo visível. O catálogo e a lista geral de assinaturas ficam no menu **Planos e assinaturas**. Jornada Chromium de vinculação, troca de condições e agendamento aprovada, incluindo ausência do catálogo e formulário no viewport; build e Docker web atualizados.

## Cadastro SaaS com contratação inicial — 06/10/2026

- Primeiro acesso pelo link **Criar minha empresa**, com página `/cadastro`: dados da empresa, documento obrigatório, plano e credenciais do administrador com confirmação de senha.
- Cadastro Nexus também exige CPF/CNPJ e plano. Planos disponíveis precisam estar ativos e configurados; valores e franquia vêm do servidor. Empresa, administrador, assinatura e primeiro ciclo iniciados hoje são criados atomicamente, sem consumo de viagem.
- Validação de CPF/CNPJ por formato, dígitos verificadores e unicidade; dados anteriores preservados, mas edição exige documento válido. CPF de passageiros permanece opcional.
- Endpoints públicos de planos/cadastro com origem permitida, limites por IP/documento e resposta sem credenciais/dados de outras empresas. Sem consulta cadastral à Receita, pagamento integrado ou envio automático de cobrança.
- Validação final: 160 testes de backend e 11 jornadas Chromium aprovados; build TypeScript/Vite, Ruff e Prettier aprovados. API, web e workers atualizados no Docker local. Guia em CADASTRO_SAAS.md.

## Cidades, documentos interestaduais e rotas por veículo — 06/10/2026

- Seleção dependente UF/cidade de origem e destino por trecho, com municípios oficiais do IBGE disponíveis localmente e validação canônica no servidor.
- CPF de todos os passageiros quando qualquer trecho cruza UFs. Flags de estrangeiro e menor de cinco anos permitem ausência de CPF; nascimento obrigatório para a exceção infantil e idade verificada em todos os trechos. Regras aplicadas em reservas manuais/públicas, edição, integração, confirmação e importação CSV/XLSX.
- Endereços manuais e links externos para conferir locais no Google Maps. Paradas específicas por veículo/trecho na ordem definida pela agência. Disponibilidade e realocação consideram pontos atendidos; edição protege reservas existentes.
- Motorista/guia visualizam suas alocações e abrem o itinerário ou um ponto no Google Maps. Rotas extensas usam etapas, sem API paga ou pesquisa integrada.
- Agenda de veículos/equipe verifica cada trecho, permitindo outras viagens entre ida e volta quando não houver sobreposição. Consumo da franquia continua por viagem comercial.
- Migração `0013_geographic_routes` aplicada no Docker local, preservando dados anteriores. Viagens antigas exigem completar cidades antes de novas reservas ou publicação.
- Validação: 174 testes de backend e todas as 11 jornadas Chromium aprovadas, com correções dos testes de seleção de campos e espera da gravação offline. Build, Ruff e Prettier aprovados. Ensaio de backup/restauração aprovado na revisão 0013, incluindo conferência de isolamento de duas empresas.
- Documentação em [GEOGRAFIA_E_ROTAS.md](GEOGRAFIA_E_ROTAS.md). Sem publicação na VPS nesta entrega.

## Edição de rotas em viagens com reservas — 06/10/2026

- Viagens agendadas sem eventos de embarque podem receber novas paradas ao fim do itinerário, antes do destino. Pontos intermediários e identidades existentes são preservados; reservas até o destino têm a posição final atualizada na mesma transação. Bilhetes, valores e franquia são mantidos.
- Endereços das paradas existentes podem ser editados. Remover paradas existentes ou alterar sua finalidade continua bloqueado quando há reservas; a mensagem agora explica as alterações permitidas.
- Na edição, inversão da volta copia apenas origem/destino e seus endereços, mantendo paradas e horários existentes. Inclusão de parada mantém as escolhas anteriores de paradas por veículo.
- Validação: 176 testes de backend aprovados; jornadas Chromium de edição/adição com reserva existente, reservas e embarque aprovadas. Build, Ruff e Prettier aprovados. API e web atualizados no Docker local; nenhuma nova migração.

## Aplicativo operacional Android — 06/10/2026

- Projeto Flutter em `mobile/`, no mesmo repositório lógico do painel e da API. Login de motorista/guia, viagens e veículos atribuídos, preparação por trecho, scanner QR nativo, embarque/desembarque pela lista, confirmação de passageiro, fila offline e Google Maps externo.
- Motoristas e guias têm os mesmos recursos operacionais nos veículos atribuídos. Guia continua opcional; teste específico cobre viagem sem guia com embarque por QR e desembarque pelo motorista. Administrações, reservas e emissão/revogação de bilhetes permanecem restritas aos perfis responsáveis.
- SQLite com conteúdo AES-GCM, chave e sessão no armazenamento seguro. Proteção de fila ao sair/trocar usuário, reenvio idempotente e confirmação atômica, bloqueio de comandos dependentes após conflito e revisão explícita mantendo o servidor. Preparação limitada à validade da sessão e oito horas.
- Configurações por empresa para nome, pacote Android, slug e endereço da API. Estrutura iOS com permissão de câmera/Keychain, sem compilação nesta máquina Windows. APK debug local disponível em `artifacts/mobile/nexus-rotafy-debug.apk`; script de geração `scripts/build_mobile.ps1`.
- Validação: análise Flutter sem problemas, nove testes mobile aprovados, 177 testes backend aprovados e jornadas Chromium de embarque/motorista e offline aprovadas. APK Android compilado; API/web locais atualizados, sem migração adicional.
- Sem aparelho conectado: câmera real, instalação, modo avião e uso em viagem aguardam homologação. Sincronização automática ocorre com o app aberto/ao retornar; sem serviço com app fechado, GPS ou WhatsApp. Publicação comercial e assinatura por cliente ainda pendentes. Guia em [mobile/README.md](../mobile/README.md).

## Entrega VPS / Android release ? 06/10/2026

- Dom?nio de produ??o atualizado para `frotafy.nexusdataanalytics.tech`; Compose adaptado ao Traefik existente, rede externa configur?vel, entrypoint/resolver reais obrigat?rios e confian?a de proxy por IP. Sem novo proxy ou portas p?blicas no host.
- Pacote de fontes para VPS com exclus?es de credenciais/banco e checksum; gerador de senhas no servidor sem sobrescrever ambiente existente. Script de diagn?stico Traefik somente leitura com sa?da selecionada.
- Configura??o Android HTTPS, assinatura Nexus privada e suporte a assinatura configur?vel; iOS fora desta etapa. Build release bloqueia aus?ncia de configura??o de assinatura.
- Imagens API/web de produ??o compiladas localmente; Compose validado com par?metros de teste. An?lise Flutter sem problemas e 11 testes mobile aprovados. Publica??o remota e homologa??o via HTTPS aguardam dados reais do Traefik.
- APK release 1.0.0 (65,4 MB) compilado e assinatura RSA 3072 / APK v2 verificada com apksigner. Pacote `br.com.nexusdataanalytics.rotafy`, Android 7+ (API 24). Artefatos e checksums em `artifacts/`.
