# Padrão visual dos painéis web

Implementado em 13/11/2026, como continuação do piloto da Visão geral. Abrange os painéis autenticados da empresa e da Nexus, utilizando os componentes existentes. Não exige migração de banco ou atualização do APK.

| Antes | Depois | Objetivo |
| --- | --- | --- |
| Títulos e textos com tamanhos diferentes entre menus | Hierarquia comum para títulos, descrições e cards | Facilitar leitura e orientação |
| Formulários com espaçamentos inconsistentes | Campos alinhados, rótulos legíveis e uma coluna no celular | Reduzir esforço de preenchimento |
| Janelas longas com ações fora da área visível | Cabeçalho e ações principais fixos dentro da janela | Manter salvar, cancelar e fechar acessíveis |
| Foco de retorno dependente do navegador | Foco devolvido ao controle que abriu a janela | Preservar navegação por teclado |
| Botões e tabelas sem padrão visual comum | Controles com alvos de toque adequados e tabelas legíveis | Consistência entre cadastros, operação e administração |
| Texto genérico abaixo do título | Descrições relacionadas à função de cada menu | Explicar o contexto sem termos técnicos |

## Alcance e preservação

Equipe, empresas, veículos, rotas, pacotes, viagens, alocações, passageiros, vendas, reservas, financeiro, WhatsApp, NPS, configurações e relatórios recebem os estilos compartilhados. O mapa da frota preserva a área inteira; atividades preservam a tabela compacta. Paginação, autorizações, valores, validações e regras de negócio continuam nos componentes e APIs existentes.

O arquivo `frontend/src/workspace-ui.css` é carregado após os estilos existentes e limita a maior parte das regras aos painéis autenticados e às janelas compartilhadas. Checkboxes e radios permanecem pequenos, ao lado do texto. Não foram adicionadas dependências, fontes remotas, rastreadores ou animações decorativas.

## Verificação

Build de produção e testes de interface com APIs simuladas cobrem navegação, permissões, formulários, operações, cobrança, WhatsApp, NPS e mapas. A janela de rota é verificada entre 320 e 1440 pixels: sem transbordamento horizontal, validação nativa mantida, ações acessíveis, fundo bloqueado para rolagem e foco restaurado ao fechar com Escape.

As capturas usam dados fictícios. Essa verificação não substitui testes no ambiente real, em Safari/Firefox e aparelhos físicos. O aplicativo Android nativo não foi alterado nesta etapa.
