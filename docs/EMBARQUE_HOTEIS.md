# Locais de embarque e desembarque por reserva

Entrega: 16/10/2026. Android 1.6.0 (11).

Cada `reservation_legs` recebe `boarding_location` e `dropoff_location`, opcionais em JSON, com nome, endereço, complemento e ordem. A migração `0028_reservation_locations` apenas adiciona campos, preservando reservas, posições, bilhetes e histórico. O script existente `scripts/update_vps.sh` aplica as migrações pendentes sem recriar o banco.

O formulário usa um único campo com sugestões nativas para pontos da rota, hotéis e endereços já utilizados. Pode-se informar somente nome ou somente endereço. `JourneyLocation` exige pelo menos um deles; endereço sem nome é normalizado para nome de exibição. O editor mantém os objetos antigos, complementos e ordem até uma alteração explícita. A alteração textual preserva complemento e ordem, consolidando o novo texto no nome do local.

Novos locais usam a origem como referência de embarque e o destino como referência de desembarque. O cálculo de lugares conserva todo o segmento, evitando vender capacidade baseada em endereços ainda não geocodificados. Não há otimização automática nem validação geográfica do endereço. As posições das sugestões existentes e da rota são preservadas.

Na criação, locais são repetidos por padrão nos deslocamentos cuja cidade/UF de origem ou de retorno coincide com a saída inicial. Um ajuste individual desmarca a repetição e preserva os outros deslocamentos. Na edição de reserva existente, a repetição começa desmarcada para não sobrescrever diferenças anteriores. O formulário oculta os detalhes de cada deslocamento e as opções de veículo e situação até a expansão pelo usuário.

O botão de conferência usa Google Maps Search URLs, sem chave. Nome sem endereço utiliza a cidade/UF do deslocamento para contextualizar a busca e a navegação. É uma abertura externa: não lê a seleção nem marca o ponto como validado. O usuário pode copiar o endereço do Maps para o mesmo campo. A busca integrada não faz parte desse fluxo.

O roteiro é composto por veículo e deslocamento a partir de reservas confirmadas e bloqueios ainda válidos. Hotéis iguais na mesma referência são agrupados; passageiros confirmados e temporários aparecem separados. Cancelados e bloqueios vencidos não participam. Realocar a reserva move o hotel junto com os passageiros. A rota modelo não muda. Ordem numérica organiza hotéis entre referências; empates seguem a ordem de criação das reservas.

GET `/trips/{id}/boarding-locations` disponibiliza os locais já utilizados para administrador/atendente. GET `/trips/{id}/vehicles/{allocation}/route` inclui os pontos e links do Maps apenas para os usuários autorizados àquele veículo. Manifestos online/offline e bilhete público usam o endereço específico. Alterações após histórico de embarque ou conclusão do deslocamento são rejeitadas.

Atualize API/painel. Esta simplificação é compatível com o Android 1.6.0 (11), sem exigir outro APK ou migração adicional. No Android, sincronizar atualiza o manifesto e a rota. Sem conexão, a última preparação é mantida, sem receber alterações posteriores.
