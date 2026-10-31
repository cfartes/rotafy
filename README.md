# Nexus Rotafy

Plataforma SaaS de viagens e embarque. Entregas atuais: fundação multiempresa, acessos, planos, frota, viagens, reservas familiares, página pública, integrações, bilhetes QR e presença online. O plano completo está em [PLANO_DESENVOLVIMENTO.md](PLANO_DESENVOLVIMENTO.md).

## Executar localmente com Docker

Apresentação do sistema e manual de utilização estão na central `/ajuda`, acessível pelo login e pelo menu **Ajuda e manuais**. Inclui apresentação HTML/PDF, PowerPoint exclusivo do Superadmin completo e manual HTML/PDF, com instruções por perfil e exemplos. Fontes, geração e publicação: [documentação dos materiais](docs/PUBLICACAO_DOCUMENTACAO.md).

Requisitos: Docker Desktop em execução. Node 24 e Python 3.13/3.14 somente para desenvolvimento/testes fora dos containers.

No PowerShell, na raiz do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File infra/setup.ps1
docker compose up -d --build
```

O setup gera senhas aleatórias em `.env`, sem sobrescrever um arquivo existente. O banco local tem volume próprio; não usa o banco de outros projetos. Migrações rodam antes da API. O bootstrap cria o primeiro administrador Nexus e não redefine sua senha nas próximas inicializações.

| Acesso | Endereço |
|---|---|
| Portal da empresa | http://localhost:5178 |
| Administração Nexus | http://localhost:5178/nexus |
| Documentação da API | http://localhost:8018/docs |
| Saúde da API | http://localhost:8018/api/v1/health |

Entre no painel Nexus com `BOOTSTRAP_EMAIL` e `BOOTSTRAP_PASSWORD` do `.env`. Cadastre uma empresa e seu administrador; o identificador escolhido será utilizado no login da empresa. Guia e motorista terão contas independentes em cada empresa.

Alterar `BOOTSTRAP_PASSWORD` no `.env` não modifica a senha de uma conta já criada. Para aplicar explicitamente essa senha ao administrador Nexus **local**, execute `.venv\Scripts\python.exe scripts/reset_local_nexus.py`. O comando conecta somente ao banco `rotafy` em `127.0.0.1`, atualiza a conta ativa correspondente a `BOOTSTRAP_EMAIL`, revoga suas sessões/links antigos e registra auditoria. Não redefine usuários das empresas nem opera na VPS. Para o uso normal, prefira **Alterar minha senha** no painel.

Senhas novas de usuários exigem de 8 a 128 caracteres, incluindo pelo menos uma letra maiúscula e um caractere especial. Espaços não contam como caractere especial. O perfil abre a troca de senha. Administradores da empresa podem gerar um link de recuperação válido por 30 minutos; compartilhe por canal seguro. Convites e recuperação por e-mail, inclusive da Nexus, estão implementados via Resend e dependem de chave/remetente configurados. Consulte [configuração dos e-mails](docs/EDICAO_E_EMAILS.md).

O compose atual é para desenvolvimento local: portas vinculadas a `127.0.0.1`, HTTP e cookie sem Secure para localhost. Não publicar este compose como produção sem HTTPS, cookie Secure, origens corretas, revisão das portas e backup externo.

## Serviços e persistência

```powershell
docker compose ps
docker compose logs --tail 50 api
docker compose stop
docker compose start db api web billing
```

O volume `nexus-rotafy_rotafy_data` preserva os dados. Não remova volumes para atualizar código. Para atualizar a aplicação e executar novas migrações, use novamente `docker compose up -d --build`.

As senhas dos papéis PostgreSQL são provisionadas na primeira criação do volume. Alterar somente `.env` não modifica as senhas já existentes no banco.

## Desenvolvimento e testes

Instale as dependências do backend em ambiente virtual na raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q --tb=short
Set-Location ..
.\.venv\Scripts\ruff.exe check backend
```

Os testes criam o banco dedicado `rotafy_test` no container local e limpam apenas esse banco. Validam políticas reais do PostgreSQL, não um substituto em memória. A conexão de proprietário é usada somente na preparação do banco de teste e nas migrações.

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run build
npx.cmd playwright install chromium
Set-Location ..
.\.venv\Scripts\python.exe scripts/test_e2e.py
```

Testes de navegador exigem os containers web/api em execução. Criam empresas e pessoas de homologação no banco local, identificadas por slug `e2e-*`; não apontar para produção. Screenshots são gravadas em `docs/screenshots/`.

O executor `scripts/test_e2e.py` cria contas Nexus temporárias separadas por arquivo de cenário e revoga suas sessões/acesso ao finalizar, usando a conexão de proprietário somente nessa preparação. Assim, a suíte respeita o limite individual de login sem consumir as tentativas da conta Nexus habitual. `npm.cmd run test:e2e` continua disponível em frontend/, mas utiliza a conta de bootstrap se não receber credenciais exclusivas de homologação.

Para editar o frontend com atualização automática, pare somente o container web (`docker compose stop web`) e execute `npm.cmd run dev` em frontend/. O Vite utiliza a mesma porta 5178 e encaminha `/api` para a API local na porta 8018.

`frontend/package-lock.json` fixa as dependências web. `backend/requirements.txt` registra as versões de runtime verificadas em Linux; `requirements.in` preserva as faixas de origem para futuras atualizações deliberadas.

## Segurança e contratos

- Sessão opaca em cookie HttpOnly, com hash persistido e expiração. Logout, suspensão e troca de senha revogam acesso no servidor.
- Proteção CSRF e validação de Origin nas operações com sessão. Tokens não são armazenados em localStorage.
- PostgreSQL com RLS forçado, contexto de empresa local à transação e papéis de runtime sem superusuário/BYPASSRLS.
- Papéis separados para empresa e plataforma; tabelas de administração Nexus inacessíveis pelo papel da empresa.
- Relações entre sessão/usuário usam chave composta com company_id. Usuários da API não podem fornecer outra empresa ao criar cadastros internos.
- Consulta pública de marca retorna somente dados públicos; não expõe usuários, CNPJ ou razão social.
- Alterações de marca, conta, sessão e recuperação geram eventos de auditoria sem senhas/tokens.
- Limite de tentativas de login persistido no banco e compartilhado entre processos.
- Em produção, revisar a identidade de IP transmitida pelo proxy; atualmente requisições pelo proxy local compartilham seu limite por IP, além do limite individual por empresa/e-mail.

API web usa cookies; integrações de reservas usam chaves por empresa. O cliente nativo será implementado posteriormente. A API está versionada em `/api/v1`.

Referências usadas na fundação: [FastAPI](https://fastapi.tiangolo.com/), [PostgreSQL RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html), [Vite](https://vite.dev/guide/).

## Escopo atual

Implementados: acessos Nexus/empresa, cadastro e suspensão de empresas, equipe e perfis, suspensão/ativação de usuários, identidade de nome/cores, troca e recuperação de senha, auditoria, interface responsiva e ambiente Docker. Planos Basic/Professional/Enterprise e planos adicionais configuráveis, condições versionadas, assinatura por empresa, mudança agendada de plano, ciclos mensais e demonstrativos.

Abra **Planos e assinaturas** na Nexus para configurar valores e vincular empresas. Os três planos iniciais começam sem valores, aguardando configuração. O administrador da agência consulta **Meu plano**. Regras e exemplos em [docs/PLANOS_E_ASSINATURAS.md](docs/PLANOS_E_ASSINATURAS.md).

O container `billing` renova ciclos e processa expiração de bloqueios de lugares a cada 60 segundos. Criação e cancelamento de viagens já estão ligados ao consumo e estorno, na mesma transação, com proteção contra requisições repetidas.

Cadastre percursos reutilizáveis em **Rotas** e selecione-os ao agendar uma **Viagem**, com duração manual e chegada prevista calculada. Use os menus **Equipe → Veículos → Rotas → Pacotes → Viagens → Vender bilhete** para preparar a operação. Cadastre viagens com múltiplos veículos, ida/volta ou trecho único e equipe. Pacotes com vários destinos possuem roteiro por dia, retorno incluído e venda completa; cada destino comercial consome uma unidade da franquia. Motoristas e guias consultam somente suas viagens em **Minhas viagens**. Guias em [docs/PACOTES_MULTIDESTINOS.md](docs/PACOTES_MULTIDESTINOS.md), [docs/ROTAS_REUTILIZAVEIS.md](docs/ROTAS_REUTILIZAVEIS.md) e [docs/FROTA_E_VIAGENS.md](docs/FROTA_E_VIAGENS.md).

No cadastro da empresa, escolha **Turismo e transfers** ou **Transporte regular**, independentemente do plano comercial. Regular oferece Rotas, viagens avulsas e bilhetes, sem novos pacotes. Empresas anteriores recebem Turismo automaticamente. A Nexus altera o perfil em **Empresas → Editar dados**, com bloqueio para pacotes ativos e auditoria. Linhas recorrentes e venda independente por trecho continuam em etapa futura. Consulte [docs/PLANO_PERFIS_OPERACIONAIS.md](docs/PLANO_PERFIS_OPERACIONAIS.md).

Em **Detalhes → Reservas e lugares**, administradores e atendentes cadastram famílias com um único telefone, passageiros, pontos por trecho, sugestão de veículo e bloqueios de 15 minutos. CPF segue a regra interestadual e suas exceções. Podem confirmar, cancelar, realocar e importar CSV/XLSX com prévia e conferência de lotação. Regras em [docs/RESERVAS_E_DISPONIBILIDADE.md](docs/RESERVAS_E_DISPONIBILIDADE.md).

O menu antigo **Página pública e integrações** permanece oculto; seu código está preservado. A integração atual com parceiros é habilitada por módulos e possui guia e endpoints próprios: [módulos](docs/MODULOS_E_INTEGRACAO.md) e [integração](docs/integracao/README.md).

Bilhetes individuais, válidos para todos os trechos contratados do passageiro, são emitidos em **Detalhes da reserva** após confirmação. O passageiro abre o link privado do bilhete, imprime/salva PDF ou compartilha seu link. Guias e motoristas operam **Abrir embarque · Ida/Volta** nos veículos atribuídos; guia é opcional. Veja [bilhetes e embarque](docs/BILHETES_E_EMBARQUE.md).

Na tela de embarque, **Preparar para uso offline** guarda o manifesto por veículo/trecho e abre `/offline`. A PWA permite leitura QR e presença sem rede, com fila persistente, sincronização idempotente e revisão de conflitos. Veja [uso e limites do offline](docs/OFFLINE_E_SINCRONIZACAO.md). Validação em iPhone/Android físicos pendente.

Em **Relatórios → Visão gerencial**, administradores e atendentes consultam deslocamentos diários, viagens comerciais, ocupação dos veículos, valores confirmados/PAGO, passageiros, ranking de destinos e próximas saídas com baixa ocupação. Os relatórios detalhados de ocupação por segmento, reservas e presença continuam disponíveis com CSV. Administradores consultam consumo da franquia; a Nexus filtra ciclos por empresa. Datas em Brasília. Veja [RELATORIOS.md](docs/RELATORIOS.md) e as [pendências futuras](docs/PENDENCIAS_FUTURAS.md).

Em **Nexus → Configurações**, cadastre as chaves OpenWA/Resend, o e-mail remetente e uma sessão WhatsApp por empresa. Confirmação, cancelamento e marcação PAGO geram mensagens em fila; detalhes da reserva mostram histórico e permitem envio manual. Veja [WHATSAPP_E_CONFIGURACOES.md](docs/WHATSAPP_E_CONFIGURACOES.md), incluindo ativação, proteção das credenciais e backup da chave local.

Logs JSON e métricas autenticadas da Nexus disponíveis. Configuração de produção independente, HTTPS/Traefik existente e serviço de backup externo criptografado preparados em `compose.production.yaml`. Restauração ensaiada em container isolado; carga local medida com duas empresas, 20 veículos e 800 passageiros. Consulte [implantação e operação](docs/IMPLANTACAO_E_OPERACAO.md) e [pendências de homologação](docs/HOMOLOGACAO.md). A VPS e o envio de backups externos ainda não foram configurados.

A assinatura da empresa possui cobrança de setup ao fim do teste e mensalidade ao fim de ciclos de 30 dias, com links de pagamento e confirmação automática quando configurados. Veja [cobranças](docs/COBRANCAS_MENSAIS.md) e [pagamentos e teste](docs/INFINITEPAY_E_TESTE.md). O pagamento do passageiro continua sendo registrado manualmente por **Marcar PAGO**, separado da confirmação da reserva. O APK 1.10.1 oferece início automático e rastreamento previsto a cada minuto, com avisos configuráveis: [rastreamento](docs/RASTREAMENTO_E_AVISOS.md).

Edição de viagens/reservas, realocação após desembarque/reversão e convites/recuperação por Resend foram acrescentados. Configure chave e remetente verificado para ativar os e-mails; a integração foi testada com transporte simulado. Consulte [edição e e-mails de acesso](docs/EDICAO_E_EMAILS.md).

### Acesso do administrador da empresa

Abra http://localhost:5178/ para entrar no painel. Administradores e atendentes têm atalhos para **Veículos**, **Viagens**, **Alocar veículos** e **Passageiros**. Passageiros são cadastrados nas reservas de cada viagem, inclusive famílias com um único telefone. A alocação permite adicionar veículos a viagens agendadas antes dos embarques, sem consumir novamente a franquia.

O cadastro da empresa exige CPF/CNPJ com máscara e validação dos dígitos verificadores, além de indicar documento ou identificador de acesso já cadastrado. Para passageiros, CPF é obrigatório nas viagens interestaduais, com exceções para estrangeiros e menores de cinco anos.

### Gerenciamento de empresas e planos pela Nexus

Na lista **Empresas**, use **Editar dados** para alterar nome comercial, razão social, CPF/CNPJ e identificador de acesso. Mudar o identificador exige informar a equipe e atualizar os links públicos. A edição mantém usuários, viagens, assinatura, identidade visual e situação de acesso.

Use **Gerenciar plano** na linha da empresa para abrir diretamente **Plano da empresa**, com a empresa selecionada. O catálogo geral continua acessível pelo menu **Planos e assinaturas**. Novas empresas escolhem o plano no cadastro e recebem uma assinatura iniciada hoje. Empresas antigas sem assinatura podem selecionar o plano e a data de início e clicar em **Vincular assinatura**. Com assinatura ativa, a mudança de plano é agendada para o próximo ciclo mensal; o ciclo atual mantém franquia e preços contratados. O catálogo permite configurar nome, quantidade mensal de viagens, valor do plano e valor de viagem extra.

### Primeiro acesso do cliente SaaS

O cadastro de empresas é exclusivo da equipe Nexus. O login não oferece cadastro e `POST /api/v1/public/companies` retorna 403. Vendedores com perfil Equipe Nexus podem cadastrar empresa, CPF/CNPJ obrigatório, plano e administrador. Empresa, administrador, assinatura e primeiro ciclo são gravados na mesma transação. Após salvar, a opção **Enviar acesso** envia dados cadastrais e um link de definição de senha por e-mail e/ou WhatsApp. O WhatsApp usa a sessão Nexus configurada para comunicação/cobrança, sem exigir sessão do novo cliente.

CPF/CNPJ é normalizado e validado por formato, dígitos verificadores e unicidade no sistema, sem consulta à situação cadastral da Receita. Empresas antigas sem documento permanecem preservadas, mas precisam informar um documento válido para salvar alterações cadastrais. O e-mail do administrador é registrado no cadastro. Não há integração de pagamento, emissão de cobrança nem envio automático de fatura nesta entrega.

### Cidades, CPF interestadual e rotas por veículo

Viagens exigem cidades de origem/destino selecionadas por UF. CPF é obrigatório para todos os passageiros em viagens interestaduais, com flags para estrangeiros e menores de cinco anos; a exceção por idade exige nascimento e valida ida e volta. Cada veículo pode atender paradas diferentes na sequência da agência. Motoristas e guias abrem sua rota ou um ponto no Google Maps por links externos, com endereços manuais. Não há pesquisa integrada nem chave Google Cloud. Viagens antigas precisam completar cidades antes de novas reservas/publicação. Guia: [docs/GEOGRAFIA_E_ROTAS.md](docs/GEOGRAFIA_E_ROTAS.md).

### Aplicativo Android

O projeto Flutter está em [mobile/](mobile/README.md), usando a mesma API e as contas de motorista/guia. Ambos preparam manifestos, leem QR, registram embarque/desembarque offline e sincronizam com revisão de conflitos. Viagem sem guia funciona com o motorista atribuído. SQLite com conteúdo criptografado e sessão no armazenamento seguro do aparelho. APK debug de homologação gerado por `scripts/build_mobile.ps1`; configuração separada por empresa. Testes em aparelho real, distribuição assinada e compilação iOS ainda precisam de homologação/configuração.

Detalhes e endpoints em [cadastro SaaS](docs/CADASTRO_SAAS.md).

Instalador Hostinger/Traefik: [guia e comandos](docs/INSTALACAO_VPS.md).
## Integração com sistemas parceiros

Atendimento e supervisão: [Conversas WhatsApp e conexões das empresas](docs/CHAT_WHATSAPP_E_SUPERVISAO.md).

Automação: [Comandos para passageiros e fila de bilhetes 24 horas antes](docs/AUTOMACAO_WHATSAPP.md).

Consulte também [Módulos por empresa e operação integrada](docs/MODULOS_E_INTEGRACAO.md) para configurar o acesso do cliente e emitir as credenciais operacionais.

O [guia de WhatsApp, bilhetes e embarque](docs/integracao/README.md) reúne os endpoints existentes, dados necessários, autenticação, exemplos, OpenAPI e coleção Postman para integrar um sistema externo à comunicação e à operação pelo APK.

### Documentação revisada em 22/10/2026

A central de ajuda está na revisão 16: manuais separados para empresa e Nexus, HTML/PDF e apresentação de 26 slides em HTML/PDF; o PowerPoint editável é exclusivo do Superadmin completo. O [documento consolidado](PROJETO_COMPLETO_ROTAFY.md) reúne funcionalidades e referências técnicas.

**Conversas WhatsApp** permite atendimento e anexos no painel; **Conexões WhatsApp** permite supervisão pelo Superadmin completo. A automação apresenta menu numerado personalizado para qualquer texto, transfere à equipe e encerra somente conversas automáticas após dez minutos de inatividade. Bilhetes podem entrar na fila 24 horas antes do primeiro embarque, com intervalo configurado pela Nexus (padrão: 30 segundos) entre envios automáticos. Ambos exigem habilitação do administrador. Consulte [conversas e conexões](docs/CHAT_WHATSAPP_E_SUPERVISAO.md) e [atendimento e bilhetes](docs/AUTOMACAO_WHATSAPP.md).

**NPS e satisfação:** avaliações pelo WhatsApp após concluir atendimento humano ou viagem completa, com nota e comentário opcional. Administradores e atendentes consultam indicadores, filtros, evolução e relatórios CSV/PDF; somente o administrador configura as pesquisas. Veja [NPS e satisfação](docs/NPS_E_SATISFACAO.md).

**Horários de atendimento:** o administrador define dias, turnos e fuso em Configurações ou WhatsApp. Fora do expediente, a solicitação humana recebe os horários e a próxima abertura, sem perder o registro. O NPS utiliza respostas por categoria e encaminha avaliações negativas à equipe de qualidade no próprio app. Consulte [horários](docs/HORARIOS_DE_ATENDIMENTO.md).


Privacidade e condições públicas: `/privacidade`, `/termos`, `/cancelamento-reembolso` e `/privacidade/solicitacao`. O canal LGPD registra protocolo e permite triagem pelo Superadmin em Configurações, sem exclusão automática. Auditoria de segurança, privacidade e acessibilidade: [checklist de 23/10/2026](docs/CHECKLIST_SEGURANCA_PRIVACIDADE_2026-10-23.md).

Revisão de 26/10/2026: [refinamentos visuais e segurança, incluindo APK 1.9.1](docs/REVISAO_VISUAL_E_SEGURANCA_2026-10-26.md).

Realocação após cancelamento: administradores e atendentes consultam alternativas compatíveis por data/hora, registram a concordância do cliente e aproveitam créditos com histórico preservado. [Operação e atualização](docs/REALOCACAO_APOS_CANCELAMENTO.md).

Localização automática de embarques: [configuração Google, limites e operação](docs/GEOCODIFICACAO_GOOGLE.md).

Previsão de chegada, mapa geral, sequência dos pontos e APK 1.10.0: [operação e publicação](docs/RASTREAMENTO_E_PREVISAO.md).
