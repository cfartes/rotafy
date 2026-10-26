## 1. Conheça o Nexus Rotafy {#visao-geral}

O **Nexus Rotafy** organiza a operação de empresas de turismo e transporte: cadastros, rotas, viagens, pacotes, reservas familiares, bilhetes individuais, embarque, comunicação e relatórios. A equipe administrativa usa o painel web; motoristas e guias usam o painel operacional ou o aplicativo Android.

Este manual descreve a implementação disponível em **26/10/2026**. As imagens utilizam dados demonstrativos. Os menus dependem do perfil do usuário e do tipo de empresa. Uma captura pode mostrar uma seleção de filtros diferente da sua operação.

**Endereço do painel:** <https://rotafy.nexusdataanalytics.tech>. O cadastro da empresa é realizado pela equipe comercial Nexus. A central de documentação utiliza `/ajuda`.

### O fluxo de trabalho

1. Cadastre a empresa, escolha seu perfil operacional e o plano.
2. Cadastre a equipe e os veículos.
3. Prepare as rotas reutilizáveis e, quando necessário, os modelos de pacote.
4. Agende a viagem e atribua veículos, motoristas e guias.
5. Venda a reserva, confira a capacidade e marque PAGO quando recebido.
6. Emita o bilhete individual e envie o link ao cliente.
7. Prepare os manifestos, realize os embarques e registre a chegada.
8. Consulte a finalização, a ocupação, as vendas e o consumo do plano.

<aside class="note"><strong>Três conceitos diferentes.</strong> Rota é o percurso reutilizável. Pacote é o produto turístico e seu roteiro. Viagem é a saída agendada, com datas, horários, equipe e veículos. Cadastrar uma Rota ou um modelo de pacote não agenda uma saída nem consome a franquia.</aside>

## 2. Perfis e permissões {#perfis}

Cada empresa tem seu espaço e seus usuários. Um profissional que atende duas empresas deve possuir um cadastro em cada uma. No painel web, o identificador de acesso da empresa define em qual espaço ele entra.

| Perfil | O que utiliza |
| --- | --- |
| Administrador da empresa | Cadastros operacionais, vendas, relatórios, equipe, convites, identidade da empresa e consulta do próprio plano. |
| Atendente | Cadastros operacionais, reservas, bilhetes e relatórios gerenciais da empresa. Não administra usuários nem os planos da plataforma. |
| Motorista | Viagens e deslocamentos atribuídos; manifesto, leitura de QR, embarque, desembarque, saída e chegada. |
| Guia | Mesmos recursos operacionais do motorista, nos deslocamentos atribuídos. Guia é opcional. |
| Passageiro | Consulta do bilhete privado pelo link recebido; não acessa o painel administrativo. |

### Turismo e transporte regular

**Turismo e transfers:** permite viagens simples e pacotes com vários destinos, incluindo passeios diários com retorno à base e circuitos com permanência entre cidades.

**Transporte regular:** utiliza viagens simples, rotas, frota, reservas e embarque. Os controles turísticos de pacotes ficam ocultos.

O perfil operacional não é o plano contratado. Basic, Professional e Enterprise são planos comerciais configurados pela Nexus. A troca do tipo de empresa é controlada pela Nexus e pode ser bloqueada enquanto houver viagens turísticas abertas.

## 3. Primeiro acesso e cadastro da empresa {#primeiro-acesso}

1. Entre em contato com a equipe comercial Nexus para definir o plano e informar os dados da empresa e do administrador.
2. A Nexus cadastra a empresa e define o perfil **Turismo e transfers** ou **Transporte regular**, conforme a operação.
3. Receba por e-mail ou WhatsApp os dados cadastrais, a página de acesso, o identificador da empresa e o e-mail de login.
4. Abra o link recebido para definir sua senha. Ele é válido por 24 horas e pode ser usado uma única vez.
5. Defina uma senha com pelo menos 8 caracteres, uma letra maiúscula e um caractere especial.
6. Entre no painel com o identificador da empresa, seu e-mail e a senha definida.

Todos os campos do cadastro são obrigatórios. O identificador de acesso deve conter somente letras minúsculas sem acentos e números, de 2 a 50 caracteres. Não utilize espaços, sublinhado (_), hífen (-) ou outros caracteres especiais. Por exemplo, `agenciaexemplo` é um identificador de acesso, não uma senha. Guarde-o junto das orientações entregues à equipe.

O cliente não realiza cadastro público. Se o convite expirar, solicite um novo envio à equipe Nexus ou utilize **Esqueci minha senha** no acesso da empresa.

O administrador pode editar o cadastro clicando no bloco com o logo e o nome da empresa no menu lateral. O formulário permite atualizar nome comercial, razão social, CPF/CNPJ, telefone/WhatsApp e cores. O identificador de acesso aparece somente para consulta. A alteração do telefone suspende os envios pelo número anterior; confira a conexão no menu **WhatsApp**.

## 4. Login, senhas e recuperação {#acesso}

### Entrar no painel web

1. Abra o endereço do sistema em um navegador atualizado.
2. Informe o identificador da empresa, o e-mail cadastrado e a senha.
3. Clique em **Acessar painel**. Os menus apresentados correspondem ao perfil do usuário.

### Definir a senha pelo convite

Abra o link recebido por e-mail ou WhatsApp, escolha a nova senha e confirme. O convite vale **24 horas** e só pode ser usado uma vez. Depois, entre com o e-mail cadastrado; o número de WhatsApp não substitui o e-mail de login.

### Esqueci minha senha

Use **Esqueci minha senha** no login. Informe e-mail e identificador da empresa. O link por e-mail vale **uma hora**. Por privacidade, a resposta pública não confirma se a conta existe.

O administrador também pode gerar um link manual de recuperação para um colaborador, válido por **30 minutos**. A troca de senha encerra as sessões anteriores daquele usuário. Não compartilhe sua própria conta com outras pessoas.

Se receber erro de credenciais, confira a empresa, o e-mail, o perfil ativo e a senha. Muitas tentativas podem gerar bloqueio temporário. Uma conta suspensa não consegue entrar.

## 5. Colaboradores e convites {#equipe}

**Acesso:** administrador da empresa → **Equipe**.

### Adicionar uma pessoa

1. Clique em **Adicionar pessoa**.
2. Preencha nome, e-mail, perfil e telefone/WhatsApp do colaborador.
3. Para compartilhar uma senha inicial, mantenha o convite desmarcado e informe pelo menos 8 caracteres, uma letra maiúscula e um caractere especial.
4. Para a pessoa definir a própria senha, marque **Enviar convite para a pessoa definir sua senha**.
5. Escolha **E-mail**, **WhatsApp** ou **E-mail e WhatsApp**. O telefone é obrigatório para os dois últimos.
6. Salve. O envio entra na fila e depende da integração do canal escolhido estar habilitada.

O número pode ser nacional com DDD ou internacional com `+` e código do país. O sistema valida e normaliza o telefone.

### Reenviar, suspender e consultar

Utilize **Editar colaborador** para alterar nome, e-mail de acesso, telefone/WhatsApp e função (Administrador, Atendente, Motorista ou Guia). Alterar o e-mail ou a função encerra as sessões anteriores. A troca de e-mail invalida os links antigos de recuperação. O sistema impede remover seu próprio acesso administrativo ou o último administrador ativo.

Na linha do colaborador, clique em **Enviar convite**, escolha o canal e confira ou atualize o telefone. Um novo convite substitui os links anteriores. Ao escolher os dois canais, ambos recebem o mesmo link.

Utilize **Suspender/Ativar** para controlar o acesso. O sistema preserva pelo menos um administrador ativo e impede remover seu próprio acesso administrativo nessa tela.

Abra **E-mails de acesso** para consultar a fila de e-mails e a seção **Convites por WhatsApp**. A aceitação do envio não comprova entrega ou leitura. Um envio incerto precisa ser conferido antes do reenvio.

## 6. Veículos e capacidade {#veiculos}

**Acesso:** administrador ou atendente → menu **Veículos**.

1. Abra o cadastro de novo veículo.
2. Informe nome de identificação, placa e quantidade de lugares.
3. Confira a placa brasileira tradicional ou Mercosul e salve.
4. Mantenha o cadastro ativo para novas alocações. Edite os dados quando necessário ou arquive o veículo quando deixar de utilizá-lo.

A capacidade é de **1 a 200 lugares**. O sistema distribui quantidade de passageiros; não utiliza escolha de poltrona numerada. Os motoristas e guias são definidos na alocação da viagem, não como uma equipe permanente do veículo.

A capacidade atribuída é preservada na viagem. Alterar a frota depois não recalcula a capacidade histórica de saídas já criadas. O mesmo veículo pode operar em diferentes horários, desde que não haja conflito de agenda.

## 7. Rotas reutilizáveis e Google Maps {#rotas}

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

[CAPTURA:rotas-catalogo-desktop.png]

### Abrir a navegação

Na viagem atribuída, o motorista ou guia abre a rota ou um ponto específico no **Google Maps externo**. Confira os pontos e a ordem programada. A navegação e suas condições dependem do aplicativo Maps e da conectividade do aparelho.

### A Rota mudou depois de agendar?

A viagem guarda uma cópia do percurso. Editar o catálogo não muda automaticamente uma saída já criada. Em **Detalhes**, use **Atualizar com a versão atual da Rota**, confirme e confira as chegadas recalculadas.

A atualização é permitida para viagens agendadas sem eventos de embarque. Com reservas, preserva a posição, quantidade e finalidade das paradas utilizadas. Mudanças incompatíveis são bloqueadas. Prepare novamente os manifestos offline após uma atualização. Para outro percurso ou composição incompatível, crie uma nova viagem.

## 8. Pacotes turísticos: modelos e formatos {#pacotes}

**Acesso:** empresa de Turismo → menu **Pacotes**. Um pacote é um modelo reutilizável, sem data fixa. A data real é definida ao criar a viagem no menu **Viagens**. Os cadastros de veículos e rotas possuem seus próprios menus.

### Pacote simples

Cadastre nome, informações comerciais e valor por passageiro. Ao criar uma saída, selecione o pacote, a Rota e os horários. O modelo não consome franquia: o consumo ocorre no agendamento da viagem.

### Passeios com ida e volta

Use este formato quando cada passeio retorna à mesma cidade-base no próprio dia.

1. Cadastre previamente Rotas de ida e volta para os passeios.
2. Em **Novo pacote**, habilite o roteiro de vários destinos e escolha **Passeios com ida e volta**.
3. Em cada caixa, selecione a Rota, o nome comercial do destino, o dia relativo, a saída e o horário de retorno saindo do destino.
4. O primeiro passeio começa no dia 1. Os seguintes podem acontecer em dias espaçados.
5. Confira a ordem e salve o modelo.

**Exemplo:** dia 1, Maceió → Maragogi → Maceió; dia 3, Maceió → Praia do Gunga → Maceió. São dois destinos comerciais e quatro deslocamentos. A saída desse pacote consome **duas unidades** da franquia.

### Viagem com destinos em sequência

Use este formato quando os passageiros seguem para outra cidade e permanecem nela antes de continuar.

1. Cadastre as Rotas necessárias para cada deslocamento.
2. Informe os destinos comerciais na ordem do roteiro.
3. Configure dia relativo, horário, Rota/sentido e finalidade de cada deslocamento.
4. Associe cada chegada ao destino comercial correto, uma única vez.
5. Termine com o retorno à origem, sem novo destino comercial.
6. Acrescente atividades e dias livres, quando necessário, e confira as validações antes de salvar.

**Exemplo:** Maceió → Fortaleza no dia 1; Fortaleza → Natal no dia 3; Natal → Maceió no dia 6. A franquia considera os destinos comerciais Fortaleza e Natal: **duas unidades**.

<aside class="note"><strong>Venda completa.</strong> O pacote inclui o roteiro inteiro e o retorno. Não existe venda de um destino isolado dentro do pacote; crie outro pacote para esse produto. Paradas, atividades, retorno e transferências sem nova chegada comercial não acrescentam unidades à franquia.</aside>

O modelo admite até 20 destinos, 60 deslocamentos, 60 dias relativos e 120 atividades. As caixas com borda verde petróleo separam os itens do roteiro. CEP e datas fixas não fazem parte do modelo.

## 9. Criar e alocar uma viagem {#viagens}

**Acesso:** administrador ou atendente → **Viagens** ou a aba de viagens no módulo de frota.

### Saída simples

1. Clique em **Nova viagem**.
2. Escolha a Rota; vincule um pacote simples se aplicável.
3. Informe nome comercial, destino apresentado ao comprador e preço por passageiro.
4. Informe data e hora de saída e, para ida e volta, data e hora de retorno.
5. Confira as chegadas previstas a partir da duração da Rota.
6. Inclua os veículos e escolha o motorista principal de cada alocação. Marque os motoristas adicionais que acompanharão o mesmo veículo. Selecione nenhum, um ou vários guias, conforme a operação.
7. Revise as paradas atendidas por cada veículo, a capacidade e os conflitos de agenda; salve.

### Saída de pacote com roteiro

Selecione o pacote e informe a **Data inicial do pacote**. Os dias relativos se transformam em datas reais. Confira cada deslocamento e seus horários, sem sobreposição. Atribua equipe e veículo aos deslocamentos correspondentes.

Cada veículo pode ter até 20 motoristas e 20 guias. Todos os motoristas e guias atribuídos podem consultar agenda, rota e manifesto e operar os embarques no app atualizado. O cadastro impede sobreposição de horários e repetição de pessoas em veículos que atendem o mesmo trecho.

Vários veículos podem atender o mesmo deslocamento. Um pacote também pode trocar de veículo, motorista ou guia entre etapas. Cada família permanece inteira no veículo escolhido para cada deslocamento. O cadastro verifica conflitos e impede duplicar o mesmo recurso na mesma etapa.

### Consulta, edição e duplicação

Utilize o filtro **Situação da viagem**: Todas, Abertas, Agendadas, Em andamento, Fechadas/concluídas e Canceladas. Abertas reúne agendadas e em andamento; isso não significa que todas ainda permitam novas vendas.

Em **Detalhes**, confira roteiro, equipe, capacidade, reservas e finalização. A edição operacional respeita a situação da viagem e protege reservas e embarques existentes. Alterar o preço para novas reservas não recalcula as reservas já vendidas.

**Duplicar viagem** cria uma nova saída; confirme as datas e a equipe antes de salvar. Ao cancelar a viagem, reservas ativas são canceladas, lugares são liberados e o consumo é estornado no ciclo original. Não há reembolso bancário automático.

## 10. Vender bilhetes e cadastrar uma família {#vendas}

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

### Embarque em hotel ou outro endereço

Em **Local de embarque**, digite somente o nome do hotel ou o endereço. O mesmo campo oferece os pontos da viagem e locais já utilizados como sugestões. Não é necessário preencher nome e endereço separadamente.

Clique em **Conferir no Maps** para abrir a busca do local em uma nova aba. Confira se o resultado corresponde ao hotel desejado; se preferir, copie o endereço e cole no campo. A escolha feita no Maps não é transferida automaticamente para o formulário.

Nas novas reservas, **Usar este local nos passeios com saída da cidade e no retorno** vem marcado quando há deslocamentos correspondentes. Ao informar o embarque, esses locais são preenchidos juntos. Abra **Ajustar locais por passeio/trecho** para alterar apenas um deles. O destino principal aparece no resumo; use **Alterar desembarque** quando necessário. Reservas já existentes preservam os locais de cada deslocamento ao abrir o editor.

Veículo e situação inicial ficam em **Opções da reserva**. O padrão é confirmar a reserva usando a sugestão de veículo. Para familiares que embarcam em locais diferentes, faça reservas separadas.

Esses locais pertencem à reserva e ao veículo de cada saída. A Rota cadastrada permanece disponível para reutilização. Motoristas e guias consultam os endereços, complementos e passageiros previstos no roteiro e abrem a navegação. Após alterações, sincronize ou prepare novamente o trecho no Android antes de operar sem internet.

### Ocupação por segmento

A capacidade é conferida entre cada par de pontos consecutivos. Quem desembarca antes do destino libera o lugar para outro passageiro que embarque depois. A sugestão procura um veículo que comporte toda a família e deixe menos lugares livres no percurso reservado.

Somar vagas de ônibus diferentes não garante lugar para uma família no mesmo ônibus. Se nenhum veículo comportar todos os integrantes nos trechos necessários, o sistema informa indisponibilidade e não divide a família automaticamente. Em pacotes, a combinação deve atender todos os deslocamentos; o veículo pode mudar entre eles.

### Situações da reserva

| Situação | Efeito |
| --- | --- |
| Confirmada | Mantém os lugares até cancelamento. Permite emissão de bilhete enquanto a viagem estiver ativa. |
| Bloqueio pendente | Segura os lugares por 15 minutos desde a criação. Confirme antes do vencimento. |
| Expirada | Não ocupa lugares e não pode ser confirmada. Faça nova reserva se ainda houver capacidade. |
| Cancelada | Libera os lugares; não reativa a reserva nem devolve dinheiro automaticamente. |

Consultas não garantem as vagas: o sistema valida a capacidade novamente ao salvar. A confirmação da reserva e a marcação **PAGO** são ações diferentes.

## 11. CPF, estrangeiros e menores {#documentos}

Quando o roteiro cruza UFs, o sistema exige CPF dos passageiros, com as exceções cadastrais abaixo. A regra considera o roteiro completo do pacote, não apenas a primeira etapa.

| Situação | Como cadastrar |
| --- | --- |
| Passageiro brasileiro em roteiro interestadual | Informe CPF válido. |
| Estrangeiro | Marque a opção **Estrangeiro**; a validação considera a exceção ao CPF. |
| Criança menor de 5 anos | Marque **Menor de 5 anos** e informe nascimento para validar a idade. |
| Viagem dentro da mesma UF | CPF é opcional; quando informado, precisa ser válido. |

CPFs não podem repetir entre passageiros de reservas ativas da mesma viagem. Corrija erros de digitação antes de concluir. Estas são regras cadastrais do sistema; a empresa continua responsável por conferir os documentos e os requisitos da sua operação.

## 12. Pagamento, edição e realocação {#atendimento}

Em **Reservas e lugares → Ver reserva**, consulte a família, os passageiros, os pontos, o veículo de cada etapa e o valor.

### Marcar PAGO

Marque **PAGO** somente depois de conferir o recebimento pela empresa. O Rotafy não consulta banco, cartão ou PIX. Desmarcar PAGO corrige o registro interno; não realiza devolução financeira. Quando habilitado, o WhatsApp envia uma mensagem ao mudar para PAGO, não ao salvar repetidamente o mesmo estado.

### Editar a reserva

Utilize **Editar reserva** para corrigir responsável, telefone, nomes, CPF e pontos permitidos. O editor preserva quantidade de passageiros, valor, bilhetes e marcação PAGO. Incluir ou remover pessoas e mudar a composição de trechos exige outro cadastro compatível com a operação.

Pontos de um trecho com eventos de embarque são protegidos. Reservas expiradas/canceladas e viagens encerradas não permitem edição operacional.

### Realocar a família

Escolha um veículo com capacidade para todos os integrantes nos segmentos reservados. A realocação mantém a família inteira e exige que ninguém esteja a bordo. Histórico já realizado permanece associado ao veículo original. Em pacotes iniciados, a realocação completa é bloqueada para preservar as etapas executadas.

Depois de alterações, os operadores precisam atualizar os manifestos. Aparelhos sem conexão ainda podem mostrar a informação antiga até sincronizar.

## 13. Importar passageiros por CSV/XLSX {#importacao}

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

## 14. Bilhete único, QR Code e envio {#bilhetes}

**Acesso:** **Ver reserva → Bilhetes individuais**.

1. Confirme a reserva e confira se a viagem está ativa.
2. Clique em **Emitir bilhetes**. Cada passageiro recebe um único link e QR para todos os trechos contratados.
3. Abra o bilhete para conferir nome, viagem, veículos, pontos, horários e situação de cada trecho.
4. Copie o link ou use **Enviar bilhete pelo WhatsApp**. O envio utiliza o telefone da reserva.
5. Na página do bilhete, o cliente pode compartilhar o link, imprimir/salvar PDF e baixar a imagem do QR.

O mesmo QR é apresentado na ida, na volta e nas etapas do pacote. O controle de embarque permanece separado por veículo e trecho. O passageiro não precisa de aplicativo próprio para abrir o bilhete no navegador.

### Reemitir e revogar

**Reemitir bilhete** cria uma nova credencial para todos os trechos daquele passageiro e invalida as anteriores. **Revogar bilhete** impede usar o QR em todos esses trechos. Não apaga o histórico de embarque.

O link aparece na emissão/reemissão. Ao fechar a tela, reemita se precisar obter novamente o link para envio. Na reemissão, avise o cliente e atualize os manifestos offline.

Nas reservas antigas com bilhetes por trecho, use **Emitir bilhetes** para converter. Links anteriores são invalidados pela conversão. Prepare novamente os manifestos depois.

<aside class="note"><strong>Link individual e privado.</strong> Compartilhe com o passageiro ou responsável correto. O cancelamento da reserva, a revogação e o encerramento da viagem impedem o embarque. Um link já enviado pelo WhatsApp não pode ser retirado da conversa, mas pode deixar de autorizar o uso no sistema.</aside>

## 15. Mensagens de WhatsApp e e-mail {#mensagens}

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

### Entenda o histórico

**Na fila/aguardando:** ainda não enviado. **Enviando:** processamento em curso. **Aceito pelo provedor:** o provedor aceitou a solicitação, sem confirmação de leitura. **Falhou:** rejeição ou esgotamento de tentativas. **Descartado:** registro obsoleto, vencido, substituído ou incompatível. **Incerto:** a resposta não permite afirmar se o envio foi aceito.

Sessões WhatsApp desconectadas mantêm os envios aguardando. Mensagens automáticas de vendas anteriores à ativação não são enviadas retroativamente. Mensagens pendentes podem ser descartadas se os dados ou o link deixarem de ser válidos.

Se o resultado estiver incerto, confira o recebimento com o destinatário antes de reenviar. Para um convite com falha definitiva, solicite um novo envio pelo cadastro do colaborador.



### Endereço de embarque nas mensagens

Os novos bilhetes enviados manualmente ou de forma automática, confirmações e informações da reserva, respostas do menu e avisos de saída em quinze minutos ou de proximidade incluem o local de embarque, endereço, complemento quando cadastrado e um link para pesquisar no Google Maps. Os bilhetes e consultas mostram cada trecho contratado em ordem; os avisos apresentam somente o trecho correspondente, com endereço próprio na ida e no retorno.

O hotel/local personalizado tem prioridade. Na ausência dele, usa-se a parada escolhida ou a origem do trecho. Se o endereço não estiver cadastrado, a mensagem informa isso e oferece uma busca pelo nome do local e cidade, sem substituir pelo endereço de outro ponto. Confira os dados de embarque na reserva antes de enviar. O link do Maps não substitui o link privado do bilhete. Mensagens já recebidas não são alteradas.


## 16. App Android: acesso e agenda {#android}

O app operacional é destinado a **motoristas e guias**, com os mesmos recursos para ambos. A empresa distribui o APK configurado para sua operação.

1. Instale ou atualize o APK fornecido pela empresa. Prefira atualizar sobre a instalação existente, sem desinstalar, para preservar registros locais.
2. Confira a empresa apresentada. Se o APK não tiver empresa fixa, informe o identificador correto.
3. Entre com e-mail e senha do seu cadastro nessa empresa.
4. Em **Minhas viagens**, consulte os deslocamentos atribuídos a você.
5. Abra **Agenda** para ver as próximas viagens/etapas dos sete dias seguintes, com data, horário e destino.

Utilize o aplicativo fornecido pela empresa e mantenha-o atualizado.

Viagens concluídas deixam de estar disponíveis para operação. Conclusões feitas por outro usuário aparecem após atualizar ou sincronizar. Registros pendentes continuam acessíveis para revisão, sem reabrir a viagem.

### Biometria opcional

Durante o login, marque **Usar biometria nos próximos acessos** e conclua a autenticação inicial. No próximo acesso, utilize **Entrar com biometria**. A disponibilidade depende de biometria forte e de um aparelho compatível; a proteção do cofre biométrico exige Android 9 ou superior.

Cancelar a biometria não abre o painel. A senha continua como alternativa. No menu, é possível desativar o recurso; **Sair** também remove o acesso biométrico salvo. Mudança de senha pode exigir entrar novamente de forma manual.

## 17. Preparar e realizar o embarque {#embarque}

Prepare cada **veículo e trecho** enquanto houver conexão. Preparar a ida não prepara automaticamente a volta, e uma etapa não prepara todas as etapas do pacote.

1. Abra a viagem atribuída e selecione o veículo/trecho que irá operar.
2. Carregue/prepare o manifesto online antes de sair.
3. Confira lista, pontos, equipe e situação da operação.
4. Abra a leitura de QR, conceda permissão de câmera e leia o bilhete do passageiro.
5. Confira o passageiro identificado e confirme o embarque. Ler o QR não registra o embarque sozinho.
6. Quando necessário, utilize a lista para embarcar ou desembarcar manualmente.
7. Confira os totais e a sincronização antes de encerrar.

O sistema valida reserva, credencial, empresa, viagem, trecho, veículo e situação. Um QR de outro passageiro ou uma reserva inválida não autoriza o embarque. O bilhete unificado funciona em cada trecho contratado, respeitando sua alocação.

### Lista e filtros

Use **Todos**, **Não embarcados** e **Embarcados**. Desembarcados aparecem em Todos. É possível recolher/expandir a lista sem perder o resumo. Os filtros do Android consideram também as ações locais pendentes.

**Desembarcar todos** considera somente quem está a bordo no veículo/trecho selecionado e pede confirmação. Quem ainda não embarcou continua aguardando. Se houver conflitos, revise-os antes de confirmar o lote.

O painel web também oferece operação por lista, leitura pela câmera e leitura de QR por imagem. As ações dependem das permissões e da viagem atribuída.

## 18. Sem internet: preparação e sincronização {#offline}

O app Android e a operação web preparada podem manter registros locais durante uma interrupção. Para novos registros offline, o manifesto precisa ter sido preparado antes e ainda estar válido. A preparação tem validade limitada, de até **oito horas**, respeitando também a sessão.

1. Prepare cada veículo/trecho online.
2. Durante a falta de conexão, registre os embarques e desembarques permitidos.
3. Observe a quantidade de ações pendentes. O registro local ainda não é confirmação no servidor.
4. Reconecte com o mesmo usuário e sincronize.
5. Revise as ações rejeitadas ou em conflito e atualize o manifesto.

Outra pessoa pode cancelar uma reserva, editar pontos, realocar passageiros ou reemitir o bilhete enquanto seu aparelho está offline. Essas mudanças não aparecem instantaneamente no dispositivo, mas são verificadas pelo sistema ao sincronizar.

<aside class="note"><strong>Preserve a fila.</strong> Não limpe dados, desinstale o app ou troque de operador para tentar resolver pendências. Antes de iniciar a operação, confirme que o dispositivo é do usuário correto. Depois de alteração de Rota, reserva ou bilhete, prepare novamente os manifestos. O sistema não confirma automaticamente uma ação incompatível com o estado atual.</aside>

Iniciar a viagem e registrar chegada exigem conexão. A fila local permite operar presenças preparadas; os registros são conferidos pelo sistema ao sincronizar.

## 19. Iniciar, chegar e consultar a finalização {#chegada}

O início e a chegada pertencem ao **veículo e trecho** selecionados. Iniciar um ônibus não inicia os demais. Registrar chegada da ida não encerra a volta.

### Iniciar viagem

Com conexão, selecione a etapa correta, toque em **Iniciar viagem** e confirme. A primeira saída coloca a viagem geral em andamento. Etapas seguintes respeitam a conclusão das anteriores.

### Fechar viagem na chegada

1. Desembarque quem ainda está a bordo, individualmente ou por **Desembarcar todos**.
2. Sincronize e resolva todas as pendências do trecho.
3. Com conexão, toque em **Fechar viagem** e confirme a chegada.
4. Autorize a localização do celular, quando disponível.
5. Confira o registro concluído. O trecho deixa de aceitar novos embarques e desembarques.

O sistema impede fechar com passageiros a bordo. A viagem comercial é concluída quando todos os veículos encerram todos os deslocamentos previstos, incluindo retorno. Em uma saída com vários ônibus, a chegada de um deles não conclui os outros.

### GPS pontual

A captura registra latitude, longitude, precisão e horário do dispositivo. Se não houver permissão, sinal ou posição válida, o fechamento pode continuar com o motivo da ausência.

### Consultar no painel

Abra **Viagens → Detalhes → Finalização e chegadas**. Consulte saída/chegada por veículo e trecho, responsável, coordenadas, precisão, horário de captura e o link para o local no Maps. Quando faltarem dados, o sistema informa a ausência.

O encerramento administrativo tem seu próprio registro e não é apresentado como uma chegada física quando não houve captura. Em viagens concluídas ou canceladas, navegação operacional, embarque e **Reservas e lugares** ficam desabilitados; o histórico de finalização permanece consultável.

[CAPTURA:finalizacao-viagem-desktop.png]

## 20. Relatórios e visão gerencial {#relatorios}

**Acesso:** administrador ou atendente → **Relatórios**. Cada empresa consulta seus dados. Motoristas e guias não recebem relatórios financeiros/administrativos.

### Visão gerencial

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

[CAPTURA:visao-gerencial-desktop.png]

### Relatórios detalhados e CSV

As abas oferecem **Ocupação**, **Reservas e pagamentos**, **Presença** e, para o administrador, **Consumo da franquia**. Ocupação detalhada considera os segmentos entre paradas. Presença utiliza os registros aceitos pelo servidor, não as ações offline ainda pendentes.

Use **Exportar CSV completo** para analisar em planilha. O arquivo usa UTF-8, separador `;`, datas de Brasília e reais com vírgula decimal. O filtro de pagamento da tabela não altera automaticamente o escopo do CSV completo; leia a indicação da tela.

Os valores não representam lucro, fluxo de caixa, confirmação de PIX ou extrato bancário. O filtro por veículo pode incluir a reserva inteira de um pacote quando esse veículo atende uma de suas etapas.

Se a consulta atingir o limite, reduza o período ou escolha uma viagem. O sistema solicita ajuste em vez de mostrar totais parciais sem avisar.

## 21. Meu plano e consumo mensal {#meu-plano}

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

A cobrança automática registra o demonstrativo e disponibiliza o link de pagamento quando a integração está ativa. A confirmação ocorre após a verificação do pagamento. Contratos manuais preservam a baixa pela Nexus. Não há pró-rata ou reembolso automático neste fluxo.

## 22. Comunicação da empresa {#configuracoes}

A empresa utiliza seu próprio número de WhatsApp para comunicar reservas e bilhetes. A Nexus orienta a ativação dos canais e do remetente dos e-mails de acesso.

### Conectar o WhatsApp no painel da empresa

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

### Conferir os canais

1. Confirme com a Nexus o número da empresa e o e-mail remetente.
2. Envie um convite para um colaborador autorizado.
3. Confira o recebimento no canal selecionado.
4. Consulte o histórico de mensagens no painel.
5. Solicite suporte caso haja falha persistente.

### Boas práticas

Confira o telefone do responsável antes de enviar o bilhete. Consulte o histórico antes de reenviar uma comunicação. Compartilhe cada link somente com a pessoa correta.

## 23. Rotina por perfil {#rotina}

### Administrador da empresa

Organize equipe, frota e rotas. Cadastre viagens, acompanhe reservas, confira o plano contratado e analise os relatórios. Oriente os colaboradores sobre os procedimentos da empresa.

### Atendente

Selecione a viagem no menu **Vender bilhete**, cadastre os passageiros, confira disponibilidade, confirme a reserva e marque **PAGO** após verificar o recebimento. Envie os bilhetes e acompanhe as mensagens.

### Motorista e guia

Consulte a agenda, confira veículo e deslocamento, prepare a lista de passageiros e registre os embarques. No destino, registre os desembarques, sincronize as ações e finalize o trecho.

## 24. Dúvidas frequentes e solução de problemas {#duvidas}

### Não vejo um menu

Confira o perfil do usuário e o tipo da empresa. Atendente não administra equipe/plano; motorista e guia veem somente sua operação. Pacotes aparecem para Turismo.

### A família não cabe, mas a soma de vagas parece suficiente

A família precisa caber inteira em um veículo por deslocamento. Verifique os pontos, todos os segmentos e todos os dias do pacote; bloqueios temporários válidos também ocupam capacidade.

### Alterei uma Rota e a viagem continua com o endereço antigo

A saída guarda uma cópia. Utilize a atualização explícita da Rota nos detalhes, quando permitida, e depois atualize os manifestos. Se houver incompatibilidade ou operação iniciada, faça uma nova saída conforme o atendimento.

### Não consigo salvar o roteiro do pacote

Confira o formato escolhido, destinos comerciais na ordem, chegada associada uma vez por destino, dia 1 na primeira saída e retorno final. Para passeios diários com volta à base, prefira **Passeios com ida e volta**.

### O QR não funciona

Confira reserva confirmada, viagem ativa, passageiro, trecho e veículo selecionados. Verifique se houve reemissão/revogação e se o manifesto está atualizado. O bilhete único exige dados preparados novamente após a conversão dos bilhetes antigos.

### O celular mostra “Sem conexão”

Os registros locais podem estar preservados. Confira a conexão com a internet, mantenha o mesmo usuário e sincronize quando reconectar. Não limpe os dados para resolver uma pendência. Utilize o aplicativo fornecido pela empresa.

### Não consigo fechar o trecho

Desembarque todos que estão a bordo e sincronize/revise as pendências. O fechamento exige conexão e as etapas anteriores precisam estar concluídas. A falta de GPS pode ser registrada como motivo.

### O convite ou mensagem falhou

Consulte o histórico de mensagens. Confira telefone, e-mail do destinatário e canal selecionado. Falha definitiva exige novo convite; em resultado incerto, verifique o recebimento antes de reenviar. Solicite suporte se a falha persistir.

### Como pedir suporte

Informe empresa, perfil, tela, operação, data/hora e a mensagem apresentada. Use o identificador da solicitação se a tela o fornecer. Não envie senhas ou links privados de passageiros. O manual não substitui a análise de uma ocorrência real pela equipe responsável.

## 25. Checklist diário e glossário {#checklist}

### Antes da saída

- Conferir data, horário, Rota, equipe, veículos e capacidade.
- Conferir reservas, pontos, nomes, documentos e PAGO manual.
- Emitir/enviar os bilhetes e avisar alterações relevantes aos clientes.
- Preparar os manifestos de cada veículo/trecho online e testar o acesso operacional.
- Conferir câmera, bateria, internet e permissões necessárias.

### Durante e depois

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

**Documento de uso:** edição 2026.10, revisão 11. Em caso de diferença entre uma imagem e a tela, prevalecem a validação do sistema e as regras descritas para a versão publicada. As atualizações do sistema e do aplicativo são orientadas pela Nexus.


## 26. Financeiro da empresa e pagamento da assinatura {#financeiro}

O administrador encontra as cobranças da assinatura em **Meu plano** e no menu **Financeiro e cobranças**. Cada demonstrativo apresenta período, plano, utilização, excedentes, setup quando aplicável, total e prazo para pagamento.

### A vencer e resumo da assinatura

A tela Financeiro apresenta cinco cards: **Valor a vencer**, **Parcela X/12**, **Valor do plano**, **Próximo vencimento** e **Situação da assinatura**. Antes da emissão, o valor previsto soma a mensalidade e os excedentes apurados até o momento; pode mudar até o fechamento. Depois da emissão, prevalece o valor definitivo da fatura. O vencimento corresponde ao prazo de pagamento.

**Parcela X/12** é um contador dos ciclos da assinatura: após 12/12, reinicia em 1/12. Não cria um contrato parcelado ou fidelidade. O setup é uma cobrança única e não entra nesse contador.

Nos cinco dias anteriores ao vencimento e no próprio dia, o administrador vê uma caixa informativa ao abrir o app, com data e valor. Use **Desativar avisos de vencimento para mim** para ocultá-la. Para reativar, abra Financeiro e utilize **Reativar avisos de vencimento para mim**. A preferência fica salva por usuário; os demais administradores não são afetados. Os cards continuam disponíveis e os envios de cobrança por e-mail e WhatsApp mantêm seu funcionamento.

Abrir essa tela não emite uma nova fatura. Para uma cobrança definitiva com pagamento online, utilize **Gerar link para pagamento** quando o link ainda não estiver disponível. O sistema prepara o link e mostra **Pagar agora**. Se houver pagamento em conferência, aguarde a orientação da Nexus antes de pagar novamente.


Quando houver período de teste, ele aparece em **Meu plano**. A franquia do plano vale para o teste, sem cobrança de excedentes. Na data do término, começa uma nova franquia e é enviada somente a cobrança de setup, quando houver. A primeira mensalidade e os excedentes são cobrados após 30 dias de uso. Os ciclos seguintes também duram 30 dias e são cobrados no fechamento. Contratos anteriores preservam suas condições.

Um dia antes da cobrança, o aviso é parcial e ainda pode mudar. Aguarde a cobrança definitiva. Use **Pagar agora** para acessar o pagamento seguro, também enviado por e-mail e WhatsApp. A confirmação é automática após aprovação; o retorno do checkout pode aguardar alguns instantes pela conferência.

O prazo é de dois dias úteis a partir do dia seguinte ao fechamento, no horário de Brasília, excluindo fins de semana e feriados do calendário nacional, incluindo a Sexta-feira da Paixão. Pontos facultativos e feriados estaduais ou municipais não entram nesse calendário.

Cobranças manuais ou antigas podem apresentar chave Pix, favorecido e Copia e Cola, com baixa pela Nexus. Nesses casos, siga as instruções do demonstrativo. Em caso de divergência ou pagamento em conferência, informe à Nexus a referência da cobrança e os dados do pagamento.

Sem confirmação no prazo, o administrador passa a acessar somente o Financeiro para consultar e pagar a cobrança pendente. Motorista e guia preservam o acesso à operação das viagens já vendidas. A confirmação remove a restrição da cobrança paga; outros débitos vencidos podem manter o bloqueio. Uma suspensão administrativa segue tratamento separado.

Os avisos são enviados por e-mail aos administradores ativos e por WhatsApp ao telefone de contato da empresa. Mantenha seus dados atualizados.


## 27. Contrato de utilização e aceite no primeiro acesso {#contrato}

Quando a Nexus publica uma versão aprovada do contrato, os novos cadastros passam a exigir o aceite do representante da empresa. Cadastros anteriores à ativação não recebem aceite retroativo.

1. Entre com o administrador da empresa e confira seus dados. Comece pelo CEP: ao completar oito dígitos, o sistema preenche endereço, bairro, cidade e UF. Confira os dados e informe número e complemento, se houver. Todos os campos podem ser corrigidos manualmente; se a consulta falhar, preencha o endereço diretamente.
2. Informe nome, CPF e função do representante e declare os poderes para representar a empresa.
3. Clique em **Conferir dados e preparar contrato**. Use **Ler contrato completo** e **Baixar PDF antes de aceitar** para consultar a cópia personalizada.
4. Após abrir o texto integral, solicite o código pelo e-mail do seu acesso. O código vale por dez minutos e permite até cinco tentativas. Se os dados estiverem errados, solicite a correção ou gere outra cópia antes de aceitar.
5. Informe o código, marque a declaração de leitura e aceite e clique em **Confirmar aceite do contrato**. A caixa não vem marcada.

Você receberá por e-mail o PDF aceito e o comprovante. Em **Meu contrato**, consulte versão, data, hash SHA-256 e situação do envio; baixe os documentos ou solicite reenvio ao e-mail confirmado. Uma falha no e-mail não apaga o registro: o sistema tenta enviar novamente. Confira também o spam.

O hash identifica a integridade daquela cópia. Alterações cadastrais posteriores não modificam o contrato aceito. O aceite eletrônico não é apresentado como assinatura certificada ICP-Brasil. A equipe Nexus não marca o aceite pelo cliente.


### Mudança de plano e assinatura do aditivo

Quando a Nexus propuser uma mudança, você receberá um convite por e-mail. Entre como administrador e abra **Meu contrato**. A página apresenta plano anterior, plano novo, mensalidade, franquia, excedente e previsão de vigência.

Use **Conferir e ler aditivo**, confirme os dados do representante e prepare o documento. Leia o aditivo completo ou baixe o PDF antes de solicitar o código por e-mail. Informe o código, marque a declaração de aceite e confirme. A simples solicitação ou o recebimento do e-mail não muda o plano.

A alteração aceita valerá no próximo ciclo indicado no aditivo, sem cobrança proporcional, novo setup ou reinício do teste. Até a vigência, permanece o plano atual. Se a data prevista passar antes da confirmação, gere e leia uma nova cópia com a próxima data válida.

Após o aceite, o PDF e o comprovante serão enviados ao e-mail confirmado. Os aditivos ficam disponíveis em **Meu contrato**, com seus hashes e opção de reenvio. O contrato inicial continua disponível. Alterações posteriores no catálogo não modificam os valores aceitos.


## Atualização do aplicativo {#atualizacao}

O sistema verifica a versão ao abrir e ao retornar à tela. Quando houver atualização no navegador, salve o cadastro em andamento e clique em **Atualizar aplicativo**. A atualização pede confirmação antes de recarregar.

No Android, a partir da versão 1.7.0, o botão abre o download de uma versão mais nova disponibilizada pela Nexus. Sincronize os registros pendentes e instale por cima do aplicativo atual, sem desinstalar. Versões anteriores precisam receber a primeira atualização manualmente. Sem conexão, o trabalho offline permanece disponível.

Nas mensagens de reserva, os campos Empresa e Responsável pela reserva distinguem os nomes; os passageiros aparecem na lista. Cada mensagem de bilhete identifica o passageiro do QR correspondente.


## Rastreamento e avisos de embarque {#rastreamento}

O administrador acessa **Rastreamento** para ativar a coleta durante as viagens, ajustar o raio de proximidade (inicialmente cinco quilômetros) e habilitar o lembrete de saída. Os controles são independentes: o lembrete pode funcionar sem GPS.

Em **Locais de embarque para avisos**, selecione a viagem e confirme cada local no mapa, incluindo hotéis. Sem coordenadas confirmadas, não há aviso de proximidade. Alterar o endereço exige nova confirmação. É possível clicar no mapa ou colar coordenadas explícitas de um link completo do Google Maps.

No Android, a partir de 1.8.0, inicie o trecho e use **Assumir rastreamento deste veículo**. Autorize a localização e mantenha o celular no veículo. Uma notificação acompanha a coleta a cada cinco minutos. Outro motorista ou guia atribuído pode confirmar a transferência. O rastreamento termina na chegada; cada retorno ou próximo trecho exige nova ativação. **Interromper rastreamento neste celular** permite parar o compartilhamento.

A versão 1.9.1 melhora a leitura dos campos, cartões e botões. As posições de GPS aguardam envio somente na memória durante a sessão ativa; se o Android encerrar o processo, essas amostras temporárias serão perdidas. As posições já recebidas continuam no servidor. Os embarques e desembarques offline permanecem salvos no aparelho e devem ser sincronizados. Instale a atualização por cima da versão atual, sem desinstalar.

O administrador acompanha as posições no mapa e consulta o horário da última coleta. A linha liga amostras e não representa o caminho exato entre elas. A tela indica posição desatualizada. Não há coleta entre os passeios; sem contato com o servidor por quinze minutos, o compartilhamento local é interrompido.

Os avisos são enviados por WhatsApp ao telefone da reserva familiar. O lembrete informa a saída programada de cada trecho, incluindo volta, nos quinze minutos anteriores. O aviso de proximidade depende de GPS recente, boa precisão, embarque confirmado no mapa e passageiros ainda aguardando. Ambos evitam repetição e expiram quando deixam de ser úteis. A proximidade é aproximada, sem previsão exata de chegada. Rede, GPS, bateria e permissões podem atrasar a coleta ou o envio.


## Conversas WhatsApp e atendimento da equipe {#conversas-whatsapp}

Administradores e atendentes encontram **Conversas WhatsApp** quando o módulo está habilitado. A tela utiliza somente o número conectado da própria empresa. Pesquise uma conversa, consulte o histórico, responda a uma mensagem específica ou inicie uma conversa informando o telefone com DDI. No celular, use voltar para retornar à lista.

Envie texto ou anexe imagens, PDF, áudio ou vídeo nos formatos aceitos. O limite de envio é **2 MB por arquivo**. Mensagens antigas e mídias dependem do histórico disponível; um anexo indisponível não significa que a conversa foi apagada. A lista e a conversa aberta são atualizadas automaticamente.

O acompanhamento distingue mensagens pendentes, enviando, aceitas, falhas, incertas ou descartadas. Aceitação não comprova entrega nem leitura. Em **Envio incerto**, confira a conversa antes de reenviar para evitar duplicidade.

### Alerta de atendimento no painel

Quando houver atendimento humano pendente, administradores e atendentes veem um aviso nas telas do painel, atualizado a cada dez segundos. Clique em **Atender** ao lado do telefone para abrir diretamente a conversa. O aviso permanece até a equipe usar **Concluir atendimento**. Usuários sem o módulo WhatsApp e administradores restritos ao Financeiro não recebem esse alerta.

### Assumir e concluir um atendimento

Em **Solicitações de atendimento**, abra a conversa solicitada pelo cliente. A opção **Falar com a equipe** pausa as respostas automáticas. Uma resposta manual enviada pela equipe nesta tela também assume a conversa quando a automação está ativa. Enquanto o atendimento humano estiver aberto, o sistema não reapresenta o menu nem envia despedida por inatividade.

Ao finalizar, use **Concluir atendimento**. A próxima mensagem do cliente poderá iniciar um novo atendimento automático.

## Menu automático e bilhetes antecipados {#automacoes-whatsapp}

Em **WhatsApp → Atendimento e bilhetes automáticos**, o administrador habilita separadamente o atendimento automático e o envio de bilhetes. Ambos começam desabilitados. Confira a conexão e os envios, escolha as opções, acrescente uma mensagem complementar se desejar e clique em **Salvar automações**.

### Como o passageiro conversa

Qualquer mensagem de texto não vazia inicia o atendimento. O sistema apresenta **“Olá, Nome, em que podemos ajudar?”**, priorizando o nome do responsável pela reserva confirmada de viagem ativa associada ao telefone. Sem esse nome, utiliza o nome público do perfil do WhatsApp; sem nome disponível, apresenta apenas **“Olá, em que podemos ajudar?”**.

As opções habilitadas aparecem numeradas: **Bilhete de embarque**, **Meu veículo**, **Minha reserva**, **Local e horário de embarque** e **Falar com a equipe**. O passageiro responde com o número mostrado. Durante a conversa, outro texto reapresenta o menu. Quando houver várias reservas ou passageiros, o sistema solicita a seleção correspondente. As consultas utilizam o telefone da reserva e não permitem consultar dados de terceiros.

Após **dez minutos sem nova mensagem do cliente**, o atendimento automático envia: “Oi! Como não nos falamos há um tempinho, estamos fechando essa conversa por agora. Se precisar de mais alguma coisa, é só nos chamar novamente por aqui, tá bom? Tenha um ótimo dia! ✨” Uma nova mensagem reinicia o prazo. O envio depende da conexão; o prazo não representa garantia de recebimento no segundo exato. A regra não encerra atendimentos humanos. Após encerrar, qualquer novo texto inicia outro menu.

Ao concluir um atendimento humano, a tela informa se a pesquisa entrou na fila ou se uma regra impediu a criação. Caso não seja possível identificar o telefone, o atendimento permanece aberto e a tela orienta uma nova tentativa.


Em hotéis e endereços personalizados, confirme com a equipe o horário específico da coleta. O horário geral de saída não equivale ao horário exato de chegada ao hotel.

### Bilhetes automaticamente antes do embarque

Ative **Enviar bilhetes automaticamente 24 horas antes do primeiro embarque**. Reservas confirmadas entram na fila quando faltam até 24 horas para o primeiro embarque contratado; reservas feitas dentro dessa janela também são consideradas. Cada passageiro recebe um bilhete individual válido para todos os seus trechos. O botão de envio manual continua disponível.

Os envios automáticos respeitam um intervalo configurado pela Nexus (padrão: **30 segundos**) em uma fila compartilhada entre todas as viagens e empresas. As 24 horas indicam a entrada na fila, não um horário garantido de entrega. Volume elevado e indisponibilidade podem atrasar os envios; acompanhe a situação antes da saída. Respostas do atendimento e envios manuais não seguem esse intervalo.

Cancelamentos e alterações são conferidos antes do envio. Mensagens aceitas ou incertas não são repetidas automaticamente. Bilhetes antigos sem link recuperável aparecem como **Precisa de atenção**: utilize o envio manual com o link original ou faça uma reemissão consciente na reserva. Reemitir substitui o link anterior; a automação não faz essa troca silenciosamente.

## Módulos e integração com outro sistema {#modulos-integracao}

Os menus disponíveis dependem do perfil, dos módulos contratados e da situação da empresa. A Nexus pode disponibilizar o sistema completo ou somente os módulos necessários à operação integrada. O Financeiro da assinatura, o contrato, o acesso e a ajuda continuam como recursos básicos.

No modelo integrado, a venda acontece no sistema parceiro; o Rotafy recebe os dados autorizados para comunicação, bilhetes e operação de embarque/desembarque. O motorista ou guia usa sua própria conta no Android, prepara as viagens com conexão e sincroniza os registros realizados offline.

O administrador gerencia credenciais em **Integração com parceiros**, quando habilitado. Vincule um atendente dedicado, limite permissões e validade e entregue a credencial apenas ao responsável técnico autorizado. A credencial aparece uma única vez. Revogue-a quando não for mais necessária. Suspender ou mudar a função do atendente interrompe as credenciais vinculadas. A integração não concede acesso às configurações globais nem ao financeiro da assinatura.


## NPS e satisfação dos clientes {#nps}

Administradores e atendentes acessam **NPS e satisfação** para acompanhar as avaliações. Somente o administrador habilita as pesquisas em **Configurar pesquisas automáticas**, nessa tela ou no menu **WhatsApp**. Atendimento e viagem começam desabilitados e são independentes. A empresa precisa ter WhatsApp conectado e envios habilitados.

### Atendimento e viagem

Ao usar **Concluir atendimento**, a equipe agenda a pesquisa de atendimento, no máximo uma por telefone a cada sete dias. A mensagem começa com **“Sua opinião é fundamental para continuarmos evoluindo! 🚀”** e pergunta **“Em uma escala de 0 a 10, o quanto você recomendaria o nosso atendimento para um amigo ou familiar?”**, explicando que 0 significa não recomendaria e 10 significa com certeza recomendaria. O cliente responde apenas com o número.

A pesquisa da viagem entra na fila duas horas após a conclusão completa, incluindo retorno e último trecho do pacote. Somente reservas confirmadas com embarque registrado de pelo menos um passageiro são consideradas. O responsável recebe uma mensagem acolhedora, identificando a viagem e perguntando quanto recomendaria viajar com a empresa.

### Respostas conforme a nota

- **9 e 10 — Promotores:** recebem um agradecimento e a pesquisa é concluída, sem exigir comentário.
- **7 e 8 — Neutros:** recebem agradecimento e convite para contar o que faria a experiência chegar à nota 10.
- **0 a 6 — Detratores:** recebem um pedido de desculpas e uma pergunta sobre o que poderia ter sido feito de diferente. A avaliação aparece para a equipe de qualidade no painel.

O comentário é opcional e aceita até 2.000 caracteres. O prazo para responder é de **24 horas após a tentativa de envio**. Envie **PULAR** ou **ENCERRAR** para não participar ou pular o comentário. A nota recebida é preservada. Durante a pesquisa, números são notas, sem acionar o menu. Depois do encerramento, uma nova mensagem inicia o atendimento normal.

Uma resposta manual da equipe encerra uma pesquisa em andamento. Convites aguardam quando houver atendimento ativo ou outra pesquisa para o mesmo telefone. Os convites são espaçados conforme a configuração da Nexus (padrão: 30 segundos); respostas e agradecimentos não seguem esse intervalo. Mensagens com resultado incerto não são repetidas automaticamente. Ativar a função não envia avaliações de conclusões anteriores à ativação. Convites não enviados em 24 horas na fila são descartados.

Pesquisas já enviadas com a versão anterior preservam suas perguntas e o fluxo informado ao cliente. Convites antigos ainda sem tentativa utilizam a nova apresentação ao enviar.

### Equipe de qualidade

Administradores e atendentes veem um aviso quando há avaliação com nota de 0 a 6 aguardando análise. Clique em **Ver avaliações de qualidade** para abrir a área correspondente no NPS. Consulte nota, contato e comentário e use **Marcar avaliação como analisada**. O aviso é atualizado automaticamente; a avaliação continua no relatório.

Se a equipe analisar a nota antes de o cliente comentar, o novo comentário recoloca a avaliação na fila de análise. O encaminhamento é realizado dentro do próprio app para os usuários autorizados da empresa; não exige outro número ou e-mail de destino.

### Indicadores e relatórios

Cards: **NPS**, **taxa de resposta**, **nota média**, **promotores (9–10)**, **neutros (7–8)** e **detratores (0–6)**. NPS = percentual de promotores menos percentual de detratores, de −100 a +100. Sem notas, NPS e média são “—”; ausência de resposta nunca vira zero. A taxa usa notas recebidas sobre pesquisas enviadas, incluindo tentativa incerta quando a resposta comprova o recebimento.

Filtre por período de criação (Brasília), tipo, viagem/pacote, classificação e situação. Consulte a comparação por tipo, evolução mensal, comentários e histórico. O limite é de 366 dias inclusivos e 5.000 pesquisas por filtro. A lista usa cinquenta registros por página. Indicadores, **Exportar CSV** e **Emitir PDF** consideram todo o resultado do filtro aplicado, independentemente da página aberta.

## Horários de atendimento humano {#horarios-atendimento}

O administrador acessa **Configurações → Horários de atendimento humano** ou a mesma seção no menu **WhatsApp**.

1. Ative **Informar quando estivermos fora do horário de atendimento**.
2. Escolha o fuso do atendimento: Brasília, Manaus, Rio Branco ou Fernando de Noronha.
3. Selecione dia da semana, início e término. Use **Adicionar horário** para incluir outros dias ou turnos, inclusive intervalos antes e depois do almoço.
4. Confira e clique em **Salvar horários de atendimento**.

Dias sem horários são fechados. Se o término for anterior ao início, o turno termina no dia seguinte; por exemplo, domingo às 22:00 até segunda às 02:00. O sistema recusa turnos sobrepostos e início igual ao término. Os limites consideram abertura inclusiva e fechamento exclusivo: um horário até 18:00 já está encerrado às 18:00.

Ao escolher **Falar com a equipe** fora do expediente, o cliente recebe a confirmação da solicitação, a relação dos horários e a próxima abertura, no fuso escolhido. A solicitação permanece no painel para resposta. A equipe pode atender manualmente a qualquer momento. Essa configuração não bloqueia o menu automático, pesquisas NPS ou outros envios automáticos.

Sem a opção habilitada, continua a confirmação usual de atendimento, sem restrição de horário. A configuração é semanal; mantenha os turnos atualizados conforme a rotina da empresa.


## 35. Privacidade, cookies e seus direitos

O rodapé do aplicativo apresenta os dados legais da Nexus e os links **Privacidade**, **Termos de uso**, **Cancelamento e reembolso** e **Exercer meus direitos**. Essas páginas podem ser lidas sem entrar no sistema. As regras de cancelamento da assinatura seguem o contrato vigente; pedidos relativos a uma viagem devem ser tratados com a empresa que vendeu o bilhete.

O aviso de cookies informa quais recursos são necessários. Use **Usar somente necessários** para guardar essa preferência no navegador. Em **Preferências de cookies**, no rodapé, você pode consultar novamente as informações. Esta versão não utiliza cookies de publicidade ou análise. A navegação e os direitos do titular não dependem de aceitar publicidade.

Os formulários informam a finalidade dos dados e a base legal. Preencha somente o necessário, confira os campos opcionais e evite inserir dados sensíveis nos comentários. Ler a política não representa um consentimento geral para qualquer tratamento.

Para pedir acesso, correção ou exclusão, abra **Exercer meus direitos**, informe um e-mail para retorno e o tipo do pedido. A descrição é opcional. O sistema registra um protocolo; anote-o. Não envie documentos ou senhas. A equipe confirmará sua identidade antes de responder, e a exclusão depende da análise do controlador e das obrigações legais de conservação. Você também pode escrever para **contato@nexusdataanalytics.com.br**.

No mapa de embarque, além do clique, é possível mover a área com as setas e usar **Enter** para selecionar o centro. Os links, botões e formulários podem ser percorridos com **Tab**; caixas de diálogo podem ser fechadas com **Esc**.


Na tela de acesso, o aviso **Mostrar informações sobre o uso dos dados** começa recolhido. Clique para ler a finalidade e a base legal; use **Ocultar** para recolher sem perder o que foi digitado. Os links de privacidade, condições de uso e ajuda abrem em nova aba. As políticas são organizadas em seções expansíveis. **Dados da empresa** revela razão social, CNPJ, endereço e contato. As preferências de cookies abrem em uma janela de diálogo. A tela de acesso usa um rodapé compacto; em dispositivos menores ou com ampliação, a rolagem permanece disponível quando necessária para a leitura.
