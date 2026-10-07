# Login biométrico Android — versão 1.4.0

Motorista e guia podem marcar **Usar biometria nos próximos acessos** durante o login. Somente após a API validar empresa, e-mail e senha, o acesso pode ser salvo, com confirmação pelo Android. Se a ativação falhar ou for cancelada, o login normal continua funcionando e o app informa que a biometria não foi ativada.

Ao abrir novamente o app com a opção ativada, ele mostra a tela de login e o botão **Entrar com biometria**. A digital ou o reconhecimento facial devem ser classificados como biometria forte pelo Android. Não há substituição pelo PIN nesse botão; o login normal com a senha do Rotafy continua disponível. O cofre autenticado exige Android 9 ou superior; aparelhos sem suporte continuam com senha. A disponibilidade de reconhecimento facial depende do dispositivo.

O acesso salvo contém empresa, e-mail, senha e identificação da conta, em um namespace separado do Flutter Secure Storage. Usa Android Keystore, AES-GCM, autenticação obrigatória por operação e somente biometria forte. Nenhum template biométrico é recebido pelo Rotafy nem enviado ao backend. Os dados biométricos permanecem sob controle do sistema operacional. A senha não é gravada em SQLite, logs ou configuração de distribuição.

Após liberar o cofre, o app faz novo login na API, permitindo renovar sessões vencidas. A API continua validando senha, empresa, papel e permissões. Credenciais rejeitadas por 401/403 desativam o acesso salvo; entre manualmente para reativar com a nova senha. Cancelar a biometria não chama a API nem libera o painel. O acesso salvo não pode trocar a identidade/empresa e continua respeitando a fila do operador original.

Sem conexão, após liberar o cofre, somente a identidade original já preparada pode acessar os dados locais; validades dos manifestos continuam limitando novos registros. Os dados pendentes são preservados. O servidor verifica as permissões novamente na sincronização. Não é possível desbloquear offline por um erro de autenticação do servidor.

Para remover, use **Menu → Desativar biometria**. O usuário permanece conectado, mas os próximos acessos deixam de exigir biometria. **Sair** também apaga o acesso salvo e revoga a sessão. Havendo registros pendentes, Sair continua bloqueado para evitar perda de dados. Ao entrar manualmente, desmarcar a opção também remove a configuração anterior.

Esta implementação protege a abertura após reiniciar o processo do aplicativo; não acrescenta bloqueio automático a cada retorno do segundo plano. O app não recolhe biometria para embarque ou chegada.

Não exige alteração da API ou migração do banco. Instale o APK atualizado sobre a versão existente. Homologue no aparelho a ativação, abertura após fechar completamente o app, cancelamento, senha manual, troca de senha e desativação. Os testes automatizados validam o fluxo de controle; o prompt nativo e o cofre precisam de teste físico.

Validação automatizada: 41 testes Flutter aprovados, incluindo ativação opcional, abertura bloqueada após reiniciar, cancelamento sem chamada à API, senha alterada, identidade da empresa, desbloqueio offline, desativação e logout. Análise estática sem problemas.

Referências: [local_auth oficial](https://pub.dev/packages/local_auth), [integração Android](https://pub.dev/packages/local_auth_android), [Flutter Secure Storage](https://pub.dev/packages/flutter_secure_storage).
