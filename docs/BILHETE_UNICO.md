# Bilhete único por passageiro

Atualização de 09/10/2026, migração `0020_shared_tickets`.

Na reserva há um único cartão por passageiro. Ao emitir, cada passageiro recebe um link e QR válidos nos seus trechos contratados. A página pública lista os pontos, horários, veículo e situação em cada trecho. A leitura online e o manifesto offline selecionam o passageiro no veículo e trecho em operação, mantendo os controles individuais de embarque e desembarque.

Bilhetes antigos continuam válidos no respectivo trecho até a emissão unificada ou reemissão. Para uma reserva antiga, clique em **Emitir bilhetes** para converter os bilhetes existentes. A conversão invalida os links anteriores. **Reemitir bilhete** gera um novo QR para todos os trechos daquele passageiro; **Revogar bilhete** bloqueia todos esses trechos. Estados e histórico de embarque são preservados. Prepare novamente os manifestos offline após converter, reemitir ou revogar bilhetes.

Após emitir/reemitir, o botão **Enviar bilhete pelo WhatsApp** coloca o link privado na fila, para o telefone da reserva. A sessão da empresa precisa estar habilitada. A solicitação usa uma chave de operação para evitar duplicação ao repetir uma requisição perdida. O histórico aparece na seção WhatsApp da reserva. O texto privado não é guardado em claro no banco nem nos logs. Se o QR for invalidado antes do processamento, a mensagem pendente é descartada. Links já enviados não podem ser retirados do WhatsApp, mas deixam de autorizar embarque após revogação.

O token continua sendo mostrado apenas na emissão/reemissão, sem persistir no navegador. Ao fechar a tela, será necessário reemitir para obter e enviar novamente o link. Não há nova versão do APK nesta mudança: as leituras usam os endpoints e o formato de manifesto existentes. A homologação do envio real depende da configuração OpenWA.
