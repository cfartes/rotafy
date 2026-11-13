# Assistência operacional no APK — 1.13.0 (21)

Implementação de 13/11/2026. Sem migração de banco. Atualize a API antes de distribuir o APK; depois, sincronize/prepare os trechos para obter os vínculos novos do roteiro.

| Antes | Depois | Motivo |
| --- | --- | --- |
| Roteiro completo sem destaque da demanda seguinte | Próxima parada de passageiros com endereço, nomes, contagens e navegação | Ajudar o operador a encontrar o próximo atendimento |
| Mensagem bruta do rastreamento | Avisos de serviço parado, outro trecho, GPS sem posição recente e envio sem confirmação | Explicar o que precisa ser conferido |
| Fila única | Revisões separadas de registros aguardando envio, com ação e horário | Evitar confundir espera de rede com conflito |
| Confirmação genérica de chegada | Resumo do trecho, horários, passageiros e pendências | Conferir antes de concluir |

## Próxima parada

A API de roteiro `GET /api/v1/trips/{trip_id}/vehicles/{allocation_id}/route` inclui `boarding_passenger_ids` e `dropoff_passenger_ids` nos pontos fixos e personalizados. São IDs de passageiros de reservas confirmadas daquele veículo/trecho, protegidos pelas mesmas permissões e isolamento existentes. Reservas temporárias não geram atendimento; canceladas não participam da rota.

O APK percorre os pontos na ordem recebida e seleciona o primeiro com passageiro aguardando embarque ou a bordo para desembarque. Os estados incluem comandos locais pendentes através da projeção já utilizada no manifesto. Nomes iguais não são usados para relacionar pessoas. Após sincronizar, dados novos do servidor podem mudar o destaque. O roteiro completo, inclusive paradas fixas sem passageiros, permanece disponível. Não representa detecção por GPS ou otimização nova. Roteiros antigos orientam a atualizar/preparar o trecho, sem impedir o restante da operação.

## Localização

O canal Android expõe somente diagnósticos em memória: trecho do serviço, início, última posição válida capturada e último envio com resposta HTTP de sucesso. Não contém coordenadas, cookies ou tokens. Não muda coleta de um minuto, fila de GPS, lease, permissões ou frequência de envio.

Na tela de viagem aberta, a consulta de estado existente a cada 30 segundos mostra aviso após três minutos sem captura recente ou sem confirmação de envio. A ausência de GPS tem prioridade quando ambos estão antigos. Serviço parado não significa que o veículo inteiro está sem rastreamento; outro celular pode ser responsável. Se o serviço pertence a outro trecho, o APK avisa e não oferece interrompê-lo como se fosse o trecho atual. Mensagens e horário de envio não são apresentados como confirmação do trecho errado. Esses avisos são visuais na tela; não foi criada notificação push ou alerta externo novo.

## Fila e chegada

Aguardando envio reúne comandos pendentes; precisam de revisão reúne conflitos e rejeições. Comandos pendentes do mesmo passageiro podem depender da revisão anterior. Sincronizar não descarta conflitos, e o botão Revisar conserva a confirmação antes de manter a informação do servidor. A tela inicial também mostra os dois totais.

Antes da chegada, o resumo mostra veículo, percurso, saída registrada, chegada prevista, total de passageiros, aguardando embarque, a bordo, desembarcados e registros para envio/revisão. Os horários seguem o fuso do celular e valores ausentes são identificados. Cancelar não grava chegada. A hora efetiva continua registrada na confirmação pelo servidor; desembarque, fila vazia, conexão e demais condições anteriores permanecem obrigatórios. Passageiros que não embarcaram continuam explícitos no resumo, sem serem embarcados automaticamente.

## Verificação

67 testes Flutter e análise sem problemas; testes da API de locais de embarque, rotas geográficas e embarque (34), mais conferência de isolamento dos IDs entre veículos. Captura com dados fictícios em `docs/screenshots/apk-proxima-parada.png`. O build usa o pacote e assinatura existentes e gera `artifacts/mobile/nexus-rotafy-1.13.0.apk`, com SHA-256 ao lado.

A validação física do GPS foi adiada pelo usuário. Os testes usam canal Android/API simulados; câmera, sinal de GPS, tela bloqueada, rede real e TalkBack ainda precisam de homologação no aparelho. Não houve implantação ou distribuição automática na VPS.
