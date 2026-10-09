# Convites de colaboradores por WhatsApp

Entrega de 09/10/2026, migração `0021_whatsapp_invitations`.

Em **Equipe → Adicionar pessoa**, informe nome, e-mail, perfil e telefone/WhatsApp. Marque **Enviar convite para a pessoa definir sua senha** e selecione **E-mail**, **WhatsApp** ou **E-mail e WhatsApp**. O telefone é validado e obrigatório para WhatsApp. O e-mail permanece obrigatório porque é o identificador de login dos colaboradores.

Para um colaborador existente, use **Enviar convite** na linha da equipe. O formulário permite escolher o canal e cadastrar ou atualizar o telefone. O número é salvo na empresa daquele usuário. Apenas administradores da empresa podem convidar ou consultar os envios; o mesmo colaborador de empresas diferentes mantém cadastros independentes.

O convite usa o fluxo atual de criação de senha, com link privado de uso único válido por 24 horas. Não envia senha temporária. Ao selecionar os dois canais, ambos recebem o mesmo link. Reenviar substitui o link anterior. Ao cadastrar sem convite, a senha inicial continua disponível.

WhatsApp usa a sessão da empresa configurada em **Nexus → Configurações**. O envio apenas por WhatsApp independe da configuração Resend. E-mail ou ambos exigem Resend configurado. A operação é transacional: se faltar telefone ou integração, não cria um colaborador sem convite nem invalida um link anterior.

O worker `whatsapp` processa os convites na fila existente. O corpo com link é cifrado; o histórico não retorna corpos, tokens ou chaves. Antes de enviar, confere sessão, empresa, usuário ativo, telefone, validade e uso/substituição do link. Convites obsoletos são descartados. Respostas incertas não são reenviadas automaticamente. O histórico WhatsApp aparece na janela **E-mails de acesso**, em sua própria seção, e diferencia aceitação pelo OpenWA de entrega ao celular.

Atualize a VPS com o instalador habitual. A migração adiciona telefone aos usuários e suporte a convites na fila, preservando reservas, bilhetes e dados existentes. Não altera o APK. Testes utilizam provedores simulados; o envio real deve ser homologado com a sessão conectada e um telefone autorizado.
