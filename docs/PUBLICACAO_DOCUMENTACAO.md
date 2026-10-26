# Apresentação e manual do Nexus Rotafy

Edição 2026.10, revisão 13, revisada em 26/10/2026. Os materiais públicos apresentam somente funcionalidades disponíveis. A apresentação tem foco comercial e o manual explica o uso, sem nomes de fornecedores de comunicação, detalhes de infraestrutura ou funcionalidades planejadas.

## Acesso no aplicativo

A central pública fica em `/ajuda`, com links na tela de login e no menu **Ajuda e manuais** do painel. Não exige autenticação e não contém dados de clientes, credenciais ou chaves de API. As capturas usam dados demonstrativos dos testes.

Arquivos publicados em `frontend/public/documentacao/`:

- `manual-superadmin.html` e `manual-superadmin.pdf`: orientações exclusivas do perfil Nexus, acessíveis pela ajuda desse perfil.
- `manual.html`: manual pesquisável, responsivo e independente de serviços externos.
- `manual.pdf`: manual para impressão e download.
- `apresentacao.html`: apresentação com navegação entre slides.
- `apresentacao.pdf`: apresentação para compartilhamento.
- O PowerPoint editável é gerado em `backend/private/documentacao/apresentacao.pptx`, fora dos arquivos públicos. Somente o Superadmin completo pode baixá-lo, por `GET /api/v1/nexus/documentation/apresentacao.pptx`, na ajuda Nexus. Clientes, equipe Nexus sem acesso completo e visitantes não têm permissão. O endpoint exige autenticação e responde com `Cache-Control: no-store`; o endereço público antigo retorna 404 no Nginx.
- `manifest.json`: edição, revisão e tamanho dos arquivos.

Os materiais públicos são copiados pelo build do frontend. O PowerPoint é incluído somente na imagem da API. Atualize os serviços web e API para publicar esta restrição; não requer migração do banco. O service worker não armazena esses documentos grandes no precache nem intercepta suas URLs como páginas do aplicativo.

## Manutenção

Fontes revisáveis: `docs/publicacao/manual.md`, `manual-superadmin.md`, `apresentacao.json` e os dois templates HTML na mesma pasta. Atualize também a data e edição da central em `frontend/src/Documentation.tsx` quando publicar uma nova revisão.

Na raiz do projeto, usando o ambiente Python local e as dependências já instaladas do frontend:

```powershell
.venv\Scripts\python.exe -m pip install -r scripts/requirements-docs.txt
.venv\Scripts\python.exe scripts/generate_documentation.py
node scripts/generate_documentation.mjs
```

O segundo comando produz os HTMLs e PowerPoint. O terceiro usa Chromium do Playwright para gerar PDFs com texto selecionável, links e estrutura de navegação. Se necessário, instale o navegador com `npx playwright install chromium` dentro de `frontend`.

Antes da publicação, confira conteúdo, páginas, links e visualização em celular. Execute o build e `tests/documentation.spec.ts` com o frontend disponível na URL indicada por `E2E_BASE_URL`. Evite inserir screenshots com dados reais ou tokens de bilhetes.
