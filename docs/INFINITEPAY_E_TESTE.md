# Cobrança automática de assinaturas Nexus

Implementação de 16/10/2026. Referência: [documentação oficial do Checkout InfinitePay](https://www.infinitepay.io/checkout-documentacao).

## Ativação

1. Atualizar o aplicativo com `scripts/update_vps.sh`. A migração `0029_infinitepay` adiciona a integração; `0030_postpaid_cycles` acrescenta a modalidade de ciclos de 30 dias e a identificação de cobrança de setup; não recria o banco nem altera cobranças antigas.
2. No SuperAdmin completo, abrir **Configurações → Cobrança e período de teste**. Informar a **InfiniteTag da Nexus**, sem `$`, setup em reais e dias de teste. Não há chave de API no contrato público documentado utilizado aqui.
3. Habilitar **Usar InfinitePay nas novas cobranças**, manter remetente de e-mail e sessão WhatsApp da Nexus configurados, marcar **Ativar avisos e cobranças mensais automáticas** e salvar. A conta precisa estar apta a receber pagamentos no provedor.
4. O `PUBLIC_BASE_URL` da instalação deve ser `https://rotafy.nexusdataanalytics.tech`. Checkout, retorno e webhook usam esse endereço. Não é preciso editar arquivos para mudar InfiniteTag, setup ou teste. O callback é informado em cada criação de checkout.
5. Conferir a primeira cobrança real e seu retorno no painel do provedor e do Rotafy após ativação. Os testes automatizados usam provedores simulados, sem transações reais.

As duas opções começam desativadas. Novas empresas entram em teste quando ambas estiverem ativas. Setup e dias são capturados na contratação. A mudança dos valores globais não recalcula contratos anteriores. Desmarcar InfinitePay interrompe a adesão de novos contratos automáticos e a conversão das novas cobranças legadas; contratos automáticos existentes mantêm seu modelo e requerem a InfiniteTag configurada. Desativar a automação geral pausa novas emissões/envios, preservando a verificação de pagamentos já realizados.

## Regras confirmadas

- Cadastro dia 10, teste de 7 dias: período gratuito de 10 a 17 (fim exclusivo), cobrança no dia 17. Datas são calculadas em America/Sao_Paulo.
- Teste: franquia do plano escolhido, sem mensalidade, setup ou excedentes a pagar. Criar além da franquia é impedido. Cancelar viagens reverte o consumo no período original.
- Término do teste: setup único e separado, quando maior que zero. A franquia independente começa nessa data. A mensalidade e os excedentes do próprio ciclo são cobrados somente após 30 dias de uso.
- Exemplo: cadastro em 10/10, sete dias de teste, setup em 17/10, primeira mensalidade em 16/11. Renovações a cada 30 dias: 16/12, 15/01. Mensalidade e excedentes usam as condições do período encerrado.
- Aviso prévio um dia antes, sem link. Cobrança definitiva e link são enviados por e-mail aos administradores ativos e WhatsApp ao contato da empresa. O link também aparece em Meu plano e Financeiro.
- Prazo: dois dias úteis a partir do dia seguinte à emissão, excluindo fins de semana e feriados nacionais já usados pelo sistema. Falta de confirmação restringe novas operações, preservando consultas e viagens vendidas.
- Pagamento verificado retira apenas a pendência da respectiva fatura; não remove suspensão administrativa nem outros débitos vencidos.
- A migração 0030 converte apenas contratos automáticos ainda em teste, sem período pago materializado e sem cobrança definitiva. Um aviso parcial existente é ajustado para somente setup; mensagens parciais ainda pendentes com o valor antigo são descartadas. Contratos legados e contratos com cobranças definitivas preservam suas condições, links e pagamentos.

## Persistência e processamento

`subscriptions.billing_mode` distingue contratos mensais legados (`arrears`), contratos antecipados anteriores (`prepaid`) e novos contratos pós-pagos de 30 dias (`postpaid30`). O teste usa índice -1; os ciclos operacionais pagos começam em zero. `boundaries` calcula datas a partir da âncora, somando 30 dias por ciclo no novo modelo, e mantém aniversário para os legados.

`billing_invoices.invoice_kind` identifica `setup` ou `subscription`. No novo modelo, a cobrança de setup tem índice financeiro zero, não ocupa `period_id` e não contém mensalidade, franquia ou excedentes. Cada mensalidade usa índice financeiro ciclo+1 e o período operacional que foi encerrado. A chave única impede duplicação. Setup zero não gera fatura nem checkout.

Um dia antes da emissão, o aviso parcial é persistido. No fechamento, uso e excedentes são recalculados antes de consolidar. O setup usa a data de término do teste; a mensalidade usa o fim exclusivo do ciclo. O prazo de dois dias úteis conta da data de emissão de cada cobrança, independentemente. Um Pix de setup não dá baixa em mensalidades.

A migração é incremental: não exclui dados, não recria tabelas nem altera cobranças emitidas. Contratos que já têm histórico financeiro continuam no modelo anterior, evitando cobrar novamente um mês já antecipado. A atualização desses contratos exige conferência individual; não existe conversão automática de valores já cobrados.

`billing_checkouts` registra uma tarefa por fatura, com identificador único usado em `order_nsu`, conta de recebimento capturada e segredo protegido do webhook. Apenas a plataforma lê essas tabelas privadas. O processador financeiro cria links por `POST /links` e persiste o resultado antes de agendar as mensagens. Falhas temporárias recebem novas tentativas com espera progressiva. Recriar link não debita cliente; o identificador do pedido é preservado.

`billing_payment_events` guarda notificações sem confiar nos valores recebidos. Webhook tem token aleatório por checkout e grava o evento rapidamente. Retorno do navegador é uma segunda entrada para o mesmo fluxo. O processador consulta `POST /payment_check` com conta, pedido, transação e slug e só confirma `success=true`, `paid=true`, valor nominal exato e valor pago suficiente. Confirmações repetidas são deduplicadas, e a transação só pode baixar uma fatura.

Os webhooks documentados não especificam uma assinatura criptográfica. O token limita a entrada, mas a confirmação independente pela API é obrigatória. A página de retorno nunca considera parâmetros de URL como prova de pagamento. O endpoint público de situação mostra somente o estado, sem dados da empresa, valores ou credenciais.

O worker processa cobranças, checkouts, verificações e mensagens, mantendo o indicador de atividade. A interface e a API não bloqueiam esperando consultas ao provedor. Confirmações automáticas têm auditoria sem usuário humano; baixas manuais registram o SuperAdmin responsável.

## Operação e revisão

- Link recusado: verificar InfiniteTag e acionar **Tentar gerar link novamente**. Essa ação explícita pode usar a conta atual em uma tarefa recusada sem link emitido. Falhas de rede e links já emitidos mantêm a conta capturada.
- Pagamento após cancelamento, após baixa manual, transação já utilizada ou valor divergente: registrar para conferência, sem baixar outra fatura ou liberar acesso indevidamente.
- Cancelar fatura no Rotafy não revoga um checkout externo nem devolve dinheiro. Eventual recebimento posterior é sinalizado. A documentação utilizada não fornece cancelamento, estorno ou chargeback por API; a conferência dessas situações ocorre no painel do provedor e na Nexus.
- API indisponível: evento permanece pendente para nova consulta. Se o webhook não chegar e o comprador não retornar, não há transação/slug suficientes para uma consulta documentada por apenas pedido; o operador deve conferir a operação no provedor.
- Pix manual continua disponível para faturas anteriores e baixas excepcionais. Não é enviado QR Pix estático nas cobranças automáticas: os meios de pagamento e o QR Pix são apresentados pelo checkout.
- O cliente precisa pagar cada link. Esta integração automatiza emissão, envio e confirmação; não cadastra débito recorrente no cartão.

## Validação da separação de setup e mensalidade

Suíte backend: 355 testes aprovados durante esta entrega. Após concluir os cenários de conversão de dados, os nove casos de `test_postpaid_cycles.py` passaram em execução adicional. Os testes cobrem o exemplo 10/10 → 17/10 → 16/11 → 16/12, meses curtos e ano bissexto, setup zero, recálculo de excedentes após aviso parcial, renovação da franquia, preservação de contratos antecipados e conversão de aviso parcial durante o teste. Dez testes de interface das áreas financeira, pagamento e documentação passaram. O build web foi aprovado. Não foram emitidas cobranças reais nem enviados avisos a clientes durante a validação.
