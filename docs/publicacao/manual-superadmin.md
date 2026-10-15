## 1. Acesso à plataforma {#acesso}

Manual exclusivo da equipe Nexus. Acesse <https://rotafy.nexusdataanalytics.tech/nexus> com seu e-mail e senha de superadmin. Esse perfil não possui empresa operacional padrão. Para operar viagens, utilize uma conta cadastrada na empresa.

A senha exige pelo menos 8 caracteres, uma letra maiúscula e um caractere especial. Utilize **Esqueci minha senha** no acesso Nexus quando necessário. Não compartilhe credenciais.

### Perfis da equipe Nexus

O **Administrador Nexus completo** mantém acesso a todas as áreas. O perfil **Equipe Nexus** acessa empresas e o histórico das ações de cadastro, edição, ativação e suspensão. Esse perfil não acessa configurações, financeiro, planos e assinaturas, relatórios financeiros ou a gestão dos usuários internos. Na criação de uma empresa, pode escolher um plano do catálogo público; alterações posteriores de assinatura cabem ao administrador completo.

Para cadastrar uma pessoa da Nexus, entre com um administrador completo, abra **Equipe Nexus** e clique em **Adicionar usuário Nexus**. Informe nome, e-mail, senha inicial e perfil. O perfil restrito é sugerido por padrão. Cada pessoa entra pelo endereço `/nexus` com suas próprias credenciais.

Na mesma tela, altere o perfil ou suspenda/ative o acesso. Suspensões e mudanças de perfil encerram as sessões existentes. O sistema exige pelo menos um administrador completo ativo. Os administradores existentes mantêm acesso completo após a atualização.

### Log de acesso da equipe

Em **Equipe Nexus**, o administrador completo consulta **Log de acesso dos colaboradores Nexus**. Filtre por colaborador, entrada/saída e período. Os horários seguem Brasília e são exibidos até 200 registros por consulta. O histórico reúne entradas autenticadas e saídas pelo botão **Sair**, incluindo os registros anteriores disponíveis. Fechar o navegador ou expirar a sessão não registra uma saída. Tentativas de senha inválida não fazem parte dessa consulta.

## 2. Empresas, planos e assinaturas {#nexus}

**Exclusivo do superadmin.** Entre em `/nexus`. Esta seção descreve os menus, sem divulgar credenciais da plataforma.

### Empresas

Cadastre ou edite dados comerciais, contato e perfil operacional. O CPF/CNPJ é obrigatório e validado. Crie o primeiro administrador e selecione o plano. Utilize suspender/ativar conforme o contrato, preservando os dados históricos.

Na ação de gerenciamento do plano da empresa, confira a empresa selecionada e sua assinatura; não confunda o catálogo global de planos com o vínculo daquela empresa.

### Planos e assinaturas

1. Abra **Planos e assinaturas**.
2. Configure Basic, Professional, Enterprise ou um plano adicional.
3. Defina nome, franquia mensal, mensalidade e valor por unidade extra.
4. Publique as condições e selecione a empresa em **Assinatura e consumo**.
5. Vincule o plano e a data inicial ou programe a mudança para o próximo ciclo.
6. Confira ciclos, consumo e demonstrativos por empresa.

Alterar o catálogo não reescreve os valores históricos. Uma mudança agendada fixa a versão escolhida para o próximo ciclo. Arquivar um plano impede novas escolhas; contratos existentes preservam sua continuidade conforme as regras da assinatura.

### Atividades

Consulte **Atividades** para acompanhar alterações registradas pelo sistema. A consulta respeita o perfil e o espaço de acesso. Os eventos não revelam senhas ou links privados. O histórico auxilia conferência, mas não substitui documentos financeiros ou a política de backup da operação.


## 3. Cadastro de empresas {#empresas}

1. Abra **Empresas** e **Cadastrar empresa**.
2. Preencha nome comercial, razão social, telefone/WhatsApp, CPF/CNPJ válido e identificador de acesso.
3. O identificador aceita somente letras minúsculas sem acentos e números, de 2 a 50 caracteres. Não utilize espaços, sublinhados, hífens ou outros caracteres especiais.
4. Escolha **Turismo e transfers** ou **Transporte regular**.
5. Escolha o plano e informe nome, e-mail e senha do primeiro administrador. Todos os campos são obrigatórios.
6. Confira e salve. Oriente o administrador sobre o identificador de acesso.

O perfil operacional determina os módulos; o plano determina as condições comerciais. Viagens turísticas abertas podem impedir a troca do perfil. Suspender uma empresa preserva seus registros.

## 4. Configurações de comunicação {#comunicacao}

Abra **Configurações** no painel Nexus. Informe as credenciais dos serviços de mensagens e e-mail, configure o e-mail remetente autorizado e salve. Um campo de chave vazio preserva a chave existente. Utilize a opção de remover somente quando desejar desativar a credencial correspondente.

Mantenha as chaves restritas à equipe autorizada. Não inclua credenciais em capturas ou chamados. Confira a autorização do remetente junto ao serviço de e-mail.

### WhatsApp de cada empresa

Cada empresa utiliza seu número e uma sessão exclusiva. Conecte o número pelo QR Code no painel do serviço de mensagens antes de associá-lo à empresa.

1. Localize a empresa em **WhatsApp de cada empresa**.
2. Confira o **WhatsApp de envio**. O telefone de contato aparece como sugestão; ajuste para o número conectado. Utilize + e código do país para números internacionais.
3. Ative **Identificar e salvar a sessão automaticamente pelo telefone**. O telefone é salvo ao sair do campo.
4. Defina **Habilitar envios**. O sistema identifica uma única sessão conectada correspondente ao telefone e salva o ID automaticamente.
5. Acompanhe o estado na tela. Se a sessão ainda não existir, a busca continuará a cada minuto, mesmo com a tela fechada.

O pareamento por QR Code continua necessário no serviço de mensagens. Duplicidades e sessões vinculadas a outra empresa impedem a associação automática. Empresas suspensas não são consultadas. Os vínculos existentes são preservados até a ativação do modo automático. Para configuração manual, desmarque a identificação automática e informe o ID conferido no serviço.

### Conferir envios

Em **Configurações → Cobrança mensal**, utilize **Testar envio de cobrança**. Salve primeiro o remetente e a sessão WhatsApp de cobrança. Informe seu e-mail ou telefone de teste e clique no botão do canal desejado. O teste utiliza a configuração salva e funciona mesmo com a cobrança automática desativada. A mensagem é identificada como teste e não cria fatura, altera assinatura ou solicita pagamento.

Acompanhe o resultado na própria tela: aguardando, enviando, aceito pelo serviço, falha ou envio incerto. Aceito não confirma entrega ou leitura. Em envio incerto, confira o recebimento antes de solicitar outro teste. Testes que não forem processados em 15 minutos são descartados. Esses envios também aparecem no histórico financeiro como **Teste de cobrança**.

Envie um convite a um colaborador autorizado e confira o recebimento. Consulte o histórico antes de reenviar. A aceitação pelo serviço de e-mail não garante entrega na caixa de entrada: confira também o spam e o destinatário.

Confirmações, cancelamentos, marcação PAGO, bilhetes e convites utilizam os canais configurados conforme a ação executada. Confira os destinatários antes de enviar.

## 5. Rotina do superadmin {#rotina}

- Confira novas empresas, perfil operacional e plano.
- Acompanhe ciclos mensais, franquias, excedentes e demonstrativos.
- Consulte **Atividades** para conferir alterações registradas.
- Revise a associação da sessão quando uma empresa trocar de número.
- Apoie os administradores sem compartilhar sua conta Nexus.

## 6. Dúvidas frequentes {#duvidas}

### Como definir o plano de uma empresa?

Utilize o gerenciamento da assinatura da empresa. O catálogo cadastra as condições comerciais; a assinatura vincula o plano à empresa.

### A sessão não foi encontrada?

Confira o telefone e o pareamento. A busca depende do telefone informado pelo serviço. Se necessário, confira e selecione o ID manualmente. A busca não cria nem conecta sessões.

### O e-mail falhou?

Confira remetente autorizado, credenciais e destinatário. Consulte o histórico antes de reenviar o convite. Não exponha chaves ao solicitar suporte.

### Onde fica o manual da empresa?

Acesse `/ajuda` para o manual da equipe e a apresentação comercial. A ajuda do painel Nexus fica em `/nexus/ajuda`.


## 7. Cobranças mensais e confirmação do Pix {#cobrancas}

### Configurar e ativar

1. Entre em **Configurações**, na seção **Cobrança mensal da Nexus · Pix manual**.
2. Informe **Chave Pix da Nexus** e **Nome do favorecido do Pix**. Opcionalmente, preencha **Pix Copia e Cola sem valor definido**, com o código completo gerado pelo banco para a mesma chave Pix.
3. Selecione ou informe o **ID da sessão WhatsApp de cobrança da Nexus**. As cobranças saem pelo número da Nexus, utilizando as credenciais de comunicação configuradas no painel.
4. Confira o e-mail remetente e os canais de comunicação.
5. Marque **Ativar avisos e cobranças mensais automáticas** e salve.

A configuração começa desativada. A ativação considera ciclos cujo fechamento ocorrer após ela; não gera cobranças retroativas de ciclos antigos. Desativar pausa os novos fechamentos e envios, mas não cancela débitos existentes. Alterar a chave Pix ou o Pix Copia e Cola não reescreve cobranças já fechadas. O Copia e Cola é validado para conferir o formato, a integridade, a correspondência da chave e a ausência de valor fixo. Nas novas cobranças definitivas, o código aparece no demonstrativo e no texto das mensagens de e-mail e WhatsApp. O cliente precisa informar o valor total no banco; não é enviada uma imagem de QR Code por esse campo.

### Calendário e mensagens automáticas

O ciclo segue a data inicial da assinatura de cada empresa. Um dia antes do fechamento, a empresa recebe um aviso com valor parcial, sujeito a alteração; deve aguardar a cobrança definitiva para pagar. No fechamento, o sistema consolida mensalidade e excedentes, preserva os valores da cobrança e envia o demonstrativo com Pix e favorecido.

O prazo termina ao fim do segundo dia útil contado a partir do dia seguinte ao fechamento, no horário de Brasília. Sábados, domingos e feriados do calendário nacional, incluindo a Sexta-feira da Paixão, não entram na contagem. Pontos facultativos e feriados estaduais ou municipais não são considerados.

Os e-mails são enviados aos administradores ativos da empresa. O WhatsApp utiliza o telefone de contato cadastrado na empresa. Mantenha esses contatos atualizados.

### Acompanhar e dar baixa

Abra **Financeiro e cobranças**. Utilize o filtro de situação para consultar avisos parciais, cobranças abertas, vencidas, pagas e canceladas. Cada cobrança apresenta ciclo, plano, franquia, utilização, excedentes, valor total, prazo e referência.

Depois de conferir o recebimento integral no banco, clique em **Confirmar recebimento do Pix**, informe a data e hora do recebimento e, se necessário, a referência ou observação. Confirme o pagamento integral. O sistema registra o usuário e o momento da confirmação e agenda a comunicação à empresa.

A confirmação é manual: realizar o Pix não atualiza o sistema sozinho. O registro de recebimento e o registro da confirmação são distintos. Não é possível dar baixa em um aviso parcial nem confirmar uma data de recebimento futura. Uma cobrança já paga não gera outra baixa ao repetir a mesma solicitação.

### Bloqueio e liberação

Se não houver confirmação até o prazo, novas operações ficam bloqueadas e a empresa recebe aviso por e-mail e WhatsApp. Consultas, acesso ao financeiro, leitura de bilhetes e operação dos embarques e deslocamentos já vendidos permanecem disponíveis.

A baixa retira a restrição daquela cobrança. Se houver outras cobranças vencidas, a empresa continua restrita. Uma suspensão administrativa permanece independente e não é removida pelo pagamento.

A ação **Cancelar cobrança** preserva o histórico e retira aquela cobrança da apuração de bloqueio. Não representa devolução de dinheiro. Não cancele uma cobrança apenas para registrar um Pix recebido; utilize a confirmação de recebimento.

### Histórico dos envios financeiros

O painel mostra o evento, canal, empresa, situação e motivo de falha de cada comunicação. Aceitação pelo serviço não significa entrega ou leitura. Um WhatsApp com resultado incerto não é repetido automaticamente. Confira o recebimento antes de qualquer nova comunicação. Falhas de comunicação não desfazem uma baixa registrada.
