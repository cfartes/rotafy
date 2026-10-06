# Validação mobile — 06/10/2026

## Evidências desta revisão

Análise Flutter sem problemas e 11 testes mobile aprovados. Corrigida a atualização da tela após sincronização parcial: comandos já confirmados deixam de aparecer como pendentes mesmo quando a conexão cai no comando seguinte. Novo teste confirma a persistência da fila, identidade e chave de operação após fechar e reabrir SQLite em disco.

API, banco e workers locais saudáveis; painel web em execução. A revisão anterior registrou 177 testes backend e jornadas Chromium de embarque e offline aprovados. Não foram repetidos agora, pois esses componentes não foram alterados.

Os testes mobile verificam lógica, armazenamento e sincronização com API simulada. Não substituem câmera, interface ou comunicação HTTP nativa com servidor real.

## Falta homologar

| Verificação | Critério |
|---|---|
| Instalação e login | Android real com motorista e guia; rejeitar perfil administrativo. Nenhum aparelho conectado ou emulador instalado nesta revisão. |
| Viagem sem guia | Motorista prepara e opera sozinho seu veículo/trecho. Já coberta no backend, pendente no celular. |
| Câmera/QR | Bilhete impresso e em outra tela, foco, pouca luz, permissão negada e alternativa pela lista. Recusar QR incorreto. |
| API real | Validar login, cookies/CSRF, preparação, embarque/desembarque no APK e os mesmos eventos no painel. |
| Offline real | Preparar online, desligar conexão, registrar, fechar/reabrir, reconectar e confirmar sem duplicação. Preparação expirada bloqueia novos registros. |
| Dois operadores | Alterar o mesmo passageiro em dois aparelhos; conflito exige revisão e bloqueia comandos dependentes. |
| Sessão/isolamento | Expirar e renovar sessão; impedir troca de usuário com fila e acesso a veículos de terceiros. |
| Interface/estabilidade | Tela pequena, fonte ampliada, teclado, rotação, retorno do Maps e interrupção da câmera. Ainda não existem testes de widgets. |

Seguir [instruções USB](../mobile/README.md). O APK atual usa API local com `adb reverse tcp:8018 tcp:8018`; não opera ainda pela internet na VPS.

## Falta para distribuição comercial

- Publicar e validar API/web na VPS, domínio e HTTPS; confirmar proxy/portas existentes. Há configuração de implantação, sem publicação nesta revisão.
- Configurar armazenamento externo de backups, agendamento e restauração no ambiente publicado. Ensaio local anterior não valida backups da VPS.
- Configurar credenciais e remetente/domínio Resend e testar convites e recuperação de senha reais.
- Definir configuração, nome/ícone, identificador e assinatura de produção por empresa; preparar entrega e atualização Android. APK atual é debug para homologação.
- Compilar/homologar iOS em macOS/Xcode, identidade e assinatura por empresa e distribuição Apple. Existe estrutura inicial, sem build iOS validado.

## Etapas futuras acordadas

GPS com tela desligada e WhatsApp continuam adiados. Sincronização funciona com o app aberto/ao retornar; envio com app fechado não foi implementado. Google Maps abre externamente. Pagamento segue com marcação manual de PAGO, sem gateway.

## Próxima sequência

1. Homologar Android real via USB/API local e corrigir achados.
2. Complementar testes de interface e transporte HTTP.
3. Implantar HTTPS, Resend e backups externos.
4. Gerar e homologar versão assinada da primeira empresa.
5. Homologar iOS em ambiente Apple.
