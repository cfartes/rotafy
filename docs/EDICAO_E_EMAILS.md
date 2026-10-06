# Edição operacional e e-mails de acesso

Entrega complementar de 06/10/2026. A migração `0012_operational_edits` preserva os registros existentes e adiciona versões de edição e a fila de mensagens.

## Viagens

Administrador e atendente usam **Frota, pacotes e viagens → Detalhes → Editar viagem**. Podem corrigir nome, destino, preço para novas reservas, pacote, horários, nomes dos pontos, motorista e guias. O sistema verifica os perfis ativos e conflitos de agenda, inclusive quando motoristas trocam de veículo dentro da mesma viagem.

A edição preserva viagem, trechos, veículos já alocados, reservas e bilhetes. Não consome outra viagem da franquia nem recalcula o valor das reservas existentes. Somente viagens agendadas sem eventos de embarque permitem edição de itinerário/equipe e inclusão de novos veículos. O sistema valida a equipe e conflitos de agenda. O tipo de viagem permanece; com reservas, paradas existentes mantêm suas posições e finalidade, mas podem receber novos nomes, endereços e horários. Novas paradas podem ser acrescentadas ao fim da lista, antes do destino; reservas até o destino são ajustadas automaticamente. Sem reservas, paradas podem ser adicionadas/removidas. Para substituir veículos existentes ou mudar a composição dos trechos, use uma nova viagem e encerre a anterior conforme sua operação.

Dois editores não podem sobrescrever silenciosamente as mudanças: o segundo recebe um aviso para reabrir o editor. A alteração invalida versões de presença em espera preparadas offline; ao reconectar, ações antigas exigem atualizar/revisar o manifesto. Nomes e pontos armazenados em um aparelho sem conexão só mudam depois de atualizar.

## Reservas e realocação

Em **Reservas e lugares → Ver reserva → Editar reserva**, podem ser corrigidos responsável, telefone internacional, nomes/CPF opcionais dos passageiros e pontos dos trechos existentes. O sistema mantém identificadores dos passageiros, quantidade, bilhetes, valor e marcação PAGO. Incluir/remover passageiros ou trechos não faz parte desse editor; exige um novo cadastro compatível com a operação. Pontos de um trecho com eventos de embarque ficam protegidos, mas dados cadastrais podem ser corrigidos em uma reserva ativa de viagem aberta.

Antes de salvar, verifica a capacidade por segmento para toda a família, CPF duplicado e outra reserva ativa da mesma família. Reservas expiradas/canceladas e viagens encerradas não permitem edição.

A realocação agora aceita histórico de desembarque ou reversão e viagens em andamento. Exige que **ninguém da família esteja a bordo** e que o novo veículo comporte a família nos segmentos reservados. Estados em espera acompanham o novo veículo e recebem outra versão. Estados desembarcados e eventos históricos permanecem associados ao veículo em que ocorreram; um trecho concluído em outro veículo não pode ser revertido para embarcar novamente no novo. Trechos futuros continuam disponíveis no veículo atual. Os bilhetes consultam o veículo atual da reserva; ações offline do veículo anterior são revalidadas e rejeitadas quando incompatíveis.

## Convites e recuperação com Resend

No login da empresa ou da Nexus, **Esqueci minha senha** solicita um link por e-mail. A resposta pública é a mesma para conta existente/inexistente, com limites de tentativas. Para empresas, o identificador da agência é obrigatório na interface; a mesma pessoa em outra empresa mantém seu acesso separado. Recuperação vale uma hora, com uso único; o administrador ainda pode emitir um link manual de 30 minutos.

O administrador da agência pode selecionar **Enviar convite por e-mail** ao adicionar uma pessoa. Nenhuma senha inicial precisa ser compartilhada. Na equipe, **Enviar convite** também reenvia para usuários ativos; substitui links anteriores, mantém perfil e senha atual até redefinição e vale 24 horas. Ao definir nova senha, todas as sessões desse usuário são encerradas. Um usuário suspenso ou empresa desativada não pode usar o link.

**E-mails de acesso** mostra os 100 últimos envios da própria empresa: na fila, aceito pelo Resend, falhou e descartado. Não mostra corpo ou token. Aceito pelo provedor não significa confirmação de entrega na caixa de entrada; não há webhook de entrega/bounce nesta versão.

## Configuração

O envio real está desativado até preencher `RESEND_API_KEY` e `EMAIL_FROM` no arquivo de ambiente local/produção. A chave nunca vai para o frontend. `PUBLIC_BASE_URL` local deve apontar para a aplicação; em produção o Compose fixa `https://frotafy.nexusdataanalytics.com.br`. Com cookies Secure, links precisam usar HTTPS.

1. Verifique um domínio de envio no painel do Resend e cadastre os registros DNS indicados por ele. Escolha o remetente desse domínio, por exemplo `Nexus Rotafy <acesso@seu-dominio-verificado>`; o exemplo não é um remetente já configurado.
2. Crie uma chave com permissão de envio e configure-a diretamente no ambiente do servidor, junto de `EMAIL_FROM`. Não envie a chave no chat nem registre o arquivo real no versionamento.
3. Recrie API e worker de e-mail: `docker compose up -d api email` no ambiente local; em produção use os argumentos de arquivo/ambiente definidos no guia de implantação.
4. Solicite um convite para uma caixa controlada, confira fila/painel Resend, recebimento, link HTTPS, uso único e encerramento das sessões. Repita recuperação de agência e Nexus. Ainda não houve envio real nesta entrega.

O worker separado envia por HTTPS à API do Resend. A fila fica no PostgreSQL sob RLS por empresa. Usa uma chave de idempotência estável por mensagem, timeout de 15 segundos, até oito tentativas com espera crescente, e descarta links usados, expirados ou substituídos. Falhas definitivas exigem reenviar pelo painel. Logs omitem chave de API, destinatário, corpo e token. O corpo contém temporariamente o link privado e é limpo após envio, falha definitiva ou descarte; proteja banco e backups como dados sensíveis.

Fontes oficiais: [envio de e-mails](https://resend.com/docs/api-reference/emails/send-email), [idempotência](https://resend.com/docs/dashboard/emails/idempotency-keys), [domínios verificados](https://resend.com/docs/dashboard/domains/introduction).

## Validação da entrega

130 testes de backend e 10 jornadas Chromium aprovados. Os testes cobrem troca de motoristas, quota/valores/IDs preservados, conflitos de agenda/capacidade/edição, restrições por empresa e perfil, realocação com histórico, rejeição de versão offline antiga, convites, recuperação de agência/Nexus, expiração/uso único, revogação de sessões, retentativa/descarte e cabeçalho de idempotência do Resend. No navegador, convites e recuperação usam respostas simuladas, sem enviar mensagens reais. Build TypeScript/Vite, Ruff, Prettier e os dois Composes aprovados. Ensaio de restauração da revisão 0012 aprovado com 18 tabelas; envio real e testes em aparelhos físicos/VPS continuam pendentes.
