# Frota, pacotes e viagens comerciais

Implementado na etapa 3, em ambiente local.

## Uso

1. A Nexus configura um plano e vincula uma assinatura ativa à empresa.
2. O administrador cadastra motoristas e guias em **Equipe**. As contas são independentes por empresa.
3. Administradores e atendentes acessam **Frota, pacotes e viagens** para cadastrar veículos e pacotes.
4. Em **Viagens**, criam uma viagem avulsa ou a partir de um pacote, informando os trechos, horários, paradas e veículos com seus motoristas/guias.
5. Em **Detalhes**, consultam o itinerário e a equipe, iniciam, concluem, cancelam ou duplicam a viagem.

Guias e motoristas consultam **Minhas viagens**, com acesso somente às viagens às quais estão atribuídos. Não podem criar viagens nem alterar sua situação.

## Regras

- Placas brasileiras tradicionais e Mercosul são normalizadas, sem hífen. Quantidade de lugares entre 1 e 200; sem numeração individual de assentos.
- Cadastros de veículos e pacotes não consomem franquia. Arquivar impede novas utilizações e preserva viagens existentes.
- Preços de pacote e viagem são valores por passageiro, em centavos. A viagem mantém seu próprio valor, sem alterações retroativas quando o pacote muda.
- Ida e volta usam dois trechos em ordem temporal, com origem e destino invertidos. Viagens de trecho único usam somente um trecho.
- Paradas de embarque, desembarque ou ambos são específicas de cada trecho. Seus horários devem estar em ordem e dentro do trecho.
- Cada veículo exige um motorista ativo; pode ter vários guias ativos. Nenhum veículo ou integrante da equipe se repete na mesma viagem.
- A capacidade é copiada do veículo para a viagem. Alterações posteriores na frota não alteram a capacidade histórica daquela viagem.
- Veículos e equipe ficam reservados durante os horários de cada trecho. Podem fazer outras viagens no intervalo livre entre ida e volta. Intervalos adjacentes são permitidos; intervalos sobrepostos são bloqueados.
- Viagens agendadas podem iniciar ou cancelar. Viagens em andamento podem concluir ou cancelar. Concluídas e canceladas preservam seu estado final.
- Duplicar prepara um novo formulário com rota, paradas e equipe, mas exige novos horários. Ao salvar, cria outro identificador e outro consumo de franquia.
- A edição de itinerário/equipe está disponível antes de eventos de embarque, preservando reservas e consumo. Cidades, documentos e paradas por veículo seguem [GEOGRAFIA_E_ROTAS.md](GEOGRAFIA_E_ROTAS.md).

## Franquia e integridade

Uma viagem comercial, independentemente de quantos veículos ou trechos tenha, consome uma unidade no ciclo mensal em que é criada. Sua data futura de execução não muda o ciclo do consumo.

A criação dos trechos, paradas e atribuições e o lançamento de consumo ocorrem na mesma transação. Sem assinatura válida, sem veículo disponível ou com dados inválidos, a operação é revertida integralmente.

A chave `operation_key` permite repetir a mesma criação sem duplicar viagem nem consumo. Reutilizá-la com dados diferentes retorna conflito. Repetir uma criação posteriormente cancelada retorna a viagem cancelada, sem reativá-la.

Cancelar grava o estorno na mesma transação da mudança de situação, sempre no período do consumo original. Repetir o cancelamento não gera outro estorno. Concluir mantém o consumo.

Os comandos são serializados por empresa para impedir conflitos concorrentes de agenda. Os novos cadastros usam RLS forçado, inclusive na conexão de comandos, com contexto de empresa definido a partir da sessão. Vínculos compostos impedem associar veículo, pacote, equipe ou consumo de outra empresa. Empresas não têm acesso direto de gravação ao livro de consumo.

## API

- `GET/POST /api/v1/vehicles`; `PUT /api/v1/vehicles/{id}`.
- `GET/POST /api/v1/packages`; `PUT /api/v1/packages/{id}`.
- `GET /api/v1/operations/crew` para equipe elegível.
- `GET/POST /api/v1/trips`; `GET /api/v1/trips/{id}`.
- `PATCH /api/v1/trips/{id}/status` para iniciar, concluir ou cancelar.

Criação de viagem exige `operation_key` UUID. Datas da API incluem fuso explícito; a interface apresenta e recebe horários operacionais de São Paulo. Detalhes dos corpos e validações em `http://localhost:8018/docs`.

## Próximas etapas

Reservas familiares, ocupação real e sugestão de veículo estão disponíveis em **Detalhes → Reservas e lugares**. A lista de viagens exibe capacidade total; a tela de reservas mostra disponibilidade por itinerário/segmento e considera as paradas atendidas por cada veículo. Regras em [RESERVAS_E_DISPONIBILIDADE.md](RESERVAS_E_DISPONIBILIDADE.md). Página pública e marcação manual PAGO também estão disponíveis. Sem pagamento integrado, rastreamento ou WhatsApp.
