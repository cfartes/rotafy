# Distância e duração padrão de rotas — 05/11/2026

## Fluxo

O cadastro consulta a previsão depois de cidades e endereços completos, com debounce de um segundo. A ordem das paradas é mantida. Cada sentido tem sua previsão; inverter a ida não copia um resultado do provedor para a volta. Uma rota nova recebe o tempo calculado apenas enquanto o operador não o editou. Rotas existentes/duplicadas preservam o tempo; o botão Usar tempo calculado aplica explicitamente a sugestão. Paradas somam sua margem sem nova consulta.

O botão Consultar distância e tempo no card abre uma previsão atual, sem modificar a rota. Respostas atrasadas de outra geometria e respostas após fechar a tela não são aplicadas. O salvamento aguarda o cálculo automático pendente, mas permanece disponível para um tempo manual. Falha no serviço permite preenchimento manual. TripModal e a validação de snapshots já utilizam duration_minutes + stop_minutes; não há mudança nos snapshots das viagens existentes.

## API e segurança

- `GET /api/v1/routes/estimate-availability`: somente disponibilidade e orientação, sem chave ou contadores globais.
- `POST /api/v1/routes/estimate`: cidades IBGE válidas, endereços de 3 a 300 caracteres e até cinquenta endereços de parada. Retorna distance_m, duration_minutes e source. Administrador/atendente com módulo routes; serviço parceiro, motorista/guia e equipe Nexus não acessam o cálculo.
- Destino HTTPS fixo e redirecionamentos recusados. Somente endereços e municípios são enviados, sem dados dos passageiros. Resposta limitada a 256 KiB, distância/duração validadas e tempo de rede de oito segundos. Falhas não devolvem mensagens/chaves do provedor.
- Reserva atômica no mesmo routes_used/routes_limit de previsão/otimização. Até duas chamadas por sentido, preservando a sequência com endpoint compartilhado entre os blocos. Trinta solicitações por minuto por empresa. A reserva é confirmada antes das chamadas para não liberar consumo ilimitado por falhas/repetições.
- Usa chave criptografada do backend e o controle routes_enabled, cujo rótulo agora contempla cadastro e previsão de chegada. Campos e valores da configuração são preservados. Sem nova migração ou APK.

## Conteúdo do provedor

A resposta usa TRAFFIC_UNAWARE, duration e distanceMeters. Os segundos são somados antes do arredondamento para minutos; margem de atendimento é cálculo operacional separado. Não persiste nem registra a resposta bruta ou cria cache de distância do Google em banco, snapshots ou armazenamento offline. A API responde Cache-Control: no-store; o cliente mantém a consulta somente no estado do componente. O tempo confirmado pelo operador permanece como parâmetro de seu planejamento existente. Atribuição Google Maps acompanha a previsão; não são desenhados resultados sobre OSM. Termos/privacidade públicos incluem links e explicam o compartilhamento.

Referências oficiais: [computeRoutes](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes), [políticas e atribuição](https://developers.google.com/maps/documentation/routes/policies) e [termos específicos](https://cloud.google.com/maps-platform/terms/maps-service-terms). A retenção de resultados não deve ser ampliada sem conferir os termos aplicáveis à conta.
