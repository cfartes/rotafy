# NPS e satisfação

Implementado em 22/10/2026. Documentação operacional e técnica; o manual público descreve o uso sem detalhes de infraestrutura.

## Configuração e permissões

O administrador habilita as pesquisas em **WhatsApp → Configurar pesquisas automáticas** ou **NPS e satisfação → Configurar pesquisas automáticas**. Atendimento e viagem começam desativados, são independentes e não retroagem sobre conclusões anteriores à ativação. Administradores e atendentes consultam indicadores, avaliações e exportações; somente administradores alteram a configuração. O módulo WhatsApp é exigido na API e na navegação. Credenciais de parceiros, motoristas, guias e perfis Nexus não têm acesso a esses endpoints. Restrições financeiras e contratuais existentes continuam válidas.

## Elegibilidade e perguntas

- Atendimento: após concluir uma solicitação humana aberta, com telefone identificado, no máximo uma pesquisa por telefone da empresa a cada sete dias. Repetir a conclusão não cria outra pesquisa. O registro identifica quem concluiu o atendimento.
- Viagem: duas horas após a conclusão integral, incluindo todos os veículos/trechos. O término é conferido pela situação da viagem e evento `trip.completed`. Reserva confirmada com pelo menos um evento de embarque; envio ao telefone do responsável, uma pesquisa por reserva. Viagens sem conclusão completa e reservas sem embarque não são elegíveis.
- O texto inicial e o nome do destinatário são preservados com os vínculos; a resposta escolhida conforme a nota também é registrada, sem reescrever avaliações anteriores.

Atendimento:

1. Em uma escala de 0 a 10, o quanto você recomendaria o nosso atendimento para um amigo ou familiar?
2. Conforme a nota: agradecimento e encerramento para 9–10; convite a sugestões para 7–8; pedido de desculpas e oportunidade de explicar para 0–6.

Viagem:

1. Em uma escala de 0 a 10, o quanto você recomendaria viajar com a [Empresa] para um amigo ou familiar?
2. Retorno por categoria com texto específico sobre a experiência na viagem.

## Fila, mensagens e respostas

`app.whatsapp_worker` executa `schedule_surveys` e `process_nps`. Não exige outro serviço ou APK. A fila persistente de convites NPS tem relógio global próprio, compartilhado entre empresas, com intervalo configurado pela Nexus (padrão: 30 segundos), independente dos bilhetes automáticos. Perguntas de continuação e agradecimentos não consomem essa cadência. Atendimento ativo ou outra pesquisa para o telefone adia o convite. Convites expiram em 24 horas na fila; a seleção de viagens recupera conclusões elegíveis de até 26 horas atrás (duas horas de espera mais a janela de envio).

As respostas são aceitas por 24 horas contadas da tentativa de envio, antes da interpretação do menu automático. A nota é um inteiro de 0 a 10. Promotores encerram com agradecimento; neutros e detratores recebem convite ao comentário opcional de até 2.000 caracteres. `PULAR`, `ENCERRAR`, `SAIR`, `CANCELAR`, `MENU` e `/menu` encerram. Uma nota recebida permanece válida mesmo se o comentário for pulado, expirar ou houver retomada humana. Uma resposta manual da equipe encerra a pesquisa e cancela mensagens ainda pendentes. Depois de encerrar, a próxima mensagem inicia o fluxo normal. A despedida de inatividade do bot não atua durante a pesquisa.

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

## Redação acolhedora e qualidade — revisão de 22/10/2026

As perguntas iniciais passam a utilizar `app.nps_copy`, com introdução acolhedora, escala de 0 a 10, explicação dos extremos e solicitação de resposta numérica. A viagem identifica o passeio e usa uma redação equivalente. As regras de elegibilidade, cadência, janela e KPIs permanecem.

- Promotores (9–10): agradecimento correspondente ao tipo e encerramento imediato, sem segunda pergunta.
- Neutros (7–8): agradecimento e convite para sugerir como chegar à nota 10.
- Detratores (0–6): pedido de desculpas, pergunta sobre o que poderia ter sido diferente e encaminhamento interno à qualidade.

A redação do atendimento segue o texto aprovado pelo usuário. O comentário de neutros/detratores permanece opcional; a nota é preservada em desistência ou expiração. A resposta escolhida conforme a nota fica preservada em `question_comment`, junto ao texto inicial em `question_score`.

`template_version=2` identifica o novo fluxo. Pesquisas já tentadas/enviadas com a versão 1 mantêm suas perguntas e protocolo anterior. Convites antigos ainda sem tentativa são atualizados na preparação, antes do POST, sem repetir envios ou reescrever respostas anteriores.

Administradores e atendentes recebem um aviso no painel para avaliações novas com nota até 6 e podem analisá-las em **NPS e satisfação → Equipe de qualidade**. O encaminhamento é no próprio app; não envia informações para um destinatário externo adicional. `GET /api/v1/nps/quality` lista até cinquenta pendências e total; `POST /api/v1/nps/quality/{survey_id}/review` registra análise e responsável, enviando o comentário exibido em `{"comment": "texto exibido"}` ou `{"comment": null}`. Se o comentário mudar durante a análise, retorna 409 e pede conferência; repetir a análise da mesma versão é idempotente. Se o cliente comentar após uma análise, o feedback volta à fila. O histórico das notas não é apagado.

Migração aditiva `0045_service_hours_nps_copy`: versão, colunas de análise e agenda semanal da empresa. Consulte [horários de atendimento](HORARIOS_DE_ATENDIMENTO.md). Os horários afetam o aviso do atendimento humano, sem bloquear pesquisas automáticas.


### Diagnóstico ao concluir atendimento

A tela informa se a pesquisa entrou na fila, se o NPS está desabilitado ou se já existe pesquisa para o telefone nos últimos sete dias. A elegibilidade considera a data do encerramento, incluindo atendimentos iniciados antes da ativação do NPS. Telefones ausentes são obtidos do identificador telefônico ou do mapeamento de LID na sessão da empresa. Se não for possível identificar o telefone, o encerramento é revertido com uma mensagem explicativa, permitindo tentar novamente.

A fila mantém intervalo configurado pela Nexus (padrão: 30 segundos) entre convites; conversas automáticas ativas por até dez minutos e atendimentos humanos ainda abertos podem adiar o envio. Não há reenvio automático de pesquisas incertas ou retroativo de atendimentos encerrados.

Diagnóstico de leitura, sem mensagens, chaves ou telefones completos:

```bash
cd /opt/rotafy-tech
docker compose --env-file .env.production -f compose.production.yaml exec -T whatsapp python - --company nexus < scripts/diagnose_nps.py
```

Substitua `nexus` pelo identificador da empresa. Consulte o resultado para identificar o motivo de pesquisas anteriores não enviadas.
