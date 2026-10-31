# Rastreamento, previsão de chegada e ordem dos embarques

## Publicação

Atualize com `bash scripts/update_vps.sh`. As migrações incrementais
`0051_arrival_estimates` e `0052_route_order` preservam o banco atual.
O worker `geocoding` existente também processa previsões e ordem dos pontos,
fora do worker de WhatsApp. Não é criada uma base de mapas na VPS.

Publique no Superadmin o APK assinado **1.10.0, compilação 16**, gerado em
`artifacts/mobile/nexus-rotafy-1.10.0.apk`. Instale por cima do app atual,
sincronizando registros antes e sem desinstalar. As versões antigas continuam
com coleta de cinco minutos e ativação manual. O controle de início também
é validado no backend e, portanto, vale para versões antigas.

No Google Cloud, habilite **Routes API** e permita-a nas restrições da chave
de backend, mantendo a restrição ao IP de saída da VPS. No Superadmin:

1. Habilite a previsão de chegada.
2. Defina a cota mensal de rotas (inicialmente 9.000, compartilhada entre todas
   as empresas e entre previsões e otimizações).
3. Ajuste os minutos de atendimento por parada, inicialmente dois.
4. Habilite o cálculo de sequência otimizada se desejado.

As opções de rotas começam desativadas. Geocodificação e Routes têm contadores
distintos. Trânsito e otimização podem usar SKUs com preços/franquias diferentes
da Geocoding API; configure cotas no Google Cloud, que é a fonte da cobrança.

## APK e responsabilidade pelo GPS

Ao registrar a saída, o APK tenta assumir o rastreamento automaticamente quando
o módulo e a empresa o permitem. O sistema Android ainda exige permissão e GPS
disponível. Se a localização falhar, a saída não é desfeita: a tela informa a
falha e permite assumir depois. O celular deve permanecer no veículo.

A frequência prevista passa para **um minuto**, com notificação visível e
funcionamento em segundo plano. Rede, bateria, permissões e gerenciamento de
energia do fabricante podem atrasar amostras. Não é uma garantia de intervalo
exato nem dispensa teste em aparelhos reais.

Uma sessão ativa é responsável por veículo. Se outro aparelho já está ativo,
o início automático o preserva. Motorista/guia atribuídos podem confirmar uma
transferência. A troca é serializada no servidor e invalida a sessão anterior;
amostras do aparelho antigo não passam a substituir as do novo.

## Agenda e liberação da saída

- Motorista: lista e trechos preparados do dia de cada deslocamento, no horário
  de Brasília. O backend filtra a lista e protege a consulta operacional fora
  do dia. Viagens em andamento permanecem disponíveis depois da meia-noite.
- Guia: mantém a consulta antecipada. Preparar/consultar o manifesto é permitido
  antes do limite de início.
- Motorista e guia: não podem registrar uma nova saída antes dos trinta minutos
  anteriores ao horário do trecho. Há aviso no APK e rejeição HTTP 409 no
  servidor. Uma repetição idempotente não reinicia um trecho já em andamento.
- Dados offline e pendências não são apagados para esconder uma viagem. A tela
  mantém pendências para sincronização/revisão. Ajustar o relógio do aparelho
  não altera o relógio do servidor usado para autorizar a saída.

## Sequência do percurso

O mesmo construtor de rota atende administrador, APK e previsão de chegada.
Os pontos fixos, origem, destino e horários cadastrados não são alterados.
Somente hotéis/casas personalizados dentro do mesmo segmento e da mesma
operação podem ser reordenados. Embarques e desembarques nunca trocam de grupo,
preservando embarque antes de desembarque e os segmentos de lotação.

O worker usa `computeRoutes` com `optimizeWaypointOrder`, sem alterar reservas.
Requer dois a 25 pontos por grupo e endereços nos limites do segmento. Grupos
maiores ou incompletos mantêm a sequência original. Os cálculos novos são feitos
antes de iniciar cada trecho, nas 24 horas anteriores; os resultados são reutilizados
por até 29 dias. Alterações nos pontos invalidam o vínculo. Falhas não alteram
o trajeto e podem ser tentadas novamente depois de cinco minutos.

Não é uma otimização global de todos os veículos, nem promete cumprir um horário
inviável. O modo DRIVING do Google não considera restrições específicas de
peso/altura de ônibus. O motorista segue responsável pela circulação permitida.
Sincronize o APK antes de sair para carregar a sequência calculada. Sem rede,
continua disponível a última rota preparada, que pode estar desatualizada.

## Previsão no WhatsApp

O sistema só solicita previsão quando um aviso de proximidade é elegível:
local válido, passageiro aguardando, veículo no raio e sessão em andamento.
A posição deve ter até noventa segundos para uma previsão numérica. O cálculo
considera trânsito e os pontos anteriores na sequência do motorista; paradas
concluídas são removidas e há margem estimada para atendimento nas restantes.
Não é calculado um atalho direto ignorando os embarques conhecidos.

As requisições são compartilhadas entre famílias no mesmo ponto quando a rota
e a amostra GPS coincidem. O aviso aguarda até trinta segundos. Falha, falta de
permissão na chave, limite de consultas, posição antiga, excesso de pontos ou
mudança inconsistente na ordem mantêm o aviso sem minutos. Não há mensagens
extras para cada amostra GPS. A fila conserva a deduplicação por reserva/trecho/
veículo; o aviso de saída em quinze minutos continua independente do GPS.

O conteúdo de previsão expira em dois minutos na fila. Payloads temporários
de cálculo são apagados ao finalizar ou em até cinco minutos pelo worker.
Só coordenadas e endereços necessários são enviados ao Google, sem nomes ou
telefones de passageiros. A chave não é enviada ao APK ou ao navegador.

## Mapa geral

O menu **Rastreamento** da empresa exibe as últimas posições GPS recebidas de
todos os seus veículos ativos. Os marcadores mostram identificação ao apontar;
os cartões oferecem uma alternativa textual e acesso ao histórico individual.
Posições antigas são sinalizadas; sem primeira amostra o veículo fica na lista,
sem marcador. A tela consulta o servidor a cada quinze segundos: isso não aumenta
a frequência de captura do celular. O mapa não conecta veículos distintos.

O mapa existente usa OpenStreetMap apenas para posições do GPS próprio.
Coordenadas e trajetos calculados pelo Google não são desenhados nesse mapa.
O isolamento entre empresas permanece aplicado no backend.

## Referências

- https://developers.google.com/maps/documentation/routes/compute_route_directions
- https://developers.google.com/maps/documentation/routes/opt-way
- https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes
