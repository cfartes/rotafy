# Embarque offline e sincronização

## Uso pela equipe

1. Com conexão, entre na empresa com a conta do motorista, guia, administrador ou atendente. Abra o embarque do veículo e trecho e escolha **Preparar para uso offline**. Prepare ida e volta separadamente. Motorista e guia podem registrar presença nos veículos atribuídos. O aplicativo Flutter usa a mesma API; detalhes em [mobile/README.md](../mobile/README.md).
2. Aguarde abrir **Embarque offline**. O navegador guarda a interface e o manifesto mínimo no dispositivo. Em produção, instale a PWA pelo navegador Android ou adicione à tela de início pelo Safari no iPhone. Instalação e câmera exigem HTTPS; localhost atende ao desenvolvimento.
3. Sem rede, abra `/offline` ou o aplicativo instalado, selecione o manifesto e leia o QR pela câmera, imagem ou código/link. Confira o passageiro antes de registrar. Também é possível embarcar, desembarcar e reverter pela lista.
4. **Pendente neste dispositivo** significa que a ação foi guardada localmente e ainda não foi aceita pela agência. Recarregar ou reabrir a página preserva a fila no mesmo navegador/perfil.
5. Ao reconectar, mantenha a página aberta: há tentativa automática a cada 15 segundos e o botão **Sincronizar agora**. A sincronização usa a sessão do mesmo usuário e empresa que preparou o manifesto. Se a sessão terminou, entre novamente com essa conta.
6. Em conflito, consulte o estado atual exibido. **Manter servidor** descarta a ação local e as seguintes do mesmo passageiro nesse manifesto. **Reaplicar ação após revisão** consulta novamente o servidor e cria uma nova operação quando a transição ainda é válida. Nenhuma resolução apaga eventos já aceitos.

Sair da conta, limpar dados pela aplicação e remover um manifesto são bloqueados enquanto houver ações pendentes. Ações podem ser descartadas explicitamente na fila. Não limpe os dados do navegador nem desinstale a PWA antes de sincronizar: ações locais perdidas não podem ser recuperadas do servidor.

## Validade e dados locais

- Cada preparação pertence a uma empresa, usuário, viagem, veículo e trecho. Vale até o menor prazo entre oito horas e a expiração da sessão que a preparou. A validade não é renovada sem conexão.
- Manifestos expirados não mostram passageiros nem permitem novas ações. A fila é preservada para sincronização/revisão pelo usuário original. Cópias expiradas sem fila são removidas ao abrir a tela ou na verificação periódica.
- IndexedDB contém nomes, pontos, presença, versões, identificação operacional e hashes dos bilhetes ativos. Não contém CPF, telefone, senha nem informação financeira. O token lido por QR permanece apenas na ação pendente, até aceitação ou descarte.
- Dados locais usam o armazenamento do navegador, sem criptografia própria. Use dispositivos protegidos e contas individuais. Uma troca de usuário limpa os manifestos anteriores quando não há fila; com fila de outro acesso, exige resolver pelo usuário original.
- O navegador pode remover armazenamento local por decisão do usuário ou falta de espaço. A aplicação solicita persistência, mas não pode garantir que o navegador a conceda.

## Regras de sincronização

O servidor continua sendo a autoridade. A cópia offline pode desconhecer revogações de QR, cancelamentos, perda de atribuição e registros feitos em outros aparelhos. Essas condições são verificadas novamente ao enviar cada ação; leitura local de QR não é confirmação definitiva.

Cada ação tem UUID, versão esperada, identidade do operador, dispositivo e horário local de captura. O servidor grava seu próprio horário de recebimento e o indicador de operação offline. O relógio do dispositivo não determina autorização nem ordena o histórico do servidor. Uma repetição da mesma operação recupera o resultado original, inclusive após perda da resposta, sem duplicar evento.

A fila é processada na ordem local. Uma rejeição ou conflito interrompe as ações seguintes do mesmo passageiro; os demais podem sincronizar. Falha de rede, timeout, erro de servidor ou sessão inválida preservam as ações para nova tentativa. Uma viagem encerrada ou perda de acesso detectada bloqueia novos registros nessa cópia. Resolver um conflito substitui sua cadeia local em uma transação; abas com suporte a Web Locks compartilham o bloqueio de sincronização.

O service worker guarda arquivos estáticos da interface, incluindo o leitor QR. Não guarda respostas da API. Não há envio em segundo plano com a página fechada. Atualizações da PWA aguardam o encerramento das abas da versão anterior; a fila fica no IndexedDB.

## Implementação

- `GET /api/v1/trips/{trip_id}/vehicles/{allocation_id}/legs/{leg_id}/offline-manifest`: preparação autenticada, restrita por empresa, perfil e atribuição.
- Comandos usam o endpoint de embarque existente, com `expected_actor_id`, `captured_at` e `offline`. Metadados novos opcionais preservam a idempotência de comandos da versão anterior.
- Migração `0010_offline_events`: horário capturado e indicador offline no histórico imutável.
- Interface: `frontend/src/offline`; armazenamento Dexie/IndexedDB; service worker gerado por Vite PWA; leitor compartilhado em `frontend/src/qr.ts`.
- Referências: [Vite PWA](https://vite-pwa-org.netlify.app/guide/) e [Dexie com React](https://dexie.org/docs/Tutorial/React).

## Homologação

Os testes automatizados verificam preparação, perfis/empresas, expiração de sessão, idempotência, metadados, revogação, viagem cancelada, conflito e operador original. No Chromium, verificam QR real sem rede, oito padrões de máscara QR, recarga e nova aba offline, fila durável, perda de resposta após commit, resolução explícita de conflito, rejeição de QR revogado e bloqueio de logout com fila. Capturas ficam em `docs/screenshots/offline-pendentes-mobile.png` e `offline-conflito-desktop.png`.

Ainda é necessária a homologação em **iPhone e Android físicos**, em HTTPS: instalação, permissão da câmera, leitura de bilhete impresso/tela, modo avião, fechamento/reabertura, armazenamento após reiniciar o aparelho e reconexão. A emulação de rede/viewport no Chromium não substitui essa validação. PWA não implementa o futuro rastreamento GPS com a tela desligada.

### Entrada no aplicativo

O aplicativo instalado inicia no painel (`/`). Sem conexão, esse endereço encaminha para a operação offline. Administradores e atendentes que abrem `/offline` online, sem manifesto preparado nem ações pendentes, são encaminhados ao painel. Manifestos existentes e filas pendentes permanecem disponíveis. Após atualizar a versão, feche todas as abas do Rotafy e abra novamente o endereço do painel; não apague os dados do navegador enquanto houver ações pendentes.
