# Viagens, finalização e venda de bilhetes

## Consulta e filtros

Em **Viagens**, o filtro **Situação da viagem** oferece Todas, Abertas, Agendadas, Em andamento, Fechadas/concluídas e Canceladas. Viagens ainda não iniciadas ficam Abertas quando faltam até 48 horas para a saída e Agendadas quando faltam mais de 48 horas. O limite exato de 48 horas já é considerado Aberta. Se o horário passou sem início registrado, a viagem continua Aberta. Em andamento, concluídas e canceladas preservam suas situações próprias. A classificação é atualizada a cada 30 segundos e ao retornar à janela; não altera as regras de venda ou inicia a viagem automaticamente. O contador informa quantas viagens correspondem ao filtro.

## Detalhes e chegada

**Detalhes → Finalização e chegadas** mostra o encerramento no sistema e o responsável, obtidos do histórico de auditoria existente. Para cada veículo/trecho, mostra saída e chegada registradas pelo app, responsável, latitude/longitude, precisão, horário da captura e link de consulta no Google Maps. Sem GPS, mostra o motivo enviado pelo app. Sem registro de chegada, informa sua ausência, mesmo que a viagem tenha sido encerrada administrativamente. O horário de encerramento administrativo não é apresentado como chegada real.

O modal foi ampliado de 580 para 960 pixels em telas grandes, com cartões distribuídos em colunas e adaptação ao celular. Em viagens concluídas ou canceladas, os controles de navegação da rota, embarque e **Reservas e lugares** ficam desabilitados. Trechos já concluídos de uma viagem ainda aberta também não permitem navegar/abrir embarque. O itinerário permanece legível. O link para o ponto GPS da chegada é uma consulta histórica e continua disponível. Duplicar viagem continua permitido, criando uma nova viagem.

## Vender bilhete

Admin e atendente têm o menu lateral **Vender bilhete**. A busca por nome/destino e o seletor oferecem somente viagens agendadas com saída futura. Ao selecionar e clicar em Vender bilhete, abre o formulário existente de reserva familiar, com passageiros, telefone, CPF/exceções, trechos, alocação conforme capacidade e sugestão do veículo. A disponibilidade e o status são validados novamente pela API antes de salvar.

Depois de salvar, a reserva fica disponível no atendimento da viagem escolhida, incluindo emissão/consulta dos bilhetes e a marcação manual PAGO existentes. **Voltar à venda de bilhetes** retorna ao seletor. A venda não depende de abrir o cadastro de viagens. Motorista/guia não recebem este menu. A consulta do status também é renovada enquanto o atendimento está aberto.

## Atualização e validação

Atualize API e painel na VPS: `cd /opt/nexus-rotafy` e `bash scripts/install_vps.sh`. Não há migração nova nem alteração do APK. O banco e os registros existentes são preservados.

Validação: 182 testes da API, build de produção do painel e seis testes Chromium da interface. Os testes de interface usam respostas controladas para filtros, fechamento, GPS, tela pequena, admin/atendente e reserva na viagem selecionada; a suíte da API valida as operações reais e o isolamento por empresa. Capturas em `docs/screenshots/finalizacao-viagem-desktop.png` e `docs/screenshots/finalizacao-viagem-mobile.png`.
