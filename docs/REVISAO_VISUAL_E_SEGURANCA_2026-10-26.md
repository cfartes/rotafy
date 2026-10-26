# Revisão visual e segurança — 26/10/2026

## Escopo

Revisão local do painel web, API e aplicativo Android de motorista/guia. Aplicadas as orientações da skill instalada `emil-design-eng` (Emil Kowalski) e o princípio de fazer a menor alteração completa. Não houve alteração de banco de dados, contratos, cobrança ou envio de mensagens reais.

## Refinamentos visuais

| Before | After | Why |
| --- | --- | --- |
| Botões sem feedback de pressão | Pressão discreta com mouse, sem movimento no foco por teclado; resposta de cor no toque | Confirmar a interação sem atrasar o trabalho |
| Botões de ícone com área pequena | Área mínima de 44 × 44 pixels na web | Facilitar toque e foco |
| Campos de 14 pixels também em telas de toque | Texto de 16 pixels em dispositivos de ponteiro grosso | Melhorar leitura e evitar zoom automático ao preencher |
| Foco de campo apenas pelo contorno | Borda e halo de foco, preservando indicador de teclado | Tornar o campo ativo mais evidente |
| Texto claro em estados vazios | Cor mais escura | Melhorar contraste |
| APK com cartões, campos e botões pouco alinhados ao painel | Cartões brancos com borda, campos preenchidos e foco turquesa, cabeçalho azul escuro, botões de 48 pontos | Reforçar hierarquia e consistência |
| Teclado sem ação de próxima entrada no login Android | Empresa e e-mail com ação Próximo | Reduzir toques entre campos |

Mantidas as regras de movimento reduzido. Não foram adicionadas bibliotecas de animação, efeitos decorativos, novos menus ou alterações no fluxo operacional.

## Segurança: achados e correções

| Achado | Classificação e alcance | Correção |
| --- | --- | --- |
| `fast-uri` com avisos de normalização de URI | Dependência transitiva da ferramenta de build; npm classificou a dependência como moderada | Lock atualizado para 3.1.9 |
| `serialize-javascript` com aviso de XSS na serialização | Dependência transitiva da ferramenta de build; classificação baixa | Lock atualizado para 7.1.4 |
| Coordenadas temporárias do serviço nativo em SharedPreferences sem criptografia | Exposição de localização caso a área privada do aplicativo fosse lida; não demonstrado acesso remoto | Removida a persistência. A fila permanece em memória e é descartada após envio, revogação ou encerramento do serviço. Preferências legadas são limpas |
| Bloqueio de HTTP dependia de padrões da plataforma e validação Flutter | Fortalecimento explícito de configuração | `usesCleartextTraffic=false` no manifesto principal; exceção de HTTP apenas em debug para a API local |

### Efeito da alteração de GPS

As posições já aceitas continuam no banco do servidor. Se o processo Android morrer antes de enviar uma amostra, ela não será recuperada; o colaborador precisa reabrir o app e assumir o rastreamento novamente. Isso não afeta a fila de embarques/desembarques: ela continua persistida em SQLite com conteúdo AES-GCM e chave no armazenamento seguro do sistema.

O serviço já não reiniciava automaticamente após a morte do processo e a inicialização do app já removia a antiga fila órfã. Mantidos intervalo de cinco minutos, limite de 300 amostras, interrupção após quinze minutos sem contato, confirmação de transferência e validação de atribuição pelo backend.

## Verificações executadas

| Verificação | Resultado |
| --- | --- |
| `npm audit`, incluindo ferramentas de desenvolvimento | Zero alertas após as duas atualizações |
| `npm audit --omit=dev` | Zero alertas |
| `pip-audit -r backend/requirements.txt` | Nenhuma vulnerabilidade conhecida reportada |
| `pip-audit -r scripts/requirements-docs.txt` | Nenhuma vulnerabilidade conhecida reportada |
| OSV querybatch para os 106 pacotes hospedados de `mobile/pubspec.lock`, ecossistema Pub | Nenhum aviso retornado; sem páginas adicionais |
| Gitleaks no histórico Git completo e diff de trabalho | Nenhum novo segredo encontrado |
| Varredura local ampliada | 219 alertas: 212 em dependências Python locais, cinco em configurações privadas não versionadas e dois falsos positivos revisados em SQL/fixture de teste. Não classificar esse total como 219 vulnerabilidades do aplicativo |
| Backend: identidade, segurança de requests, privacidade/RLS, embarque, offline, rastreamento e publicação mobile | 70 testes aprovados |
| Web: login, políticas/LGPD, perfis operacionais, navegação e acessibilidade | 16 testes distintos aprovados, incluindo toque e movimento reduzido |
| Central e materiais de ajuda, incluindo restrição do PowerPoint | Cinco testes aprovados; documentação na revisão 12 |
| Flutter: análise estática e testes | Sem problemas na análise; 51 testes aprovados |
| Login Flutter em 360 × 800 com texto a 140% | Sem overflow; botão de entrada com altura mínima de 48 pontos |
| Build web de produção | Concluído |
| APK release | Compilado, assinatura e manifesto do arquivo final conferidos |

Os testes web incluem verificação automatizada das tags WCAG 2 A/AA, 2.1 AA e 2.2 AA nas páginas públicas. O teste de ausência de gravação de GPS é uma guarda estática do código nativo; não simula o serviço no Android.

Os testes backend exercitam origem/CSRF, limites de requisição e login, respostas sem credenciais, restrições por perfil, isolamento entre empresas, RLS, QR inválido, autorização de veículo/trecho e revogação do rastreamento. As consultas inspecionadas usam parâmetros vinculados. Os dados livres são renderizados como texto; o teste XSS do painel não executou o HTML recebido. Não foi identificado fluxo de LLM na área revisada.

## APK entregue

- Arquivo local: `artifacts/mobile/nexus-rotafy-1.9.1.apk`.
- Pacote: `br.com.nexusdataanalytics.rotafy`.
- Versão 1.9.1, compilação 15.
- SHA-256: `7d07419d1b2a55ee297698800f7f7fb8087cf5ccbcce0b28ae59c602d74a77ea` (ver arquivo `.sha256` ao lado do APK).
- Certificado SHA-256: `88943be1261e26a610b5c857e53e42da444af8ceecddf0a9f69762eec0de654c`, igual ao APK 1.9.0 conferido.
- Assinatura v2 validada por `apksigner`. Manifesto final sem modo depurável, backup desativado, HTTP desativado e TrackingService não exportado.
- Publicação: Superadmin completo → Configurações → Atualizações do aplicativo Android. A geração local não publica o arquivo na VPS.

Sincronize os registros operacionais pendentes e instale por cima. Não desinstale o app para atualizar.

## Limites e verificações externas

Não houve aparelho/emulador Android disponível, teste de câmera/GPS/biometria em hardware, interceptação de tráfego, engenharia reversa dinâmica ou exploração da VPS. Não foi executada uma auditoria de todas as dependências Maven nativas; a consulta OSV cobre os pacotes Pub do lockfile. Não foi introduzido certificate pinning sem uma estratégia de rotação de certificados.

Os resultados valem para as versões e o código analisados nesta data. Não são certificação MASVS/WCAG nem garantia de ausência de falhas. Homologar o novo APK em um aparelho com uma viagem de teste, inclusive GPS com tela bloqueada, modo avião, encerramento do processo e retomada. As credenciais privadas locais e a chave de assinatura devem continuar fora do Git.

## Referências primárias

- [Skill Emil Kowalski instalada](C:/Users/ThinkPad/.codex/skills/emil-design-eng/SKILL.md).
- [OWASP MASVS — requisitos para aplicações móveis](https://mas.owasp.org/MASVS/).
- [Android — riscos de comunicação sem criptografia](https://developer.android.com/privacy-and-security/risks/cleartext-communications).
- [fast-uri — aviso oficial e versões corrigidas](https://github.com/fastify/fast-uri/security/advisories/GHSA-w74x-v6f9-j3xg).
- [serialize-javascript — aviso oficial](https://github.com/yahoo/serialize-javascript/security/advisories/GHSA-m5mm-p8h7-m29v).
- [OSV — consulta em lote](https://google.github.io/osv.dev/post-v1-querybatch/).
