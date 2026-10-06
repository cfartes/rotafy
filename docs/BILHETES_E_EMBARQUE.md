# Bilhetes e embarque — etapa 6

O administrador ou atendente confirma a reserva e, em **Detalhes da reserva**, usa **Emitir bilhetes**. Cada passageiro recebe um bilhete para cada trecho reservado. Uma família com dois passageiros e ida/volta recebe quatro bilhetes.

## Bilhete individual

O link `/bilhete#token=bt.{company_id}.{segredo}` mostra a marca da agência, o passageiro, viagem, veículo, pontos e horários do trecho, situação de presença e QR. Não mostra CPF, telefone, preço da família, pagamento ou dados de outros passageiros. O QR codifica somente a credencial aleatória, sem dados pessoais no conteúdo.

O segredo possui 32 bytes aleatórios; apenas seu SHA-256 fica no banco. O token é enviado no corpo de consultas POST e não na URL HTTP. As respostas não são armazenadas em cache. Qualquer pessoa com o link pode consultar aquele bilhete: compartilhe por canal seguro.

A emissão cria somente bilhetes ainda não existentes. Os links novos são exibidos uma única vez no painel. **Reemitir bilhete** gera outra credencial e invalida o QR/link anterior; **Revogar bilhete** impede a leitura dessa credencial. Caso uma resposta de emissão se perca, consulte a lista e reemita os bilhetes necessários; não são criados bilhetes duplicados.

O passageiro pode **Compartilhar link**, **Baixar QR** como PNG e **Imprimir ou salvar PDF** pelo diálogo de impressão do navegador. Um QR impresso representa a credencial; a validade é sempre verificada no servidor durante a operação.

Bilhetes só são emitidos/reemitidos para reservas confirmadas em viagens agendadas ou em andamento. Marcação PAGO é independente: reserva confirmada NÃO PAGO pode receber bilhete e embarcar. Viagem cancelada/concluída ou reserva cancelada torna o bilhete inválido para embarque. Revogação não apaga presença nem cancela a reserva; confirmação manual pela lista continua possível para funcionário autorizado.

## Guia

Entre com a conta da empresa, abra **Minhas viagens**, **Detalhes** e **Abrir embarque · Ida/Volta** no veículo atribuído. Administrador/atendente também podem operar pelo painel de viagens.

O manifesto inclui somente passageiros confirmados daquele veículo e trecho: nome, pontos/horários e situação de presença. Não inclui CPF, telefone, preço ou pagamento. Há busca por nome e contagem de aguardando, a bordo e desembarcados. Reservas pendentes não aparecem.

A leitura aceita câmera, imagem PNG/JPEG até 5 MB, código QR ou link do bilhete. Após conferir o QR, o guia vê o passageiro e usa **Confirmar embarque do QR**. A leitura não embarca silenciosamente. Pela lista, use **Embarcar**, **Desembarcar** ou **Reverter**.

| Situação atual | Ação | Resultado |
|---|---|---|
| Aguardando | Embarcar | A bordo |
| A bordo | Desembarcar | Desembarcado |
| A bordo | Reverter | Aguardando |
| Desembarcado | Reverter | A bordo |

A reversão pede confirmação. Presença de ida e volta é independente. Reversões e registros preservam funcionário, data/hora, origem manual/QR e versões no histórico. A câmera é encerrada após leitura, fechamento ou saída da interface.

Câmera requer permissão e um contexto seguro (HTTPS em produção; localhost no desenvolvimento). A captura em iPhone/Android reais ainda precisa de homologação. A leitura por imagem foi validada em Chromium com um QR gerado pelo próprio bilhete.

## Motorista

O motorista vê a agenda atribuída e abre **Abrir embarque · Ida/Volta** somente no seu veículo. Assim como o guia, consulta contagens, nomes, pontos e histórico e registra embarque/desembarque, por QR ou lista. Não emite/revoga bilhetes nem altera reservas. Guia é opcional; atribuição ao veículo e isolamento entre empresas são validados também na API.

Guia e motorista não acessam o manifesto de outro veículo, mesmo dentro de uma viagem da qual participam. Tokens públicos e chaves de integração não substituem login operacional. Administradores Nexus não usam esses endpoints operacionais.

## Concorrência e encerramento

Cada passageiro/trecho possui versão. Um comando informa a versão lida, uma chave UUID única e a ação. A transação bloqueia a empresa, confere autorização e reserva, verifica o token quando há QR e registra estado/evento/auditoria de forma atômica.

Dois guias com a mesma versão não duplicam embarque: o primeiro comando passa; o segundo recebe conflito e precisa atualizar. Repetir exatamente a operação original retorna seu resultado sem novo evento. Reutilizar a chave com outro conteúdo ou funcionário produz conflito.

Se a resposta não chegar ou houver erro de servidor, a tela oferece **Tentar novamente a mesma operação**, conservando o UUID e a versão. Outras ações ficam bloqueadas até resolver essa tentativa. Essa pendência existe somente em memória nesta etapa; não é uma fila offline. Fechar/recarregar o navegador exige consultar a situação atual antes de registrar outro comando.

Não se cancela uma reserva ou encerra/cancela uma viagem enquanto houver passageiros a bordo. Registre o desembarque ou corrija o embarque por reversão primeiro. Famílias sem passageiros a bordo podem trocar de veículo mesmo com histórico, respeitando a capacidade; eventos e estados de trechos concluídos preservam o veículo original. Um trecho concluído em outro veículo não pode ser revertido no novo. Veja [edição e realocação](EDICAO_E_EMAILS.md). Histórico permanece após encerramento/cancelamento.

## Contrato da API

Todas as rotas operacionais exigem a sessão da empresa e, em POST/PATCH, origem e CSRF válidos.

```text
GET  /api/v1/reservations/{reservation_id}/tickets
POST /api/v1/reservations/{reservation_id}/tickets
POST /api/v1/tickets/{ticket_id}/reissue
POST /api/v1/tickets/{ticket_id}/revoke
POST /api/v1/public/ticket                {"token":"bt..."}
```

No prefixo abaixo, `allocation_id` é o ID da alocação em `trip_vehicles`, não o ID do cadastro de veículo:

```text
/api/v1/trips/{trip_id}/vehicles/{allocation_id}/legs/{leg_id}
GET  {prefixo}/manifest
GET  {prefixo}/boarding-history
POST {prefixo}/scan                       {"token":"bt..."}
POST {prefixo}/boarding
```

```json
{
  "operation_key": "UUID único desta ação",
  "passenger_id": "UUID do passageiro no manifesto",
  "expected_version": 0,
  "action": "board",
  "token": "bt.{company_id}.{segredo}"
}
```

Substitua os placeholders por UUIDs e tokens válidos. `action` aceita `board`, `disembark`, `reverse`; `token` é opcional para registro manual; `device_id` pode identificar o dispositivo (até 100 caracteres). A resposta contém ID do evento, estado, versão e `replayed`. O histórico devolve até 200 eventos recentes do veículo/trecho, sem segredos.

Tabelas `tickets`, `boarding_states` e `boarding_events` possuem RLS forçada e vínculos compostos por empresa. O papel de comandos pode inserir, mas não editar/excluir eventos. Migração: `0009_boarding`.

Geração do QR usa [node-qrcode](https://github.com/soldair/node-qrcode); leitura usa [ZXing Browser](https://github.com/zxing-js/browser), carregado somente ao abrir o leitor. A política CSP permite imagens/streams locais `blob:` para essa operação, mantendo scripts e conexões restritos à própria origem.

## Limite desta entrega

Operação online, sem service worker, manifesto persistido ou fila durável. A próxima etapa implementará PWA/offline e tratamento de conflitos de sincronização. Não há GPS, WhatsApp, integração financeira ou implantação na Hostinger nesta entrega.
