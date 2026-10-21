# Rastreamento de veículos e avisos de embarque

## Regras definidas

- Localização do celular responsável pelo veículo, associada à empresa, viagem, veículo alocado e deslocamento.
- Intervalo nominal de coleta de cinco minutos, com indicação visível de horário da coleta e do recebimento. O sistema não apresenta isso como rastreamento em tempo real.
- Um celular responsável por veículo em operação, com transferência explícita para outro motorista/guia autorizado. Uma transferência invalida a sessão anterior.
- Rastreamento limitado à operação do trecho, encerrado na chegada, cancelamento, desativação da empresa ou desativação pelo administrador.
- Administrador da empresa pode habilitar/desabilitar o rastreamento e configurar o raio de proximidade, inicialmente cinco quilômetros.
- Avisos por WhatsApp ao telefone da reserva, uma vez por família, veículo e deslocamento, respeitando remanejamentos, cancelamentos e passageiros já embarcados.
- Lembrete de saída quinze minutos antes do horário programado de cada deslocamento, incluindo retorno e todos os deslocamentos dos pacotes. Não depende de o motorista ter iniciado a viagem.
- Lembrete de saída e proximidade são controles separados: desligar a coleta não impede, por si só, o lembrete por horário. O administrador pode desligar ambos.

## Localização dos embarques

Os endereços e nomes de hotéis atuais não possuem latitude/longitude. O aviso de proximidade requer a confirmação das coordenadas do embarque da reserva, ou do ponto de rota usado por ela. Não se usa o centro da cidade como substituto silencioso.

Definido: confirmação por mapa sem API paga, aproveitando coordenadas explícitas de links Maps. Pontos sem coordenadas continuam aptos ao lembrete de saída, mas ficam identificados como não preparados para proximidade.

## Implementação executada (consulte RASTREAMENTO_E_AVISOS.md)

1. Migração incremental para preferências da empresa, sessões de rastreamento, posições e registros de avisos; políticas de isolamento por empresa. Não recriar banco.
2. API autenticada para assumir/transferir/encerrar o rastreamento, receber posições e consultar o histórico. Validar alocação do colaborador e exclusividade do aparelho; impedir coleta após encerramento ou desativação. Coordenadas, precisão e datas precisam de validação.
3. APK com serviço de localização em primeiro plano, iniciado por ação visível durante a operação e acompanhado por notificação persistente. Parar ao concluir o trecho e respeitar a desativação remota ao conseguir contato com o backend. Não coletar no intervalo entre passeios.
4. Fila local para posições coletadas sem internet, preservando o horário original e evitando duplicação. Posições antigas podem compor histórico, mas nunca disparar avisos de proximidade atrasados.
5. Tela do administrador com configuração, veículos em viagem, mapa, trilha dos pontos coletados e horário da última posição. Sinalizar posição desatualizada, sem apresentar interpolação como trajeto realmente percorrido.
6. Coordenadas confirmadas dos locais de embarque, vinculadas ao local real da reserva ou ponto da rota; alterações de endereço invalidam a confirmação anterior.
7. Processamento de lembretes por horário e proximidade, integrado à fila existente de WhatsApp. Usar chaves de deduplicação persistentes e validade curta. Antes do envio, revalidar horário, trecho, veículo, reserva e embarque; não enviar alertas vencidos após reconexão.
8. Testes de isolamento, desativação, troca de aparelho, modo offline, precisão, idade da posição, ida/volta, pacotes, cancelamento e duplicidade. Gerar novo APK assinado e documentação; migração via atualização normal da VPS.

## Limites operacionais

Coleta de cinco em cinco minutos é uma meta de intervalo. GPS, rede, permissões, otimização de bateria, encerramento forçado do aplicativo e disponibilidade do provedor de WhatsApp podem causar atrasos ou interrupções. O administrador precisa ver quando os dados estão atrasados. Sem conexão, não há alerta imediato ao passageiro.

O raio é distância geográfica aproximada, não distância rodoviária nem previsão de chegada. Com cinco minutos entre amostras, o veículo pode atravessar um raio inteiro entre coletas. O sistema não deve prometer aviso garantido antes da chegada, sobretudo em rodovias. O texto do alerta deve comunicar proximidade aproximada e não um horário calculado.

Um celular rastreia o próprio aparelho; não prova a localização física do veículo se o responsável sair dele. O recurso exige orientação e permissão de localização do colaborador, com coleta restrita à viagem, acesso limitado à própria empresa e política explícita de retenção do histórico.

## Referências Android

- https://developer.android.com/develop/sensors-and-location/location/permissions
- https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start

O serviço de localização deve declarar o tipo e as permissões exigidas pelo Android. Não tratar um temporizador Dart na tela como solução de rastreamento com o aparelho bloqueado.
