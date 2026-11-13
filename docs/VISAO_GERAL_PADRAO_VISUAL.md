# Piloto visual — Visão geral da empresa

Implementação: 13/11/2026. Escopo: painel web de administrador e atendente da empresa. Superadmin, demais menus e telas nativas do APK não mudam. Não exige banco, API ou APK novo.

| Antes | Depois | Motivo |
| --- | --- | --- |
| Uma grade única de indicadores | Operação no período e Reservas e valores | Facilitar leitura por assunto, sem inventar indicadores |
| Texto de metodologia sempre aberto | Detalhes nativos com resumo acessível por teclado | Reduzir ruído mantendo critérios disponíveis |
| Cards sem distinção de função | Destaque discreto para viagens em andamento e ícones decorativos | Dar hierarquia sem depender apenas de cor |
| Textos pequenos nos cabeçalhos das tabelas | Tipografia e espaçamentos locais mais legíveis | Melhorar leitura sem alterar tabelas das outras telas |
| Tabelas em sequência no desktop | Próximas saídas e ranking lado a lado quando há espaço | Aproveitar a largura disponível |
| Nove indicadores com aparência uniforme | Oito cards agrupados e rotas ativas junto ao ranking | Diferenciar períodos de viagem do cadastro atual de rotas |
| Layout adaptado só pela janela | Container queries com fallback conservador | Funcionar com a largura real disponível, inclusive sidebar |

## Regras preservadas

Mesmo endpoint `/dashboard`, mesmos filtros e valores, módulos, perfis, limites de vinte registros e fuso de Brasília. Próximas saídas independem do período selecionado; o indicador de rotas ativas reflete o cadastro atual. Passageiros reservados não significam embarcados; valores são da operação, não da assinatura. Nada de tendências, percentuais ou gráficos sem dados que os sustentem.

Estilos ficam em `frontend/src/company-dashboard.css`, limitados ao dashboard e ao cabeçalho da Visão geral da empresa. Tokens semânticos locais, títulos com quebra equilibrada, numerais tabulares, controles de pelo menos 44 px e tabelas com títulos e cabeçalhos semânticos. Não há bibliotecas novas, fonte remota, rastreamento ou animações decorativas. Ícones não substituem rótulos. Cores não são a única informação de estado. Navegadores sem container queries recebem grade de duas colunas e formulários empilhados no celular.

## Verificação

Playwright verifica período, permissão dos módulos, ausência de equipe/atalhos removidos, paginação, estados vazios, nomes e valores extensos e ausência de overflow entre 320 e 1440 px. Axe verifica WCAG A/AA e navegação por teclado no resumo dos critérios. Capturas com dados fictícios são conferidas em desktop e celular. Validação em aparelhos reais e Safari/Firefox continua necessária antes de afirmar compatibilidade completa.

## Referências

- https://developer.chrome.com/docs/modern-web-guidance/get-started?hl=pt-br
- https://developer.chrome.com/docs/modern-web-guidance/guides/visual-design/improve-text-layout-and-legibility?hl=pt-br
- Skill local `emil-design-eng`: hierarquia, feedback e uso comedido de movimento.

O pacote do Google não é dependência de execução do app e não foi instalado neste piloto. As orientações foram aplicadas diretamente aos componentes existentes.
