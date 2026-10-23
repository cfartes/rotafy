# Revisão de segurança — Nexus Rotafy

Revisão histórica. Consulte o [checklist atualizado de 23/10/2026](CHECKLIST_SEGURANCA_PRIVACIDADE_2026-10-23.md) para as verificações e correções mais recentes.

Data: 16/10/2026. Base analisada: commit `f9687cb`, acrescido das correções desta entrega.

## Conclusão e alcance

Foram corrigidas duas fragilidades na API e lacunas nos cabeçalhos HTTP. Não foram identificadas vulnerabilidades críticas ou altas nas verificações executadas. Isso não constitui garantia de ausência de falhas nem substitui um teste de invasão independente.

A revisão abrangeu autenticação, sessões, CSRF, permissões Nexus/empresa/equipe, isolamento entre empresas por RLS, recuperação de senha, rotas públicas, bilhetes, uploads, importações, exportações, integração de pagamentos, armazenamento local Android e configuração de publicação Docker/Nginx/Traefik.

Não foram enviados e-mails, mensagens WhatsApp ou cobranças reais. Não foi alterado o banco de produção. As correções não exigem migração ou recriação do banco.

## Achados corrigidos

| Identificação | Gravidade | Evidência anterior | Correção |
| --- | --- | --- | --- |
| SEC-01 | Média | A API era publicada diretamente pelo Traefik; o limite de 3 MB do Nginx web não abrangia essa entrada. JSON e corpos sem Content-Length não tinham limite global antes da leitura e validação. | Middleware ASGI limita o corpo a 3 MB, verifica tamanho declarado e efetivamente recebido, inclusive em partes, e rejeita excesso antes da execução da rota. Uploads continuam com seus limites específicos menores. |
| SEC-02 | Baixa | A resposta padrão de validação do FastAPI/Pydantic incluía `input` e contextos de erro com dados submetidos, podendo repetir senha ou informações pessoais na resposta. O próprio usuário já conhece os dados; o risco é sua cópia em ferramentas e registros que coletem respostas. | Respostas 422 preservam localização, tipo e mensagem; removem valores de entrada e contextos arbitrários. Somente limites numéricos de tamanho são preservados para manter as mensagens do formulário. JSON malformado recebe mensagem genérica. |
| SEC-03 | Baixa / proteção adicional | A página principal não enviava HSTS. A API não enviava proteção contra enquadramento. No `/sw.js`, um `add_header` local removia por herança os cabeçalhos de segurança do servidor. As ausências foram confirmadas por GET público. | HSTS na publicação web e API com cookies seguros; X-Frame-Options/CSP na API; cache do service worker configurado com `expires`, preservando os cabeçalhos herdados. HSTS limita-se a este host, sem incluir outros subdomínios. |

Arquivos: `backend/app/request_security.py`, `backend/app/main.py`, `frontend/nginx.conf`.

## Verificações realizadas

- **Dependências web:** `npm audit --json`, incluindo desenvolvimento. Resultado: zero vulnerabilidades conhecidas reportadas; árvore com 471 dependências.
- **Dependências Python de produção:** `pip-audit -r backend/requirements.txt`. Resultado: zero vulnerabilidades conhecidas reportadas nas 40 dependências consultadas. Os resultados dependem das bases de avisos disponíveis na data da consulta.
- **Análise estática Python:** Bandit em `backend/app`. Encontrou 45 alertas: 35 B608, seis B108 e um de cada B310, B103, B105 e B405. Eles foram analisados como sinais para revisão, não como 45 vulnerabilidades confirmadas. As consultas examinadas usam valores parametrizados e nomes de tabelas/colunas definidos pelo código ou por modelos com campos fechados. Os demais alertas referem-se a arquivos fixos de saúde em containers, diretório privado da chave, URL fixa HTTPS do provedor, mensagem de política de senha e importação da exceção ParseError; o leitor de planilhas usa defusedxml e limites de expansão.
- **Segredos versionados:** verificação de 359 arquivos de texto rastreados, com até 2 MB cada, por padrões de chave privada, tokens GitHub, Resend e AWS. Nenhum desses padrões encontrado. Arquivos locais de ambiente e assinaturas Android não estão rastreados. Essa busca limitada não certifica ausência de outros formatos de segredo e não percorreu o histórico Git ou artefatos binários.
- **Nginx:** configuração modificada validada com `nginx -t` em container local.
- **HTTPS público:** GET de `/`, `/sw.js` e `/api/v1/health` em `https://rotafy.nexusdataanalytics.tech`, com validação TLS padrão e resposta 200. Não houve varredura agressiva ou exploração do ambiente público.
- **Testes de regressão:** sete novos casos de segurança passaram: remoção de credenciais em erros, JSON malformado, corpo grande, corpo fragmentado, tamanho declarado incorreto, limites exatos, cabeçalhos em erro de autenticação e HSTS em configuração de produção. Algumas verificações são combinadas no mesmo caso.
- **Suíte completa:** **348 testes passaram** em execução isolada no banco dedicado `rotafy_test` (202,48 segundos). Inclui cenários existentes de RLS, troca indevida de empresa, CSRF, revogação de sessão, permissões Nexus e de equipe, bilhetes, importações e verificação de pagamentos. Houve apenas um aviso de depreciação do cliente de teste Starlette/httpx.

## Controles existentes revisados

- Hash de senha Argon2, tokens aleatórios e somente seus hashes nas tabelas de sessão/recuperação; sessão HttpOnly, Secure em produção e SameSite=Lax.
- Origem permitida e token CSRF nas alterações autenticadas; limitação de tentativas no login/recuperação; encerramento e redefinição revogam sessões.
- Usuários de empresas diferentes com o mesmo e-mail mantêm identidades distintas. RLS restringe consultas e alterações do papel da aplicação; tokens de sessão adulterados não mudam a empresa autenticada.
- Usuário Nexus restrito não recebe permissão para configuração/financeiro. Guias e motoristas precisam de atribuição ao veículo para o manifesto e embarque.
- Notificações InfinitePay não bastam para dar baixa: o worker consulta o provedor, verifica valor e referência e impede reutilização de transação. URLs aceitas exigem HTTPS e domínio InfinitePay; redirecionamentos HTTP do cliente de integração são recusados.
- Importação limita arquivo, linhas, expansão ZIP e conteúdo de planilhas; imagens são reprocessadas; exportação CSV neutraliza fórmulas.
- Chaves de integrações ficam cifradas no banco, com chave de proteção em volume separado. O Android usa armazenamento seguro e cifra os dados locais com AES-GCM; exige HTTPS em release e não segue redirecionamentos com a sessão.
- Logs da aplicação registram o modelo da rota, não query strings, corpo ou valores dos tokens. O comando de produção desabilita o access log do Uvicorn.

## Limites da avaliação e cuidados operacionais

1. Sem acesso administrativo à VPS nesta revisão: firewall, SSH, exposição efetiva de portas, permissões reais, versões e vulnerabilidades das imagens/host, configuração global e access logs do Traefik, isolamento de outros containers e restauração de backups não foram certificados. O YAML do projeto foi revisado; isso não comprova o estado real do servidor.
2. O endpoint de webhook tem um segredo no caminho. A aplicação não o registra, mas um access log do proxy configurado para gravar a URL completa pode registrá-lo. A configuração global do Traefik deve omitir/filtrar esses caminhos ou restringir rigorosamente acesso e retenção dos logs.
3. O limite de corpo reduz consumo por requisição; não impede ataque distribuído, conexões lentas ou muitas conexões simultâneas. Limites de taxa, conexões e tempo no proxy/infraestrutura precisam ser avaliados considerando os demais aplicativos da VPS.
4. Não houve análise binária do APK, teste em dispositivo comprometido, auditoria completa de dependências Flutter ou teste de invasão autenticado em produção. A revisão Android foi de código/configuração.
5. Não há afirmação de conformidade formal LGPD/PCI. Para contas Nexus com acesso completo, autenticação multifator é uma melhoria de defesa recomendada; não foi introduzida nesta correção.

## Aplicação das correções

Após atualizar a entrega:

```bash
cd /opt/rotafy-tech
git pull --ff-only origin main
bash scripts/update_vps.sh
```

Não executar `docker compose down -v`, apagar volumes ou recriar o banco. Esta entrega modifica a API e a imagem web; não requer atualização do APK.

Conferência pública após implantação:

```bash
curl -fsSI https://rotafy.nexusdataanalytics.tech/
curl -fsSI https://rotafy.nexusdataanalytics.tech/sw.js
curl -fsS -D - -o /dev/null https://rotafy.nexusdataanalytics.tech/api/v1/health
```

O host deve enviar `Strict-Transport-Security`; `/sw.js` deve manter CSP, X-Frame-Options e nosniff. A API deve manter no-store e enviar as novas proteções. HEAD pode ser tratado de forma diferente de GET em rotas FastAPI; o último comando usa GET.

Para coletar evidências adicionais da VPS, executar na pasta da instalação:

```bash
bash scripts/diagnose_security.sh
```

O script é somente leitura: mostra portas TCP, estado do UFW quando presente, política efetiva de autenticação SSH, propriedades de segurança dos containers desta instalação e cabeçalhos HTTPS. Não imprime `.env`, senhas, chaves ou logs da aplicação. A saída contém informações do host/rede; revisar antes de compartilhar. Não testa restauração de backups, não faz auditoria de pacotes/imagens e a ausência de UFW não significa ausência de outro firewall.
