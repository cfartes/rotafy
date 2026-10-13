# Instalação automática na Hostinger

Domínio: **rotafy.nexusdataanalytics.tech**. Instala API, painel, PostgreSQL/PostGIS, migrações, superadmin e workers. A configuração de novos builds Android utiliza esse domínio. APKs antigos precisam ser atualizados para utilizar o endereço corrigido.

## Instalação completa ou correção do domínio

No DNS, configure o registro **A** de `rotafy.nexusdataanalytics.tech` para **187.77.58.10**. Remova um eventual registro AAAA que aponte para outro servidor. O Traefik existente precisa conseguir emitir o certificado para o endereço correto.

Execute na VPS:

```sh
curl --fail --show-error --location \
  https://raw.githubusercontent.com/cfartes/rotafy/main/scripts/install_vps.sh \
  --output /tmp/install-rotafy-vps.sh
bash /tmp/install-rotafy-vps.sh
```

O mesmo script faz a instalação completa em um diretório novo ou atualiza uma instalação existente em `/opt/nexus-rotafy`. Na instalação existente, mantém o projeto `nexus-rotafy-prod`, seus volumes, senhas e contas, realiza backup e aplica a configuração do domínio correto. Não remova a pasta, o arquivo `.env.production` ou os volumes para corrigir o domínio. A emissão dos novos bilhetes e links de acesso passa a utilizar o endereço corrigido; links enviados com o domínio anterior devem ser enviados novamente ao destinatário.

O script pode pedir os parâmetros do Traefik se a detecção não encontrar uma única configuração. Em repositório privado, utilize o checkout autenticado existente e o procedimento de atualização abaixo.

## Pré-requisitos

VPS Linux com Python 3.9+, Git, Docker e Compose v2.24 ou superior, acesso ao repositório e Traefik existente com provider Docker, rede bridge compartilhada, entrypoint HTTPS e resolver ACME. O script não reinstala Docker nem modifica o proxy dos demais apps. Configure DNS A para a VPS e não mantenha AAAA incorreto.

## Primeira instalação

Execute no terminal SSH/Hostinger como root:

```sh
git clone --branch main https://github.com/cfartes/rotafy.git /opt/nexus-rotafy
cd /opt/nexus-rotafy
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

```sh
bash /opt/nexus-rotafy/scripts/install_vps.sh
```

O wrapper clona em diretório novo ou atualiza `main` do remoto correto com `pull --ff-only`, preservando configurações ignoradas. Bloqueia diretório existente sem Git, outro remoto, outra branch e alterações locais. Outro diretório pode ser definido por `ROTAFY_INSTALL_DIR=/opt/rotafy`.

O wrapper pode atualizar/clonar Git mesmo recebendo `--dry-run`; apenas o script Python não modifica arquivos nesse modo. Sincronize aparelhos e programe janela antes de atualizações. Backup local não substitui armazenamento externo criptografado e restauração ensaiada.

## Diagnóstico

```sh
cd /opt/nexus-rotafy
docker compose --project-name nexus-rotafy-prod --env-file .env.production -f compose.production.yaml ps -a
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
cd /opt/nexus-rotafy
git pull --ff-only origin main
bash scripts/install_vps.sh
```

Não é necessário remover o banco, alterar a revisão Alembic manualmente ou liberar as permissões das credenciais.

Sete testes do instalador aprovados em container Linux: preservação de credenciais, banco sem ambiente, configuração de proxy, modo de inspeção e falha de backup antes das migrações. Sintaxe Bash validada. Não houve execução na VPS nem homologação no Traefik real nesta entrega.
