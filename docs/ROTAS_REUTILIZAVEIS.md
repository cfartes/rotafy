# Rotas reutilizáveis

## Cadastro

Administradores e atendentes da empresa acessam **Rotas** no menu lateral.

Cada Rota contém nome, somente ida ou ida e volta, cidades selecionadas por UF,
endereços de saída/chegada e paradas ordenadas para embarque, desembarque ou ambos.
As paradas não exigem data ou horário individual. Na ida e volta, a volta inverte
as cidades da ida; o botão **Gerar volta invertendo a ida** sugere endereços e
paradas invertidas, trocando embarque por desembarque. A sugestão pode ser editada.

Por sentido, informe **Deslocamento estimado (minutos)** e **Tempo adicional total
nas paradas (minutos)**. Por exemplo: 60 + 20 = 80 minutos previstos. Não existe
consulta à API do Google nesta versão. Os links continuam abrindo Google Maps.

É possível editar, duplicar e desativar uma Rota. Desativá-la impede novas
seleções, preservando as viagens que já a utilizam. O catálogo pertence à empresa
e não consome viagens da franquia mensal.

## Agendar uma viagem

Em **Viagens → Nova viagem**, selecione a Rota e informe as datas e horários de
saída da ida e, quando aplicável, da volta, no fuso de São Paulo. A chegada prevista
é calculada pela soma dos tempos cadastrados na Rota. O servidor valida esse
cálculo, a geografia e as paradas, além de verificar conflitos da frota e da equipe.

Preço, pacote opcional, veículos, motoristas e guias continuam na Viagem. Cada
veículo pode atender uma seleção diferente das paradas, respeitando a ordem da
Rota e os pontos usados nas reservas. Guia permanece opcional.

Uma viagem consome uma unidade da franquia, independentemente da quantidade de
veículos. O catálogo não cria automaticamente viagens recorrentes: reutilize a
Rota em novas datas ou use **Duplicar viagem**.

## Preservação do histórico

Nos detalhes da viagem, administradores e atendentes podem usar **Atualizar com a versão atual da Rota**. A ação exige confirmação e só é permitida enquanto a viagem estiver agendada e sem eventos de embarque. Nas saídas de pacote, atualiza todas as Rotas referenciadas pelos deslocamentos, preservando o modelo comercial, os destinos, atividades, preço e consumo da franquia.

A atualização copia os endereços, nomes, paradas e durações atuais. Mantém as partidas e recalcula as chegadas previstas, verificando sobreposição entre deslocamentos e conflitos de veículos/equipe. Com reservas, preserva a quantidade, finalidade e posições das paradas, além dos IDs dos trechos, paradas, alocações e bilhetes. Uma reordenação reconhecida ou mudança incompatível bloqueia a operação. Para mudar cidades ou formato do percurso, crie outra viagem. Rotas inativas não são aplicadas.

As versões e a auditoria registram a atualização explícita. Se alguma Rota ou horário for incompatível, nenhuma alteração é aplicada. Após atualizar, prepare novamente os manifestos offline nos dispositivos da equipe. O endpoint é `POST /api/v1/trips/{trip_id}/refresh-routes`, com `expected_version` da viagem; respeita permissões, isolamento por empresa e controle de concorrência. Esta funcionalidade não exige migração nem novo APK.

A Viagem salva a identidade, versão e uma cópia do percurso da Rota. Alterar o
catálogo não altera automaticamente viagens agendadas, reservas ou bilhetes.
Na edição de uma viagem vinculada, os horários podem ser ajustados usando a
duração da cópia original; a seleção da Rota fica protegida. Para outro percurso,
cadastre uma nova viagem. A edição continua restrita a viagens agendadas sem
embarques e às regras que preservam reservas existentes.

Viagens anteriores à atualização continuam disponíveis. Em seus detalhes, use
**Salvar percurso como Rota** para aproveitar o cadastro. A duração inicial é
copiada do intervalo previsto de cada trecho, com tempo adicional zero; revise-a
no catálogo. Datas e horários individuais das paradas não são copiados. Viagens
antigas sem cidades selecionadas precisam completar a geografia antes de converter.
Ao editar uma viagem antiga, as paradas passam a não ter horário individual;
viagens históricas que não forem editadas preservam os horários anteriores.

CPF em viagens interestaduais, capacidade por trecho, reservas de famílias,
bilhetes QR Code, operação offline, registro de chegada e coordenadas GPS mantêm
as regras existentes. Bilhetes com embarque em parada sem horário exibem
**Conforme orientação da agência**. O APK 1.4.0 continua compatível: não é
necessário reinstalar o aplicativo por causa desta alteração.

## Banco e publicação

Migração **0016_route_catalog**, após **0015_vehicle_journeys**:

- Cria `route_templates`, com isolamento por empresa e FORCE RLS.
- Acrescenta `trips.route_id` e `trips.route_snapshot`, com chave estrangeira
  composta por empresa e Rota.
- Permite `trip_stops.scheduled_at` nulo, preservando os valores antigos.

Não remove tabelas, empresas, reservas ou viagens. Atualize na VPS pelo fluxo
normal, que realiza backup e aplica as migrações:

```bash
cd /opt/nexus-rotafy
bash scripts/install_vps.sh
```

APIs autenticadas: `GET/POST /api/v1/routes` e
`PATCH /api/v1/routes/{id}` (edição exige `expected_version`). Os comandos de
Viagem recebem `route_id` e `route_version`, além dos dados operacionais. Clientes
antigos da API continuam podendo enviar percursos explícitos; o formulário web
exige Rota para novas viagens.
