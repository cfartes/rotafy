# Equipe, antecedência e comparação de rotas

Entrega de 02/11/2026. Migração incremental **0053_crew_operations**; não recria nem limpa o banco. APK **1.11.0, compilação 19**.

## Download automático para motoristas e guias

Os cadastros com senha inicial e por convite enfileiram uma única mensagem independente `crew_apk`, com o nome do colaborador, a empresa e o link estável `/api/v1/public/mobile/latest/download`. A URL serve o maior build publicado do pacote global `br.com.nexusdataanalytics.rotafy`. Não contém senha nem token e não expira ao usar o convite. É necessário publicar primeiro um APK.

A mensagem usa a sessão WhatsApp da empresa. Sem telefone, módulo ou configuração, o cadastro informa que não foi possível preparar o envio; não inventa confirmação de entrega. A fila revalida o telefone, o papel motorista/guia, a situação ativa e a sessão antes de enviar. O prazo da mensagem na fila é sete dias. Reenviar convite não duplica a mensagem do aplicativo. Não há disparo retroativo para toda a equipe.

## Antecedência

`GET/PUT /api/v1/company/operation-settings`: leitura por usuário da própria empresa; alteração somente pelo administrador. Campos `early_start_enabled` e `early_start_minutes` (inteiro de 1 a 1.440). Desativado equivale a zero minutos de antecedência. O padrão é habilitado com trinta minutos, preservando a regra anterior. Administradores e atendentes mantêm suas permissões; a restrição aplica-se a motorista e guia. A agenda do motorista continua no dia da viagem em Brasília.

A API valida o horário atual em cada início de trecho. Manifestos online/offline incluem `departure_policy`. O APK 1.11.0 usa a regra do manifesto; sincronizar após mudanças. Um aparelho antigo não contorna a regra atual no backend, mas pode mostrar disponibilidade diferente. Consultar o manifesto não inicia a viagem.

## Comparação visual

Ao iniciar o trecho, a mesma função que monta a navegação do motorista preserva a sequência de pontos em `journey_route_snapshots`. O registro é único por empresa, alocação e trecho e não é substituído por uma segunda solicitação. Preserva nomes dos locais, endereços, tipo de operação e horários, sem copiar nomes dos passageiros ou coordenadas de resultados Google. Não produz histórico retroativo.

Somente o administrador consulta `/api/v1/tracking/routes?trip_id=UUID` e `/api/v1/tracking/routes/{allocation_id}/{leg_id}`. A comparação reúne GPS de todas as sessões do mesmo veículo/trecho, inclusive transferências, e os registros de embarque/desembarque. Até dez mil amostras e quinhentos grupos de eventos por consulta. O roteiro preservado e as posições acompanham a limpeza operacional de noventa dias do worker. RLS obrigatória, inclusive para o papel da plataforma.

A configuração de chave web fica junto à geocodificação no Superadmin, separada da chave privada de backend. Ambas são criptografadas em repouso. O endpoint `/api/v1/tracking/routes/map` fornece apenas a chave web ao administrador de empresa autorizado. Nunca fornece a chave de backend. A chave web deve ter restrição de HTTP referrer para o domínio do app e de APIs para Maps JavaScript API e Geocoding API.

O botão de carregar o mapa informa compartilhamento de endereços/posições e consumo no Google. A visualização localiza até cem pontos planejados; consultas repetidas dentro da mesma visualização são reaproveitadas em memória. O consumo é próprio do Google, fora do contador de geocodificação do servidor. Listas continuam disponíveis sem chave ou quando houver falha externa. Pontos ambíguos ou sem endereço não geram ligações inventadas. Azul representa a sequência planejada; verde, amostras GPS. Não há reconstrução pelas ruas, cálculo de quilometragem real, classificação ou alertas de desvio.

O SDK Google executa em iframe opaco, sem acesso ao DOM/sessão do aplicativo. A permissão `unsafe-eval` necessária à política desse SDK fica restrita ao documento do mapa; a CSP principal continua sem ela e sem scripts inline. O iframe recebe dados somente de sua janela pai e não grava coordenadas em armazenamento persistente. A política de referência por origem fica restrita ao documento do mapa para permitir a restrição da chave web. O mapa geral OSM permanece separado e não recebe resultados Google.

## Atualizar e validar

Use `scripts/update_vps.sh` na instalação existente para aplicar a migração. Depois publique `artifacts/mobile/nexus-rotafy-1.11.0.apk` no Superadmin e instale sobre o aplicativo anterior. Configure a chave web; não copie a chave de backend. Validar no ambiente real o recebimento da mensagem de download, a antecedência com a opção marcada/desmarcada e a comparação em um novo trecho com GPS e embarques. Os testes automatizados usam provedores simulados, sem chamadas pagas ao Google ou mensagens reais.

## Mapa da frota em tela inteira

Menu separado de Rastreamento, exclusivo do administrador e condicionado ao módulo tracking. Ocupa a área de trabalho e oferece expansão nativa quando suportada. Consulta `/api/v1/tracking/vehicles` a cada quinze segundos; a coleta do APK permanece a cada minuto. Mostra placa, veículo, viagem, precisão e horário do GPS; amostras acima de dois minutos são sinalizadas. Atualizações preservam zoom e enquadramento. Veículos sem posição ficam contabilizados como aguardando GPS. A função usa GPS próprio sobre OSM, sem resultados Google ou chave web. Configurações, histórico e comparação permanecem em Rastreamento.
