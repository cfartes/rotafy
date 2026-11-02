# Atualização de produção com duas versões

O `scripts/update_vps.sh` usa publicação blue-green em instalações existentes. A instalação inicial continua usando o Compose principal. Não é necessário trocar a VPS, recriar o banco, alterar o domínio ou gerar outro APK para ativar este procedimento.

## Publicar

Na VPS, execute:

```sh
cd /opt/rotafy-tech &&
curl -fSL https://raw.githubusercontent.com/cfartes/rotafy/main/scripts/update_vps.sh -o /tmp/update-rotafy-vps.sh &&
bash /tmp/update-rotafy-vps.sh
```

Use `&&`: se o download falhar, um script antigo não será executado. O checkout precisa estar limpo na branch `main`. A instalação e seu volume de banco são identificados antes da atualização. O instalador conserva senhas e chave de integrações.

O processo:

1. Confere recursos disponíveis: pelo menos 1 GiB de RAM disponível e 3 GiB de disco livre. São pisos de segurança, não uma estimativa de capacidade; o build e os demais aplicativos da VPS também consomem recursos.
2. Compila imagens enquanto a aplicação atual atende. Gera backup do banco e da chave de integrações, sem substituir o container do banco.
3. Prepara o slot inativo (`blue` ou `green`), usando as redes do banco e os mesmos volumes de APKs e chave. As imagens são registradas pelo ID imutável. O slot não tem rotas públicas próprias no Traefik.
4. Bloqueia migrações pendentes sem revisão explícita de compatibilidade. Aplica as permitidas com limite de espera por lock de 3 segundos e de execução de cada statement de 60 segundos.
5. Inicia somente web/API novas e aguarda saúde, incluindo acesso ao banco e identificação da versão web.
6. Na primeira transição, inicia o gateway Nginx com prioridade superior às rotas antigas no Traefik. Nas seguintes, valida e recarrega sua configuração, sem reiniciar o gateway. Confere a versão web e da API pelo HTTPS público.
7. Finaliza os workers antigos e só então inicia os novos. Não executa duas versões dos remetentes simultaneamente.
8. Registra o slot ativo e preserva o anterior para retorno. Mantém web/API anteriores disponíveis para requisições já iniciadas. Aguarda pelo menos cinco minutos antes de permitir reutilizar um slot.

Requisições que durem mais de cinco minutos podem exigir um intervalo maior entre publicações; não há garantia de retenção indefinida de conexões antigas.

O gateway utiliza o Traefik e o certificado existentes. Não abre novas portas no host nem altera os outros aplicativos da VPS. Somente o IP real do Traefik é aceito para obter o endereço do cliente; a API aceita encaminhamento da rede interna dedicada da aplicação. Não exponha essa rede a containers não confiáveis.

## Primeira transição dos workers

Workers de versões antigas não têm encerramento com drenagem. Na primeira transição, o script pausa brevemente os processos e verifica, em consulta somente leitura, se não há transações nem envios/checkouts em andamento. Se houver, retoma-os e tenta novamente, por até cinco minutos. Apenas quando estiverem ociosos eles são encerrados e substituídos. Se a verificação falhar ou não encontrar uma janela ociosa, os retoma e cancela a entrega. A web/API continuam disponíveis.

Nas versões novas, `SIGTERM` solicita a conclusão da unidade de trabalho atual. O Compose dá até cinco minutos para finalizar. Encerramento forçado cancela a entrega e exige verificar resultados incertos. Não há promessa de entrega exatamente uma vez entre sistemas externos: resultados ambíguos de provedores continuam exigindo conferência, conforme as regras atuais das filas.

## Clientes conectados e arquivos

As sessões continuam no mesmo banco; a atualização não troca credenciais nem exige novo login. A interface mantém o aviso de atualização por confirmação: não recarrega um formulário em andamento. Os bundles públicos com nomes hash das entregas anteriores ficam em `<projeto>_web_assets`, para abas abertas continuarem carregando suas telas. Esse volume não contém contratos, documentos pessoais ou configurações.

Não apague esse volume durante a atualização. Ele cresce com as entregas; monitore o disco. A remoção de bundles exige uma política de retenção compatível com abas antigas e versões offline, não é feita automaticamente. APKs permanecem no volume `mobile_releases`; o APK e as rotas públicas dos bilhetes continuam usando o mesmo domínio.

## Retorno à versão anterior

```sh
cd /opt/rotafy-tech &&
python3 scripts/deploy_vps.py --project nexus-rotafy-tech --rollback --non-interactive
```

Se a instalação usa `nexus-rotafy-prod`, use esse projeto no comando. O retorno interrompe os workers novos antes de retomar os anteriores e troca web/API. Não aplica downgrade nem restaura dump sobre o banco ativo. Dados registrados depois da publicação são preservados. Uma entrega com erro durante a troca tenta retornar automaticamente.

O retorno só está disponível enquanto o slot anterior foi preservado. Preparar a próxima entrega reutiliza esse slot e consome o retorno mais antigo. Não execute `docker compose down`, remoção de volumes ou limpeza de imagens/containers dos slots durante esse processo.

Se houver queda do processo/servidor durante a troca, o journal em `artifacts/deploy/state.json` permite que a próxima execução recupere a versão anterior antes de tentar nova entrega. Na primeira transição, isso também retoma workers legados que tenham ficado pausados. Se a recuperação falhar, não exclua o journal: confira os serviços e o motivo antes de prosseguir. A recuperação não substitui um supervisor externo ou alta disponibilidade.

## Operar e diagnosticar

Os testes de saúde da web e do gateway usam `127.0.0.1`, pois o Nginx ouve em IPv4. Em containers Alpine, `localhost` pode tentar IPv6 e informar conexão recusada mesmo com a página funcionando. Se uma entrega antiga parar em **Validando web/API novas**, atualize o script e tente novamente. Falhas nessa fase agora identificam o slot, a etapa e o estado/saúde de cada serviço, sem imprimir variáveis de ambiente, saída dos probes ou logs com dados privados. A mensagem **Administrador Nexus já provisionado; nenhuma senha foi alterada** é normal.

Os projetos de aplicação são `<projeto>-blue` e `<projeto>-green`; o gateway é `<projeto>-edge`. O banco permanece no projeto original. Para consultar a versão ativa, sem precisar descobrir a cor:

```sh
python3 scripts/production.py ps
python3 scripts/production.py logs --since 15m api
python3 scripts/production.py logs --since 15m whatsapp
python3 scripts/production.py exec -T whatsapp python - --company nexus < scripts/diagnose_nps.py
python3 scripts/production.py --base ps db
```

Após a transição, os comandos antigos de logs/exec da API e dos workers no Compose principal apontam para a instalação anterior. Use o wrapper. Os comandos do banco continuam no projeto principal. Não rode `docker compose up -d` sobre todos os serviços do projeto principal: isso poderia reativar workers antigos em paralelo. Use o atualizador para publicar versões.

Os arquivos de Compose gerados em `artifacts/deploy` contêm credenciais de execução e são gravados com permissão `0600`. Não publique, envie por chat nem sirva esse diretório pela web. Preserve também `.env.production` e os volumes compartilhados. O estado identifica versões e caminhos; não contém dados de clientes.

## Revisão obrigatória das próximas entregas

Uma migração só pode declarar `rolling_safe = True` depois de revisão que comprove compatibilidade com a API e os workers anteriores, inclusive para retorno. Use alterações aditivas, valores padrão compatíveis, índices sem bloqueio prolongado e mudanças em etapas. Remover/renomear colunas, alterar significado de campos ou exigir preenchimento imediato normalmente exige outra estratégia e janela de manutenção. Não marque a flag apenas para liberar o script.

Mantenha os contratos da API compatíveis com a interface anterior e APKs ainda em uso. O atualizador verifica saúde e identidade da entrega; não prova sozinho a compatibilidade funcional de qualquer código futuro.

## Validação e limites

Há testes de journal, falha do candidato, ordem da troca de workers, retorno, drenagem inicial, seleção do slot e bloqueio de migrações não revisadas. O teste Docker com Nginx real verifica requisições contínuas durante troca/retorno, requisição já em andamento, cookie, rejeição de cabeçalho de IP forjado, arquivos antigos e configuração inválida. Outro teste envia `SIGTERM` real ao worker e verifica conclusão da unidade de trabalho. Também foi testada a utilização do mesmo cookie em duas instâncias reais da API com o banco de teste.

```sh
python3 -m unittest scripts.tests.test_rolling_deploy scripts.tests.test_deploy_vps
ROTAFY_DOCKER_TEST=1 python3 -m unittest scripts.tests.test_rolling_gateway
```

Esses testes são isolados; não publicam no domínio de produção. A primeira execução na VPS ainda precisa confirmar Traefik, recursos e condições reais da instalação. O modelo reduz interrupções de publicação, mas não elimina falhas da VPS, banco, DNS ou proxy. Uma única VPS não oferece alta disponibilidade contra falha do servidor.
