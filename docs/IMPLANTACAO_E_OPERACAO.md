# Implanta??o Hostinger com Traefik ? 06/10/2026

Entrega: `2026-10-06-v1`. Dom?nio: `rotafy.nexusdataanalytics.tech`. VPS informada: `187.77.58.10`, SSH `root`. Nenhuma publica??o remota foi realizada nesta entrega. iOS est? fora desta etapa.

## Diagn?stico pr?vio

Copie `scripts/diagnose_traefik.py` para a VPS e execute `python3 scripts/diagnose_traefik.py`. O script ? somente leitura e seleciona nomes, redes/IPs, portas, entrypoints e resolvers. N?o retorna vari?veis de ambiente nem logs completos. Envie sua sa?da para ajustarmos os quatro par?metros `TRAEFIK_*`.

Se o resultado mostrar Swarm ativo e provider Swarm, revise a implanta??o antes de executar: esta entrega ? para Docker Compose com provider Docker; n?o ? um stack Swarm.

## Arquitetura

O Compose usa o projeto separado `nexus-rotafy-tech` e a rede externa do Traefik existente. N?o cria proxy novo nem publica portas 80/443 ou banco/API no host. Somente API e web t?m descoberta Traefik habilitada. API atende `/api/` diretamente na porta interna 8000; web atende o restante na porta 80. Banco/worker usam redes internas, e e-mail/backup t?m redes de sa?da pr?prias.

API exige cookies Secure e aceita origem `https://rotafy.nexusdataanalytics.tech`. Configure `TRAEFIK_TRUSTED_IPS` com o IP do Traefik na rede compartilhada, nunca `*`. Se o IP mudar ao recriar Traefik, atualize a configura??o e recrie a API. A valida??o de IP evita confiar indiscriminadamente em cabe?alhos de encaminhamento. Confirme tamb?m que o Traefik n?o confia em cabe?alhos externos arbitr?rios.

## Preparar o servidor

Envie o ZIP `artifacts/releases/nexus-rotafy-vps-2026-10-06-v1.zip`, confira SHA256 e extraia em `/opt/rotafy-tech`. Pacote cont?m fontes, lockfiles e configura??o; imagens ser?o compiladas na VPS. N?o cont?m banco local, credenciais, chave de assinatura Android ou depend?ncias instaladas.

Aponte DNS A do dom?nio para a VPS. S? publique AAAA se o IPv6 estiver configurado. Rede, entrypoint HTTPS e resolver TLS precisam existir no Traefik; n?o altere os servi?os dos demais apps. Use o redirecionamento HTTP?HTTPS j? configurado no Traefik, ou configure-o ap?s o diagn?stico.

Execute no diret?rio extra?do:

```sh
python3 scripts/prepare_production_env.py
nano .env.production
chmod 600 .env.production
```

O gerador cria senhas aleat?rias de banco e superadmin, sem mostr?-las e sem sobrescrever arquivo existente. Preencha `TRAEFIK_NETWORK`, `TRAEFIK_HTTPS_ENTRYPOINT`, `TRAEFIK_CERTRESOLVER`, `TRAEFIK_TRUSTED_IPS` com os dados reais do diagn?stico. Configure Resend se quiser habilitar e-mails. Guarde credenciais em cofre; n?o envie `.env.production` no chat. N?o reutilize credenciais locais.

## Subir a aplica??o

Somente ap?s preencher os par?metros reais:

```sh
docker compose --env-file .env.production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.production.yaml build api web
docker compose --env-file .env.production -f compose.production.yaml up -d
docker compose --env-file .env.production -f compose.production.yaml ps
curl --fail https://rotafy.nexusdataanalytics.tech/api/v1/health
```

N?o execute `docker compose config` sem `--quiet` ao compartilhar sa?da: pode exibir senhas. Migra??o e bootstrap precedem a API. Bootstrap cria o primeiro administrador Nexus e n?o redefine senha de instala??es existentes. Para primeiro acesso, consulte localmente os valores BOOTSTRAP_EMAIL/BOOTSTRAP_PASSWORD gerados e troque a senha no painel.

A instala??o come?a com banco novo. Dados locais existentes n?o s?o copiados automaticamente. Migra??o de dados requer backup/restaura??o separada, sem sobrescrever banco ativo.

## Android

APK release assinado: `artifacts/mobile/nexus-rotafy-release.apk`. Aponta ao dom?nio HTTPS novo e dispensa cabo/encaminhamento USB depois que a VPS estiver publicada. Este APK Nexus permite escolher empresa no login; apps exclusivos por cliente usam `mobile/config/company.example.json` com slug, nome e APP_ID espec?ficos.

Assinatura Nexus fica somente no computador de desenvolvimento em `~/.nexus-rotafy/android-signing/`; mantenha backup privado do keystore e das propriedades num cofre, pois s?o necess?rios para atualiza??es. N?o est?o no ZIP. A c?pia local de `mobile/android/key.properties` ? ignorada. Para assinatura de outro cliente, configure arquivo separado e use a propriedade Gradle `rotafySigningFile`, ou substitua a configura??o local pelo par correto antes do build.

Recompilar: execute `scripts/create_android_signing.py` na raiz e, em `mobile/`, `flutter build apk --release --dart-define-from-file=config/production.json`. N?o execute o gerador Nexus para substituir identidade j? distribu?da de um cliente.

APK tem pacote diferente do debug local e pode coexistir no celular; filas offline ficam separadas. Sincronize o app local antes de migrar o uso. Valide login de motorista/guia, c?mera, offline e atualiza??o do painel via HTTPS. APK compilado n?o comprova API publicada ou homologa??o f?sica conclu?da.

## Backup externo criptografado

O serviço `backup` está sob o perfil `backup`, sem execução automática até configurar o repositório. Usa `pg_dump` custom do banco completo, incluindo marcas, reservas, bilhetes, eventos e auditoria; restic envia o arquivo criptografado a um repositório S3 fora da VPS. Não inclui os arquivos de configuração/segredos do host nem configura??o do Traefik; mantenha esses itens em cofre/processo próprio.

Configure `.env.backup` com endpoint, bucket, credenciais S3 e senha de criptografia. Crie o repositório uma vez, com a opção de entrypoint do Compose:

```sh
docker compose --env-file .env.production -f compose.production.yaml --profile backup run --rm --entrypoint restic backup init
docker compose --env-file .env.production -f compose.production.yaml --profile backup run --rm backup
docker compose --env-file .env.production -f compose.production.yaml --profile backup run --rm --entrypoint restic backup snapshots
docker compose --env-file .env.production -f compose.production.yaml --profile backup run --rm --entrypoint restic backup check
```

Depois do primeiro envio e conferência, instale as unidades de `infra/systemd` em `/etc/systemd/system`, ajustando usuário/diretório. Execute `systemctl daemon-reload` e `systemctl enable --now rotafy-backup.timer`. A agenda é 03:00 UTC, correspondente a 00:00 de Brasília, com até cinco minutos de dispersão; horário definido explicitamente, independente do fuso do servidor. `Persistent=true` recupera uma execução perdida durante desligamento. Consulte `systemctl list-timers` e `journalctl -u rotafy-backup.service` para falhas.

Planejamento inicial: backup diário, objetivo de perda de dados de até 24 horas e restauração em até quatro horas. Esses objetivos ainda precisam ser medidos na VPS com o storage escolhido. Retenção proposta: 14 diários, oito semanais e 12 mensais. Nenhuma exclusão automática foi habilitada: aplicar política `forget/prune` somente após conferir snapshots, custo do storage e restauração. Verificar o repositório semanalmente e ensaiar a restauração mensalmente.

**O envio externo e a agenda na VPS estão pendentes**, pois o destino ainda não foi informado. Build do serviço/restic e sintaxe do script foram validados localmente.

## Ensaio de restauração e recuperação

Executado localmente com [scripts/restore_drill.py](../scripts/restore_drill.py). O script exporta um snapshot consistente e restaura num container novo, sem rede ou portas, criado com nome UUID. Cria o banco de destino a partir de `template0` para evitar conflito com schemas pré-instalados do PostGIS. Confere contagens de 18 tabelas, incluindo fila de e-mails e recuperação de senha, versão Alembic, papéis sem superusuário/BYPASSRLS, RLS forçado, escopo de duas empresas e histórico sem permissão de alteração/exclusão; remove somente esse container temporário no encerramento.

```powershell
.venv\Scripts\python.exe scripts/restore_drill.py
```

Resultado em [RESTORE_DRILL_RESULT.json](RESTORE_DRILL_RESULT.json). Dumps locais ficam em `artifacts/backups`, fora do versionamento, e contêm os dados do banco; são arquivos de desenvolvimento sem criptografia própria. O ensaio não lê um snapshot do storage externo e não prova recuperação da VPS.

Na recuperação de produção, recupere o dump do restic para um ambiente isolado, provisione os papéis `rotafy_app` e `rotafy_platform` sem superusuário/BYPASSRLS e um banco vazio criado de `template0`, então execute `pg_restore --exit-on-error --single-transaction`. Configure novas senhas dos papéis fora do dump e teste com a versão de aplicação correspondente à revisão restaurada. Somente após validação e revisão mude o tráfego para esse ambiente. Não restaure sobre o volume ativo durante o ensaio.

## Atualização e rollback

1. Registre a entrega atual e gere um backup externo; confirme seu snapshot e possibilidade de restauração.
2. Prepare as novas imagens com uma tag `RELEASE` nova e revise as migrações. Combine uma janela operacional, sincronizando os aparelhos com filas offline antes de atualizar.
3. Aplique as migrações da entrega e suba API/web/worker. Confirme saúde e jornadas principais. PWA ativa a nova interface quando as abas da versão anterior forem encerradas; a fila local permanece no IndexedDB.
4. Se o schema continuar compatível, volte API/web/workers às imagens anteriores, preservando o banco. A migração 0012 adiciona versões de edição, fila/recuperação Nexus e ajusta a restrição de motorista para permitir trocas na mesma viagem; seu downgrade é bloqueado para preservar a fila. Desative o worker de e-mail ao voltar para uma entrega que não o suporta e sincronize filas offline antes da troca. Não execute downgrade geral automaticamente: versões anteriores possuem migrações irreversíveis.
5. Se a reversão exigir recuperar dados, restaure o backup num ambiente novo, confira o impacto dos registros posteriores ao backup e revise a troca do tráfego. Esse procedimento exige uma decisão operacional sobre possível perda de dados.

## Logs e métricas

O serviço `email` envia convites e recuperação pelo Resend, com saída HTTPS numa rede própria e sem portas publicadas. Configure a chave Resend e o remetente em **Nexus → Configurações**, verifique o domínio remetente e homologue recebimento e uso único antes de liberar essa função. As variáveis antigas são aceitas até o primeiro salvamento pelo painel; consulte [WHATSAPP_E_CONFIGURACOES.md](WHATSAPP_E_CONFIGURACOES.md). Sem configuração, o worker permanece sem enviar. A fila contém links privados até seu processamento; o backup criptografado também precisa protegê-los.

API emite JSON com identificador da solicitação, método, rota normalizada, status, duração e classe de erro. Não registra query, corpo, credenciais, CPF ou telefone. `X-Request-ID` permite localizar uma falha pelo suporte. Erros inesperados retornam mensagem genérica; logs de acesso bruto do Uvicorn estão desativados. O worker emite eventos JSON de conclusão/falha de ciclo.

`GET /api/v1/nexus/metrics` exige sessão Nexus e retorna uptime, contagens, erros 5xx, soma e máximo de duração por rota. São métricas em memória de **um processo**, reiniciadas com ele, sem histórico persistente nem percentis. Compose inicial usa um processo API. Monitore também espaço do disco/volume, status dos serviços, backlog de sincronização pelos operadores e sucesso/idade do backup; a coleta externa dessas medidas ainda não foi instalada.

Docker limita cada arquivo de log a 10 MB e três arquivos por container em produção. Dimensionamento e alertas finais dependem dos demais serviços da VPS. O resultado de carga local está em `docs/LOAD_TEST_RESULT.json`, sem promessa de capacidade da Hostinger.

Referências: [Compose em produção](https://docs.docker.com/compose/how-tos/production/), [Traefik Docker](https://doc.traefik.io/traefik/reference/routing-configuration/other-providers/docker/), [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html) e [repositórios restic](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html).
