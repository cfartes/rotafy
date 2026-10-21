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

Ao suspender uma empresa, o sistema também suspende os envios e agenda automaticamente a desconexão do WhatsApp. A solicitação permanece registrada para nova tentativa se o serviço estiver indisponível. Reativar a empresa não reconecta o WhatsApp: o administrador deve solicitar a conexão no painel.

O cadastro de novas empresas é exclusivo da equipe Nexus, incluindo o perfil restrito **Equipe Nexus**. O cliente não possui opção de cadastro no login. Após salvar, utilize **Enviar acesso por e-mail**, **Enviar acesso por WhatsApp** ou **Enviar pelos dois canais**. O destinatário de e-mail é o primeiro administrador ativo da empresa; o WhatsApp utiliza o telefone informado no cadastro da empresa. As mensagens incluem os dados cadastrais, identificador, e-mail de login e um link para definir senha, válido por 24 horas. A senha inicial não é enviada em texto.

O WhatsApp utiliza a sessão da Nexus definida para comunicação/cobrança, sem exigir pareamento prévio da empresa recém-criada. Acompanhe o resultado nessa tela. Se faltar configuração, a empresa permanece cadastrada; corrija a configuração e envie novamente. Também é possível usar **Enviar acesso** na lista de empresas. Um novo convite invalida os links anteriores.

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

Cada empresa utiliza seu número e uma sessão exclusiva. Novos cadastros agendam a criação da sessão automaticamente. O administrador da empresa encontra o menu **WhatsApp**, confere o telefone do cadastro da empresa e escaneia o QR Code no próprio Rotafy. O sistema confere o número antes de liberar os envios. A criação da empresa não aguarda a disponibilidade do serviço de mensagens.

1. Localize a empresa em **WhatsApp de cada empresa**.
2. Confira o **WhatsApp de envio**. O telefone de contato aparece como sugestão; ajuste para o número conectado. Utilize + e código do país para números internacionais.
3. Ative **Identificar e salvar a sessão automaticamente pelo telefone**. O telefone é salvo ao sair do campo.
4. Defina **Habilitar envios**. O sistema identifica uma única sessão conectada correspondente ao telefone e salva o ID automaticamente.
5. Acompanhe o estado na tela. Se a sessão ainda não existir, a busca continuará a cada minuto, mesmo com a tela fechada.

O pareamento no celular continua necessário. A identificação automática por telefone descrita acima é uma alternativa de suporte Nexus; a empresa também pode usar o QR no próprio Rotafy. Alterações manuais da Nexus prevalecem sobre a conexão automática até nova solicitação explícita do administrador da empresa. Duplicidades e sessões vinculadas a outra empresa impedem a associação automática. Empresas suspensas não são consultadas. Os vínculos existentes são preservados até a ativação do modo automático. Para configuração manual, desmarque a identificação automática e informe o ID conferido no serviço.

### Conferir envios

Em **Configurações → Cobrança mensal**, utilize **Testar envio de cobrança**. Salve primeiro o remetente e a sessão WhatsApp de cobrança. Informe seu e-mail ou telefone de teste e clique no botão do canal desejado. O teste utiliza a configuração salva e funciona mesmo com a cobrança automática desativada. A mensagem é identificada como teste e não cria fatura, altera assinatura ou solicita pagamento.

O teste utiliza o mesmo modelo da cobrança definitiva, com valores ilustrativos e aviso **TESTE DE COBRANÇA — NÃO PAGAR**. O e-mail apresenta um resumo organizado do ciclo e dos valores, com QR Code incorporado. No WhatsApp, o QR Code é enviado como imagem com o resumo na legenda. O Copia e Cola acompanha o e-mail e a legenda quando couber.

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


## 7. Setup, teste e cobranças da assinatura {#cobrancas}

### Configurar e ativar

1. Entre em **Configurações**, na seção **Cobrança e período de teste**.
2. Marque **Usar InfinitePay nas novas cobranças**, informe **Identificador InfinitePay (InfiniteTag)**, sem `$`, **Taxa de setup (R$)** e **Prazo de teste (dias)**. O identificador deve pertencer à conta da Nexus que receberá os pagamentos.
3. Selecione ou informe o **ID da sessão WhatsApp de cobrança da Nexus**. As cobranças saem pelo número da Nexus, utilizando as credenciais de comunicação configuradas no painel.
4. Confira o e-mail remetente e os canais de comunicação.
5. Marque **Ativar avisos e cobranças mensais automáticas** e salve.

A configuração começa desativada. Configure e ative antes de cadastrar clientes com teste. Setup e prazo de teste são registrados na nova contratação; alterações posteriores não modificam essas condições nos clientes já cadastrados. Desativar a cobrança automática pausa novos fechamentos e envios, preservando débitos e pagamentos existentes. A confirmação de pagamentos já efetuados continua sendo processada.

Os dados de **Pix manual** ficam em uma seção separada. Utilize essa configuração para cobranças manuais: chave, favorecido e, opcionalmente, Pix Copia e Cola sem valor definido. Cobranças antigas preservam o meio de pagamento que receberam quando foram emitidas.

### Novos clientes e período de teste

No cadastro, a empresa recebe a franquia do plano durante o teste, sem cobrança de setup, mensalidade ou excedentes. A criação de viagens além dessa franquia é impedida durante o teste.

Exemplo: cadastro em **10/10**, com **7 dias** de teste. Em **17/10**, o sistema registra somente o **setup**, gera o link e agenda o envio por e-mail e WhatsApp. Nessa data começa o primeiro ciclo de 30 dias, com franquia nova. Em **16/11**, cobra a **primeira mensalidade e os excedentes desse ciclo**. A utilização do teste não é transferida como excedente para o período pago. Setup configurado como zero não gera cobrança separada.

Cada renovação cobra a mensalidade e os excedentes do período de 30 dias que acabou de ser utilizado. O setup é uma cobrança única e separada. Como os períodos são fixos de 30 dias, o dia do mês pode variar: 17/10 → 16/11 → 16/12 → 15/01. A franquia também é renovada a cada ciclo de 30 dias.

Clientes anteriores à ativação mantêm seus ciclos e não recebem setup ou teste retroativos. Novas cobranças definitivas desses contratos podem utilizar o link automático quando a integração estiver habilitada.

### Calendário e mensagens automáticas

Um dia antes da cobrança, a empresa recebe um aviso parcial, sujeito a alteração e sem link para pagamento. Na data prevista, o sistema consolida os valores, preserva a cobrança no financeiro e disponibiliza o link de pagamento. Se houver falha na geração do link, a cobrança permanece registrada e o sistema tenta novamente. O envio definitivo aguarda a disponibilidade do link.

O prazo termina ao fim do segundo dia útil contado a partir do dia seguinte ao fechamento, no horário de Brasília. Sábados, domingos e feriados do calendário nacional, incluindo a Sexta-feira da Paixão, não entram na contagem. Pontos facultativos e feriados estaduais ou municipais não são considerados.

Os e-mails são enviados aos administradores ativos da empresa. O WhatsApp utiliza o telefone de contato cadastrado na empresa. Mantenha esses contatos atualizados.

### Acompanhar e dar baixa

Abra **Financeiro e cobranças**. Utilize o filtro de situação para consultar avisos parciais, cobranças abertas, vencidas, pagas e canceladas. Cada cobrança apresenta ciclo, plano, franquia, utilização, excedentes, valor total, prazo e referência.

Nas cobranças com link, a confirmação é automática após verificação do pagamento. O painel mostra **Pagar agora**, situação e identificação da transação; o cliente recebe confirmação por e-mail e WhatsApp. A página de retorno aguarda a conferência do sistema.

Consulte **Confirmações automáticas de pagamento** para acompanhar verificações pendentes, confirmadas e situações que exigem conferência. Pagamentos com valor divergente ou após cancelamento/baixa ficam sinalizados para análise. A confirmação repetida da mesma transação não gera outra baixa.

Se a geração do link for recusada, confira a InfiniteTag e use **Tentar gerar link novamente**. Essa ação permite corrigir a conta de uma solicitação recusada que ainda não disponibilizou link. Links já emitidos preservam a conta de recebimento original.

Para um recebimento conferido fora desse fluxo, use **Baixa manual excepcional**; nas cobranças antigas, **Confirmar recebimento do Pix**. Informe data/hora e referência. O usuário da baixa fica registrado. Não é possível dar baixa em aviso parcial ou informar uma data futura.

### Bloqueio e liberação

Se não houver confirmação até o prazo, a empresa recebe aviso por e-mail e WhatsApp. O administrador fica restrito ao Financeiro, onde pode solicitar o link da cobrança pendente e pagar. Motorista e guia preservam o acesso às viagens já vendidas. O resumo financeiro mostra valor a vencer, contador de ciclos X/12, mensalidade, vencimento e situação. O aviso de cinco dias pode ser desabilitado individualmente, sem alterar as mensagens de cobrança.

A baixa retira a restrição daquela cobrança. Se houver outras cobranças vencidas, a empresa continua restrita. Uma suspensão administrativa permanece independente e não é removida pelo pagamento.

A ação **Cancelar cobrança** preserva o histórico e retira aquela cobrança da apuração de bloqueio. Não representa devolução de dinheiro nem cancela um link externo já emitido. Um pagamento posterior será sinalizado para conferência. Não cancele uma cobrança para registrar um recebimento; utilize a baixa correspondente.

### Histórico dos envios financeiros

O painel mostra o evento, canal, empresa, situação e motivo de falha de cada comunicação. Aceitação pelo serviço não significa entrega ou leitura. Um WhatsApp com resultado incerto não é repetido automaticamente. Confira o recebimento antes de qualquer nova comunicação. Falhas de comunicação não desfazem uma baixa registrada.

## 8. Contratos e aceitação pelo cliente {#contratos}

Em **Configurações → Contrato de utilização**, o administrador Nexus completo consulta a minuta e prepara novas versões em rascunho. Leia o texto integral e revise as condições comerciais e jurídicas antes de marcar a aprovação e usar **Publicar versão aprovada**. A versão r2 aprovada é ativada pelo processo de atualização, após conferir o texto e a configuração de e-mail. Novas versões preparadas no painel continuam dependendo de revisão e publicação explícita.

A publicação exige configuração de e-mail e ativa o aceite apenas para empresas criadas depois dela. Versões publicadas não podem ser alteradas e aceites anteriores não são reescritos por outra publicação. No endereço do cadastro, comece pelo CEP: ao completar oito dígitos, o sistema consulta e preenche logradouro, bairro, cidade e UF. Confira e informe número e complemento opcional. O preenchimento manual permanece disponível, inclusive quando o CEP não é encontrado.

O representante confirma os dados, lê ou baixa o contrato e aceita no primeiro acesso com código enviado ao próprio e-mail. A equipe comercial não aceita pelo cliente. Enquanto houver pendência exigida, o acesso operacional é restringido; ficam disponíveis os recursos necessários ao aceite e ao Financeiro.

Em **Empresas → Contrato**, consulte a situação, versão, data, e-mail, hash e evidências, e baixe a cópia preservada e seu comprovante. Este acesso é exclusivo do administrador Nexus completo. O registro eletrônico não equivale a certificação ICP-Brasil ou garantia de resultado judicial.


### Propor mudança de plano

Em **Planos e assinaturas**, abra a assinatura da empresa, escolha **Plano para o próximo ciclo** e utilize **Enviar aditivo para aceite**. É necessário ter uma versão aprovada do contrato publicada, envio de e-mail configurado e ciclo pago em andamento. A empresa deve concluir eventual aceite inicial pendente antes de receber uma mudança.

A proposta fixa as condições do plano escolhido e envia um convite por e-mail ao administrador da empresa. O painel mostra **Aguardando aceite** e a situação do envio. O plano atual permanece. Uma proposta ainda sem aceite pode ser cancelada pela Nexus; outra proposta só pode ser criada após esse cancelamento.

O representante lê, baixa e aceita o aditivo no próprio acesso, com confirmação por e-mail. Somente então a mudança fica agendada para o próximo ciclo, sem novo setup, reinício do teste ou cobrança proporcional. Caso a data prevista passe, o cliente prepara outra cópia com vigência atualizada. O botão de cancelamento de proposta não remove uma alteração já aceita.

A edição do catálogo não reajusta automaticamente os clientes nos ciclos futuros. Para alterar as condições de uma empresa, proponha um aditivo. Em **Empresas → Contrato**, consulte o histórico e baixe os aditivos aceitos e seus comprovantes. O contrato inicial e os documentos anteriores são preservados.


## 9. Publicar atualização Android {#atualizacao-android}

Em **Configurações → Atualizações do aplicativo Android**, selecione o APK e clique em **Publicar atualização Android**. A tela informa versão, compilação, data, SHA-256 e download. Utilize uma compilação superior, com o mesmo aplicativo e chave de assinatura.

A partir de 1.7.0, o Android consulta atualizações ao abrir e oferece o botão para baixar uma versão mais nova. Versões anteriores precisam receber essa primeira atualização manualmente. O cliente instala por cima, sem desinstalar, e deve sincronizar os registros pendentes antes.
