# Pacotes completos com vários destinos

## Regras comerciais

- A viagem avulsa continua selecionando uma Rota, com somente ida ou ida e volta.
- O pacote com roteiro reúne destinos comerciais, deslocamentos e atividades distribuídos em vários dias. A venda é sempre do pacote completo, com retorno incluído. Para vender outro roteiro ou uma parte dele, cadastre outro pacote.
- O preço por passageiro é o preço do pacote completo. O pagamento continua sendo marcado manualmente como PAGO, sem integração financeira.
- O cadastro do modelo não consome franquia. Ao criar uma saída, o consumo é a quantidade de destinos comerciais: quatro destinos consomem quatro viagens. Retorno, paradas, passeios e transferências locais não acrescentam unidades.
- Cancelar a saída devolve todas as unidades ao período do lançamento original. Repetir uma requisição não duplica o consumo ou o estorno.

## Cadastro e agendamento

1. Cadastre as Rotas necessárias, incluindo os sentidos de retorno, endereços, paradas e duração aproximada manual. Não há consulta à API Google.
2. Abra **Frota, pacotes e viagens → Pacotes → Novo pacote** e marque **Pacote com roteiro de vários destinos**.
3. Informe os destinos comerciais, em ordem, com suas cidades/UFs. Configure cada deslocamento com dia relativo, horário, Rota/sentido e finalidade. Cada destino comercial precisa aparecer exatamente uma vez. O primeiro deslocamento inicia no dia 1 e o último retorna à cidade de origem, sem destino comercial adicional.
4. Inclua atividades e dias livres, se necessário. São informações do programa, sem consumo adicional.
5. Em **Nova viagem**, selecione o pacote e a data inicial. O sistema gera todos os deslocamentos, paradas e chegadas previstas. Os horários podem ser ajustados sem sobreposição.
6. Aloque veículo, motorista e guias opcionais, indicando quais deslocamentos cada equipe atende. Pode haver vários veículos no mesmo deslocamento ou troca de veículo/equipe durante o roteiro. Um veículo ou profissional não pode atender duas alocações no mesmo deslocamento.

Limites desta entrega: até 20 destinos comerciais, 60 deslocamentos, 60 dias relativos e 120 atividades por modelo.

O formulário separa destinos, deslocamentos e atividades, destacando cada destino/deslocamento com borda verde petróleo. Um guia explica a montagem e uma lista identifica destinos sem chegada associada, chegadas duplicadas, ordem incorreta e retorno ausente antes de salvar. As verificações do servidor continuam validando cidades, continuidade das Rotas e duração dos deslocamentos.

Não são necessários CEP nem datas fixas no modelo do pacote. Os dias relativos podem ter intervalos: primeiro destino no dia 1, segundo no dia 4 e retorno no dia 7. As datas reais são calculadas ao agendar a viagem. Cada chegada comercial deve ser associada ao destino correspondente no campo **Finalidade do deslocamento**; passeios, transferências e retorno não acrescentam destinos à franquia.

## Reservas e operação

Toda reserva precisa incluir os deslocamentos do pacote. A disponibilidade é verificada em cada trecho entre paradas e em cada veículo; o sistema sugere uma combinação que mantém a família inteira no mesmo veículo em cada deslocamento. É possível trocar de veículo entre os deslocamentos. Sem capacidade para a família em todos eles, a venda não é permitida.

As reservas mostram o veículo de cada deslocamento. Manifestos, bilhetes QR, embarques, relatórios e registros de chegada usam a alocação de cada etapa. A regra de CPF em viagens interestaduais considera o roteiro completo.

Motorista e guia veem somente os deslocamentos atribuídos à sua equipe. A agenda Android considera as próximas etapas dos sete dias seguintes, mesmo que o pacote já tenha começado. A etapa seguinte depende da conclusão das anteriores; a viagem completa é encerrada após todos os veículos concluírem o retorno.

O modelo é versionado. Cada saída guarda uma cópia do roteiro: editar Rotas ou o modelo do pacote não altera viagens já criadas. A edição de uma saída mantém o roteiro vinculado e sua quantidade de destinos; para outro roteiro, crie outra saída. Após iniciar o pacote, a realocação da reserva completa fica bloqueada para preservar o histórico de etapas já executadas.

## Atualização e validação

A migração **0017_package_itineraries** acrescenta roteiro e versão ao pacote, cópia do roteiro e unidades à viagem, seleção de deslocamentos por equipe e alocação por trecho da reserva. Reservas antigas recebem a alocação já existente; viagens antigas mantêm consumo de uma unidade. Não é necessário reinstalar o banco.

Atualize o backend/web com o instalador existente na VPS e depois instale o APK Android **1.5.0 (7)** sobre a versão anterior. A assinatura permanece a mesma. Não foi gerada versão iOS.

```bash
cd /opt/nexus-rotafy
bash scripts/install_vps.sh
```

A atualização ainda precisa de homologação do roteiro com troca de veículos em aparelho real. Os testes automatizados cobrem franquia, reserva completa, isolamento entre empresas, versões, manifestos, QR, conclusão após retorno e agenda Android.
