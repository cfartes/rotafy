# Atualizações do Rotafy

## Navegador

Ao abrir o sistema ou retornar à janela, o Rotafy compara a versão carregada com a publicada. Quando há diferença, apresenta **Atualizar aplicativo**. O usuário confirma a atualização depois de salvar os cadastros em andamento. Uma atualização de service worker também apresenta esse aviso. Falhas de conexão não bloqueiam o trabalho offline e a atualização não apaga o banco local de embarques.

## Android

A partir de **1.7.0, compilação 12**, o aplicativo consulta a versão disponível ao iniciar e ao retornar ao primeiro plano. Somente uma compilação superior do mesmo identificador de aplicativo oferece atualização. O botão abre o download do APK no navegador do aparelho. O Android solicita a autorização de instalação; instale por cima, sem desinstalar. Sincronize os registros pendentes antes da instalação.

Versões anteriores precisam receber o APK 1.7.0 manualmente uma primeira vez. A publicação no servidor não adiciona o verificador a um aplicativo antigo já instalado.

## Publicação pelo Superadmin

1. Atualize a VPS com `bash scripts/update_vps.sh` após atualizar o repositório.
2. Entre com Superadmin Nexus de acesso completo, em **Configurações → Atualizações do aplicativo Android**.
3. Selecione o APK e clique em **Publicar atualização Android**.

Após a publicação, **Ajuda e manuais** apresenta a versão disponível e o botão **Baixar APK Android**, para acesso público sem login. O arquivo é servido pela própria VPS. Antes da primeira publicação, a ajuda informa que o download ainda não está disponível; não oferece um link quebrado.

O APK genérico é gerado por `scripts/build_mobile.ps1 -Release`, que inclui os metadados de versão. O arquivo desta entrega está em `artifacts/mobile/nexus-rotafy-1.7.0.apk`. As próximas versões devem aumentar a compilação e manter o identificador e a chave de assinatura anteriores. A instalação Android verifica a compatibilidade de assinatura; o servidor registra o SHA-256 do arquivo publicado.

Somente o Superadmin completo publica APKs. Arquivos específicos de uma empresa não são aceitos na distribuição geral. Limite: 150 MB. A API disponibiliza consulta e download públicos para funcionar antes do login, sem incluir credenciais de usuários no APK.

Os metadados ficam na tabela `mobile_releases`, criada por migração incremental. Os arquivos ficam no volume persistente `mobile_releases`, montado em `/app/mobile-releases`. Inclua esse volume nos backups; o backup do banco, isoladamente, não contém APKs. A atualização não recria o banco nem exige reinstalação dos demais serviços.

O navegador utiliza `/version.json`, sem cache, emitido junto com a compilação web. O build de produção recebe o identificador `RELEASE` do processo de implantação.
