# NPS e satisfação

Implementado em 22/10/2026. Documentação operacional e técnica; o manual público descreve o uso sem detalhes de infraestrutura.

## Configuração e permissões

O administrador habilita as pesquisas em **WhatsApp → Configurar pesquisas automáticas** ou **NPS e satisfação → Configurar pesquisas automáticas**. Atendimento e viagem começam desativados, são independentes e não retroagem sobre conclusões anteriores à ativação. Administradores e atendentes consultam indicadores, avaliações e exportações; somente administradores alteram a configuração. O módulo WhatsApp é exigido na API e na navegação. Credenciais de parceiros, motoristas, guias e perfis Nexus não têm acesso a esses endpoints. Restrições financeiras e contratuais existentes continuam válidas.

## Elegibilidade e perguntas

- Atendimento: após concluir uma solicitação humana aberta, com telefone identificado, no máximo uma pesquisa por telefone da empresa a cada sete dias. Repetir a conclusão não cria outra pesquisa. O registro identifica quem concluiu o atendimento.
- Viagem: duas horas após a conclusão integral, incluindo todos os veículos/trechos. O término é conferido pela situação da viagem e evento `trip.completed`. Reserva confirmada com pelo menos um evento de embarque; envio ao telefone do responsável, uma pesquisa por reserva. Viagens sem conclusão completa e reservas sem embarque não são elegíveis.
- O texto das duas perguntas e o nome do destinatário são preservados na criação, junto aos vínculos, para que uma alteração posterior de cadastro não reescreva a avaliação.

Atendimento:

1. De 0 a 10, quanto você recomendaria o atendimento da [Empresa] a um amigo ou familiar?
2. O que podemos melhorar no nosso atendimento?

Viagem:

1. De 0 a 10, quanto você recomendaria viajar com a [Empresa] a um amigo ou familiar?
2. O que mais marcou sua experiência e o que podemos melhorar?

## Fila, mensagens e respostas

`app.whatsapp_worker` executa `schedule_surveys` e `process_nps`. Não exige outro serviço ou APK. A fila persistente de convites NPS tem relógio global próprio, compartilhado entre empresas, com intervalo mínimo de três minutos, independente dos bilhetes automáticos. Perguntas de continuação e agradecimentos não consomem essa cadência. Atendimento ativo ou outra pesquisa para o telefone adia o convite. Convites expiram em 24 horas na fila; a seleção de viagens recupera conclusões elegíveis de até 26 horas atrás (duas horas de espera mais a janela de envio).

As respostas são aceitas por 24 horas contadas da tentativa de envio, antes da interpretação do menu automático. A nota é um inteiro de 0 a 10; depois, comentário opcional de até 2.000 caracteres. `PULAR`, `ENCERRAR`, `SAIR`, `CANCELAR`, `MENU` e `/menu` encerram. Uma nota recebida permanece válida mesmo se o comentário for pulado, expirar ou houver retomada humana. Uma resposta manual da equipe encerra a pesquisa e cancela mensagens ainda pendentes. Depois de encerrar, a próxima mensagem inicia o fluxo normal. A despedida de inatividade do bot não atua durante a pesquisa.

Usa o mesmo webhook assinado HMAC-SHA256 do atendimento. A sincronização do webhook também funciona se apenas o NPS estiver habilitado. Empresa, sessão, telefone/contato e janela temporal são conferidos. Identificadores privados e variantes brasileiras com/sem nono dígito só são associados por vínculo já verificado ou consulta ao serviço que comprove o mesmo contato. Sem prova, não há aproximação por sufixo. As consultas têm timeout e falhas temporárias não são convertidas em uma nota nem em resposta falsa do menu. Mensagens de grupo, do próprio número, eventos antigos e assinaturas inválidas seguem as rejeições existentes. Hashes de identificação deduplicam respostas; não são usados como credenciais. As mensagens pendentes são criptografadas e o corpo é apagado após o resultado.

O POST de envio ocorre somente depois de gravar a tentativa. Aceite ambíguo ou timeout resulta em envio incerto sem repetição automática. Se a mensagem chegou, uma resposta válida ainda pode registrar a nota. Falha explícita é registrada; não existe reenvio cego. Empresa desativada, configuração desabilitada, sessão substituída, módulo removido ou reserva inválida impedem mensagens pendentes. Reinícios recuperam tentativas antigas como incertas, preservando o histórico.

## Indicadores e relatório

Filtros: período de criação (Brasília), tipo, viagem/pacote, classificação e situação. Máximo de 366 dias inclusivos e 5.000 registros; resultados maiores pedem refinamento sem truncar silenciosamente. A lista tem 50 registros por página. Indicadores e exportações usam o conjunto completo do filtro.

- Promotores: notas 9–10; neutros: 7–8; detratores: 0–6.
- NPS: `100 × (promotores − detratores) / respostas com nota`.
- Média: soma das notas dividida pela quantidade de notas.
- Taxa de resposta: notas / pesquisas com envio aceito; tentativas incertas que receberam nota também entram no denominador, pois a resposta comprova recebimento.
- Ausência de nota não vira zero. Sem respostas, NPS e média são nulos; sem envios, a taxa é nula.
- Comparação por tipo e evolução mensal da mesma coorte. Notas recebidas posteriormente continuam vinculadas ao período de criação da pesquisa.

CSV e PDF usam os filtros aplicados, incluindo registros fora da página atual. CSV protege células que poderiam ser interpretadas como fórmulas; PDF escapa comentários antes de compor o documento. Conteúdo de cliente é renderizado como texto na interface.

## Endpoints internos autenticados

| Método | Caminho | Finalidade |
| --- | --- | --- |
| GET | `/api/v1/nps/settings` | Configuração atual, administrador/atendente |
| PUT | `/api/v1/nps/settings` | Habilitar pesquisas, somente administrador |
| GET | `/api/v1/nps/trips` | Viagens com pesquisas, para o filtro |
| GET | `/api/v1/nps/report` | Indicadores e lista paginada ou exportação |

Configuração: `{"service_enabled": true, "trip_enabled": true}`. Relatório: `start`/`end` em YYYY-MM-DD; `kind=service|trip`; `trip_id` UUID; `classification=promoter|passive|detractor|unanswered`; `status`; `page` (1–100); `output=json|csv|pdf`. Nenhuma dessas rotas libera envio arbitrário ou consulta de outra empresa.

## Banco e atualização

Migração incremental **0044_nps**, com tabelas `nps_settings`, `nps_surveys`, `nps_messages`, `nps_receipts` e `nps_dispatch`. Tabelas de empresa têm RLS obrigatório; mensagens privadas e recibos são acessíveis somente ao papel de plataforma. Chaves compostas impedem vínculos entre empresas.

Atualize com `scripts/update_vps.sh`, que faz backup e aplica migrações sem recriar o banco. Depois, o administrador conecta o WhatsApp, habilita envios e escolhe as pesquisas. Os históricos de NPS ficam preservados ao desabilitar. Não exige nova publicação do APK.

## Validação

Testes automatizados usam transportes simulados, sem mensagens reais. Cobrem nota zero, nota inválida, comentário opcional, desistência, prazo, deduplicação, prioridade humana, cooldown, cadência, elegibilidade de viagem, permissões, isolamento, filtros, exportações, neutralização de fórmulas e acesso à tela por perfil. A entrega ao aparelho continua dependendo da conexão WhatsApp em produção.
