# Instalação automática na Hostinger

Domínio: **rotafy.nexusdataanalytics.tech**. Instala API, painel, PostgreSQL/PostGIS, migrações, superadmin e workers. A configuração de novos builds Android utiliza esse domínio. APKs antigos precisam ser atualizados para utilizar o endereço corrigido.

## Instalação independente

### Instalação limpa, com banco vazio

```sh
curl -fSL https://raw.githubusercontent.com/cfartes/rotafy/main/scripts/install_clean_vps.sh -o /tmp/install-rotafy-clean.sh
bash /tmp/install-rotafy-clean.sh
```

Esse comando clona novamente o código em `/opt/rotafy-tech`, remove containers e volumes de uma eventual instalação do projeto **nexus-rotafy-tech** e gera novas credenciais. Os dados desse projeto são apagados. Um checkout anterior nessa pasta é renomeado. Não copia banco, empresas ou usuários da instalação antiga. Quando a nova aplicação estiver saudável, para os containers do projeto **nexus-rotafy-prod** para liberar a rota do domínio. Os volumes antigos não são apagados; nenhum outro projeto da VPS é interrompido.

O primeiro administrador Nexus é criado conforme `.env.production` da nova pasta. Consulte as credenciais privadamente no servidor e cadastre novamente planos, empresas e colaboradores. Não envie o arquivo de ambiente pelo chat.

No DNS, configure o registro **A** de `rotafy.nexusdataanalytics.tech` para **187.77.58.10**. Remova um eventual registro AAAA que aponte para outro servidor. O Traefik existente precisa conseguir emitir o certificado para o endereço correto.

Execute na VPS:

```sh
curl --fail --show-error --location \
  https://raw.githubusercontent.com/cfartes/rotafy/main/scripts/install_vps.sh \
  --output /tmp/install-rotafy-vps.sh
bash /tmp/install-rotafy-vps.sh
```

O script instala em `/opt/rotafy-tech`, com o projeto `nexus-rotafy-tech`, banco inicialmente vazio, credenciais próprias e regras exclusivas do Traefik. Não reutiliza os volumes ou o ambiente da instalação antiga. Não copie o `.env.production` antigo: o instalador bloqueia ambientes sem a identificação desta instalação. Atualizações posteriores preservam os dados deste novo projeto e realizam backup antes das migrações.

Se o sistema já foi instalado com um script anterior, confira o nome do projeto antes de executar novamente. Esta versão cria uma instalação independente; não transfere dados de `nexus-rotafy-prod`.

O script pode pedir os parâmetros do Traefik se a detecção não encontrar uma única configuração. Em repositório privado, utilize o checkout autenticado existente e o procedimento de atualização abaixo.

## Pré-requisitos

VPS Linux com Python 3.9+, Git, Docker e Compose v2.24 ou superior, acesso ao repositório e Traefik existente com provider Docker, rede bridge compartilhada, entrypoint HTTPS e resolver ACME. O script não reinstala Docker nem modifica o proxy dos demais apps. Configure DNS A para a VPS e não mantenha AAAA incorreto.

## Primeira instalação

Execute no terminal SSH/Hostinger como root:

```sh
git clone --branch main https://github.com/cfartes/rotafy.git /opt/rotafy-tech
cd /opt/rotafy-tech
python3 scripts/deploy_vps.py
```

Se o repositório for privado, autentique Git no terminal sem incluir tokens na URL/comando. O diretório de instalação precisa ser novo; para checkout existente, use o procedimento de atualização abaixo.

O script detecta o container Traefik, rede, entrypoint e resolver pelas labels/flags. Em caso de ambiguidade ou configuração somente em arquivo, pede os nomes reais no terminal. Para investigar: `python3 scripts/diagnose_traefik.py`.

Com nomes conhecidos, substitua os exemplos:

```sh
python3 scripts/deploy_vps.py \
  --traefik-container NOME_CONTAINER \
  --network NOME_REDE \
  --entrypoint NOME_HTTPS \
  --resolver NOME_RESOLVER \
  --admin-email admin@nexusdataanalytics.com.br \
  --non-interactive
```

`python3 scripts/deploy_vps.py --dry-run` verifica sem criar ambiente nem iniciar containers. O checkout precisa estar limpo; a tag da imagem identifica a revisão Git instalada.

## Etapas automatizadas

1. Verifica Linux, acesso ao Docker/Compose e Git limpo; bloqueia implantações concorrentes.
2. Obtém parâmetros/IP do Traefik; a API confia somente no IP desse proxy para cabeçalhos de encaminhamento.
3. Cria `.env.production` com permissão 600 e senhas aleatórias apenas na primeira instalação, sem imprimi-las. Preserva senhas existentes; banco existente sem arquivo de ambiente interrompe o processo.
4. Valida Compose sem imprimir valores e compila imagens API/web.
5. Com volume de banco existente, inicia apenas DB e faz dump antes das migrações. Se o backup falhar, não inicia a aplicação/migrações. Dump local contém dados pessoais e precisa de proteção e cópia externa.
6. Executa migrações/bootstrap, inicia serviços e aguarda saúde; verifica os processos únicos.
7. Confere API interna e HTTPS público com certificado válido. Falha pública informa erro e mantém serviços para diagnóstico; não faz rollback/downgrade automático.

Não remove volumes, não copia banco local, não abre portas novas no host nem altera outros projetos. Provider Swarm, quando detectado, exige outra implantação e é bloqueado.

## Acesso e Android

Abra `https://rotafy.nexusdataanalytics.tech`. Consulte privadamente `BOOTSTRAP_EMAIL`/`BOOTSTRAP_PASSWORD` em `.env.production`; guarde no cofre e não compartilhe o arquivo. O bootstrap não redefine senha de administrador já provisionado.

Cadastre planos/empresas e homologue o APK release: motorista, guia, viagem sem guia, câmera, offline e presença no painel. Debug/local e release usam pacotes/ambientes diferentes; sincronize pendências antes de mudar de app.

## Atualizar

O atualizador também reconhece a instalação ativa em `/opt/nexus-rotafy` com projeto `nexus-rotafy-prod`, mesmo sem `DEPLOY_PROJECT`. Nesse caso, mantém o projeto e o volume existentes. Antes de aceitar esse ambiente, confere as labels do banco, a pasta e o volume montado. Não cria um banco `nexus-rotafy-tech` durante essa atualização.

Entre na pasta da instalação antes de executar o script. A pasta atual é utilizada quando contém Git e `.env.production`; caso contrário, o script busca uma única instalação conhecida. Em caso de ambiguidade, informe `ROTAFY_INSTALL_DIR` explicitamente.

Para atualizar a instalação independente existente, utilize o checkout Git da VPS. Isso também funciona com repositório privado, desde que o Git do servidor esteja autenticado. Execute os comandos encadeados para interromper em caso de falha:

```sh
cd /opt/rotafy-tech &&
git pull --ff-only origin main &&
bash scripts/update_vps.sh
```

O atualizador exige o checkout, um ambiente correspondente ao projeto identificado e o volume de banco existente. Não cria uma instalação nova nem transfere dados entre projetos. Obtém a versão mais recente de `main`, compila os serviços, faz backup, aplica eventuais migrações e verifica os serviços e o HTTPS. Preserva credenciais, banco e chave de integrações. Se já tiver o script atualizado no checkout, use `bash scripts/update_vps.sh` dentro da instalação.

Se `raw.githubusercontent.com` retornar 404, não execute uma cópia antiga em `/tmp`. Use o procedimento Git acima. Em instalações que continuam em `/opt/nexus-rotafy`, substitua somente a pasta no comando `cd`; o atualizador confere o projeto e o volume antes de prosseguir.

O instalador pode clonar um diretório novo; o atualizador exige uma instalação existente. Ambos atualizam `main` do remoto correto com `pull --ff-only`, preservando configurações ignoradas. Bloqueiam outro remoto, outra branch e alterações locais. Outro diretório pode ser definido por `ROTAFY_INSTALL_DIR=/opt/rotafy`.

Os scripts podem atualizar Git mesmo recebendo `--dry-run`; apenas o script Python não modifica arquivos nesse modo. O instalador também pode clonar nesse modo. Sincronize aparelhos e programe janela antes de atualizações. Backup local não substitui armazenamento externo criptografado e restauração ensaiada.

## Diagnóstico

```sh
cd /opt/rotafy-tech
docker compose --project-name nexus-rotafy-tech --env-file .env.production -f compose.production.yaml ps -a
python3 scripts/diagnose_traefik.py
curl --fail https://rotafy.nexusdataanalytics.tech/api/v1/health
```

Não compartilhe `.env.production`, `docker inspect` completo ou `docker compose config` sem `--quiet`. Se o IP do Traefik mudar, reaplique o instalador. DNS/certificado incorreto exige ajuste no domínio/proxy existente.

WhatsApp e Resend são configurados em **Nexus → Configurações**, sem editar o ambiente nem reiniciar serviços. Consulte [WHATSAPP_E_CONFIGURACOES.md](WHATSAPP_E_CONFIGURACOES.md). Storage externo e agenda de backup seguem [IMPLANTACAO_E_OPERACAO.md](IMPLANTACAO_E_OPERACAO.md). Nenhuma credencial de storage é presumida.

## Validação

### Permissões de arquivos e recuperação

O código Git precisa ser legível pelos usuários dos containers. O wrapper usa `umask 022` para o checkout; o instalador Python mantém `umask 077` para credenciais e backups. As imagens ajustam leitura/travessia do código e dos arquivos estáticos, mantendo a execução da API sem root. O script público de inicialização PostgreSQL tem permissão 644; `.env.production` continua 600.

Antes de substituir serviços, o instalador executa `alembic heads` na imagem de migração para conferir carregamento dos arquivos sem acessar ou alterar o banco.

Se uma versão anterior falhar com `PermissionError` ao ler uma migração, atualize e reaplique:

```sh
cd /opt/rotafy-tech
git pull --ff-only origin main
bash scripts/install_vps.sh
```

Não é necessário remover o banco, alterar a revisão Alembic manualmente ou liberar as permissões das credenciais.

Sete testes do instalador aprovados em container Linux: preservação de credenciais, banco sem ambiente, configuração de proxy, modo de inspeção e falha de backup antes das migrações. Sintaxe Bash validada. Não houve execução na VPS nem homologação no Traefik real nesta entrega.
