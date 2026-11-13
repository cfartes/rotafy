# Correção de tabelas e horários no celular — 13/11/2026

A regra compartilhada `overflow-wrap: anywhere`, introduzida na revisão visual dos painéis, reduzia a largura mínima das células a uma letra. Em telas estreitas, empresas, identificadores, status, placas, valores e botões ficavam fragmentados. A grade de atendimento, por sua vez, distribuía dia e início na primeira linha e término/remoção na segunda.

| Antes | Depois | Motivo |
| --- | --- | --- |
| Palavras divididas em letras e números quebrados | Quebra normal nas células e preservação de placas, valores, identificadores e status | Manter leitura dos dados |
| Tabelas comprimidas para caber na tela | Largura mínima legível com rolagem dentro da tabela | Preservar as colunas sem ampliar a página inteira |
| Ações fora da vista sem orientação | Indicação para deslizar nas listas de empresas/equipe e operação, com região focável por teclado | Tornar o restante das colunas acessível |
| Dia/início e término/remoção em pares inconsistentes | Dia em linha própria, início e término lado a lado e remoção abaixo | Agrupar os horários do mesmo turno |

As tabelas mantêm a semântica HTML, a paginação de vinte registros, os filtros e as ações existentes. Os botões de paginação ficam acessíveis mesmo após a rolagem lateral. No desktop, continuam utilizando a largura disponível. A Visão geral conserva sua estratégia própria para tabelas estreitas. Não altera banco, API, APK, critérios de cobrança ou horários gravados.

Verificação: reproduzida a placa dividida em três linhas antes da correção; regressão automatizada para empresas, veículos, pacotes e horários entre 320 e 1440 pixels. Verifica texto inteiro, ausência de transbordamento horizontal da página, rolagem local por teclado, acesso à edição, alinhamento dos horários e gravação/remoção. Capturas com dados fictícios ficam em `artifacts/mobile-layout-*.png`.

A validação automatizada é Chromium em larguras de celular. A aparência final ainda deve ser conferida no aparelho do usuário, incluindo rolagem por toque e seletores nativos de horário. Esta mudança exige atualizar o painel na VPS e aceitar a atualização da versão web/PWA; não exige instalar um APK novo.
