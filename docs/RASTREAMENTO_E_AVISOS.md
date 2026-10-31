# Rastreamento e avisos de embarque

## Ativar por empresa

O administrador da empresa acessa **Rastreamento**. O recurso começa desabilitado. Ative a coleta e, se desejar, os avisos de proximidade. O raio inicial é **5 km**, ajustável entre 0,5 e 20 km. O lembrete de saída é um controle separado: pode funcionar mesmo com a coleta desativada.

É necessário que o WhatsApp da empresa esteja conectado e com envios habilitados. O destinatário é o telefone da reserva familiar. Os avisos identificam empresa, responsável, passageiros, viagem e deslocamento. Não há mensagens para reservas canceladas, temporárias ou famílias sem passageiros aguardando embarque.

## Localizar os embarques

Selecione a viagem em **Locais de embarque para avisos**. Cada deslocamento da reserva mostra seu local real: hotel/endereço personalizado ou ponto de embarque da rota. Com a integração habilitada pela Nexus, as coordenadas são obtidas automaticamente em segundo plano. Revise apenas os endereços não encontrados ou ambíguos. A correção manual continua em **Confirmar ponto no mapa**.

É possível colar latitude/longitude ou links completos do Maps contendo `q`, `query`, `ll` ou a posição explícita `!3d…!4d…`. Links curtos não são expandidos. A posição da câmera `@…` não é considerada confirmação do hotel. Há um botão para abrir a pesquisa no Google Maps e o mapa permite clicar para marcar o embarque, sem consulta adicional ao provedor durante a marcação manual. A busca automática usa a chave e os limites do Google configurados no Superadmin.

Se o endereço/ponto mudar, a confirmação anterior perde validade. Sem coordenadas válidas (automáticas ou manuais), o aviso de proximidade não é enviado; o lembrete de saída continua possível.

## Operação no Android

Instale o **APK 1.10.0, compilação 16**, sobre a versão anterior. **Iniciar viagem** tenta ativar o GPS automaticamente quando habilitado pela empresa. Autorize a localização e mantenha o celular no veículo. Se outro aparelho já está ativo, sua sessão é preservada; use **Assumir rastreamento deste veículo** para transferir. Falha de GPS não desfaz a saída, e pode ser corrigida para assumir depois. O app tenta atualizar a rota ao registrar a saída; se essa consulta falhar, preserva a saída e informa a necessidade de sincronizar.

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
