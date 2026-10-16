# Nexus Rotafy — documentação consolidada do projeto

**Data da consolidação:** 16/10/2026.  
**Produto:** Nexus Rotafy.  
**Responsável pela plataforma:** Nexus.  
**Painel:** https://rotafy.nexusdataanalytics.tech  
**Administração Nexus:** https://rotafy.nexusdataanalytics.tech/nexus  
**Central de ajuda:** https://rotafy.nexusdataanalytics.tech/ajuda

Este arquivo descreve o produto e sua implementação atual: funcionalidades, perfis, regras de negócio, uso administrativo, operação de viagens, aplicativo Android e organização técnica. É uma documentação textual autossuficiente, sem depender das imagens dos manuais. Não contém senhas, chaves ou dados reais de clientes.

O arquivo consolida o estado atual do projeto. Não é uma cópia do código-fonte, do banco, das imagens de publicação ou do APK e não substitui seus backups. Também não apresenta propostas de desenvolvimento como recursos existentes.

## Sumário

1. [Visão do produto e conceitos](#visao-do-produto)
2. [Mapa dos recursos e regras centrais](#mapa-dos-recursos)
3. [Manual completo da empresa](#manual-da-empresa)
4. [Manual completo da administração Nexus](#manual-nexus)
5. [Recursos implementados com acesso oculto no menu](#recursos-com-menu-oculto)
6. [Arquitetura, dados e operação técnica](#arquitetura)
7. [Segurança e evidências de validação](#seguranca)
8. [Mapa do repositório e referências internas](#repositorio)

<a id="visao-do-produto"></a>
## 1. Visão do produto e conceitos

O Rotafy é uma plataforma SaaS para organizar empresas de turismo, transfers e transporte regular. Integra cadastros, equipe, veículos, rotas, pacotes, viagens, reservas, bilhetes, embarques e indicadores gerenciais. A Nexus administra os clientes da plataforma e sua cobrança em uma área própria.

A aplicação web atende várias empresas no mesmo banco, com separação de dados e permissões. O aplicativo Android atende motoristas e guias na operação das viagens atribuídas. O passageiro acessa seu bilhete por um link privado, sem precisar entrar no painel administrativo.

### Conceitos do domínio

| Conceito | Significado |
| --- | --- |
| Empresa | Cliente contratante do SaaS, com equipe, frota, cadastros e assinatura próprios. |
| Perfil operacional | Turismo e transfers ou transporte regular; determina as funcionalidades apresentadas. |
| Usuário | Pessoa autenticada com função e permissões no espaço da empresa ou na administração Nexus. |
| Veículo | Unidade da frota, identificada por nome, placa, capacidade e situação. |
| Rota | Percurso reutilizável com origem, destino, paradas e duração estimada. |
| Pacote | Produto turístico reutilizável, com preço e, quando aplicável, roteiro de vários destinos. |
| Destino comercial | Destino vendido no pacote e considerado no consumo da franquia. |
| Viagem comercial | Saída efetivamente agendada, simples ou vinculada a um pacote. |
| Deslocamento | Etapa física do roteiro, incluindo ida, volta, transferência ou chegada a um destino. |
| Alocação | Associação entre viagem, veículo, motoristas, guias e deslocamentos atendidos. |
| Reserva familiar | Grupo de passageiros com responsável e telefone compartilhado. |
| Segmento | Parte do deslocamento entre dois pontos consecutivos, usada no cálculo de ocupação. |
| Manifesto | Relação operacional dos passageiros de um veículo e deslocamento. |
| Bilhete | Credencial individual com QR Code e link privado para os deslocamentos da reserva. |
| Assinatura | Contrato da empresa com plano, ciclo e condições comerciais da Nexus. |
| Franquia | Quantidade de unidades de viagem incluídas no período contratado. |
| Cobrança SaaS | Valor devido pela empresa à Nexus, separado do pagamento dos passageiros à agência. |

### Dois fluxos financeiros distintos

**Passageiro → empresa:** o atendente registra manualmente a situação **PAGO** da reserva. A empresa recebe por seus próprios meios. A marcação não equivale à confirmação bancária e não confirma automaticamente uma reserva pendente.

**Empresa → Nexus:** a plataforma registra as cobranças da assinatura, setup e excedentes. Quando configurada e ativada, a integração InfinitePay gera links de pagamento, envia os avisos e verifica pagamentos automaticamente. Cobranças manuais mantêm baixa pela Nexus e dados Pix próprios.

<a id="mapa-dos-recursos"></a>
## 2. Mapa dos recursos e regras centrais

### Recursos por área

| Área | Recursos |
| --- | --- |
| Acesso | Login por empresa, funções, convites, recuperação, troca e visualização da senha. |
| Administração Nexus | Empresas, perfis operacionais, planos, assinaturas, equipe interna e atividades. |
| Equipe da empresa | Cadastro, edição de dados e função, ativação, suspensão e convites por dois canais. |
| Frota | Veículos, placas, capacidade e disponibilidade cadastral. |
| Rotas | Cidades por UF, endereços, paradas, ida/volta, duração estimada, edição e duplicação. |
| Pacotes turísticos | Passeios de um dia e circuitos de vários dias, destinos, deslocamentos e atividades. |
| Viagens | Agendamento, filtros por situação, edição, duplicação, alocações e finalização. |
| Vendas | Escolha da viagem, reserva familiar, sugestão de veículo, hotel/endereço e conferência de vagas. |
| Passageiros | Dados individuais, documentação, estrangeiros, menores e vínculo à reserva. |
| Reservas | Bloqueio temporário, confirmação, cancelamento, edição, realocação e importação. |
| Bilhetes | QR individual único, link privado, impressão/PDF, reemissão, revogação e envio. |
| Operação | Manifesto, QR, embarque/desembarque, início/chegada e navegação externa. |
| Android | Agenda de sete dias, biometria opcional, operação offline preparada e GPS na chegada. |
| Relatórios | Gráficos diários, ocupação, vendas, presença, destinos e exportação CSV. |
| Comunicação | Avisos de reserva, cancelamento, PAGO, convites, bilhetes e cobranças. |
| Assinaturas SaaS | Planos versionados, consumo, excedentes, teste, setup, links e restrições por inadimplência. |
| Documentação | Manuais da empresa e Nexus em HTML/PDF e apresentação para consulta e download. |

### Regras que atravessam os módulos

- A empresa é cadastrada pela equipe Nexus. Não existe opção de autocadastro de empresa na tela de login.
- CPF/CNPJ da empresa é obrigatório e validado. O identificador utiliza somente letras minúsculas sem acentos e números, de 2 a 50 caracteres.
- A conta Nexus completa não possui uma empresa operacional padrão. A operação exige conta da empresa.
- Um motorista ou guia que atende empresas diferentes possui cadastro em cada uma delas.
- Uma viagem pode ter vários veículos; cada alocação pode ter vários motoristas e guias. Guia é opcional.
- Cadastrar veículo, Rota ou modelo de pacote não consome franquia. O consumo ocorre ao criar a saída comercial.
- Uma viagem simples consome uma unidade, incluindo ida/volta e independentemente do número de veículos. Um pacote consome uma unidade por destino comercial; retorno e paradas não acrescentam unidades.
- Cancelar a viagem estorna o lançamento no ciclo original. Cancelar uma reserva não altera o consumo da viagem.
- O pacote é vendido completo. A mesma reserva cobre seus deslocamentos; não há venda de um destino isolado dentro desse produto.
- Famílias não são divididas automaticamente entre veículos. A disponibilidade precisa atender o grupo em todos os deslocamentos necessários.
- CPF do passageiro é exigido quando o roteiro é interestadual, respeitando as exceções identificadas de estrangeiro e menor de cinco anos.
- Endereços específicos da reserva compõem o roteiro operacional do veículo, sem modificar o modelo reutilizável da Rota.
- Alterar a Rota não altera automaticamente viagens existentes: elas guardam uma cópia do percurso. A atualização é uma ação explícita e validada.
- A chegada física é registrada por veículo/deslocamento; não encerra automaticamente as demais etapas ainda abertas.
- O GPS é capturado pontualmente na chegada quando disponível. Esse recurso não representa rastreamento contínuo.
- Valores de reservas e valores da assinatura SaaS têm finalidades e processos distintos.

### Sequência de implantação operacional na empresa

1. Cadastro pela Nexus e envio do acesso ao primeiro administrador.
2. Cadastro da equipe.
3. Cadastro dos veículos.
4. Cadastro das Rotas.
5. Cadastro de modelos de pacote, quando aplicável ao turismo.
6. Agendamento das viagens e definição de equipe/veículos.
7. Venda de reservas e emissão dos bilhetes.
8. Preparação dos manifestos e operação de embarques.
9. Registro de chegada e consulta dos indicadores.

<a id="manual-da-empresa"></a>
## 3. Manual completo da empresa

As subseções abaixo detalham os recursos disponíveis à empresa e à equipe operacional. Os títulos preservam a numeração do manual de utilização para facilitar a consulta.

### 1. Conheça o Nexus Rotafy

O **Nexus Rotafy** organiza a operação de empresas de turismo e transporte: cadastros, rotas, viagens, pacotes, reservas familiares, bilhetes individuais, embarque, comunicação e relatórios. A equipe administrativa usa o painel web; motoristas e guias usam o painel operacional ou o aplicativo Android.

Este manual descreve a implementação disponível em **16/10/2026**. As imagens utilizam dados demonstrativos. Os menus dependem do perfil do usuário e do tipo de empresa. Uma captura pode mostrar uma seleção de filtros diferente da sua operação.

**Endereço do painel:** <https://rotafy.nexusdataanalytics.tech>. O cadastro da empresa é realizado pela equipe comercial Nexus. A central de documentação utiliza `/ajuda`.

#### O fluxo de trabalho

1. Cadastre a empresa, escolha seu perfil operacional e o plano.
2. Cadastre a equipe e os veículos.
3. Prepare as rotas reutilizáveis e, quando necessário, os modelos de pacote.
4. Agende a viagem e atribua veículos, motoristas e guias.
5. Venda a reserva, confira a capacidade e marque PAGO quando recebido.
6. Emita o bilhete individual e envie o link ao cliente.
7. Prepare os manifestos, realize os embarques e registre a chegada.
8. Consulte a finalização, a ocupação, as vendas e o consumo do plano.

> **Três conceitos diferentes.** Rota é o percurso reutilizável. Pacote é o produto turístico e seu roteiro. Viagem é a saída agendada, com datas, horários, equipe e veículos. Cadastrar uma Rota ou um modelo de pacote não agenda uma saída nem consome a franquia.

### 2. Perfis e permissões

Cada empresa tem seu espaço e seus usuários. Um profissional que atende duas empresas deve possuir um cadastro em cada uma. No painel web, o identificador de acesso da empresa define em qual espaço ele entra.

| Perfil | O que utiliza |
| --- | --- |
| Administrador da empresa | Cadastros operacionais, vendas, relatórios, equipe, convites, identidade da empresa e consulta do próprio plano. |
| Atendente | Cadastros operacionais, reservas, bilhetes e relatórios gerenciais da empresa. Não administra usuários nem os planos da plataforma. |
| Motorista | Viagens e deslocamentos atribuídos; manifesto, leitura de QR, embarque, desembarque, saída e chegada. |
| Guia | Mesmos recursos operacionais do motorista, nos deslocamentos atribuídos. Guia é opcional. |
| Passageiro | Consulta do bilhete privado pelo link recebido; não acessa o painel administrativo. |

#### Turismo e transporte regular

**Turismo e transfers:** permite viagens simples e pacotes com vários destinos, incluindo passeios diários com retorno à base e circuitos com permanência entre cidades.

**Transporte regular:** utiliza viagens simples, rotas, frota, reservas e embarque. Os controles turísticos de pacotes ficam ocultos.

O perfil operacional não é o plano contratado. Basic, Professional e Enterprise são planos comerciais configurados pela Nexus. A troca do tipo de empresa é controlada pela Nexus e pode ser bloqueada enquanto houver viagens turísticas abertas.

### 3. Primeiro acesso e cadastro da empresa

1. Entre em contato com a equipe comercial Nexus para definir o plano e informar os dados da empresa e do administrador.
2. A Nexus cadastra a empresa e define o perfil **Turismo e transfers** ou **Transporte regular**, conforme a operação.
3. Receba por e-mail ou WhatsApp os dados cadastrais, a página de acesso, o identificador da empresa e o e-mail de login.
4. Abra o link recebido para definir sua senha. Ele é válido por 24 horas e pode ser usado uma única vez.
5. Defina uma senha com pelo menos 8 caracteres, uma letra maiúscula e um caractere especial.
6. Entre no painel com o identificador da empresa, seu e-mail e a senha definida.

Todos os campos do cadastro são obrigatórios. O identificador de acesso deve conter somente letras minúsculas sem acentos e números, de 2 a 50 caracteres. Não utilize espaços, sublinhado (_), hífen (-) ou outros caracteres especiais. Por exemplo, `agenciaexemplo` é um identificador de acesso, não uma senha. Guarde-o junto das orientações entregues à equipe.

O cliente não realiza cadastro público. Se o convite expirar, solicite um novo envio à equipe Nexus ou utilize **Esqueci minha senha** no acesso da empresa.

O administrador pode editar o cadastro clicando no bloco com o logo e o nome da empresa no menu lateral. O formulário permite atualizar nome comercial, razão social, CPF/CNPJ, telefone/WhatsApp e cores. O identificador de acesso aparece somente para consulta. A alteração do telefone suspende os envios pelo número anterior; confira a conexão no menu **WhatsApp**.

### 4. Login, senhas e recuperação

#### Entrar no painel web

1. Abra o endereço do sistema em um navegador atualizado.
2. Informe o identificador da empresa, o e-mail cadastrado e a senha.
3. Clique em **Acessar painel**. Os menus apresentados correspondem ao perfil do usuário.

#### Definir a senha pelo convite

Abra o link recebido por e-mail ou WhatsApp, escolha a nova senha e confirme. O convite vale **24 horas** e só pode ser usado uma vez. Depois, entre com o e-mail cadastrado; o número de WhatsApp não substitui o e-mail de login.

#### Esqueci minha senha

Use **Esqueci minha senha** no login. Informe e-mail e identificador da empresa. O link por e-mail vale **uma hora**. Por privacidade, a resposta pública não confirma se a conta existe.

O administrador também pode gerar um link manual de recuperação para um colaborador, válido por **30 minutos**. A troca de senha encerra as sessões anteriores daquele usuário. Não compartilhe sua própria conta com outras pessoas.

Se receber erro de credenciais, confira a empresa, o e-mail, o perfil ativo e a senha. Muitas tentativas podem gerar bloqueio temporário. Uma conta suspensa não consegue entrar.

### 5. Colaboradores e convites

**Acesso:** administrador da empresa → **Equipe**.

#### Adicionar uma pessoa

1. Clique em **Adicionar pessoa**.
2. Preencha nome, e-mail, perfil e telefone/WhatsApp do colaborador.
3. Para compartilhar uma senha inicial, mantenha o convite desmarcado e informe pelo menos 8 caracteres, uma letra maiúscula e um caractere especial.
4. Para a pessoa definir a própria senha, marque **Enviar convite para a pessoa definir sua senha**.
5. Escolha **E-mail**, **WhatsApp** ou **E-mail e WhatsApp**. O telefone é obrigatório para os dois últimos.
6. Salve. O envio entra na fila e depende da integração do canal escolhido estar habilitada.

O número pode ser nacional com DDD ou internacional com `+` e código do país. O sistema valida e normaliza o telefone.

#### Reenviar, suspender e consultar

Utilize **Editar colaborador** para alterar nome, e-mail de acesso, telefone/WhatsApp e função (Administrador, Atendente, Motorista ou Guia). Alterar o e-mail ou a função encerra as sessões anteriores. A troca de e-mail invalida os links antigos de recuperação. O sistema impede remover seu próprio acesso administrativo ou o último administrador ativo.

Na linha do colaborador, clique em **Enviar convite**, escolha o canal e confira ou atualize o telefone. Um novo convite substitui os links anteriores. Ao escolher os dois canais, ambos recebem o mesmo link.

Utilize **Suspender/Ativar** para controlar o acesso. O sistema preserva pelo menos um administrador ativo e impede remover seu próprio acesso administrativo nessa tela.

Abra **E-mails de acesso** para consultar a fila de e-mails e a seção **Convites por WhatsApp**. A aceitação do envio não comprova entrega ou leitura. Um envio incerto precisa ser conferido antes do reenvio.

### 6. Veículos e capacidade

**Acesso:** administrador ou atendente → menu **Veículos**.

1. Abra o cadastro de novo veículo.
2. Informe nome de identificação, placa e quantidade de lugares.
3. Confira a placa brasileira tradicional ou Mercosul e salve.
4. Mantenha o cadastro ativo para novas alocações. Edite os dados quando necessário ou arquive o veículo quando deixar de utilizá-lo.

A capacidade é de **1 a 200 lugares**. O sistema distribui quantidade de passageiros; não utiliza escolha de poltrona numerada. Os motoristas e guias são definidos na alocação da viagem, não como uma equipe permanente do veículo.

A capacidade atribuída é preservada na viagem. Alterar a frota depois não recalcula a capacidade histórica de saídas já criadas. O mesmo veículo pode operar em diferentes horários, desde que não haja conflito de agenda.

### 7. Rotas reutilizáveis e Google Maps

**Acesso:** administrador ou atendente → **Rotas**.

1. Clique em **Nova Rota** e informe um nome reconhecível.
2. Escolha somente ida ou ida e volta.
3. Selecione UF e cidade de origem e destino. A lista de cidades acompanha a UF escolhida.
4. Informe os endereços de saída e chegada, de modo que possam ser localizados no Google Maps.
5. Inclua as paradas intermediárias na ordem da operação. Defina embarque, desembarque ou ambos em cada uma.
6. Informe o deslocamento estimado em minutos e o tempo adicional total nas paradas.
7. Para ida e volta, utilize **Gerar volta invertendo a ida**, quando adequado, e revise a sugestão antes de salvar.

As paradas adicionais da Rota não exigem data nem horário individual. Exemplo: 60 minutos de trajeto mais 20 nas paradas resultam em 80 minutos previstos. Informe a duração estimada do percurso para planejar os horários.

As ações **Editar Rota**, **Duplicar Rota** e desativar permitem manter o catálogo. Desativar impede novas escolhas, preservando o histórico das viagens que já utilizam o percurso.

#### Abrir a navegação

Na viagem atribuída, o motorista ou guia abre a rota ou um ponto específico no **Google Maps externo**. Confira os pontos e a ordem programada. A navegação e suas condições dependem do aplicativo Maps e da conectividade do aparelho.

#### A Rota mudou depois de agendar?

A viagem guarda uma cópia do percurso. Editar o catálogo não muda automaticamente uma saída já criada. Em **Detalhes**, use **Atualizar com a versão atual da Rota**, confirme e confira as chegadas recalculadas.

A atualização é permitida para viagens agendadas sem eventos de embarque. Com reservas, preserva a posição, quantidade e finalidade das paradas utilizadas. Mudanças incompatíveis são bloqueadas. Prepare novamente os manifestos offline após uma atualização. Para outro percurso ou composição incompatível, crie uma nova viagem.

### 8. Pacotes turísticos: modelos e formatos

**Acesso:** empresa de Turismo → menu **Pacotes**. Um pacote é um modelo reutilizável, sem data fixa. A data real é definida ao criar a viagem no menu **Viagens**. Os cadastros de veículos e rotas possuem seus próprios menus.

#### Pacote simples

Cadastre nome, informações comerciais e valor por passageiro. Ao criar uma saída, selecione o pacote, a Rota e os horários. O modelo não consome franquia: o consumo ocorre no agendamento da viagem.

#### Passeios com ida e volta

Use este formato quando cada passeio retorna à mesma cidade-base no próprio dia.

1. Cadastre previamente Rotas de ida e volta para os passeios.
2. Em **Novo pacote**, habilite o roteiro de vários destinos e escolha **Passeios com ida e volta**.
3. Em cada caixa, selecione a Rota, o nome comercial do destino, o dia relativo, a saída e o horário de retorno saindo do destino.
4. O primeiro passeio começa no dia 1. Os seguintes podem acontecer em dias espaçados.
5. Confira a ordem e salve o modelo.

**Exemplo:** dia 1, Maceió → Maragogi → Maceió; dia 3, Maceió → Praia do Gunga → Maceió. São dois destinos comerciais e quatro deslocamentos. A saída desse pacote consome **duas unidades** da franquia.

#### Viagem com destinos em sequência

Use este formato quando os passageiros seguem para outra cidade e permanecem nela antes de continuar.

1. Cadastre as Rotas necessárias para cada deslocamento.
2. Informe os destinos comerciais na ordem do roteiro.
3. Configure dia relativo, horário, Rota/sentido e finalidade de cada deslocamento.
4. Associe cada chegada ao destino comercial correto, uma única vez.
5. Termine com o retorno à origem, sem novo destino comercial.
6. Acrescente atividades e dias livres, quando necessário, e confira as validações antes de salvar.

**Exemplo:** Maceió → Fortaleza no dia 1; Fortaleza → Natal no dia 3; Natal → Maceió no dia 6. A franquia considera os destinos comerciais Fortaleza e Natal: **duas unidades**.

> **Venda completa.** O pacote inclui o roteiro inteiro e o retorno. Não existe venda de um destino isolado dentro do pacote; crie outro pacote para esse produto. Paradas, atividades, retorno e transferências sem nova chegada comercial não acrescentam unidades à franquia.

O modelo admite até 20 destinos, 60 deslocamentos, 60 dias relativos e 120 atividades. As caixas com borda verde petróleo separam os itens do roteiro. CEP e datas fixas não fazem parte do modelo.

### 9. Criar e alocar uma viagem

**Acesso:** administrador ou atendente → **Viagens** ou a aba de viagens no módulo de frota.

#### Saída simples

1. Clique em **Nova viagem**.
2. Escolha a Rota; vincule um pacote simples se aplicável.
3. Informe nome comercial, destino apresentado ao comprador e preço por passageiro.
4. Informe data e hora de saída e, para ida e volta, data e hora de retorno.
5. Confira as chegadas previstas a partir da duração da Rota.
6. Inclua os veículos e escolha o motorista principal de cada alocação. Marque os motoristas adicionais que acompanharão o mesmo veículo. Selecione nenhum, um ou vários guias, conforme a operação.
7. Revise as paradas atendidas por cada veículo, a capacidade e os conflitos de agenda; salve.

#### Saída de pacote com roteiro

Selecione o pacote e informe a **Data inicial do pacote**. Os dias relativos se transformam em datas reais. Confira cada deslocamento e seus horários, sem sobreposição. Atribua equipe e veículo aos deslocamentos correspondentes.

Cada veículo pode ter até 20 motoristas e 20 guias. Todos os motoristas e guias atribuídos podem consultar agenda, rota e manifesto e operar os embarques no app atualizado. O cadastro impede sobreposição de horários e repetição de pessoas em veículos que atendem o mesmo trecho.

Vários veículos podem atender o mesmo deslocamento. Um pacote também pode trocar de veículo, motorista ou guia entre etapas. Cada família permanece inteira no veículo escolhido para cada deslocamento. O cadastro verifica conflitos e impede duplicar o mesmo recurso na mesma etapa.

#### Consulta, edição e duplicação

Utilize o filtro **Situação da viagem**: Todas, Abertas, Agendadas, Em andamento, Fechadas/concluídas e Canceladas. Abertas reúne agendadas e em andamento; isso não significa que todas ainda permitam novas vendas.

Em **Detalhes**, confira roteiro, equipe, capacidade, reservas e finalização. A edição operacional respeita a situação da viagem e protege reservas e embarques existentes. Alterar o preço para novas reservas não recalcula as reservas já vendidas.

**Duplicar viagem** cria uma nova saída; confirme as datas e a equipe antes de salvar. Ao cancelar a viagem, reservas ativas são canceladas, lugares são liberados e o consumo é estornado no ciclo original. Não há reembolso bancário automático.

### 10. Vender bilhetes e cadastrar uma família

**Acesso:** administrador ou atendente → **Vender bilhete**. Também é possível abrir **Detalhes da viagem → Reservas e lugares**.

1. Pesquise por nome ou destino e selecione uma viagem agendada com saída futura.
2. Clique em **Vender bilhete** ou **Nova reserva**.
3. Preencha nome do responsável, telefone da família e país do telefone.
4. Adicione os passageiros, um cadastro por pessoa. Inclua o responsável na lista se ele também viajar.
5. Informe CPF e as exceções aplicáveis, conforme o capítulo seguinte.
6. Informe **Local de embarque**: selecione um ponto sugerido ou digite o hotel/endereço. Confira no Maps se necessário. O destino e o retorno são sugeridos; abra os ajustes apenas se precisar mudá-los.
7. Confira a sugestão de veículo e a disponibilidade para a família inteira.
8. Salve como confirmada ou bloqueio pendente, conforme a operação, e confira o resultado.

Uma reserva pode ter de 1 a 200 passageiros com um único telefone compartilhado. O valor nominal é o preço por passageiro da saída multiplicado pelo total de passageiros e fica preservado na reserva.

#### Embarque em hotel ou outro endereço

Em **Local de embarque**, digite somente o nome do hotel ou o endereço. O mesmo campo oferece os pontos da viagem e locais já utilizados como sugestões. Não é necessário preencher nome e endereço separadamente.

Clique em **Conferir no Maps** para abrir a busca do local em uma nova aba. Confira se o resultado corresponde ao hotel desejado; se preferir, copie o endereço e cole no campo. A escolha feita no Maps não é transferida automaticamente para o formulário.

Nas novas reservas, **Usar este local nos passeios com saída da cidade e no retorno** vem marcado quando há deslocamentos correspondentes. Ao informar o embarque, esses locais são preenchidos juntos. Abra **Ajustar locais por passeio/trecho** para alterar apenas um deles. O destino principal aparece no resumo; use **Alterar desembarque** quando necessário. Reservas já existentes preservam os locais de cada deslocamento ao abrir o editor.

Veículo e situação inicial ficam em **Opções da reserva**. O padrão é confirmar a reserva usando a sugestão de veículo. Para familiares que embarcam em locais diferentes, faça reservas separadas.

Esses locais pertencem à reserva e ao veículo de cada saída. A Rota cadastrada permanece disponível para reutilização. Motoristas e guias consultam os endereços, complementos e passageiros previstos no roteiro e abrem a navegação. Após alterações, sincronize ou prepare novamente o trecho no Android antes de operar sem internet.

#### Ocupação por segmento

A capacidade é conferida entre cada par de pontos consecutivos. Quem desembarca antes do destino libera o lugar para outro passageiro que embarque depois. A sugestão procura um veículo que comporte toda a família e deixe menos lugares livres no percurso reservado.

Somar vagas de ônibus diferentes não garante lugar para uma família no mesmo ônibus. Se nenhum veículo comportar todos os integrantes nos trechos necessários, o sistema informa indisponibilidade e não divide a família automaticamente. Em pacotes, a combinação deve atender todos os deslocamentos; o veículo pode mudar entre eles.

#### Situações da reserva

| Situação | Efeito |
| --- | --- |
| Confirmada | Mantém os lugares até cancelamento. Permite emissão de bilhete enquanto a viagem estiver ativa. |
| Bloqueio pendente | Segura os lugares por 15 minutos desde a criação. Confirme antes do vencimento. |
| Expirada | Não ocupa lugares e não pode ser confirmada. Faça nova reserva se ainda houver capacidade. |
| Cancelada | Libera os lugares; não reativa a reserva nem devolve dinheiro automaticamente. |

Consultas não garantem as vagas: o sistema valida a capacidade novamente ao salvar. A confirmação da reserva e a marcação **PAGO** são ações diferentes.

### 11. CPF, estrangeiros e menores

Quando o roteiro cruza UFs, o sistema exige CPF dos passageiros, com as exceções cadastrais abaixo. A regra considera o roteiro completo do pacote, não apenas a primeira etapa.

| Situação | Como cadastrar |
| --- | --- |
| Passageiro brasileiro em roteiro interestadual | Informe CPF válido. |
| Estrangeiro | Marque a opção **Estrangeiro**; a validação considera a exceção ao CPF. |
| Criança menor de 5 anos | Marque **Menor de 5 anos** e informe nascimento para validar a idade. |
| Viagem dentro da mesma UF | CPF é opcional; quando informado, precisa ser válido. |

CPFs não podem repetir entre passageiros de reservas ativas da mesma viagem. Corrija erros de digitação antes de concluir. Estas são regras cadastrais do sistema; a empresa continua responsável por conferir os documentos e os requisitos da sua operação.

### 12. Pagamento, edição e realocação

Em **Reservas e lugares → Ver reserva**, consulte a família, os passageiros, os pontos, o veículo de cada etapa e o valor.

#### Marcar PAGO

Marque **PAGO** somente depois de conferir o recebimento pela empresa. O Rotafy não consulta banco, cartão ou PIX. Desmarcar PAGO corrige o registro interno; não realiza devolução financeira. Quando habilitado, o WhatsApp envia uma mensagem ao mudar para PAGO, não ao salvar repetidamente o mesmo estado.

#### Editar a reserva

Utilize **Editar reserva** para corrigir responsável, telefone, nomes, CPF e pontos permitidos. O editor preserva quantidade de passageiros, valor, bilhetes e marcação PAGO. Incluir ou remover pessoas e mudar a composição de trechos exige outro cadastro compatível com a operação.

Pontos de um trecho com eventos de embarque são protegidos. Reservas expiradas/canceladas e viagens encerradas não permitem edição operacional.

#### Realocar a família

Escolha um veículo com capacidade para todos os integrantes nos segmentos reservados. A realocação mantém a família inteira e exige que ninguém esteja a bordo. Histórico já realizado permanece associado ao veículo original. Em pacotes iniciados, a realocação completa é bloqueada para preservar as etapas executadas.

Depois de alterações, os operadores precisam atualizar os manifestos. Aparelhos sem conexão ainda podem mostrar a informação antiga até sincronizar.

### 13. Importar passageiros por CSV/XLSX

**Acesso:** atendimento da viagem → **Importar CSV/XLSX**.

1. Baixe o modelo CSV e mantenha seu cabeçalho.
2. Use uma linha por passageiro. Repita o identificador da família, o responsável e o telefone para agrupar as pessoas.
3. Preencha CPF e indicadores `estrangeiro`/`menor_5_anos` com `sim` ou `nao`; nascimento usa `AAAA-MM-DD`.
4. Envie o arquivo e leia a prévia. Corrija todos os erros identificados por linha.
5. Confirme a importação somente depois da conferência e da disponibilidade.

O cabeçalho atual é: `familia,responsavel,telefone,pais,passageiro,cpf,estrangeiro,menor_5_anos,nascimento`.

CSV deve ser UTF-8; aceita vírgula ou ponto e vírgula. XLSX utiliza uma única aba e células de texto, especialmente para CPF e telefone. Fórmulas e macros não são aceitas.

Limites: 2 MB, 500 linhas e 200 passageiros por família. A prévia vale 30 minutos e não segura vagas. Na confirmação, se uma família não couber ou houver conflito, o lote inteiro é recusado; nenhuma parte é vendida silenciosamente.

A importação cria reservas confirmadas para o percurso completo. Para pontos intermediários específicos, utilize o cadastro manual. Repetir um arquivo aplicado não cria as mesmas famílias novamente.

### 14. Bilhete único, QR Code e envio

**Acesso:** **Ver reserva → Bilhetes individuais**.

1. Confirme a reserva e confira se a viagem está ativa.
2. Clique em **Emitir bilhetes**. Cada passageiro recebe um único link e QR para todos os trechos contratados.
3. Abra o bilhete para conferir nome, viagem, veículos, pontos, horários e situação de cada trecho.
4. Copie o link ou use **Enviar bilhete pelo WhatsApp**. O envio utiliza o telefone da reserva.
5. Na página do bilhete, o cliente pode compartilhar o link, imprimir/salvar PDF e baixar a imagem do QR.

O mesmo QR é apresentado na ida, na volta e nas etapas do pacote. O controle de embarque permanece separado por veículo e trecho. O passageiro não precisa de aplicativo próprio para abrir o bilhete no navegador.

#### Reemitir e revogar

**Reemitir bilhete** cria uma nova credencial para todos os trechos daquele passageiro e invalida as anteriores. **Revogar bilhete** impede usar o QR em todos esses trechos. Não apaga o histórico de embarque.

O link aparece na emissão/reemissão. Ao fechar a tela, reemita se precisar obter novamente o link para envio. Na reemissão, avise o cliente e atualize os manifestos offline.

Nas reservas antigas com bilhetes por trecho, use **Emitir bilhetes** para converter. Links anteriores são invalidados pela conversão. Prepare novamente os manifestos depois.

> **Link individual e privado.** Compartilhe com o passageiro ou responsável correto. O cancelamento da reserva, a revogação e o encerramento da viagem impedem o embarque. Um link já enviado pelo WhatsApp não pode ser retirado da conversa, mas pode deixar de autorizar o uso no sistema.

### 15. Mensagens de WhatsApp e e-mail

Cada empresa utiliza seu próprio número de WhatsApp. O administrador consulta os envios da sua empresa. Os e-mails de acesso utilizam o remetente configurado para a plataforma.

| Mensagem | Quando é gerada |
| --- | --- |
| Confirmação da reserva | Ao criar uma reserva já confirmada ou confirmar uma pendente. |
| Cancelamento | Ao cancelar a reserva ou a viagem que contém reservas ativas. |
| PAGO | Quando o registro muda para PAGO. |
| Resumo da reserva | Pela ação **Enviar resumo pelo WhatsApp**, nos detalhes. |
| Link do bilhete | Pela ação **Enviar bilhete pelo WhatsApp**, após emissão/reemissão. |
| Convite do colaborador | Pelo cadastro/reenvio de convite, no canal escolhido. |
| Recuperação por e-mail | Pela solicitação de recuperação de acesso. |

#### Entenda o histórico

**Na fila/aguardando:** ainda não enviado. **Enviando:** processamento em curso. **Aceito pelo provedor:** o provedor aceitou a solicitação, sem confirmação de leitura. **Falhou:** rejeição ou esgotamento de tentativas. **Descartado:** registro obsoleto, vencido, substituído ou incompatível. **Incerto:** a resposta não permite afirmar se o envio foi aceito.

Sessões WhatsApp desconectadas mantêm os envios aguardando. Mensagens automáticas de vendas anteriores à ativação não são enviadas retroativamente. Mensagens pendentes podem ser descartadas se os dados ou o link deixarem de ser válidos.

Se o resultado estiver incerto, confira o recebimento com o destinatário antes de reenviar. Para um convite com falha definitiva, solicite um novo envio pelo cadastro do colaborador.

### 16. App Android: acesso e agenda

O app operacional é destinado a **motoristas e guias**, com os mesmos recursos para ambos. A empresa distribui o APK configurado para sua operação.

1. Instale ou atualize o APK fornecido pela empresa. Prefira atualizar sobre a instalação existente, sem desinstalar, para preservar registros locais.
2. Confira a empresa apresentada. Se o APK não tiver empresa fixa, informe o identificador correto.
3. Entre com e-mail e senha do seu cadastro nessa empresa.
4. Em **Minhas viagens**, consulte os deslocamentos atribuídos a você.
5. Abra **Agenda** para ver as próximas viagens/etapas dos sete dias seguintes, com data, horário e destino.

Utilize o aplicativo fornecido pela empresa e mantenha-o atualizado.

Viagens concluídas deixam de estar disponíveis para operação. Conclusões feitas por outro usuário aparecem após atualizar ou sincronizar. Registros pendentes continuam acessíveis para revisão, sem reabrir a viagem.

#### Biometria opcional

Durante o login, marque **Usar biometria nos próximos acessos** e conclua a autenticação inicial. No próximo acesso, utilize **Entrar com biometria**. A disponibilidade depende de biometria forte e de um aparelho compatível; a proteção do cofre biométrico exige Android 9 ou superior.

Cancelar a biometria não abre o painel. A senha continua como alternativa. No menu, é possível desativar o recurso; **Sair** também remove o acesso biométrico salvo. Mudança de senha pode exigir entrar novamente de forma manual.

### 17. Preparar e realizar o embarque

Prepare cada **veículo e trecho** enquanto houver conexão. Preparar a ida não prepara automaticamente a volta, e uma etapa não prepara todas as etapas do pacote.

1. Abra a viagem atribuída e selecione o veículo/trecho que irá operar.
2. Carregue/prepare o manifesto online antes de sair.
3. Confira lista, pontos, equipe e situação da operação.
4. Abra a leitura de QR, conceda permissão de câmera e leia o bilhete do passageiro.
5. Confira o passageiro identificado e confirme o embarque. Ler o QR não registra o embarque sozinho.
6. Quando necessário, utilize a lista para embarcar ou desembarcar manualmente.
7. Confira os totais e a sincronização antes de encerrar.

O sistema valida reserva, credencial, empresa, viagem, trecho, veículo e situação. Um QR de outro passageiro ou uma reserva inválida não autoriza o embarque. O bilhete unificado funciona em cada trecho contratado, respeitando sua alocação.

#### Lista e filtros

Use **Todos**, **Não embarcados** e **Embarcados**. Desembarcados aparecem em Todos. É possível recolher/expandir a lista sem perder o resumo. Os filtros do Android consideram também as ações locais pendentes.

**Desembarcar todos** considera somente quem está a bordo no veículo/trecho selecionado e pede confirmação. Quem ainda não embarcou continua aguardando. Se houver conflitos, revise-os antes de confirmar o lote.

O painel web também oferece operação por lista, leitura pela câmera e leitura de QR por imagem. As ações dependem das permissões e da viagem atribuída.

### 18. Sem internet: preparação e sincronização

O app Android e a operação web preparada podem manter registros locais durante uma interrupção. Para novos registros offline, o manifesto precisa ter sido preparado antes e ainda estar válido. A preparação tem validade limitada, de até **oito horas**, respeitando também a sessão.

1. Prepare cada veículo/trecho online.
2. Durante a falta de conexão, registre os embarques e desembarques permitidos.
3. Observe a quantidade de ações pendentes. O registro local ainda não é confirmação no servidor.
4. Reconecte com o mesmo usuário e sincronize.
5. Revise as ações rejeitadas ou em conflito e atualize o manifesto.

Outra pessoa pode cancelar uma reserva, editar pontos, realocar passageiros ou reemitir o bilhete enquanto seu aparelho está offline. Essas mudanças não aparecem instantaneamente no dispositivo, mas são verificadas pelo sistema ao sincronizar.

> **Preserve a fila.** Não limpe dados, desinstale o app ou troque de operador para tentar resolver pendências. Antes de iniciar a operação, confirme que o dispositivo é do usuário correto. Depois de alteração de Rota, reserva ou bilhete, prepare novamente os manifestos. O sistema não confirma automaticamente uma ação incompatível com o estado atual.

Iniciar a viagem e registrar chegada exigem conexão. A fila local permite operar presenças preparadas; os registros são conferidos pelo sistema ao sincronizar.

### 19. Iniciar, chegar e consultar a finalização

O início e a chegada pertencem ao **veículo e trecho** selecionados. Iniciar um ônibus não inicia os demais. Registrar chegada da ida não encerra a volta.

#### Iniciar viagem

Com conexão, selecione a etapa correta, toque em **Iniciar viagem** e confirme. A primeira saída coloca a viagem geral em andamento. Etapas seguintes respeitam a conclusão das anteriores.

#### Fechar viagem na chegada

1. Desembarque quem ainda está a bordo, individualmente ou por **Desembarcar todos**.
2. Sincronize e resolva todas as pendências do trecho.
3. Com conexão, toque em **Fechar viagem** e confirme a chegada.
4. Autorize a localização do celular, quando disponível.
5. Confira o registro concluído. O trecho deixa de aceitar novos embarques e desembarques.

O sistema impede fechar com passageiros a bordo. A viagem comercial é concluída quando todos os veículos encerram todos os deslocamentos previstos, incluindo retorno. Em uma saída com vários ônibus, a chegada de um deles não conclui os outros.

#### GPS pontual

A captura registra latitude, longitude, precisão e horário do dispositivo. Se não houver permissão, sinal ou posição válida, o fechamento pode continuar com o motivo da ausência.

#### Consultar no painel

Abra **Viagens → Detalhes → Finalização e chegadas**. Consulte saída/chegada por veículo e trecho, responsável, coordenadas, precisão, horário de captura e o link para o local no Maps. Quando faltarem dados, o sistema informa a ausência.

O encerramento administrativo tem seu próprio registro e não é apresentado como uma chegada física quando não houve captura. Em viagens concluídas ou canceladas, navegação operacional, embarque e **Reservas e lugares** ficam desabilitados; o histórico de finalização permanece consultável.

### 20. Relatórios e visão gerencial

**Acesso:** administrador ou atendente → **Relatórios**. Cada empresa consulta seus dados. Motoristas e guias não recebem relatórios financeiros/administrativos.

#### Visão gerencial

Escolha período, situação, veículo ou viagem e aplique os filtros. O mês atual inclui o mês completo; o atalho de 30 dias termina hoje. Datas usam o fuso de São Paulo e o intervalo máximo é de 366 dias.

| Indicador | Como interpretar |
| --- | --- |
| Deslocamentos por dia | Cada etapa conta na data de saída, inclusive retorno. Vários veículos não multiplicam a contagem. |
| Viagens comerciais iniciadas | Conta a primeira saída da viagem, sem repetir destinos do pacote. |
| Ocupação confirmada | Maior quantidade simultânea de confirmados por veículo/deslocamento, dividida pela capacidade. O consolidado é ponderado pelas capacidades. |
| Passageiros e famílias confirmados | Cada reserva é contada uma vez no produto comercial, sem duplicar pelo retorno. |
| Valor confirmado | Valor nominal das reservas confirmadas selecionadas. |
| Marcado PAGO / não pago | Classificação manual de valores; não é conciliação bancária. |
| Ticket médio por passageiro | Valor confirmado dividido pelos passageiros confirmados. |
| Produtos/destinos mais vendidos | Até dez itens, por passageiros confirmados; o pacote não tem seu preço dividido entre destinos. |
| Próximas saídas com baixa ocupação | Até 30 alocações/deslocamentos futuros com ocupação confirmada inferior a 50%, dentro do filtro. |

Clique no gráfico diário para consultar os valores do dia. Bloqueios temporários aparecem separados da ocupação confirmada. Ausência de dados não deve ser interpretada como uma operação com 0% de ocupação.

#### Relatórios detalhados e CSV

As abas oferecem **Ocupação**, **Reservas e pagamentos**, **Presença** e, para o administrador, **Consumo da franquia**. Ocupação detalhada considera os segmentos entre paradas. Presença utiliza os registros aceitos pelo servidor, não as ações offline ainda pendentes.

Use **Exportar CSV completo** para analisar em planilha. O arquivo usa UTF-8, separador `;`, datas de Brasília e reais com vírgula decimal. O filtro de pagamento da tabela não altera automaticamente o escopo do CSV completo; leia a indicação da tela.

Os valores não representam lucro, fluxo de caixa, confirmação de PIX ou extrato bancário. O filtro por veículo pode incluir a reserva inteira de um pacote quando esse veículo atende uma de suas etapas.

Se a consulta atingir o limite, reduza o período ou escolha uma viagem. O sistema solicita ajuste em vez de mostrar totais parciais sem avisar.

### 21. Meu plano e consumo mensal

**Acesso:** administrador da empresa → **Meu plano**.

Consulte plano, ciclo, mensalidade, franquia, uso líquido, unidades restantes, extras e valor estimado. Nos novos contratos automáticos, os ciclos têm 30 dias e a cobrança ocorre após o uso; a franquia não acumula para o período seguinte. Contratos legados preservam o calendário contratado.

| Operação | Consumo |
| --- | --- |
| Cadastrar veículo, Rota ou modelo de pacote | Não consome. |
| Criar viagem simples, com ida/volta e vários veículos | Uma unidade. |
| Criar saída de pacote com quatro destinos comerciais | Quatro unidades. |
| Acrescentar retorno, parada ou atividade sem novo destino comercial | Não acrescenta unidade. |
| Cadastrar, confirmar ou cancelar uma reserva | Não altera a franquia. |
| Cancelar a viagem | Estorna o consumo original no ciclo em que foi lançado. |

**Estimativa do ciclo:** mensalidade + máximo(uso líquido − franquia, 0) × valor da viagem extra. Cancelar uma viagem de um ciclo anterior não transfere crédito para o ciclo atual.

A cobrança da assinatura e os links de pagamento estão detalhados na seção Financeiro da empresa e pagamento da assinatura. Contratos e cobranças manuais preservam suas condições.

### 22. Comunicação da empresa

A empresa utiliza seu próprio número de WhatsApp para comunicar reservas e bilhetes. A Nexus orienta a ativação dos canais e do remetente dos e-mails de acesso.

#### Conectar o WhatsApp no painel da empresa

O administrador encontra o menu **WhatsApp**. A sessão da nova empresa é preparada automaticamente em segundo plano; não é necessário conhecer um ID ou acessar as configurações da Nexus. Empresas já cadastradas podem iniciar a conexão pelo mesmo menu.

1. Confira o **WhatsApp de envio da empresa**, obtido diretamente do cadastro da empresa. Para alterar, clique no bloco com o logo e o nome da empresa no menu lateral e salve o cadastro.

2. Mantenha **Habilitar envios após conectar e conferir o número** marcado quando desejar ativar as mensagens.
3. Clique em **Conectar WhatsApp** e aguarde a preparação do QR Code.
4. No celular do número informado, abra **WhatsApp → Aparelhos conectados → Conectar aparelho** e escaneie o código mostrado no painel.
5. Aguarde o estado **Conectado**. O número é conferido antes de liberar os envios. O QR é atualizado automaticamente e deixa de aparecer após a conexão.

Após a conexão, a contagem e a mensagem de espera desaparecem. O botão passa a ser **Desconectar WhatsApp**. Ao clicar, os envios são suspensos imediatamente e o sistema solicita a desconexão. Se o serviço estiver indisponível, a solicitação fica pendente e será repetida automaticamente. Aguarde **Desconectado** antes de conectar novamente.

A tela mostra a contagem para a próxima tentativa e para a atualização da consulta. Use **Interromper tentativas** para pausar e **Retomar conexão** para continuar. Uma solicitação já enviada pode terminar, mas seu resultado antigo não reativa os envios.

Se aparecer **Número conectado diferente do informado**, os envios ficam suspensos. Confira o telefone; se utilizou outro WhatsApp, desconecte o dispositivo no celular e conecte o número correto. Se aparecer **Desconectado**, clique em Conectar WhatsApp para tentar novamente. Indisponibilidade do serviço ou falta de autorização deve ser conferida pela Nexus.

Apenas o administrador da empresa acessa essa tela. Não compartilhe o QR: ele autoriza uma conexão ao WhatsApp. Abra o painel em outro aparelho ou computador para escanear com o celular. A autorização no aparelho é indispensável; informar o telefone não conecta a conta sozinho.

#### Conferir os canais

1. Confirme com a Nexus o número da empresa e o e-mail remetente.
2. Envie um convite para um colaborador autorizado.
3. Confira o recebimento no canal selecionado.
4. Consulte o histórico de mensagens no painel.
5. Solicite suporte caso haja falha persistente.

#### Boas práticas

Confira o telefone do responsável antes de enviar o bilhete. Consulte o histórico antes de reenviar uma comunicação. Compartilhe cada link somente com a pessoa correta.

### 23. Rotina por perfil

#### Administrador da empresa

Organize equipe, frota e rotas. Cadastre viagens, acompanhe reservas, confira o plano contratado e analise os relatórios. Oriente os colaboradores sobre os procedimentos da empresa.

#### Atendente

Selecione a viagem no menu **Vender bilhete**, cadastre os passageiros, confira disponibilidade, confirme a reserva e marque **PAGO** após verificar o recebimento. Envie os bilhetes e acompanhe as mensagens.

#### Motorista e guia

Consulte a agenda, confira veículo e deslocamento, prepare a lista de passageiros e registre os embarques. No destino, registre os desembarques, sincronize as ações e finalize o trecho.

### 24. Dúvidas frequentes e solução de problemas

#### Não vejo um menu

Confira o perfil do usuário e o tipo da empresa. Atendente não administra equipe/plano; motorista e guia veem somente sua operação. Pacotes aparecem para Turismo.

#### A família não cabe, mas a soma de vagas parece suficiente

A família precisa caber inteira em um veículo por deslocamento. Verifique os pontos, todos os segmentos e todos os dias do pacote; bloqueios temporários válidos também ocupam capacidade.

#### Alterei uma Rota e a viagem continua com o endereço antigo

A saída guarda uma cópia. Utilize a atualização explícita da Rota nos detalhes, quando permitida, e depois atualize os manifestos. Se houver incompatibilidade ou operação iniciada, faça uma nova saída conforme o atendimento.

#### Não consigo salvar o roteiro do pacote

Confira o formato escolhido, destinos comerciais na ordem, chegada associada uma vez por destino, dia 1 na primeira saída e retorno final. Para passeios diários com volta à base, prefira **Passeios com ida e volta**.

#### O QR não funciona

Confira reserva confirmada, viagem ativa, passageiro, trecho e veículo selecionados. Verifique se houve reemissão/revogação e se o manifesto está atualizado. O bilhete único exige dados preparados novamente após a conversão dos bilhetes antigos.

#### O celular mostra “Sem conexão”

Os registros locais podem estar preservados. Confira a conexão com a internet, mantenha o mesmo usuário e sincronize quando reconectar. Não limpe os dados para resolver uma pendência. Utilize o aplicativo fornecido pela empresa.

#### Não consigo fechar o trecho

Desembarque todos que estão a bordo e sincronize/revise as pendências. O fechamento exige conexão e as etapas anteriores precisam estar concluídas. A falta de GPS pode ser registrada como motivo.

#### O convite ou mensagem falhou

Consulte o histórico de mensagens. Confira telefone, e-mail do destinatário e canal selecionado. Falha definitiva exige novo convite; em resultado incerto, verifique o recebimento antes de reenviar. Solicite suporte se a falha persistir.

#### Como pedir suporte

Informe empresa, perfil, tela, operação, data/hora e a mensagem apresentada. Use o identificador da solicitação se a tela o fornecer. Não envie senhas ou links privados de passageiros. O manual não substitui a análise de uma ocorrência real pela equipe responsável.

### 25. Checklist diário e glossário

#### Antes da saída

- Conferir data, horário, Rota, equipe, veículos e capacidade.
- Conferir reservas, pontos, nomes, documentos e PAGO manual.
- Emitir/enviar os bilhetes e avisar alterações relevantes aos clientes.
- Preparar os manifestos de cada veículo/trecho online e testar o acesso operacional.
- Conferir câmera, bateria, internet e permissões necessárias.

#### Durante e depois

- Selecionar o veículo/trecho correto e confirmar os embarques.
- Revisar pendências de sincronização antes de fechar.
- Desembarcar passageiros e registrar chegada.
- Conferir a finalização no painel e os indicadores de ocupação/vendas.

| Termo | Significado |
| --- | --- |
| Rota | Modelo do percurso, com cidades, endereços, paradas e duração. |
| Pacote | Produto comercial turístico, simples ou com roteiro de vários destinos. |
| Viagem comercial | Saída vendida e agendada, com datas e alocações. |
| Deslocamento/trecho | Uma etapa operacional, como ida, volta ou ligação entre cidades. |
| Segmento | Parte de um trecho entre dois pontos consecutivos, usada no cálculo de vagas. |
| Alocação | Veículo e equipe que atendem uma viagem ou seus deslocamentos. |
| Manifesto | Lista operacional preparada de passageiros de um veículo/trecho. |
| Reserva familiar | Grupo comercial com responsável e telefone compartilhado. |
| Bilhete | Credencial individual do passageiro, com link e QR para os trechos contratados. |
| Franquia | Quantidade de unidades comerciais incluídas no ciclo mensal. |
| PAGO | Registro manual do recebimento conferido pela empresa. |

### 26. Financeiro da empresa e pagamento da assinatura

O administrador encontra as cobranças da assinatura em **Meu plano** e no menu **Financeiro e cobranças**. Cada demonstrativo apresenta período, plano, utilização, excedentes, setup quando aplicável, total e prazo para pagamento.

Quando houver período de teste, ele aparece em **Meu plano**. A franquia do plano vale para o teste, sem cobrança de excedentes. Na data do término, começa uma nova franquia e é enviada somente a cobrança de setup, quando houver. A primeira mensalidade e os excedentes são cobrados após 30 dias de uso. Os ciclos seguintes também duram 30 dias e são cobrados no fechamento. Contratos anteriores preservam suas condições.

Um dia antes da cobrança, o aviso é parcial e ainda pode mudar. Aguarde a cobrança definitiva. Use **Pagar agora** para acessar o pagamento seguro, também enviado por e-mail e WhatsApp. A confirmação é automática após aprovação; o retorno do checkout pode aguardar alguns instantes pela conferência.

O prazo é de dois dias úteis a partir do dia seguinte ao fechamento, no horário de Brasília, excluindo fins de semana e feriados do calendário nacional, incluindo a Sexta-feira da Paixão. Pontos facultativos e feriados estaduais ou municipais não entram nesse calendário.

Cobranças manuais ou antigas podem apresentar chave Pix, favorecido e Copia e Cola, com baixa pela Nexus. Nesses casos, siga as instruções do demonstrativo. Em caso de divergência ou pagamento em conferência, informe à Nexus a referência da cobrança e os dados do pagamento.

Sem confirmação no prazo, novas operações ficam bloqueadas. A empresa mantém acesso às consultas, ao financeiro e aos embarques de viagens já vendidas. A confirmação remove a restrição da cobrança paga; outros débitos vencidos podem manter o bloqueio. Uma suspensão administrativa segue tratamento separado.

Os avisos são enviados por e-mail aos administradores ativos e por WhatsApp ao telefone de contato da empresa. Mantenha seus dados atualizados.


<a id="manual-nexus"></a>
## 4. Manual completo da administração Nexus

### 1. Acesso à plataforma

Manual exclusivo da equipe Nexus. Acesse <https://rotafy.nexusdataanalytics.tech/nexus> com seu e-mail e senha de superadmin. Esse perfil não possui empresa operacional padrão. Para operar viagens, utilize uma conta cadastrada na empresa.

A senha exige pelo menos 8 caracteres, uma letra maiúscula e um caractere especial. Utilize **Esqueci minha senha** no acesso Nexus quando necessário. Não compartilhe credenciais.

#### Perfis da equipe Nexus

O **Administrador Nexus completo** mantém acesso a todas as áreas. O perfil **Equipe Nexus** acessa empresas e o histórico das ações de cadastro, edição, ativação e suspensão. Esse perfil não acessa configurações, financeiro, planos e assinaturas, relatórios financeiros ou a gestão dos usuários internos. Na criação de uma empresa, pode escolher um plano do catálogo público; alterações posteriores de assinatura cabem ao administrador completo.

Para cadastrar uma pessoa da Nexus, entre com um administrador completo, abra **Equipe Nexus** e clique em **Adicionar usuário Nexus**. Informe nome, e-mail, senha inicial e perfil. O perfil restrito é sugerido por padrão. Cada pessoa entra pelo endereço `/nexus` com suas próprias credenciais.

Na mesma tela, altere o perfil ou suspenda/ative o acesso. Suspensões e mudanças de perfil encerram as sessões existentes. O sistema exige pelo menos um administrador completo ativo. Os administradores existentes mantêm acesso completo após a atualização.

#### Log de acesso da equipe

Em **Equipe Nexus**, o administrador completo consulta **Log de acesso dos colaboradores Nexus**. Filtre por colaborador, entrada/saída e período. Os horários seguem Brasília e são exibidos até 200 registros por consulta. O histórico reúne entradas autenticadas e saídas pelo botão **Sair**, incluindo os registros anteriores disponíveis. Fechar o navegador ou expirar a sessão não registra uma saída. Tentativas de senha inválida não fazem parte dessa consulta.

### 2. Empresas, planos e assinaturas

**Exclusivo do superadmin.** Entre em `/nexus`. Esta seção descreve os menus, sem divulgar credenciais da plataforma.

#### Empresas

Cadastre ou edite dados comerciais, contato e perfil operacional. O CPF/CNPJ é obrigatório e validado. Crie o primeiro administrador e selecione o plano. Utilize suspender/ativar conforme o contrato, preservando os dados históricos.

Ao suspender uma empresa, o sistema também suspende os envios e agenda automaticamente a desconexão do WhatsApp. A solicitação permanece registrada para nova tentativa se o serviço estiver indisponível. Reativar a empresa não reconecta o WhatsApp: o administrador deve solicitar a conexão no painel.

O cadastro de novas empresas é exclusivo da equipe Nexus, incluindo o perfil restrito **Equipe Nexus**. O cliente não possui opção de cadastro no login. Após salvar, utilize **Enviar acesso por e-mail**, **Enviar acesso por WhatsApp** ou **Enviar pelos dois canais**. O destinatário de e-mail é o primeiro administrador ativo da empresa; o WhatsApp utiliza o telefone informado no cadastro da empresa. As mensagens incluem os dados cadastrais, identificador, e-mail de login e um link para definir senha, válido por 24 horas. A senha inicial não é enviada em texto.

O WhatsApp utiliza a sessão da Nexus definida para comunicação/cobrança, sem exigir pareamento prévio da empresa recém-criada. Acompanhe o resultado nessa tela. Se faltar configuração, a empresa permanece cadastrada; corrija a configuração e envie novamente. Também é possível usar **Enviar acesso** na lista de empresas. Um novo convite invalida os links anteriores.

Na ação de gerenciamento do plano da empresa, confira a empresa selecionada e sua assinatura; não confunda o catálogo global de planos com o vínculo daquela empresa.

#### Planos e assinaturas

1. Abra **Planos e assinaturas**.
2. Configure Basic, Professional, Enterprise ou um plano adicional.
3. Defina nome, franquia mensal, mensalidade e valor por unidade extra.
4. Publique as condições e selecione a empresa em **Assinatura e consumo**.
5. Vincule o plano e a data inicial ou programe a mudança para o próximo ciclo.
6. Confira ciclos, consumo e demonstrativos por empresa.

Alterar o catálogo não reescreve os valores históricos. Uma mudança agendada fixa a versão escolhida para o próximo ciclo. Arquivar um plano impede novas escolhas; contratos existentes preservam sua continuidade conforme as regras da assinatura.

#### Atividades

Consulte **Atividades** para acompanhar alterações registradas pelo sistema. A consulta respeita o perfil e o espaço de acesso. Os eventos não revelam senhas ou links privados. O histórico auxilia conferência, mas não substitui documentos financeiros ou a política de backup da operação.

### 3. Cadastro de empresas

1. Abra **Empresas** e **Cadastrar empresa**.
2. Preencha nome comercial, razão social, telefone/WhatsApp, CPF/CNPJ válido e identificador de acesso.
3. O identificador aceita somente letras minúsculas sem acentos e números, de 2 a 50 caracteres. Não utilize espaços, sublinhados, hífens ou outros caracteres especiais.
4. Escolha **Turismo e transfers** ou **Transporte regular**.
5. Escolha o plano e informe nome, e-mail e senha do primeiro administrador. Todos os campos são obrigatórios.
6. Confira e salve. Oriente o administrador sobre o identificador de acesso.

O perfil operacional determina os módulos; o plano determina as condições comerciais. Viagens turísticas abertas podem impedir a troca do perfil. Suspender uma empresa preserva seus registros.

### 4. Configurações de comunicação

Abra **Configurações** no painel Nexus. Informe as credenciais dos serviços de mensagens e e-mail, configure o e-mail remetente autorizado e salve. Um campo de chave vazio preserva a chave existente. Utilize a opção de remover somente quando desejar desativar a credencial correspondente.

Mantenha as chaves restritas à equipe autorizada. Não inclua credenciais em capturas ou chamados. Confira a autorização do remetente junto ao serviço de e-mail.

#### WhatsApp de cada empresa

Cada empresa utiliza seu número e uma sessão exclusiva. Novos cadastros agendam a criação da sessão automaticamente. O administrador da empresa encontra o menu **WhatsApp**, confere o telefone do cadastro da empresa e escaneia o QR Code no próprio Rotafy. O sistema confere o número antes de liberar os envios. A criação da empresa não aguarda a disponibilidade do serviço de mensagens.

1. Localize a empresa em **WhatsApp de cada empresa**.
2. Confira o **WhatsApp de envio**. O telefone de contato aparece como sugestão; ajuste para o número conectado. Utilize + e código do país para números internacionais.
3. Ative **Identificar e salvar a sessão automaticamente pelo telefone**. O telefone é salvo ao sair do campo.
4. Defina **Habilitar envios**. O sistema identifica uma única sessão conectada correspondente ao telefone e salva o ID automaticamente.
5. Acompanhe o estado na tela. Se a sessão ainda não existir, a busca continuará a cada minuto, mesmo com a tela fechada.

O pareamento no celular continua necessário. A identificação automática por telefone descrita acima é uma alternativa de suporte Nexus; a empresa também pode usar o QR no próprio Rotafy. Alterações manuais da Nexus prevalecem sobre a conexão automática até nova solicitação explícita do administrador da empresa. Duplicidades e sessões vinculadas a outra empresa impedem a associação automática. Empresas suspensas não são consultadas. Os vínculos existentes são preservados até a ativação do modo automático. Para configuração manual, desmarque a identificação automática e informe o ID conferido no serviço.

#### Conferir envios

Em **Configurações → Cobrança mensal**, utilize **Testar envio de cobrança**. Salve primeiro o remetente e a sessão WhatsApp de cobrança. Informe seu e-mail ou telefone de teste e clique no botão do canal desejado. O teste utiliza a configuração salva e funciona mesmo com a cobrança automática desativada. A mensagem é identificada como teste e não cria fatura, altera assinatura ou solicita pagamento.

O teste utiliza o mesmo modelo da cobrança definitiva, com valores ilustrativos e aviso **TESTE DE COBRANÇA — NÃO PAGAR**. O e-mail apresenta um resumo organizado do ciclo e dos valores, com QR Code incorporado. No WhatsApp, o QR Code é enviado como imagem com o resumo na legenda. O Copia e Cola acompanha o e-mail e a legenda quando couber.

Acompanhe o resultado na própria tela: aguardando, enviando, aceito pelo serviço, falha ou envio incerto. Aceito não confirma entrega ou leitura. Em envio incerto, confira o recebimento antes de solicitar outro teste. Testes que não forem processados em 15 minutos são descartados. Esses envios também aparecem no histórico financeiro como **Teste de cobrança**.

Envie um convite a um colaborador autorizado e confira o recebimento. Consulte o histórico antes de reenviar. A aceitação pelo serviço de e-mail não garante entrega na caixa de entrada: confira também o spam e o destinatário.

Confirmações, cancelamentos, marcação PAGO, bilhetes e convites utilizam os canais configurados conforme a ação executada. Confira os destinatários antes de enviar.

### 5. Rotina do superadmin

- Confira novas empresas, perfil operacional e plano.
- Acompanhe ciclos mensais, franquias, excedentes e demonstrativos.
- Consulte **Atividades** para conferir alterações registradas.
- Revise a associação da sessão quando uma empresa trocar de número.
- Apoie os administradores sem compartilhar sua conta Nexus.

### 6. Dúvidas frequentes

#### Como definir o plano de uma empresa?

Utilize o gerenciamento da assinatura da empresa. O catálogo cadastra as condições comerciais; a assinatura vincula o plano à empresa.

#### A sessão não foi encontrada?

Confira o telefone e o pareamento. A busca depende do telefone informado pelo serviço. Se necessário, confira e selecione o ID manualmente. A busca não cria nem conecta sessões.

#### O e-mail falhou?

Confira remetente autorizado, credenciais e destinatário. Consulte o histórico antes de reenviar o convite. Não exponha chaves ao solicitar suporte.

#### Onde fica o manual da empresa?

Acesse `/ajuda` para o manual da equipe e a apresentação comercial. A ajuda do painel Nexus fica em `/nexus/ajuda`.

### 7. Setup, teste e cobranças da assinatura

#### Configurar e ativar

1. Entre em **Configurações**, na seção **Cobrança e período de teste**.
2. Marque **Usar InfinitePay nas novas cobranças**, informe **Identificador InfinitePay (InfiniteTag)**, sem `$`, **Taxa de setup (R$)** e **Prazo de teste (dias)**. O identificador deve pertencer à conta da Nexus que receberá os pagamentos.
3. Selecione ou informe o **ID da sessão WhatsApp de cobrança da Nexus**. As cobranças saem pelo número da Nexus, utilizando as credenciais de comunicação configuradas no painel.
4. Confira o e-mail remetente e os canais de comunicação.
5. Marque **Ativar avisos e cobranças mensais automáticas** e salve.

A configuração começa desativada. Configure e ative antes de cadastrar clientes com teste. Setup e prazo de teste são registrados na nova contratação; alterações posteriores não modificam essas condições nos clientes já cadastrados. Desativar a cobrança automática pausa novos fechamentos e envios, preservando débitos e pagamentos existentes. A confirmação de pagamentos já efetuados continua sendo processada.

Os dados de **Pix manual** ficam em uma seção separada. Utilize essa configuração para cobranças manuais: chave, favorecido e, opcionalmente, Pix Copia e Cola sem valor definido. Cobranças antigas preservam o meio de pagamento que receberam quando foram emitidas.

#### Novos clientes e período de teste

No cadastro, a empresa recebe a franquia do plano durante o teste, sem cobrança de setup, mensalidade ou excedentes. A criação de viagens além dessa franquia é impedida durante o teste.

Exemplo: cadastro em **10/10**, com **7 dias** de teste. Em **17/10**, o sistema registra somente o **setup**, gera o link e agenda o envio por e-mail e WhatsApp. Nessa data começa o primeiro ciclo de 30 dias, com franquia nova. Em **16/11**, cobra a **primeira mensalidade e os excedentes desse ciclo**. A utilização do teste não é transferida como excedente para o período pago. Setup configurado como zero não gera cobrança separada.

Cada renovação cobra a mensalidade e os excedentes do período de 30 dias que acabou de ser utilizado. O setup é uma cobrança única e separada. Como os períodos são fixos de 30 dias, o dia do mês pode variar: 17/10 → 16/11 → 16/12 → 15/01. A franquia também é renovada a cada ciclo de 30 dias.

Clientes anteriores à ativação mantêm seus ciclos e não recebem setup ou teste retroativos. Novas cobranças definitivas desses contratos podem utilizar o link automático quando a integração estiver habilitada.

#### Calendário e mensagens automáticas

Um dia antes da cobrança, a empresa recebe um aviso parcial, sujeito a alteração e sem link para pagamento. Na data prevista, o sistema consolida os valores, preserva a cobrança no financeiro e disponibiliza o link de pagamento. Se houver falha na geração do link, a cobrança permanece registrada e o sistema tenta novamente. O envio definitivo aguarda a disponibilidade do link.

O prazo termina ao fim do segundo dia útil contado a partir do dia seguinte ao fechamento, no horário de Brasília. Sábados, domingos e feriados do calendário nacional, incluindo a Sexta-feira da Paixão, não entram na contagem. Pontos facultativos e feriados estaduais ou municipais não são considerados.

Os e-mails são enviados aos administradores ativos da empresa. O WhatsApp utiliza o telefone de contato cadastrado na empresa. Mantenha esses contatos atualizados.

#### Acompanhar e dar baixa

Abra **Financeiro e cobranças**. Utilize o filtro de situação para consultar avisos parciais, cobranças abertas, vencidas, pagas e canceladas. Cada cobrança apresenta ciclo, plano, franquia, utilização, excedentes, valor total, prazo e referência.

Nas cobranças com link, a confirmação é automática após verificação do pagamento. O painel mostra **Pagar agora**, situação e identificação da transação; o cliente recebe confirmação por e-mail e WhatsApp. A página de retorno aguarda a conferência do sistema.

Consulte **Confirmações automáticas de pagamento** para acompanhar verificações pendentes, confirmadas e situações que exigem conferência. Pagamentos com valor divergente ou após cancelamento/baixa ficam sinalizados para análise. A confirmação repetida da mesma transação não gera outra baixa.

Se a geração do link for recusada, confira a InfiniteTag e use **Tentar gerar link novamente**. Essa ação permite corrigir a conta de uma solicitação recusada que ainda não disponibilizou link. Links já emitidos preservam a conta de recebimento original.

Para um recebimento conferido fora desse fluxo, use **Baixa manual excepcional**; nas cobranças antigas, **Confirmar recebimento do Pix**. Informe data/hora e referência. O usuário da baixa fica registrado. Não é possível dar baixa em aviso parcial ou informar uma data futura.

#### Bloqueio e liberação

Se não houver confirmação até o prazo, novas operações ficam bloqueadas e a empresa recebe aviso por e-mail e WhatsApp. Consultas, acesso ao financeiro, leitura de bilhetes e operação dos embarques e deslocamentos já vendidos permanecem disponíveis.

A baixa retira a restrição daquela cobrança. Se houver outras cobranças vencidas, a empresa continua restrita. Uma suspensão administrativa permanece independente e não é removida pelo pagamento.

A ação **Cancelar cobrança** preserva o histórico e retira aquela cobrança da apuração de bloqueio. Não representa devolução de dinheiro nem cancela um link externo já emitido. Um pagamento posterior será sinalizado para conferência. Não cancele uma cobrança para registrar um recebimento; utilize a baixa correspondente.

#### Histórico dos envios financeiros

O painel mostra o evento, canal, empresa, situação e motivo de falha de cada comunicação. Aceitação pelo serviço não significa entrega ou leitura. Um WhatsApp com resultado incerto não é repetido automaticamente. Confira o recebimento antes de qualquer nova comunicação. Falhas de comunicação não desfazem uma baixa registrada.

<a id="recursos-com-menu-oculto"></a>
## 5. Recursos implementados com acesso oculto no menu

O menu **Página pública e integrações** está oculto por configuração da interface. O código das páginas e endpoints permanece no projeto. Ocultar o menu não desativa as rotas públicas nem substitui uma restrição de acesso no backend.

### Página da empresa e solicitações públicas

- Página por empresa em `/comprar/{slug}`, com identidade visual e viagens publicadas.
- Detalhes e solicitação de reserva em `/comprar/{slug}/{trip_id}`.
- Novas viagens privadas por padrão. A oferta pública considera publicação, situação agendada e data futura; viagens concluídas e canceladas não são ofertadas.
- Cadastro do responsável, telefone da família, passageiros e pontos dos deslocamentos.
- Regra documental vinculada ao roteiro, incluindo exigência de CPF para viagens interestaduais e exceções identificadas.
- Conferência de capacidade e sugestão que mantém a família reunida no veículo.
- Reserva inicialmente pendente, com bloqueio de lugares por 15 minutos, exigindo confirmação pela agência.
- Link privado para acompanhamento, protegido por uma credencial própria da reserva.
- Sinalização à agência quando não há disponibilidade, com agrupamento de alertas repetidos.
- Não há recebimento automático do pagamento do passageiro neste módulo; a marcação PAGO continua manual.

### Integrações de reservas com sites externos

Existem endpoints de integração e chaves por empresa, com identificação, validade e possibilidade de revogação. As solicitações externas usam as regras de disponibilidade, documentação e reserva do sistema. Credenciais de integração não equivalem a uma sessão administrativa e não devem ser expostas em uma página pública ou no código do navegador.

### Identidade visual

O projeto mantém recursos de nome, cores e logotipo para identificação da empresa e apresentação pública. O menu independente **Identidade da empresa** não é apresentado na navegação administrativa atual. A existência da implementação não significa que o menu removido esteja disponível ao usuário.

<a id="arquitetura"></a>
## 6. Arquitetura, dados e operação técnica

### Componentes da solução

| Componente | Implementação e finalidade |
| --- | --- |
| Frontend web | React, TypeScript e Vite; painel responsivo, formulários, relatórios e páginas de consulta. |
| Camada visual | Estilos e componentes compartilhados, com verde petróleo para ações e agrupamentos do roteiro/reserva. |
| API | Python com FastAPI; contrato versionado em `/api/v1` e validação de entrada com Pydantic. |
| Persistência | PostgreSQL com extensão PostGIS na imagem de publicação, SQLAlchemy e consultas parametrizadas. |
| Evolução do banco | Migrações Alembic incrementais; o banco não precisa ser recriado a cada atualização. |
| Aplicativo de campo | Flutter/Dart, versão Android; acesso aos mesmos serviços e regras do backend. |
| Dados locais Android | SQLite com conteúdo cifrado; chaves e sessão em armazenamento seguro do dispositivo. |
| Aplicação web instalável | PWA com service worker, preparação de manifestos e fila local de ações. |
| Publicação | Docker Compose, frontend servido por Nginx e entrada HTTPS pelo Traefik da VPS. |
| Tarefas assíncronas | Workers separados para ciclos/cobranças, e-mails e WhatsApp. |
| Pagamento da assinatura | Checkout externo, retorno, webhook e verificação independente antes da baixa. |
| Documentação | Fontes no repositório e geração de HTML, PDF e apresentação para publicação. |

### Estrutura lógica dos dados

| Grupo | Registros principais |
| --- | --- |
| Plataforma | Usuários Nexus, sessões, configurações e auditoria. |
| Empresas | Dados cadastrais, perfil operacional, contato e identidade visual. |
| Equipe | Usuários da empresa, funções, sessões, convites e redefinições. |
| Comercial SaaS | Planos, versões das condições, assinaturas, períodos e eventos de consumo. |
| Operação | Veículos, Rotas, paradas, pacotes, viagens e deslocamentos. |
| Alocações | Veículos por viagem, motoristas, guias e etapas atendidas. |
| Reservas | Responsável, telefone, passageiros, trechos, alocações e locais específicos. |
| Embarque | Bilhetes, estado do passageiro, eventos, versões e chaves de operação. |
| Chegada | Histórico por veículo/deslocamento, usuário, horários e localização quando enviada. |
| Cobranças Nexus | Faturas, composição de valores, vencimento, baixa, checkout e eventos de pagamento. |
| Comunicação | Filas de mensagens, tentativas, situações, referências e resultados dos envios. |
| Importação | Prévia, validações, lote, referência da família e aplicação transacional. |

### Isolamento multiempresa

Os registros operacionais são vinculados à empresa. O PostgreSQL aplica políticas de segurança por linha, com contexto de empresa limitado à transação. Relações compostas incluem a empresa para impedir vínculos operacionais incompatíveis entre clientes.

A aplicação usa papéis diferentes para o acesso operacional e a administração da plataforma. O papel de migração é separado dos papéis utilizados pela API. Usuários da empresa não acessam tabelas de administração Nexus por meio do seu papel de banco.

O fato de compartilhar o banco não permite compartilhar automaticamente usuários ou dados. A mesma pessoa pode ter contas diferentes em empresas diferentes, inclusive com o mesmo e-mail.

### Consistência e sincronização

Comandos críticos usam transações, validação de estado e identificação da operação. A capacidade é conferida novamente ao criar ou confirmar a reserva, não apenas quando a tela apresenta a sugestão de veículo.

O consumo da franquia e a criação/cancelamento da viagem são coordenados para evitar lançamentos duplicados. As operações de embarque usam versões e chaves de operação para que uma sincronização repetida não seja interpretada como outro embarque.

Ação gravada offline é uma intenção local. A confirmação depende de aceitação pelo servidor; alterações concorrentes, cancelamentos ou mudanças de manifesto podem gerar conflito para revisão.

### Filas de comunicação e cobrança

Os eventos de negócio alimentam filas persistidas. Workers processam envios, tentativas e expirações. O painel diferencia pendência, aceitação, falha e resultado incerto. Uma falha no canal não desfaz a reserva ou a baixa que originou a comunicação.

A aceitação pelo serviço de mensagens não comprova entrega ou leitura. Envios de WhatsApp com resultado incerto exigem conferência antes de repetir, evitando duplicidade de convites ou cobranças.

Na assinatura automática, a fatura é registrada antes da emissão do link. O envio definitivo aguarda um link válido. A confirmação de pagamento depende da consulta ao provedor e da conferência de valor, referência e reutilização de transação. Eventos divergentes são encaminhados para análise.

### Configuração e publicação

A instalação independente de produção utiliza o domínio `rotafy.nexusdataanalytics.tech`. O arquivo `compose.production.yaml` descreve banco, migração, bootstrap, API, painel e workers. Os serviços da aplicação são integrados à rede do Traefik existente, sem publicar diretamente a porta do banco no host.

As configurações comerciais e de comunicação são administradas no painel Nexus conforme as permissões. Variáveis de infraestrutura, senhas de banco e material criptográfico continuam sob gestão operacional; não são expostos neste documento.

| Script | Finalidade |
| --- | --- |
| `scripts/install_clean_vps.sh` | Instalação limpa, para ambiente novo e finalidade explicitamente autorizada. |
| `scripts/install_vps.sh` | Rotina de instalação descrita nos documentos de implantação. |
| `scripts/update_vps.sh` | Atualização de instalação existente, preservando dados e aplicando migrações. |
| `scripts/migrate_vps.sh` | Apoio à execução de migrações do banco conforme a rotina operacional. |
| `scripts/build_mobile.ps1` | Validação e compilação do aplicativo Android. |
| `scripts/generate_documentation.py` | Geração dos materiais de documentação. |
| `scripts/diagnose_security.sh` | Diagnóstico somente leitura de portas, SSH, containers e cabeçalhos HTTPS. |
| `scripts/diagnose_traefik.py` | Apoio à identificação da configuração do proxy de publicação. |
| `scripts/restore_drill.py` | Ensaio de restauração em ambiente isolado. |

Atualização da instalação existente:

```bash
cd /opt/rotafy-tech
git pull --ff-only origin main
bash scripts/update_vps.sh
```

Atualizar não significa apagar volumes. Não usar uma instalação limpa como substituto de atualização de um ambiente com dados que precisam ser preservados.

### Aplicativo Android e distribuição

O aplicativo de motorista/guia é compilado em Flutter e distribuído como APK Android assinado. A configuração de compilação permite definir o nome, o identificador da empresa e a URL da API. O endpoint de produção usa HTTPS no domínio correto.

A versão identificada no projeto é **1.6.0, código 11**. O artefato versionado de distribuição local encontra-se em `artifacts/mobile/nexus-rotafy-1.6.0.apk`, quando gerado no ambiente de desenvolvimento. A pasta de artefatos não faz parte do código versionado no Git.

Atualizar sobre uma instalação com a mesma assinatura preserva os dados locais conforme as regras do Android. Desinstalar pode remover dados ainda não sincronizados. Backend e painel devem estar compatíveis antes de disponibilizar uma atualização operacional.

Este documento descreve o aplicativo Android existente para motorista/guia. O acesso atual do passageiro ocorre pelo bilhete web privado.

### Backup e continuidade

A configuração de produção inclui suporte a backup externo cifrado e procedimento de restauração em ambiente isolado. Sua operação depende da configuração do destino e do agendamento na instalação. Ter o recurso no repositório não comprova a execução de backups na VPS.

O plano de restauração deve preservar tanto o banco quanto a chave local de proteção das integrações. Restaurar apenas o banco pode tornar credenciais cifradas inutilizáveis se a chave correspondente for perdida.

<a id="seguranca"></a>
## 7. Segurança e evidências de validação

### Proteções presentes

- Senhas armazenadas com hash Argon2; política de oito a 128 caracteres, com letra maiúscula e caractere especial.
- Sessões opacas, com hash no servidor, expiração, cookie HttpOnly e Secure em produção.
- Verificação de origem e proteção CSRF nas alterações autenticadas.
- Limitação de tentativas de autenticação e recuperação.
- Convites e redefinições de uso único, com validade e revogação de sessões após redefinição.
- Permissões verificadas no backend, além da visibilidade dos menus.
- Isolamento por empresa e auditoria dos eventos relevantes.
- Links privados de bilhete e acompanhamento com credenciais próprias, sem exposição em query string nos fluxos que usam fragmento.
- Chaves de comunicação cifradas e não devolvidas integralmente pela API.
- Validação e limites para uploads, imagens, planilhas e corpos de requisição.
- Remoção de valores de entrada das respostas de validação para evitar repetir senhas e dados pessoais.
- Cabeçalhos de proteção HTTP, incluindo HSTS, bloqueio de enquadramento e política de conteúdo.
- Logs da aplicação sem corpos, senhas ou valores de tokens.
- Dados locais Android cifrados e biometria forte opcional para recuperação das credenciais.
- Verificação independente dos eventos de pagamento antes de dar baixa.

### Evidências disponíveis em 16/10/2026

A revisão de segurança registrou **348 testes backend aprovados**, incluindo testes de isolamento, permissões, sessão, validação, reservas e pagamentos. As consultas de vulnerabilidades conhecidas das dependências web e Python não reportaram ocorrências na data da execução.

O diagnóstico enviado da VPS identificou a versão publicada `git-c38047e8df68`, firewall ativo e serviços do Rotafy sem portas publicadas diretamente no host. API e workers executavam como usuário `rotafy`, sem modo privilegiado e sem socket Docker. Os cabeçalhos foram confirmados na página, no service worker e na API.

Essas evidências têm escopo e data. Não constituem garantia de ausência de vulnerabilidades, teste de invasão integral, certificação de conformidade ou confirmação da restauração de backups. O relatório técnico de segurança registra os achados, correções e limites da avaliação.

<a id="repositorio"></a>
## 8. Mapa do repositório e referências internas

### Organização

| Caminho | Conteúdo |
| --- | --- |
| `backend/app/` | API, autenticação, operação, reservas, relatórios, comunicação e cobrança. |
| `backend/app/billing/` | Planos, consumo, ciclos, cobranças, notificações e verificação de pagamentos. |
| `backend/migrations/` | Histórico incremental de evolução do banco. |
| `backend/tests/` | Testes automatizados da API e das regras de negócio. |
| `frontend/src/` | Interface web administrativa, operacional e consultas públicas. |
| `frontend/tests/` | Testes de interface e fluxos de navegador. |
| `frontend/public/documentacao/` | Materiais publicados de ajuda e apresentação. |
| `mobile/lib/` | Aplicativo Flutter de campo, cliente da API e persistência local. |
| `mobile/android/` | Configuração nativa Android e compilação. |
| `infra/` | Preparação de banco e recursos de backup/infraestrutura. |
| `scripts/` | Instalação, atualização, compilação, documentação e diagnósticos. |
| `docs/` | Manuais, guias funcionais, evidências e documentos técnicos. |
| `compose.yaml` | Ambiente de desenvolvimento local. |
| `compose.production.yaml` | Serviços e redes da instalação de produção. |
| `PROJETO_COMPLETO_ROTAFY.md` | Este documento consolidado do produto e do projeto. |

### Referências que fundamentam a consolidação

- `docs/publicacao/manual.md`: manual operacional da empresa.
- `docs/publicacao/manual-superadmin.md`: manual da administração Nexus.
- `docs/ROTAS_REUTILIZAVEIS.md`: catálogo e cópia das Rotas nas viagens.
- `docs/PACOTES_MULTIDESTINOS.md`: destinos, roteiro e consumo do pacote.
- `docs/RESERVAS_E_DISPONIBILIDADE.md`: capacidade, grupos e reservas.
- `docs/EMBARQUE_HOTEIS.md`: endereços específicos por reserva e roteiro do veículo.
- `docs/BILHETE_UNICO.md`: bilhete individual compartilhado entre etapas.
- `docs/OFFLINE_E_SINCRONIZACAO.md`: preparação, fila e conflitos.
- `docs/BIOMETRIA_MOBILE.md`: autenticação biométrica opcional.
- `docs/RELATORIOS.md`: indicadores e exportações.
- `docs/PLANOS_E_ASSINATURAS.md`: planos, ciclos e consumo.
- `docs/INFINITEPAY_E_TESTE.md`: setup, teste, mensalidades e confirmação automática.
- `docs/INSTALACAO_VPS.md` e `docs/IMPLANTACAO_E_OPERACAO.md`: instalação e operação.
- `docs/SECURITY_REVIEW_2026-10-16.md`: evidências da revisão de segurança.

Os materiais mais antigos do repositório registram etapas históricas e podem conter nomes de menus, caminhos ou condições anteriores. Esta consolidação usa os manuais atuais e a implementação vigente para descrever o produto na data informada.
