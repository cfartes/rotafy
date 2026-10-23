# Rotafy — regras e diretrizes de segurança, privacidade e acessibilidade

Consolidado em **23/10/2026**, referente à implementação `e483b55`.

Este documento registra os controles implementados e as diretrizes para sua manutenção. A implantação na VPS deve acompanhar a versão do código. As evidências dos testes e os limites da revisão estão no [checklist dos 28 itens](CHECKLIST_SEGURANCA_PRIVACIDADE_2026-10-23.md).

## 1. Segurança da aplicação

### 1.1. XSS e renderização

- Exibir entradas de usuários, mensagens e comentários como texto, usando o escape padrão do React.
- Escapar valores ao compor HTML de e-mails e outros documentos.
- Não transformar entradas não confiáveis em HTML executável, JavaScript ou comandos.
- Manter a validação de tipo, tamanho, formato e campos permitidos no backend. Campos livres podem conter caracteres especiais; o armazenamento desses caracteres não autoriza executá-los no navegador.
- Manter a CSP: scripts da própria origem e hashes exatos dos scripts estáticos dos manuais; `object-src 'none'` e `frame-src 'none'`.
- Regenerar os hashes CSP ao modificar os scripts dos materiais publicados, usando o gerador de documentação.
- Preservar cabeçalhos de segurança também nas respostas de erro. Diretivas locais do Nginx não devem eliminar, por herança, as proteções do servidor.

### 1.2. Sessão, autenticação e CSRF

- A sessão web utiliza cookie `HttpOnly`, `SameSite=Lax` e `Secure` em produção.
- O cookie CSRF é separado da sessão e precisa ser acessível ao código que envia o cabeçalho de proteção.
- Alterações autenticadas por cookie validam origem e token CSRF.
- Tokens de sessão e de recuperação são aleatórios; os registros de autenticação utilizam seus hashes.
- Não registrar senhas, tokens, chaves, conteúdo sensível de requisições ou links privados em logs.
- Utilizar o domínio correto: `https://rotafy.nexusdataanalytics.tech`.

### 1.3. Autorização por empresa e objeto

- UUIDs identificam recursos; não substituem autorização.
- Validar usuário, perfil, empresa, módulos e vínculo ao objeto em cada operação aplicável.
- Motoristas e guias acessam os deslocamentos atribuídos, conforme as regras operacionais.
- Chaves de integração possuem permissões fechadas; não concedem acesso indiscriminado a usuários, contratos ou financeiro.
- O perfil Nexus restrito não recebe as permissões do Superadmin completo.
- O PowerPoint editável e a administração dos pedidos de privacidade são exclusivos do Superadmin completo.

### 1.4. Banco de dados e RLS

- Manter RLS e FORCE RLS nas tabelas de negócio, incluindo as tabelas internas protegidas nesta entrega.
- Os papéis de runtime `rotafy_app` e `rotafy_platform` não podem ser superusuários nem possuir BYPASSRLS.
- Preservar a definição do escopo da empresa por transação e os relacionamentos que impedem vincular registros de empresas diferentes.
- A leitura dos catálogos compartilhados `plans` e `plan_versions` é permitida ao papel da aplicação conforme as policies e permissões existentes.
- O papel da plataforma possui acesso administrativo mais amplo; isso não dispensa autorização e filtros na API.
- `alembic_version` e `spatial_ref_sys` são exceções documentadas de metadados, sem dados privados de clientes.
- Criar futuras tabelas com políticas e permissões explícitas, evitando conceder acesso amplo apenas por conveniência.

### 1.5. Consultas SQL

- Vincular valores por parâmetros SQLAlchemy.
- Não interpolar diretamente valores recebidos em requisições.
- Nomes dinâmicos de tabelas, colunas e critérios somente podem vir de listas fechadas e definições controladas pelo código.
- Tratar alertas de análise estática por contexto; um alerta não comprova uma vulnerabilidade, mas não deve ser descartado sem revisão.

### 1.6. Limites de requisição

- Manter limites persistentes por IP e identidade nos fluxos de autenticação e recuperação.
- Responder com 429 e informação de nova tentativa quando o limite for excedido.
- Preservar os limites específicos de chat, integrações, operações públicas e solicitações LGPD.
- Não confiar em cabeçalhos de IP enviados diretamente pelo cliente. Em produção, somente os proxies configurados devem ser confiáveis.
- Os limites de requisição são distintos do intervalo das filas de mensagens WhatsApp.

### 1.7. Secrets e fornecedores

- Chamadas a provedores e acesso a credenciais ficam no backend.
- Chaves protegidas no banco não são devolvidas ao frontend.
- Não versionar arquivos de ambiente, chaves privadas, segredos de produção ou material de assinatura Android.
- Manter secret scanning com saídas redigidas. Exceções devem ser específicas, justificadas e revisadas.
- As três exceções históricas atuais do Gitleaks correspondem a falsos positivos revisados; não representam autorização para ignorar novos achados semelhantes.

### 1.8. Dependências e ferramentas

- Confirmar existência, origem e projeto mantenedor antes de adicionar bibliotecas.
- Manter versões de produção fixadas e o lockfile npm com integridade.
- Auditar dependências de runtime, frontend e ferramentas de documentação.
- Versões corrigidas nesta entrega: Pillow **13.0.0**, OpenTelemetry API **1.45.1** e pypdf **6.21.2**.
- A ferramenta de testes de acessibilidade adicionada é `@axe-core/playwright` **4.14.0**.
- O workflow `.github/workflows/security.yml` executa auditoria de dependências e Gitleaks em push, pull request e semanalmente. Actions usam SHA fixo; o binário Gitleaks tem checksum verificado.
- Resultado sem alertas conhecidos não certifica ausência de malware ou de vulnerabilidades ainda não publicadas.

### 1.9. Prompt injection

A aplicação atual não utiliza LLMs ou ferramentas acionadas por modelos. A automação WhatsApp é determinística. Mensagens recebidas, documentos e comentários são dados não confiáveis e não devem ser executados como instruções. Uma futura integração com IA exige avaliação específica de privilégios, isolamento e acesso a dados.

## 2. Privacidade e condições de uso

### 2.1. Identificação oficial

| Campo | Informação publicada |
| --- | --- |
| Razão social | ANDRADE FARTES TI LTDA |
| CNPJ | 65.186.307/0001-74 |
| Endereço | R Jornalista Abdon Foes, 200, anexo 302, Navegantes/SC |
| CEP | 88.372-822, conforme o contrato aprovado |
| Contato | contato@nexusdataanalytics.com.br |

### 2.2. Páginas públicas

| Página | Endereço |
| --- | --- |
| Política de privacidade | `/privacidade` |
| Termos de uso | `/termos` |
| Cancelamento e reembolso | `/cancelamento-reembolso` |
| Solicitações de direitos do titular | `/privacidade/solicitacao` |

Essas páginas são acessíveis sem login. O rodapé apresenta os links e os dados legais. Os materiais HTML publicados também oferecem links para as políticas.

### 2.3. Responsabilidades e bases legais

- A Nexus é controladora dos dados de contratação, contas, cobrança e segurança de seu serviço.
- A empresa de turismo ou transporte é controladora dos dados de passageiros e colaboradores; a Nexus atua como operadora desses dados conforme as instruções e obrigações aplicáveis.
- Informar finalidade e base legal nos formulários e na política.
- Tratamentos contratuais ou legais não devem depender de uma caixa genérica de consentimento.
- Quando consentimento for a base aplicável a uma finalidade opcional, ele precisa ser específico e revogável.
- Ler a política não equivale a consentir com qualquer tratamento.
- Localização de colaboradores, dados de menores e pesquisas exigem avaliação do controlador, observando necessidade, direitos dos titulares e as regras aplicáveis.

### 2.4. Minimização

- Solicitar apenas os dados necessários à finalidade informada.
- Preservar a condição opcional dos campos que não são obrigatórios, incluindo o CPF do passageiro quando aplicável.
- Utilizar o telefone compartilhado da reserva conforme o funcionamento existente.
- Não solicitar senhas, documentos, CPF ou dados sensíveis no formulário público de privacidade.
- Orientar usuários a evitar dados sensíveis nos campos livres.
- Os campos cadastrais obrigatórios já exigidos para contratação não foram removidos nesta entrega.

## 3. Cookies, armazenamento e rastreamento

- `rotafy_session` mantém a sessão autenticada.
- `rotafy_csrf` protege os formulários contra solicitações indevidas.
- Cookies estritamente necessários não são apresentados como uma opção de publicidade nem condicionados a consentimento opcional.
- O aviso permite **Usar somente necessários** e **Gerenciar cookies**.
- As preferências podem ser reabertas pelo rodapé.
- A preferência é armazenada no navegador com versão e data, sem habilitar categorias de análise ou publicidade.
- O aplicativo também utiliza armazenamento local necessário para preferências e operação offline. Sair da conta não equivale a apagar registros operacionais pendentes de sincronização.
- Não foram identificados Google Analytics, Google Tag Manager, pixels de publicidade, Hotjar ou Clarity na versão auditada.
- Não carregar rastreadores opcionais futuros sem implementar a escolha prévia adequada e os mecanismos de revogação aplicáveis.

## 4. Canal LGPD e solicitações de exclusão

### 4.1. Abertura do pedido

O formulário público solicita:

1. E-mail para retorno.
2. Tipo de solicitação.
3. Descrição opcional, limitada a 2.000 caracteres.

Os tipos disponíveis são acesso, correção, exclusão, portabilidade, oposição/revogação e outros pedidos. Campos extras são rejeitados. O registro retorna um protocolo aleatório e não confirma publicamente a existência de uma conta.

O canal continua disponível sem login, inclusive para clientes com acesso suspenso. O e-mail oficial é uma alternativa ao formulário.

### 4.2. Tratamento pela Nexus

- Consultar os últimos cem pedidos em **Superadmin → Configurações → Solicitações de privacidade**.
- Acompanhar recebimento, verificação, análise, conclusão ou indeferimento.
- Confirmar identidade antes de disponibilizar dados ou atender uma exclusão.
- Encaminhar ao controlador responsável quando o pedido se referir à operação de uma empresa de transporte.
- Avaliar conservação legal, exercício de direitos, backups e demais cópias antes de efetivar a exclusão.
- Responder ao solicitante pelo canal apropriado e manter as evidências do atendimento pelos procedimentos internos.

**Alterar a situação do pedido não envia e-mail nem apaga dados automaticamente.** A conclusão no painel é um registro de acompanhamento, não comprovação de que houve exclusão ou resposta enviada.

### 4.3. Endpoints

| Método e rota | Finalidade | Acesso |
| --- | --- | --- |
| `POST /api/v1/public/privacy-requests` | Registrar pedido e retornar protocolo | Público, com rate limiting |
| `GET /api/v1/nexus/privacy-requests` | Consultar pedidos | Superadmin completo |
| `PATCH /api/v1/nexus/privacy-requests/{id}` | Atualizar acompanhamento | Superadmin completo |

Os pedidos são armazenados em `privacy_requests`, com RLS e permissões restritas ao papel da plataforma.

## 5. Termos, cancelamento e reembolso

- Preservar o contrato individual aprovado e o fluxo de aceite com confirmação por e-mail.
- A publicação das políticas não altera o hash do contrato aprovado, não cria aceite retroativo e não substitui o Quadro de Contratação.
- Solicitações de cancelamento da assinatura são feitas por comunicação escrita aos canais oficiais.
- Conforme o contrato vigente, não há fidelidade automática de doze parcelas nem exigência automática de aviso de trinta dias.
- O encerramento interrompe novos ciclos a partir de sua efetivação; valores emitidos permanecem sujeitos à conferência e às regras aplicáveis.
- Não há multa automática sobre um saldo hipotético de doze parcelas futuras.
- Cancelamento não produz exclusão do histórico, confirmação de pagamento ou reembolso automático.
- A política não estabelece uma vedação geral de restituição. Direitos legais, incluindo o arrependimento previsto no artigo 49 do CDC quando aplicável, não são afastados pelo teste ou pelo contrato.
- Cancelamento, remarcação e reembolso de viagens ou bilhetes devem ser tratados com a empresa que realizou a venda, conforme as condições da compra e a legislação.

## 6. Integrações e compartilhamento

| Integração | Finalidade e dados necessários |
| --- | --- |
| WhatsApp/Meta e serviço conectado | Comunicação operacional e atendimento, com os dados necessários à mensagem |
| Resend | Envio de e-mails operacionais |
| InfinitePay | Cobranças da assinatura; o Rotafy não recebe os dados completos do cartão inseridos no checkout do provedor |
| ViaCEP | Consulta de endereço pelo backend, transmitindo somente o CEP |
| OpenStreetMap | Tiles dos mapas; pode receber IP e área consultada |
| Google Maps | Navegação por link aberto por ação do usuário |

Informar esse compartilhamento na política. Contratos com operadores, suboperadores, transferências internacionais e configurações das contas exigem validação jurídica e operacional própria.

## 7. Acessibilidade e conteúdo

- Manter textos alternativos funcionais nas imagens e QR Codes.
- Não inventar descrições do conteúdo de fotos enviadas por terceiros.
- Utilizar controles com nomes acessíveis e ações claras.
- Preservar contraste adequado entre texto e fundo, incluindo textos auxiliares, cabeçalhos e rodapés.
- Preservar foco visível e navegação por teclado.
- Diálogos devem permitir operação por teclado e fechamento por Esc, conforme o componente utilizado.
- O mapa de embarque permite mover a área com as setas e selecionar o centro com Enter, além da seleção por clique.
- Manter testes Axe/WCAG nas telas cobertas e testes funcionais dos fluxos de teclado.
- Não apresentar depoimentos fictícios como avaliações reais.
- Identificar telas e dados demonstrativos como exemplos.
- Evitar promessas absolutas de segurança, disponibilidade, entrega, leitura, localização ou conformidade.
- Verificar os direitos de uso de marcas, logos e imagens fornecidos por terceiros e preservar as atribuições das bibliotecas e mapas.

Os testes automatizados não certificam todos os estados, personalizações, leitores de tela ou dispositivos. A revisão humana continua necessária.

## 8. Materiais internos e documentação

- O PowerPoint editável fica fora da pasta pública e exige autenticação de Superadmin completo para download.
- O endereço público antigo do PPT retorna 404; PDF e HTML continuam disponíveis aos clientes.
- Manter manuais, apresentação e instruções de uso compatíveis com os recursos implementados.
- Não inserir funcionalidades planejadas como se já estivessem disponíveis.
- A documentação foi atualizada para a revisão 11 em 23/10/2026.

## 9. Implantação e validação

As migrações 0047 e 0048 são incrementais: reforçam as políticas de banco e criam a tabela dos pedidos LGPD, sem recriar o banco ou excluir dados existentes.

Atualização da instalação:

```bash
cd /opt/rotafy-tech
bash scripts/update_vps.sh
```

Atualizar API e web juntos. As novas páginas e o canal ficam disponíveis na VPS após a implantação.

Evidências desta entrega: 613 casos distintos do backend e 104 cenários web aprovados, build e verificações estáticas aprovados, auditorias de dependências sem alertas conhecidos após correção e validação local do Nginx/CSP. O [checklist](CHECKLIST_SEGURANCA_PRIVACIDADE_2026-10-23.md) detalha metodologia, referências e cobertura.

## 10. Pontos que continuam exigindo confirmação externa

Estes itens não foram certificados pela implementação:

1. Revisão jurídica dos textos, bases legais e correspondência com as práticas reais da empresa.
2. Política operacional de retenção, descarte, tratamento de backups e registros de acesso exigíveis pelo Marco Civil.
3. Contratos com operadores, suboperadores e mecanismos aplicáveis às transferências internacionais.
4. Configuração real da VPS: TLS, proxies confiáveis, firewall, portas, volumes, imagens, credenciais e restauração de backups.
5. Direitos de uso da marca e dos materiais enviados por terceiros.
6. Revisão manual de acessibilidade em fluxos completos, leitores de tela e dispositivos reais.

Essas pendências devem ser tratadas pelos responsáveis correspondentes; não devem ser divulgadas como obrigações já comprovadamente atendidas.


Na tela de acesso, o aviso **Mostrar informações sobre o uso dos dados** começa recolhido. Clique para ler a finalidade e a base legal; use **Ocultar** para recolher sem perder o que foi digitado. Os links de privacidade, condições de uso e ajuda abrem em nova aba. As políticas são organizadas em seções expansíveis. **Dados da empresa** revela razão social, CNPJ, endereço e contato. As preferências de cookies abrem em uma janela de diálogo. A tela de acesso usa um rodapé compacto; em dispositivos menores ou com ampliação, a rolagem permanece disponível quando necessária para a leitura.
