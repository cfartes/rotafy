# Localização automática dos embarques

## Ativação

Atualize o Rotafy com `bash scripts/update_vps.sh`. A migração
`0050_google_geocoding` acrescenta tabelas e preserva reservas, posições e
confirmações manuais. O Compose inicia o serviço `geocoding`, separado do
WhatsApp. Nenhuma importação de mapas nem instalação de Nominatim é necessária.

No Superadmin completo, abra Configurações → Localização automática de
embarques. Cadastre a chave de **backend** com Geocoding API habilitada,
faturamento ativo e restrição ao IP público de saída da VPS. Ative o serviço.
A chave é criptografada pela chave persistente das integrações; a API devolve
somente se está configurada, nunca a credencial. Não é necessário alterar APK,
informar a chave Android ou expor credenciais no frontend.

O limite inicial é 9.000 tentativas por mês UTC, global para todas as empresas.
Configure também cotas e alertas no Google Cloud. O contador local não contabiliza
uso feito fora deste app e não substitui o relatório de cobrança do Google.
Uma interrupção abrupta após o envio HTTP e antes do commit pode deixar uma
consulta sem registro local; a cota do Google é a proteção externa.

## Funcionamento

- O administrador da empresa deve habilitar o rastreamento. O worker pesquisa
  locais das reservas confirmadas em viagens ativas, nos 29 dias anteriores ao
  trecho, incluindo reservas existentes e os endereços da volta.
- A busca é assíncrona, sem impedir a venda. Cada ciclo processa até um endereço
  novo por empresa, com intervalo de dois segundos entre ciclos. Tempo de rede
  e tamanho da fila podem aumentar a espera.
- A consulta contém endereço ou nome do local e cidade/UF. Nome do passageiro,
  telefone, complemento pessoal e número de quarto não são enviados.
- Endereços normalizados iguais reaproveitam coordenadas válidas somente dentro
  da mesma empresa. O cache guarda hash do endereço, coordenadas e estado,
  sem armazenar o retorno integral do Google.
- Só são aceitos resultados únicos, sem correspondência parcial, com cidade/UF
  e país compatíveis e precisão de imóvel ou interpolação de endereço. Centro
  de cidade, rua inteira, múltiplas opções e resultados inconsistentes exigem
  revisão. Essa filtragem reduz erros, mas não garante a entrada física exata.
- As coordenadas expiram em 29 dias. A leitura ignora imediatamente um cache
  expirado; o worker remove seu conteúdo mesmo se a integração estiver desativada
  e pesquisa novamente quando o embarque ainda precisar de localização.
- A correção manual prevalece e não é substituída. Mudança do endereço invalida
  a associação, sem aplicar resultados de outro endereço à reserva.
- Erros de rede/provedor têm até cinco tentativas, com espera de cinco minutos.
  Depois, ficam para revisão; a confirmação manual continua funcionando.
- Endereços incompletos, sem número ou só com nome de hotel podem ficar para
  revisão se o Google não encontrar resultado suficientemente específico.

## Tela e avisos

A tela Rastreamento identifica pontos automáticos e oferece **Ver no Google
Maps**. Coordenadas obtidas do Google não são desenhadas no mapa OpenStreetMap.
Se for necessário corrigir um ponto manualmente, o mapa abre sem usar o
resultado automático como marcador inicial. O mapa de percurso do veículo
continua usando exclusivamente posições GPS do aparelho.

O APK permanece enviando a posição após o motorista iniciar o trecho e escolher
**Assumir rastreamento deste veículo**. O servidor exige posição de até seis
minutos, precisão de até 100 metros, raio configurado e passageiro aguardando.
O lembrete de saída em quinze minutos continua independente da geocodificação.

## Diagnóstico

```bash
cd /opt/rotafy-tech
docker compose --env-file .env.production -f compose.production.yaml ps geocoding
docker compose --env-file .env.production -f compose.production.yaml logs --tail 50 geocoding
```

Sem progresso: confira integração e chave cadastradas, rastreamento da empresa,
reserva confirmada, data do trecho e consumo mensal. No Google Cloud confira
Geocoding API, faturamento, cotas e IP de saída autorizado. Não cole chaves ou
URLs de requisições em logs, chamados ou mensagens.

## Referências

- https://developers.google.com/maps/documentation/geocoding/requests-geocoding
- https://developers.google.com/maps/documentation/geocoding/policies
- https://cloud.google.com/maps-platform/terms/maps-service-terms
- https://developers.google.com/maps/billing-and-pricing/pricing
