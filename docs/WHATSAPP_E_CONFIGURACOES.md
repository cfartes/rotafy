# WhatsApp OpenWA e configuração Resend

## Conexão pelo administrador da empresa

Desde 16/10/2026, novos cadastros agendam a criação automática da sessão. O administrador da empresa pode informar o número e ler o QR no menu **WhatsApp** do Rotafy, sem conhecer o ID ou a chave. As instruções abaixo de associação por ID/telefone continuam disponíveis como alternativas de suporte Nexus. A operação exige permissão da chave para criar/iniciar sessões e autorização no celular. Consulte [Conexão WhatsApp da empresa](CONEXAO_WHATSAPP_EMPRESA.md) para o fluxo, a migração e os controles de segurança.

## Modelos financeiros com QR Code

Novas notificações financeiras usam um envelope `billing-v1` criptografado na fila, contendo texto, HTML e o BR Code estático. O QR PNG é gerado localmente; dados Pix não são enviados a um gerador externo. O Resend recebe HTML com `cid:pix-rotafy` e attachment base64 com `content_id`, conforme [documentação de imagens incorporadas](https://resend.com/changelog/embed-images-using-cid). O OpenWA recebe uma única chamada `messages/send-image` com base64, mimetype, filename e caption; resultados ambíguos não são reenviados. Legendas longas são resumidas, preservando o total e o prazo. Filas antigas em texto continuam compatíveis. Nenhum envio antigo é reescrito.

Cobranças definitivas e bloqueios incluem QR sem valor; aviso prévio e pagamento confirmado não o incluem. O teste usa o mesmo modelo da cobrança definitiva com dados ilustrativos e NÃO PAGAR. As novas imagens exigem a dependência `qrcode` da imagem backend atualizada. Não há alteração no banco.

Entrega de 09/10/2026. O painel **Nexus → Configurações**, exclusivo do superadmin, permite informar API_KEY do OpenWA, API_KEY do Resend e e-mail remetente, além de associar uma sessão WhatsApp a cada empresa. Não é preciso alterar arquivos de produção ou reiniciar serviços para trocar essas credenciais.

## Configuração

1. Publique a atualização com `bash scripts/install_vps.sh`. A migração `0019_messaging` cria as configurações e a fila, preservando os dados existentes.
2. Entre em `/nexus` e abra **Configurações**. Salve a chave OpenWA e, para e-mails, a chave Resend e o endereço remetente de um domínio verificado no Resend.
3. No painel OpenWA, crie uma sessão por empresa e conecte seu número lendo o QR. O pareamento permanece no OpenWA.
4. Em cada empresa, ative **Identificar e salvar a sessão automaticamente pelo telefone** e informe **WhatsApp de envio**. O telefone é persistido ao sair do campo. O worker consulta a cada minuto até encontrar uma única sessão `READY`/`CONNECTED` com telefone exato, sem duplicidades ou vínculo com outra empresa. O ID é salvo automaticamente e os envios seguem **Habilitar envios**. A busca continua com o navegador fechado. Vínculos existentes são preservados até a ativação explícita do modo automático. A configuração manual permanece disponível desmarcando esse modo. A troca do telefone suspende os envios pelo vínculo anterior até resolver o novo. O pareamento por QR Code continua no OpenWA.
5. Homologue uma reserva com um telefone de teste autorizado e confira a mensagem e o histórico no Rotafy. A documentação fornecida descreve os endpoints, mas não detalha todos os formatos de resposta; resultados não reconhecidos são exibidos como incertos para revisão.

O gateway é fixo em `https://openwa.187-77-58-10.sslip.io/api`. A autenticação utiliza `X-API-Key`; não utiliza os usuários e senhas do painel. Credenciais do documento não são copiadas para o projeto. As chaves nunca são devolvidas pelo GET de configuração. Campos de chave vazios mantêm os valores salvos; as opções de remoção desabilitam a respectiva integração. O controle de versão impede sobrescrever uma configuração alterada em outra sessão.

Antes do primeiro salvamento pelo painel, Resend continua aceitando a configuração anterior por ambiente. Ao salvar, a configuração anterior é preservada no banco, protegida, e o painel passa a ser a fonte das alterações. Os workers consultam as configurações atualizadas a cada ciclo.

## Mensagens

- Reserva confirmada: após criação manual/importação já confirmada ou confirmação de uma solicitação pendente.
- Cancelamento: ao cancelar a reserva ou a viagem; inclui reservas canceladas junto com a viagem.
- PAGO: quando a marcação muda para PAGO. Não envia ao simplesmente salvar novamente o mesmo estado nem ao desmarcar.
- Resumo manual: em **Detalhes da reserva → Enviar resumo pelo WhatsApp**. Cada solicitação tem uma chave de operação para não repetir uma requisição perdida por falha de conexão.
- Bilhete individual: após emitir ou reemitir, use **Enviar bilhete pelo WhatsApp** na seção de bilhetes da reserva. O link vai para o telefone da família. Um único link/QR por passageiro atende todos os trechos contratados; embarques e desembarques continuam separados por trecho. O conteúdo com link é cifrado na fila e descartado se o bilhete for revogado/reemitido ou a viagem encerrada antes do envio.
- Convite de colaborador: escolha E-mail, WhatsApp ou ambos em **Equipe → Adicionar pessoa** ou **Enviar convite**. Usa o telefone do colaborador e o mesmo link privado de criação de senha nos dois canais. Consulte [CONVITES_WHATSAPP.md](CONVITES_WHATSAPP.md).

O resumo contém empresa, responsável, viagem/pacote, destino, saída em Brasília, quantidade de passageiros, valor nominal, referência curta da reserva, situação e marcação PAGO. Não inclui CPF ou nomes individuais dos passageiros. Usa o único telefone internacional da família, no formato `<DDI><DDD><número>@c.us`. O envio do bilhete inclui o link privado para a página com QR. Não há cobrança integrada, anexos, senha de passageiro, lembretes, grupos ou recebimento de mensagens nesta etapa.

## Fila e histórico

O envio é realizado pelo serviço Docker `whatsapp`, fora da transação de venda. Uma mensagem por empresa/ciclo, a cada cinco segundos. A sessão precisa estar `READY` ou `CONNECTED`. Sessões desconectadas ficam aguardando; a empresa pode pausar os envios na configuração.

O histórico da reserva é visível para administradores e atendentes e distingue pendente, enviando, aceita pelo OpenWA, falha, incerta e descartada. **Aceita pelo OpenWA não significa entregue ou lida.** Não há webhook de confirmação de entrega nesta etapa.

Eventos repetidos não geram a mesma notificação novamente. Confirmações obsoletas, troca de telefone ou sessão, mensagens vencidas e pagamentos desmarcados são descartados. A troca da sessão é bloqueada enquanto há uma mensagem em envio. Não há envio retroativo automático das vendas realizadas antes de habilitar a integração.

O OpenWA não documenta uma chave de idempotência para envio. Por isso, timeout, interrupção durante POST, erro 5xx ou resposta não reconhecida não são repetidos automaticamente: ficam **incertos**. Confira no OpenWA antes de reenviar manualmente. HTTP 429 é reagendado com intervalo de um minuto, até oito tentativas; outros 4xx são falhas. Falhas na consulta de estado não enviam mensagem. Conteúdos pendentes são cifrados e descartados após dois dias; após conclusão, falha ou incerteza o corpo é removido, preservando o histórico operacional.

## Proteção e operação

A busca utiliza os telefones retornados pela listagem de sessões e, se necessário, seus detalhes. Não interpreta nomes de sessões, UUIDs ou identificadores `@lid` como números. Se o provedor omitir o telefone, houver ambiguidade, falha de consulta ou mais de 50 sessões conectadas, a busca automática é bloqueada com orientação para conferência manual. O QR de pareamento continua sendo lido no painel do provedor. Não há migração de banco para essa funcionalidade.

As chaves e corpos pendentes utilizam Fernet com criptografia autenticada. A chave local fica fora do banco, em `/run/rotafy/integrations.key`, no volume Docker persistente `integration_keys`, criado pelo serviço `integration-secrets`. API e workers recebem esse volume somente para leitura. A inicialização preserva a chave em atualizações. Não remova o volume nem gere uma chave substituta para uma base já cifrada.

O instalador salva uma cópia protegida da chave junto ao backup local anterior à implantação, quando já há banco existente. A chave também precisa ser guardada em backup externo criptografado, juntamente com o dump. O backup PostgreSQL isolado não contém essa chave. Em uma restauração para outra VPS, restaure o conteúdo da chave no volume antes de iniciar API e workers; sem a chave original será necessário cadastrar novamente as credenciais e descartar mensagens antigas indecifráveis. Não envie a chave, arquivos de ambiente ou logs contendo credenciais no chat.

Serviços para consulta, sem imprimir configurações:

```bash
docker compose --env-file .env.production -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.production.yaml logs --tail=100 whatsapp email integration-secrets
```

Os logs do worker mostram apenas evento e situação, não chaves, destinatários ou conteúdo. Não há alteração no APK. O menu de página pública permanece oculto.

## Validação

Testes usam provedor simulado, cobrindo criptografia, permissões, sessão exclusiva por empresa, isolamento, eventos automáticos, idempotência, sessão desconectada, rate limit, timeout sem duplicação, cancelamentos, troca de sessão e aplicação dinâmica do Resend. A homologação real depende do preenchimento das chaves e de sessões conectadas pelo administrador; nenhum envio real é realizado pelos testes.


## Diagnóstico de envio incerto

O código antigo `acceptance_unknown` não distingue falhas de rede, timeout e JSON inválido. Registros existentes não são reclassificados, pois a causa original não foi armazenada. Novos envios registram `send_timeout`, `tls_error`, `invalid_response` ou `connection_error`; todos mantêm o estado incerto sem repetição automática. Os logs incluem somente situação e código, sem corpo, telefone ou credencial.

Para verificar a comunicação a partir do worker com a chave salva, sem enviar mensagens:

```bash
cd /opt/rotafy-tech &&
git pull --ff-only origin main &&
docker compose --env-file .env.production -f compose.production.yaml exec -T whatsapp python - < scripts/diagnose_whatsapp.py
```

A consulta utiliza apenas `GET /sessions`. Um resultado positivo verifica essa consulta naquele momento; não comprova aceitação do POST anterior, disponibilidade de uma sessão específica ou entrega do convite. O diagnóstico funciona antes de reconstruir a imagem. Para aplicar os novos códigos aos próximos envios, atualize os serviços pelo script habitual. Nenhuma mensagem incerta é reenviada ou alterada pela atualização.


## Resolução do destinatário (15/10/2026)

Antes do POST, o worker consulta `GET /sessions/{id}/contacts/check/{telefone}` e utiliza o `whatsappId` retornado, seja `@c.us` ou `@lid`. O telefone continua sendo a referência da reserva/colaborador; o LID não é calculado pelo Rotafy nem substitui o cadastro. A sessão da própria empresa resolve cada destinatário.

Se a consulta falhar, retornar dados incompletos ou um identificador que não seja individual, nenhum POST é realizado: a mensagem aguarda nova consulta (`recipient_lookup_failed`). Um número informado como não registrado encerra o envio com `recipient_not_registered`. Resultados incertos de POSTs anteriores continuam sem reenvio automático. Essa alteração vale para convites, reservas, pagamentos, cancelamentos e bilhetes; não exige migração de banco nem novo APK.

Teste autorizado em produção: o envio direto ao endereço por telefone excedeu 90 segundos; a consulta do destinatário retornou um LID e um novo teste dirigido ao LID recebeu HTTP 201 com messageId em aproximadamente 5 segundos. Aceitação pela API ainda não comprova entrega ao aparelho.
