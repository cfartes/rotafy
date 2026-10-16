# Locais de embarque e desembarque por reserva

Entrega: 16/10/2026. Android 1.6.0 (11).

Cada `reservation_legs` recebe `boarding_location` e `dropoff_location`, opcionais em JSON, com nome, endereço, complemento e ordem. A migração `0028_reservation_locations` apenas adiciona campos, preservando reservas, posições, bilhetes e histórico. O script existente `scripts/update_vps.sh` aplica as migrações pendentes sem recriar o banco.

Os pontos existentes continuam selecionados no formulário. Um endereço adicional usa a posição existente como referência: embarque após a referência e desembarque antes da referência. O cálculo de lugares conserva todo o segmento entre referências, evitando vender capacidade baseada em endereços ainda não geocodificados. Não há otimização automática nem validação geográfica do endereço.

O roteiro é composto por veículo e deslocamento a partir de reservas confirmadas e bloqueios ainda válidos. Hotéis iguais na mesma referência são agrupados; passageiros confirmados e temporários aparecem separados. Cancelados e bloqueios vencidos não participam. Realocar a reserva move o hotel junto com os passageiros. A rota modelo não muda. Ordem numérica organiza hotéis entre referências; empates seguem a ordem de criação das reservas.

GET `/trips/{id}/boarding-locations` disponibiliza os locais já utilizados para administrador/atendente. GET `/trips/{id}/vehicles/{allocation}/route` inclui os pontos e links do Maps apenas para os usuários autorizados àquele veículo. Manifestos online/offline e bilhete público usam o endereço específico. Alterações após histórico de embarque ou conclusão do deslocamento são rejeitadas.

Atualize API/painel antes do APK. No Android, sincronizar atualiza o manifesto e a rota. Sem conexão, a última preparação é mantida, sem receber alterações posteriores. Instale `artifacts/mobile/nexus-rotafy-1.6.0.apk` para visualizar o roteiro com endereços e passageiros por ponto.
