# Demonstração WhatsApp e leads do RotaFY

Implementado em 11/11/2026. Site: `https://nexusdataanalytics.com.br`. Backend: `https://rotafy.nexusdataanalytics.tech`. A integração é servidor a servidor; o site permanece um projeto independente. Nenhuma publicação no site externo é feita pela atualização do app.

## Ativação

1. Atualizar a VPS pelo script normal. A migração incremental `0055_demo_leads` cria somente duas tabelas novas, com RLS e acesso do papel de plataforma; não recria o banco.
2. No Superadmin completo, abrir **Leads da demonstração → Configurar demonstração do site**.
3. Gerar a credencial do site. Ela aparece uma única vez; guardar exclusivamente em variável de ambiente/secret do servidor do site (`ROTAFY_DEMO_KEY`). Renovar invalida a anterior. Nunca inserir a chave em JavaScript, HTML, URL, repositório ou logs.
4. Criar um widget Cloudflare Turnstile para `nexusdataanalytics.com.br` e `www.nexusdataanalytics.com.br`, com ação `demo-ticket`. A site key pública fica no formulário; a secret key fica no Superadmin. O RotaFY valida token, hostname e ação no servidor. Documentação: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
5. Configurar o WhatsApp da Nexus e a chave do serviço de mensagens nas configurações já existentes. O número remetente continua sendo o da Nexus. Empresa e passageiro aparecem no texto.
6. Escolher limite diário (padrão 100; máximo 1000) e ativar a demonstração. O intervalo entre demonstrações segue a configuração de intervalo da fila no Superadmin (padrão 30 s). A fila de demonstrações tem seu próprio relógio; isso não promete espaçamento global com cobranças, respostas ou todos os outros tipos de mensagem.

## Formulário público

Campos obrigatórios: empresa, nome do passageiro/contato, telefone com DDD. Cidade/UF opcionais. Não pedir GPS preciso, documento ou dados de pagamento.

Texto da autorização obrigatória, versão `demo-v1`:

> Autorizo a Nexus a enviar uma demonstração do bilhete RotaFY para o WhatsApp informado. Sei que é um exemplo sem validade para embarque. Li o aviso de privacidade.

Opção comercial **separada, opcional e desmarcada**:

> Também autorizo a Nexus a entrar em contato comigo sobre o RotaFY. Posso revogar essa autorização pelo e-mail contato@nexusdataanalytics.com.br.

Aviso resumido: empresa, nome, telefone e consentimentos são usados para demonstração e eventual contato autorizado. Origem/campanha, cidade/UF opcionais, navegador, sistema, idioma e fuso são registrados; IP é processado para segurança e enviado na validação do CAPTCHA, mas não fica salvo em forma original. O token e IP são enviados à Cloudflare; nome, telefone e empresa são utilizados na mensagem via WhatsApp. Não é coletado GPS preciso nem impressão digital do aparelho. Retenção de contatos na base ativa: 90 dias; bilhete de exemplo: 24 horas. Informações do navegador não comprovam localização. Não apresentar a origem por IP como cidade real.

Vincular o aviso completo de privacidade. Para atualizar textos de autorização, alinhar previamente a versão de consentimento na API. Não marcar a autorização pelo visitante.

## Criar demonstração

`POST /api/v1/public/demo-ticket`

Cabeçalhos enviados **pelo servidor do site**:

```http
Authorization: Bearer <ROTAFY_DEMO_KEY>
Content-Type: application/json
```

```json
{
  "company_name": "Empresa Exemplo",
  "name": "Maria Silva",
  "phone": "+5547999999999",
  "demo_consent": true,
  "marketing_consent": false,
  "captcha_token": "TOKEN_DO_WIDGET",
  "client_ip": "203.0.113.20",
  "source": "https://nexusdataanalytics.com.br",
  "user_agent": "USER_AGENT_RECEBIDO_PELO_SERVIDOR_DO_SITE",
  "city": "Blumenau",
  "state": "SC",
  "language": "pt-BR",
  "timezone": "America/Sao_Paulo",
  "utm_source": "google",
  "utm_medium": "cpc",
  "utm_campaign": "demo-rotafy"
}
```

O servidor do site deve montar uma lista explícita de campos, fixar `source`, obter `user_agent` da requisição e `client_ip` da conexão confiável. Ignorar qualquer IP informado livremente pelo formulário. Atrás de proxy, aceitar cabeçalhos de IP apenas de proxies verificados/configurados na hospedagem. Nunca repassar cegamente `X-Forwarded-For` ou `CF-Connecting-IP` fornecido pelo visitante. O corpo da ponte usa `client_ip` porque o app recebe a conexão do servidor do site, não do visitante.

No navegador, coletar somente:

```js
const context = {
  language: navigator.language || '',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
  utm_source: new URLSearchParams(location.search).get('utm_source') || '',
  utm_medium: new URLSearchParams(location.search).get('utm_medium') || '',
  utm_campaign: new URLSearchParams(location.search).get('utm_campaign') || ''
};
// Enviar ao endpoint do PRÓPRIO SITE com os campos e o token Turnstile.
// A credencial RotaFY nunca participa deste código.
```

O servidor do site faz o POST HTTPS ao RotaFY com `ROTAFY_DEMO_KEY`, valida limites, impõe timeout e devolve ao navegador somente o resultado necessário. CORS não precisa ser liberado no app para este fluxo; CORS não substitui autenticação. Se a resposta se perder, não reenviar automaticamente: pode já ter sido aceita. Exibir orientação para aguardar, com limite de uma demonstração por telefone a cada 24 horas.

Resposta **202**:

```json
{"id":"UUID_DA_SOLICITACAO","status":"pending","message":"Solicitação recebida. O envio será processado; a entrega ainda não foi confirmada."}
```

Não informar "entregue" na página. O nome da empresa não muda o nome do perfil remetente WhatsApp.

## Andamento

`GET /api/v1/public/demo-ticket/{id}/status` com a mesma credencial no servidor do site. Retorna somente `id` e `status`; não expõe nome, telefone, QR ou credenciais. Fazer consultas espaçadas e com duração limitada, por exemplo a cada 10 s por até 2 minutos. Encerrar ao receber estado final.

Estados: `pending`, `sending`, `sent` (aceito pelo serviço, sem confirmação de entrega/leitura), `uncertain`, `expired`, `failed`. Resposta ambígua ou interrupção durante POST vira `uncertain`, sem repetição automática. A mensagem é imagem PNG do QR Code com legenda personalizada e link público temporário. O QR aponta para demonstração identificada, não um bilhete real. Não cria usuário, empresa cliente, reserva, pagamento ou embarque.

Erros: 401 credencial inválida; 422 campos/CAPTCHA inválidos ou repetidos; 429 limite por IP (5/hora), telefone (24h) ou diário; 503 desativado/validação indisponível; 409 configuração alterada durante solicitação. O CAPTCHA é validado no servidor e seu hash é único na tabela para evitar reutilização mesmo em solicitações concorrentes. A credencial é verificada antes da chamada externa.

## Administração e privacidade

Menu exclusivo do **Superadmin completo**, protegido também nas APIs `/api/v1/nexus/demo-*`; `nexus_staff` e perfis de clientes recebem 403. Tabela com 20 por página, filtros de situação e autorização comercial, detalhes de origem/contexto e alteração da situação para Novo, Contatado, Interessado ou Convertido. Contatos sem autorização comercial continuam apenas para acompanhamento da demonstração, com prospecção bloqueada. CSV exporta somente autorizados (até 10 mil por filtro), com proteção contra fórmulas de planilha.

Credenciais ficam fora das respostas de listagem. O QR usa token aleatório de 256 bits com expiração de 24h, hash para busca e cópia cifrada somente enquanto aguarda envio. O IP fica como HMAC, sem IP original; não é anonimização irreversível. User-Agent bruto é descartado após classificação simples. Consentimento e sua versão ficam registrados com data do cadastro. A limpeza de 90 dias roda no worker WhatsApp; mantê-lo ativo inclusive com a demonstração desabilitada. Backups seguem seu ciclo próprio, sem promessa de apagamento instantâneo. Solicitações LGPD/revogação devem ser tratadas pelo canal publicado; não é criada uma assinatura de marketing automática em outro serviço.

## Validação antes de publicar o formulário

Testar em homologação: consentimento opcional desmarcado, nome/empresa na imagem/legenda, CAPTCHA e hostname, bloqueio de telefone repetido, navegação do QR e expiração, Superadmin restrito, configuração desativada, falha/retorno incerto do provedor e indicação correta de que 202 não confirma entrega. A mudança do app não instala o formulário no domínio externo. Não usar números de pessoas sem solicitação.
