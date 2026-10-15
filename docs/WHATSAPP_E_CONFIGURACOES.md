# WhatsApp OpenWA e configuração Resend

Entrega de 09/10/2026. O painel **Nexus → Configurações**, exclusivo do superadmin, permite informar API_KEY do OpenWA, API_KEY do Resend e e-mail remetente, além de associar uma sessão WhatsApp a cada empresa. Não é preciso alterar arquivos de produção ou reiniciar serviços para trocar essas credenciais.

## Configuração

1. Publique a atualização com `bash scripts/install_vps.sh`. A migração `0019_messaging` cria as configurações e a fila, preservando os dados existentes.
2. Entre em `/nexus` e abra **Configurações**. Salve a chave OpenWA e, para e-mails, a chave Resend e o endereço remetente de um domínio verificado no Resend.
3. No painel OpenWA, crie uma sessão por empresa e conecte seu número lendo o QR. O pareamento permanece no OpenWA.
4. Em cada empresa, confira **WhatsApp de envio** e clique em **Buscar sessão pelo telefone**. O contato cadastrado é sugerido, mas o número de envio pode ser outro. A busca normaliza DDI/DDD e exige uma única sessão `READY`/`CONNECTED`, com telefone identificado e sem vínculo com outra empresa. Confira nome, número, estado e ID, marque **Habilitar envios** e clique em **Salvar sessão**. A busca não salva nem ativa o vínculo. A consulta manual e o preenchimento do UUID continuam disponíveis.
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
