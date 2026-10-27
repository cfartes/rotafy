# Plano — realocação após cancelamento de viagem

Status: implementado em 26/10/2026. Consulte REALOCACAO_APOS_CANCELAMENTO.md e o capítulo 36 do manual.

## Decisões confirmadas

- Notificar administradores e atendentes da própria empresa quando uma viagem cancelada tiver reservas afetadas.
- Sugerir outras viagens futuras ainda não iniciadas, anteriores ou posteriores à data original, ordenadas pela menor diferença de dia e hora em relação à saída originalmente contratada.
- Aproveitar valores já pagos como crédito e apresentar diferenças para revisão humana. Não cobrar nem reembolsar automaticamente.
- Não realocar passageiros automaticamente: a equipe escolhe a alternativa e confirma a concordância do responsável pela reserva.

## Situação atual verificada

`operations.change_status` cancela as reservas ativas por `reservations.cancel_trip_reservations`, registra auditoria e devolve o consumo da viagem conforme a regra existente. O cancelamento pode enfileirar mensagens aos passageiros. Passageiros a bordo impedem cancelar a viagem.

`reservations.reallocate` somente altera o veículo dentro da mesma viagem; não transfere uma reserva cancelada para outra viagem. A reserva precisa de novos vínculos de trechos, passageiros e bilhetes, preservando os registros originais.

O pagamento operacional da reserva usa `is_paid`, `paid_at` e `total_cents`; não deve ser confundido com a cobrança da assinatura Rotafy. Pagamentos parciais externos não podem ser inferidos desse indicador.

## Fluxo proposto

1. Antes de confirmar o cancelamento, mostrar quantidade de famílias e passageiros afetados, separando reservas confirmadas de bloqueios provisórios ainda válidos. Bloqueios expirados e reservas canceladas anteriormente não entram nas pendências.
2. Confirmado o cancelamento, manter a viagem e as reservas originais canceladas. Gravar as pendências de atendimento na mesma transação do cancelamento. Uma falha posterior de realocação não deve reabrir a viagem cancelada.
3. Exibir um aviso persistente, por exemplo: “Viagem cancelada: 4 famílias / 11 passageiros aguardam atendimento”. Disponibilizar em Visão geral e Viagens para administradores e atendentes, com botão **Revisar passageiros e alternativas**.
4. Abrir uma lista das famílias afetadas com responsável, contato, passageiros, situação original, valor e pagamento. A unidade de realocação é a reserva familiar inteira, sem divisão automática entre veículos.
5. Ao selecionar a família, apresentar as melhores alternativas compatíveis, com data/hora, diferença em relação à original, destino, trechos, veículo, lugares disponíveis, preço e ajuste financeiro.
6. O atendente seleciona a alternativa, confere os embarques da ida e da volta, registra a concordância do cliente e confirma a transferência.
7. Criar uma nova reserva vinculada à original, copiar os dados necessários da família, registrar o crédito aplicado e gerar novos bilhetes. Preservar o cancelamento, documentos de pagamento e histórico da reserva anterior.
8. Encerrar a pendência operacional; manter eventuais ajustes financeiros identificados e rastreáveis. Permitir **Encerrar sem realocar**, com motivo, quando o cliente não aceitar as alternativas.

O aviso só deixa de contar uma família quando houver realocação concluída ou encerramento com motivo. Fechar a tela não resolve a pendência nem a oculta dos demais atendentes.

## Hierarquia de sugestões

Aplicar os filtros de compatibilidade antes da ordenação por horário:

- Mesma empresa, acesso autorizado e módulos/restrições operacionais vigentes.
- Viagens ainda não iniciadas, com saída futura. As classificações visuais Abertas e Agendadas podem ser elegíveis; viagens em andamento, concluídas e canceladas não são.
- Origem, destino, sentido e trechos compatíveis com o que foi contratado. Proximidade de horário não torna um destino diferente equivalente.
- Ida e retorno precisam ser compatíveis. Pacotes com vários destinos exigem correspondência do itinerário contratado; não sugerir troca parcial como se fosse equivalente ao pacote inteiro.
- Capacidade suficiente para a família em cada segmento, respeitando as regras de contagem de lugares e atribuição dos veículos existentes.
- Hotéis e pontos personalizados precisam de conferência logística. Mapear as paradas para os novos trechos, sem copiar seus índices antigos. Rever endereço e horário de cada embarque.

Ordenação: menor diferença absoluta entre as saídas original e alternativa; no empate, preferir a saída posterior à original e depois data/hora e identificador para estabilidade. Mostrar claramente quando a proposta antecipa ou posterga a viagem. Apresentar inicialmente as cinco melhores opções, permitindo consultar as demais sem um novo campo de configuração.

Viagens parcialmente realizadas ficam sinalizadas para tratamento manual: não copiar passageiros/etapas já atendidos, não reaproveitar o valor integral como se nada tivesse sido consumido e não transferir automaticamente o pacote restante.

## Valores e pagamento

Mostrar na confirmação: valor original, valor reconhecido como pago, crédito aplicado, novo preço, diferença a pagar e eventual saldo a revisar.

- Reserva original marcada como PAGO: usar seu valor registrado como referência de crédito, sujeito à conferência do atendente.
- Reserva sem pagamento confirmado: não gerar crédito automaticamente.
- Pagamento parcial feito fora do sistema ou viagem parcialmente consumida: exigir revisão, sem presumir o valor recebido/disponível.
- Alternativa mais cara: aplicar o crédito e deixar a diferença em aberto.
- Alternativa mais barata: registrar a diferença a favor do cliente para ajuste manual, sem executar estorno ou criar uma carteira genérica.
- Mesmo valor: a aplicação do crédito pode quitar a nova reserva, identificada como pagamento por crédito de transferência.

O lançamento deve vincular origem e destino, impedir reaproveitar o mesmo crédito duas vezes e manter a receita recebida originalmente sem duplicá-la nos relatórios. Atualizar consultas financeiras, indicação de pagamento, valor pendente e mensagem ao passageiro para distinguir crédito aplicado de novo recebimento. Essa melhoria não muda o plano SaaS ou as cobranças da assinatura.

## Comunicação e bilhetes

Manter o aviso de cancelamento existente. A confirmação da nova viagem somente ocorre depois da decisão da equipe e concordância do cliente. Usar as filas já existentes e informar novas datas, trechos, endereços e links do Maps.

Os bilhetes antigos continuam inválidos para embarque porque a reserva original permanece cancelada. Emitir novos bilhetes vinculados à nova viagem. Não reutilizar tokens ou alterar retroativamente o histórico dos embarques. Não emitir uma mensagem de novo pagamento recebido quando apenas houver aplicação de crédito.

O servidor rejeita o bilhete da reserva cancelada. Um aparelho offline só descobre o cancelamento ao conectar; registros locais anteriores continuam sujeitos à validação na sincronização e não devem ser apagados automaticamente. Orientar motorista/guia a sincronizar e preparar o manifesto da nova viagem.

## Implementação técnica

1. **Banco:** migração incremental para registrar pendências/vínculos de realocação, estados, valores aplicados, responsável e datas; campos de crédito da nova reserva quando necessários. UUIDs, referências com `company_id`, índices, RLS e unicidade da transferência de origem. Sem recriar o banco ou apagar dados.
2. **Backend:** integrar o registro das pendências ao cancelamento; disponibilizar consulta de casos e sugestões; criar comando de transferência e encerramento. Reutilizar disponibilidade, criação de reserva, emissão de bilhetes, filas e auditoria existentes, sem remover suas validações.
3. **Concorrência:** revalidar preço, horários, status e capacidade na confirmação, sob os bloqueios transacionais da empresa. Usar chave de operação e unicidade para que duplo clique, retry ou dois atendentes não criem transferências/créditos duplicados. Se perderem-se as vagas, preservar a pendência e atualizar as opções.
4. **Interface:** aviso compartilhado e tela/modal de resolução dentro de Viagens. Manter o fluxo curto: selecionar família, escolher alternativa, revisar embarques/valores, confirmar. Sem novo menu lateral ou configuração para ativar a proteção.
5. **Financeiro e atendimento:** ajustar projeções e mensagens necessárias para refletir o crédito e saldos sem dupla contabilização. Registrar auditoria de cancelamento, decisão, realocação e resolução financeira.
6. **Documentação:** atualizar ajuda e manuais somente após a implementação, descrevendo os controles efetivamente disponíveis. Este plano é técnico e não será exposto nos materiais comerciais.

## Critérios de aceite

- Cancelar uma viagem sem reservas não cria aviso vazio.
- Cancelar com reservas confirmadas/provisórias válidas cria uma pendência por família, visível aos perfis autorizados da empresa.
- Sugestões respeitam proximidade de data/hora, compatibilidade e capacidade, inclusive trechos de retorno e pacotes.
- Outra empresa e perfis não autorizados não consultam ou executam transferências.
- A família inteira é preservada; trechos, hotel/endereço e veículo são revistos para a nova viagem.
- Valores pagos não desaparecem, não são duplicados e não são creditados duas vezes. Diferenças positivas, negativas e nulas são cobertas por testes.
- Tentativas simultâneas, mudança de preço e perda da última vaga falham de forma segura, sem reservar parcialmente ou perder a pendência.
- Bilhete antigo não embarca na nova viagem; o novo bilhete funciona somente nos trechos e veículos corretos.
- Uma viagem parcialmente atendida exige revisão e não concede crédito integral automaticamente.
- Cancelamento e filas existentes continuam funcionando; não são enviados pagamentos fictícios ou confirmações antes da conclusão da transferência.

Implementação concluída com testes usando dados e transportes simulados. Não houve envio real nem alteração na VPS durante o desenvolvimento.
