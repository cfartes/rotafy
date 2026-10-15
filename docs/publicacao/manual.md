## 1. Conheça o Nexus Rotafy {#visao-geral}

O **Nexus Rotafy** organiza a operação de empresas de turismo e transporte: cadastros, rotas, viagens, pacotes, reservas familiares, bilhetes individuais, embarque, comunicação e relatórios. A equipe administrativa usa o painel web; motoristas e guias usam o painel operacional ou o aplicativo Android.

Este manual descreve a implementação disponível em **15/10/2026**. As imagens utilizam dados demonstrativos. Os menus dependem do perfil do usuário e do tipo de empresa. Uma captura pode mostrar uma seleção de filtros diferente da sua operação.

**Endereço do painel:** <https://rotafy.nexusdataanalytics.tech>. O cadastro inicial de empresa utiliza `/cadastro`. A central de documentação utiliza `/ajuda`.

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

1. Na tela inicial, abra o cadastro da empresa, ou acesse `/cadastro`.
2. Informe nome comercial, razão social, identificador de acesso e telefone/WhatsApp de contato.
3. Escolha **Turismo e transfers** ou **Transporte regular**, conforme a operação.
4. Informe **CPF/CNPJ obrigatório e válido**, utilizado no cadastro comercial e na cobrança da assinatura. Confira os dígitos; a máscara não garante a validade do documento.
5. Selecione o plano disponível. Leia mensalidade, franquia de viagens e valor por unidade extra.
6. Informe nome, e-mail e senha do primeiro administrador. A senha exige pelo menos 8 caracteres, com uma letra maiúscula e um caractere especial.
7. Confirme o cadastro e entre no painel da empresa com seu identificador, e-mail e senha.

Todos os campos do cadastro são obrigatórios. O identificador de acesso deve conter somente letras minúsculas sem acentos e números, de 2 a 50 caracteres. Não utilize espaços, sublinhado (_), hífen (-) ou outros caracteres especiais. Por exemplo, `agenciaexemplo` é um identificador de acesso, não uma senha. Guarde-o junto das orientações entregues à equipe.

A Nexus também pode cadastrar a empresa por seu painel. Nesse caso, o administrador recebe as orientações de acesso. Planos e disponibilidade de cadastro dependem da configuração da plataforma.

### Identidade visual

O administrador utiliza **Identidade da empresa** para ajustar os dados e a marca disponíveis na interface, incluindo cores e logotipo. A identidade pertence à empresa; não troca os dados de outras empresas.

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
3. Para compartilhar uma senha inicial, mantenha o convite desmarcado e informe uma senha com 12 ou mais caracteres.
4. Para a pessoa definir a própria senha, marque **Enviar convite para a pessoa definir sua senha**.
5. Escolha **E-mail**, **WhatsApp** ou **E-mail e WhatsApp**. O telefone é obrigatório para os dois últimos.
6. Salve. O envio entra na fila e depende da integração do canal escolhido estar habilitada.

O número pode ser nacional com DDD ou internacional com `+` e código do país. O sistema valida e normaliza o telefone.

### Reenviar, suspender e consultar

Na linha do colaborador, clique em **Enviar convite**, escolha o canal e confira ou atualize o telefone. Um novo convite substitui os links anteriores. Ao escolher os dois canais, ambos recebem o mesmo link.

Utilize **Suspender/Ativar** para controlar o acesso. O sistema preserva pelo menos um administrador ativo e impede remover seu próprio acesso administrativo nessa tela.

Abra **E-mails de acesso** para consultar a fila de e-mails e a seção **Convites por WhatsApp**. A aceitação do envio não comprova entrega ou leitura. Um envio incerto precisa ser conferido antes do reenvio.

## 6. Veículos e capacidade {#veiculos}

**Acesso:** administrador ou atendente → **Veículos** ou **Frota, pacotes e viagens → Frota**.

1. Abra o cadastro de novo veículo.
2. Informe nome de identificação, placa e quantidade de lugares.
3. Confira a placa brasileira tradicional ou Mercosul e salve.
4. Mantenha o cadastro ativo para novas alocações. Edite os dados quando necessário ou arquive o veículo quando deixar de utilizá-lo.

A capacidade é de **1 a 200 lugares**. O sistema distribui quantidade de passageiros; não utiliza escolha de poltrona numerada. O motorista e os guias são definidos na alocação da viagem, não como uma equipe permanente do veículo.

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

**Acesso:** empresa de Turismo → **Frota, pacotes e viagens → Pacotes**. Um pacote é um modelo reutilizável, sem data fixa. A data real é definida ao criar a viagem.

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
6. Inclua os veículos e atribua um motorista ativo a cada alocação. Selecione guias quando houver.
7. Revise as paradas atendidas por cada veículo, a capacidade e os conflitos de agenda; salve.

### Saída de pacote com roteiro

Selecione o pacote e informe a **Data inicial do pacote**. Os dias relativos se transformam em datas reais. Confira cada deslocamento e seus horários, sem sobreposição. Atribua equipe e veículo aos deslocamentos correspondentes.

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
6. Escolha pontos de embarque e desembarque para cada trecho. O desembarque deve vir depois do embarque.
7. Confira a sugestão de veículo e a disponibilidade para a família inteira.
8. Salve como confirmada ou bloqueio pendente, conforme a operação, e confira o resultado.

Uma reserva pode ter de 1 a 200 passageiros com um único telefone compartilhado. O valor nominal é o preço por passageiro da saída multiplicado pelo total de passageiros e fica preservado na reserva.

### Como os lugares são calculados

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

Consulte plano, ciclo, mensalidade, franquia, uso líquido, unidades restantes, extras e valor estimado. Os ciclos mensais seguem o aniversário da assinatura; a franquia não acumula para o mês seguinte.

| Operação | Consumo |
| --- | --- |
| Cadastrar veículo, Rota ou modelo de pacote | Não consome. |
| Criar viagem simples, com ida/volta e vários veículos | Uma unidade. |
| Criar saída de pacote com quatro destinos comerciais | Quatro unidades. |
| Acrescentar retorno, parada ou atividade sem novo destino comercial | Não acrescenta unidade. |
| Cadastrar, confirmar ou cancelar uma reserva | Não altera a franquia. |
| Cancelar a viagem | Estorna o consumo original no ciclo em que foi lançado. |

**Estimativa do ciclo:** mensalidade + máximo(uso líquido − franquia, 0) × valor da viagem extra. Cancelar uma viagem de um ciclo anterior não transfere crédito para o ciclo atual.

Não há emissão automática de fatura, cobrança bancária, pró-rata ou reembolso financeiro. A Nexus administra a cobrança comercial com base no demonstrativo e nas condições contratadas.

## 22. Comunicação da empresa {#configuracoes}

A empresa utiliza seu próprio número de WhatsApp para comunicar reservas e bilhetes. A Nexus orienta a ativação dos canais e do remetente dos e-mails de acesso.

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

**Documento de uso:** edição 2026.10, revisão 3. Em caso de diferença entre uma imagem e a tela, prevalecem a validação do sistema e as regras descritas para a versão publicada. As atualizações do sistema e do aplicativo são orientadas pela Nexus.
