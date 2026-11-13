# Padrão visual do APK — 1.12.0 (20)

Revisão de 13/11/2026. A etapa abrange tema nativo, lista de viagens, agenda e manifesto. Não modifica API, banco, armazenamento offline, scanner, serviço Android de localização, intervalo de GPS ou notificações.

| Antes | Depois | Motivo |
| --- | --- | --- |
| Informações e ações em sequência sem separação | Resumo do trecho, contagens de passageiros e painel de localização | Facilitar leitura durante a operação |
| Leitor de QR dentro da área de rolagem | Botão no rodapé, respeitando a área segura do aparelho | Manter a ação frequente disponível |
| Chegada e leitura com igual destaque | Chegada com estilo secundário, mantendo confirmação e bloqueios | Evitar competição entre ações |
| Dados de preparação sempre expandidos | Detalhes de uso offline recolhíveis; validade vencida permanece evidente | Reduzir ruído sem esconder impedimentos |
| Nomes de veículo e botão Preparar na mesma linha | Texto e botão em coluna | Comportar nomes longos e fonte ampliada |
| Aviso genérico de fila | Sem registros pendentes ou quantidade aguardando envio/revisão | Distinguir fila vazia de operação ainda não confirmada |

O tema usa a identidade verde e azul do painel, textos legíveis, botões com alvo mínimo de 48 pontos e cartões com hierarquia consistente. A agenda elimina altura fixa de três linhas. As contagens refletem a projeção existente dos eventos locais, incluindo registros pendentes. Nenhum indicador de conexão é inventado a partir da fila vazia.

## Regras preservadas

Permissões, atribuição de motorista/guia, restrição de dia e antecedência de início continuam existentes. Iniciar e fechar viagem exigem conexão e confirmação. A chegada continua bloqueada com passageiros a bordo ou registros locais pendentes. O rastreamento continua automático ao iniciar, quando habilitado; assumir transfere a responsabilidade conforme a confirmação já existente. Leitura de QR, conflitos e sincronização utilizam os mesmos controladores.

## Verificação e distribuição

Análise Flutter e 60 testes, incluindo layouts de 320/390 pontos, texto ampliado, QR persistente durante a rolagem e impedimento de chegada com pendência. Os testes usam API e canal Android simulados. Captura de widget com dados fictícios em `artifacts/mobile/manifest-visual.png`.

O build release utiliza `scripts/build_mobile.ps1 -Release`, configuração de produção e assinatura privada existente. Saída: `artifacts/mobile/nexus-rotafy-1.12.0.apk`, com SHA-256 ao lado. Instale sobre a versão anterior, sem desinstalar; sincronize antes de atualizar. A disponibilização aos clientes exige publicar esse arquivo no painel Superadmin de atualizações Android.

Não há aparelho físico ou emulador conectado nesta revisão. Ainda é necessário homologar câmera, retorno do Maps, TalkBack, perda de rede e GPS com a tela bloqueada em Android real. Não houve publicação automática na VPS ou distribuição aos clientes.
