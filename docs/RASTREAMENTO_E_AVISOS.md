# Rastreamento e avisos de embarque

## Ativar por empresa

O administrador da empresa acessa **Rastreamento**. O recurso começa desabilitado. Ative a coleta e, se desejar, os avisos de proximidade. O raio inicial é **5 km**, ajustável entre 0,5 e 20 km. O lembrete de saída é um controle separado: pode funcionar mesmo com a coleta desativada.

É necessário que o WhatsApp da empresa esteja conectado e com envios habilitados. O destinatário é o telefone da reserva familiar. Os avisos identificam empresa, responsável, passageiros, viagem e deslocamento. Não há mensagens para reservas canceladas, temporárias ou famílias sem passageiros aguardando embarque.

## Localizar os embarques

Selecione a viagem em **Locais de embarque para avisos**. Cada deslocamento da reserva mostra seu local real: hotel/endereço personalizado ou ponto de embarque da rota. Com a integração habilitada pela Nexus, as coordenadas são obtidas automaticamente em segundo plano. Revise apenas os endereços não encontrados ou ambíguos. A correção manual continua em **Confirmar ponto no mapa**.

É possível colar latitude/longitude ou links completos do Maps contendo `q`, `query`, `ll` ou a posição explícita `!3d…!4d…`. Links curtos não são expandidos. A posição da câmera `@…` não é considerada confirmação do hotel. Há um botão para abrir a pesquisa no Google Maps e o mapa permite clicar para marcar o embarque, sem consulta adicional ao provedor durante a marcação manual. A busca automática usa a chave e os limites do Google configurados no Superadmin.

Se o endereço/ponto mudar, a confirmação anterior perde validade. Sem coordenadas válidas (automáticas ou manuais), o aviso de proximidade não é enviado; o lembrete de saída continua possível.

## Operação no Android

Instale o **APK 1.10.2, compilação 18**, sobre a versão anterior. **Iniciar viagem** tenta ativar o GPS automaticamente quando habilitado pela empresa. Autorize a localização e mantenha o celular no veículo. Se outro aparelho já está ativo, sua sessão é preservada; use **Assumir rastreamento deste veículo** para transferir. Falha de GPS não desfaz a saída, e pode ser corrigida para assumir depois. O app tenta atualizar a rota ao registrar a saída; se essa consulta falhar, preserva a saída e informa a necessidade de sincronizar.

Um único aparelho fica responsável por veículo e deslocamento. Outro colaborador atribuído pode confirmar a transferência. A sessão anterior deixa de aceitar posições. Cada retorno ou próximo deslocamento inicia seu rastreamento ao registrar a saída; não há coleta durante o intervalo entre os passeios.

O serviço Android mantém uma notificação visível e solicita GPS com intervalo previsto de um minuto. O usuário pode interromper pelo app. A chegada encerra a coleta, assim como o logout. Desativar o recurso no servidor impede novas posições imediatamente; o celular toma conhecimento na próxima consulta, normalmente em até um minuto com conexão no APK atualizado. Sem contato com o servidor por quinze minutos, o serviço local se encerra para não continuar coletando indefinidamente após uma possível revogação.

Posições ainda não enviadas ficam somente na memória do processo, durante a sessão ativa, sem gravação em disco. Encerrar o processo descarta essas amostras; as posições já confirmadas permanecem no servidor. Os registros de embarque/desembarque continuam na fila SQLite criptografada. Uma interrupção ou revogação descarta posições locais que já não podem ser transmitidas. Não há credenciais persistidas pelo serviço nativo. O Android pode encerrar o processo por ação do usuário ou restrições do aparelho; nesse caso, abra o APK e assuma novamente. O recurso não reinicia a coleta silenciosamente após reinicialização do telefone.

O GPS e a manutenção do serviço consomem bateria. Oriente o uso de carregador no veículo. Permissão negada, GPS desativado, rede indisponível ou encerramento forçado interrompem ou atrasam os dados; a tela administrativa mostra o horário da última posição e sinaliza atraso acima de seis minutos.

## Acompanhamento e avisos

- **Mapa:** o administrador seleciona o veículo em viagem. A linha tracejada liga as amostras coletadas; não reconstrói o percurso real pelas ruas entre elas. O mapa geral consulta posições a cada quinze segundos; o histórico individual, a cada trinta.
- **Proximidade:** uma vez por reserva, veículo e deslocamento, quando a amostra recente está no raio configurado do embarque confirmado. Exige precisão de até 100 metros e posição com no máximo seis minutos. O gatilho usa distância geográfica. Quando habilitada, a Routes API acrescenta previsão de chegada com trânsito, paradas e margem de atendimento, exigindo amostra de até noventa segundos.
- **Saída:** o processamento prepara uma mensagem dentro dos quinze minutos anteriores ao horário de saída programado de cada deslocamento, tanto ida quanto volta e roteiros de pacote. Não depende do GPS ou do início manual. Para um hotel atendido posteriormente, o texto distingue o horário de saída do trecho do horário de atendimento do hotel.

O processamento usa a fila existente de WhatsApp, com deduplicação persistente e nova validação antes do envio. Avisos de proximidade expiram em dois minutos; lembretes expiram na saída programada. Alterações de horário/veículo, embarque, cancelamento e desativação invalidam alertas que deixaram de fazer sentido. Resultados incertos do provedor não são reenviados automaticamente.

Mesmo com intervalo previsto de um minuto entre amostras, um veículo pode atravessar o raio inteiro antes da coleta seguinte. O aviso comunica proximidade aproximada, sem garantia de antecedência ou entrega; não substitui o horário e as instruções de embarque.

## Atualização e validação

Execute a atualização normal da VPS. A migração **0038_vehicle_tracking** acrescenta tabelas, índices e campos na fila; não recria nem limpa dados existentes. O worker WhatsApp já executa o processamento de avisos, enquanto o worker `geocoding` processa coordenadas, previsões e sequência dos pontos. Publique o APK em **Superadmin → Configurações → Atualizações do aplicativo Android** para oferecê-lo na ajuda e nas versões com verificador.

O histórico de posições fica limitado a noventa dias, com limpeza pelo worker. A API e o banco isolam empresas; somente o administrador da própria empresa consulta o mapa. Colaboradores operacionais enviam posições apenas em uma sessão própria e de veículo atribuído. O acompanhamento operacional de motorista/guia continua possível em viagens já vendidas durante bloqueio financeiro, conforme a regra existente; o administrador bloqueado permanece restrito ao Financeiro.

Testes automatizados cobrem permissões, isolamento, transferência, encerramento, validação de posições, proximidade, deduplicação, passageiro já embarcado, ida/volta e janela do lembrete. A coleta com tela bloqueada e comportamento da bateria requerem homologação no aparelho Android utilizado em operação; compilação e testes automatizados não substituem essa verificação de campo.

O mapa usa Leaflet e mosaicos OpenStreetMap, com atribuição e referência limitada à origem. Não faz download para uso offline. Endereços são processados separadamente pelo backend usando Google; seus resultados não são plotados sobre o mapa OpenStreetMap. O serviço público de mosaicos não tem garantia de disponibilidade e deve respeitar sua [política de uso](https://operations.osmfoundation.org/policies/tiles/).


Os avisos de quinze minutos e proximidade incluem endereço e complemento do ponto de embarque do trecho notificado e um link de busca no Google Maps. Hotéis personalizados têm prioridade sobre parada/origem. Sem endereço cadastrado, o aviso explicita a ausência e pesquisa pelo nome e cidade, sem prometer uma posição exata.


## Regras atuais de agenda e previsão

Motorista vê seus trechos do dia no horário de Brasília, preservando os que
estão em andamento após a meia-noite. Guia mantém consulta antecipada.
Motorista e guia só podem iniciar o trecho a partir de trinta minutos antes do
horário previsto; o manifesto pode ser consultado antes. Pendências offline
não são apagadas.

O mapa geral mostra todos os veículos da empresa com GPS recebido. A previsão
e a otimização preservam os pontos fixos da rota e são configuradas pela Nexus.
Veja [configuração, limites e funcionamento](RASTREAMENTO_E_PREVISAO.md).

## Confirmação do serviço Android — 1.10.1, compilação 17

O APK aguarda a confirmação de que o serviço Android entrou em primeiro plano antes de informar que o rastreamento iniciou. A solicitação da permissão de notificações ocorre depois dessa inicialização. A primeira posição obtida na ativação é enviada ao servidor; não é descartada. Se o Android não confirmar o serviço ou a API recusar a primeira posição, a ativação falha, a sessão criada é encerrada e a tela permite tentar novamente. A saída da viagem permanece registrada.

Publicar `artifacts/mobile/nexus-rotafy-1.10.1.apk` no Superadmin e instalar sobre a versão anterior. Não há alteração de esquema nem recriação do banco. Validar no aparelho a notificação, o recebimento contínuo com tela bloqueada e o aviso em uma reserva ainda aguardando embarque. Ausência de notificação não prova, isoladamente, falha de GPS: a permissão de notificações também pode ocultá-la.

## Coleta periódica — 1.10.2, compilação 18

A coleta periódica usa o mesmo cliente de localização combinada já utilizado na captura inicial, em vez de depender exclusivamente do GPS por satélite quando ele está habilitado. Solicita uma posição recente a cada minuto, inclusive sem deslocamento, e mantém a tentativa nativa como alternativa se o cliente combinado não retornar posição. Cada tentativa é limitada no tempo e cancelada ao interromper ou transferir o rastreamento. A precisão informada é preservada: o backend continua exigindo até cem metros para aviso de proximidade. Não reutiliza indefinidamente coordenadas antigas.

O manifesto consulta o estado local a cada trinta segundos e mostra o último envio periódico confirmado pela API, falta de posição recente ou erro de comunicação HTTP. A confirmação inicial enviada pelo Flutter não é contada nesse indicador do serviço periódico. Uma notificação ativa e consultas GET com sucesso não comprovam a coleta: confirme o aumento de registros na sessão atual no banco.

Publique `artifacts/mobile/nexus-rotafy-1.10.2.apk` no Superadmin e instale sobre a versão anterior. Teste por pelo menos três minutos, com tela bloqueada, parado e em deslocamento. Ambiente fechado ou restrições do aparelho ainda podem impedir uma posição precisa. Sem alteração no banco.

## Roteiro planejado e antecedência — 1.11.0, compilação 19

A regra de trinta minutos passa a ser configurável pelo administrador em Configurações. A comparação visual preserva a sequência de pontos no início do trecho e reúne suas sessões GPS. Consulte [Operação da equipe e rotas](OPERACAO_EQUIPE_E_ROTAS.md), incluindo chave web separada, compartilhamento com Google, consumo e limites.

## Mapa da frota em tela inteira

Menu separado de Rastreamento, exclusivo do administrador e condicionado ao módulo tracking. Ocupa a área de trabalho e oferece expansão nativa quando suportada. Consulta `/api/v1/tracking/vehicles` a cada quinze segundos; a coleta do APK permanece a cada minuto. Mostra placa, veículo, viagem, precisão e horário do GPS; amostras acima de dois minutos são sinalizadas. Atualizações preservam zoom e enquadramento. Veículos sem posição ficam contabilizados como aguardando GPS. A função usa GPS próprio sobre OSM, sem resultados Google ou chave web. Configurações, histórico e comparação permanecem em Rastreamento.

## Histórico de trajetos encerrados

Menu próprio, exclusivo do administrador da empresa e condicionado ao módulo `tracking`. Usa somente GPS próprio sobre OSM, sem depender do snapshot planejado ou de chave Google. Reúne sessões por empresa, viagem, alocação e trecho; não mistura veículos ou retorno. Viagens concluídas/canceladas e trechos concluídos de viagens ainda em andamento são consultáveis. Sem migração de banco ou novo APK.

- `GET /api/v1/tracking/history?start_date=AAAA-MM-DD&end_date=AAAA-MM-DD`: período inclusivo em Brasília, até 90 dias, padrão últimos 30; máximo 200 viagens com aviso de truncamento.
- `GET /api/v1/tracking/history/{trip_id}`: veículos e trechos encerrados com sessões registradas, incluindo estados sem GPS.
- `GET /api/v1/tracking/history/{trip_id}/{allocation_id}/{leg_id}`: GPS cronológico ainda retido, máximo 10.000 amostras e aviso de percurso parcial. Retenção de 90 dias preservada; não recupera dados já removidos.

Todas as consultas exigem administrador e vínculo com a empresa autenticada, sob o RLS existente. O filtro de datas localiza a viagem, mas a seleção carrega todo o trecho retido. O mapa usa canvas para não criar um elemento por amostra; troca de sessão ou lacuna acima de dez minutos separa segmentos. A linha não reconstrói vias nem classifica desvios. A tela informa precisão baixa, ausência de GPS e amostra única.

## Estimativa de quilometragem

`GET /api/v1/tracking/history/{trip_id}/distance`, exclusivo do administrador da empresa com módulo tracking, retorna `journeys`, `distance_m` total da frota, `partial`, situação da viagem e quantidade de trechos encerrados sem rastreamento. Cada item identifica veículo, alocação, trecho, distância, qualidade e disponibilidade de sessão. A interface agrega por veículo, mostra o trecho selecionado e usa a paginação compartilhada de vinte linhas. Outras empresas recebem 404; motorista/guia não têm acesso.

O servidor reutiliza a distância esférica entre coordenadas do rastreamento. Lê amostras em ordem por alocação/trecho/horário e processa por streaming com memória limitada, sem aplicar o teto visual de 10.000 pontos do mapa. O resultado é calculado na consulta; não altera nem exclui posições e não persiste quilometragem. Retenção de noventa dias, sem migração, novo APK ou serviço externo.

Regras de qualidade: precisão acima de 100 m interrompe a cadeia; lacunas maiores que 600 s e trocas de sessão não recebem distância interpolada. Saltos acima de 160 km/h após descontar a incerteza são ignorados mantendo a última posição plausível. Horários repetidos não duplicam distância; coordenadas conflitantes no mesmo horário são sinalizadas quando excedem a incerteza. A âncora de distância só avança quando o deslocamento supera o maior valor entre 15 m e a soma das precisões, reduzindo deriva com o veículo parado. O controle de lacuna/velocidade usa a última posição plausível, não a âncora estacionária.

Um intervalo válido pode resultar em zero; sem intervalo válido o valor é null. Lacunas no início/fim acima de dez minutos, horários operacionais desconhecidos, início além da retenção, rejeições, transferências e trechos sem sessão deixam o resultado parcial. Viagens ainda não concluídas ou canceladas também têm total parcial. Sem lacunas detectadas não certifica cobertura: o traçado entre amostras subestima curvas e não substitui o hodômetro. O mapa permanece bruto, a estimativa aplica filtros. A soma inclui todos os veículos e somente trechos encerrados; não deve ser interpretada como distância de um único veículo quando a frota é múltipla.
