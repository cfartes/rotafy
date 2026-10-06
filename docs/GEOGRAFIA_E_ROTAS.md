# Cidades, documentos e rotas por veículo

Implementado em 06/10/2026 no ambiente local.

## Cadastro da viagem

Cada trecho exige UF e cidade de origem e destino. Selecionar a UF carrega suas cidades; o filtro ajuda a localizar o município. A lista local contém 27 UFs e 5.571 municípios, obtidos da [API oficial do IBGE](https://servicodados.ibge.gov.br/api/v1/localidades/municipios). Não depende de consultas externas durante o uso. A API valida os identificadores e determina a UF e o nome canônico da cidade.

Origem, destino e paradas aceitam endereço manual. **Conferir local no Google Maps** abre uma pesquisa externa pelo endereço informado. Não há pesquisa integrada, mapa embutido ou chave Google Cloud.

Ida e volta exigem cidades invertidas. Na criação, o botão de inversão copia endereços e inverte a ordem das paradas; os horários da volta precisam ser informados. Na edição, **Inverter origem e destino da volta** copia apenas cidades e endereços dos extremos, preservando as paradas e os horários já cadastrados no retorno.

## CPF dos passageiros

Se qualquer trecho tiver origem e destino em UFs diferentes, todos os passageiros precisam de CPF válido, inclusive aqueles que embarcam e desembarcam dentro de uma única UF.

- **Estrangeiro:** permite cadastro sem CPF.
- **Menor de 5 anos:** permite cadastro sem CPF e exige nascimento. A criança deve ter menos de cinco anos na data de todos os trechos, inclusive na volta.
- CPF informado sempre é validado, mesmo para passageiros com exceção marcada.

As regras valem no cadastro manual, edição, página pública, integração externa, confirmação e importação. Uma edição que torne a viagem interestadual exige corrigir antes os documentos dos passageiros ativos. Viagens antigas são preservadas; antes de novas reservas ou publicação, devem receber cidades e UFs pelo editor.

O modelo CSV/XLSX acrescenta `estrangeiro,menor_5_anos,nascimento`. Flags aceitam `sim`/`nao`; nascimento usa `AAAA-MM-DD`. Arquivos antigos com seis colunas continuam aceitos, sujeitos à obrigatoriedade de CPF da viagem.

## Rota por veículo

As paradas cadastradas no trecho formam o itinerário geral. Ao alocar veículos, marque quais paradas cada um atende na ida e na volta. A ordem permanece a da agência; origem e destino sempre são atendidos. Por padrão, todos os veículos atendem todas as paradas.

A disponibilidade só sugere veículos que atendam embarque e desembarque escolhidos e tenham lugares para a família inteira em todos os segmentos. A edição não permite retirar um ponto utilizado por uma reserva ativa daquele veículo.

Antes de eventos de embarque, viagens com reservas permitem editar nomes, endereços e horários e acrescentar paradas ao fim da lista, antes do destino final. Os pontos intermediários existentes mantêm suas posições e finalidade. Reservas que desembarcavam no destino continuam vinculadas ao destino, sem serem desviadas para a nova parada. Bilhetes e valores são preservados; versões de reservas e manifestos são atualizadas para evitar alterações com cópias antigas. Remoção de paradas existentes ou mudança de finalidade permanece bloqueada quando há reservas.

Veículos, motoristas e guias podem participar de outras viagens nos intervalos livres entre trechos. Sobreposição de horários continua bloqueada. Muitos veículos na mesma viagem comercial continuam consumindo apenas uma unidade da franquia.

## Motorista e guia

Em **Minhas viagens → Detalhes**, a rota mostra apenas as alocações atribuídas ao usuário, com pontos e horários. **Abrir rota no Google Maps** abre o itinerário; **Navegar até este ponto** abre um destino específico, usando a localização atual disponível no aplicativo.

Para rotas extensas, o sistema fornece etapas com até três paradas intermediárias por link, preservando a sequência para uso no celular. O motorista abre as etapas sucessivamente. Google Maps calcula o percurso entre os endereços; a agência define a sequência de pontos. A navegação usa o aplicativo ou navegador do motorista. Não há rastreamento nesta entrega.

API: `GET /api/v1/locations/states`, `GET /api/v1/locations/cities/{uf}` e `GET /api/v1/trips/{id}/vehicles/{allocation_id}/route`. A rota respeita empresa e atribuição de equipe.

Migração: `0013_geographic_routes`, preservando dados existentes.
