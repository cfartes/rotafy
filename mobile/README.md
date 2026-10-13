# Nexus Rotafy Mobile

Aplicativo Flutter no mesmo projeto da API e do painel web. Primeira entrega para Android 7.0 ou superior (API 24); estrutura iOS criada, sem compilação/homologação nesta máquina Windows.

Motorista e guia usam login da empresa e os mesmos recursos: viagens atribuídas, preparação de cada veículo/trecho, QR pela câmera, embarque/desembarque pela lista, fila persistente, sincronização e revisão de conflitos. Guia é opcional; uma viagem de transporte pode ser operada somente pelo motorista.

## Desenvolvimento

A versão 1.4.0 inclui a opção **Usar biometria nos próximos acessos** no login. Após um login válido, o acesso é salvo em um cofre Android separado, protegido por biometria forte. Ao reiniciar, use **Entrar com biometria** ou senha. O menu permite desativar; Sair também remove o acesso biométrico. Consulte [biometria no Android](../docs/BIOMETRIA_MOBILE.md).

A versão 1.3.0 captura a localização ao confirmar chegada, para motorista e guia, quando a permissão e o serviço estiverem disponíveis. A captura inclui precisão e horário, com limite de 15 segundos. Sem localização, registra o motivo e permite fechar. Atualize a API/painel antes de instalar; consulte [localização da chegada](../docs/JORNADA_MOBILE.md).

A versão 1.2.0 adiciona o menu lateral **Agenda**, para motorista e guia. Exibe as próximas saídas entre hoje e os seis dias seguintes, em ordem cronológica, com data, horário local do celular em 24 horas e destino. Somente viagens atribuídas e abertas aparecem. A consulta/atualização exige conexão; a fila offline de embarques continua independente.

A versão 1.1.0 inclui iniciar viagem, registrar chegada, desembarcar todos os passageiros a bordo, recolher a lista e filtrar Todos / Não embarcados / Embarcados, para motorista e guia. Veja [operação da viagem](../docs/JORNADA_MOBILE.md).

Flutter está em `C:\Users\ThinkPad\develop\flutter`; Android SDK em `%LOCALAPPDATA%\Android\Sdk`. Projeto requer Flutter 3.47.6 / Dart 3.13.5 ou versão compatível com o lockfile. Não precisa de conexão direta ao PostgreSQL.

Na raiz, `powershell -File scripts/build_mobile.ps1` executa análise, testes e gera um APK debug para homologação. O script aceita `-FlutterSdk` e `-Config`. A saída fica em `artifacts/mobile/nexus-rotafy-debug.apk`.

Alternativamente, em `mobile/`:

```powershell
flutter pub get
flutter analyze
flutter test
flutter build apk --debug --dart-define-from-file=config/development.json
```

## Testar no Android com a API local

1. Inicie o Docker do projeto.
2. Ative depuração USB no aparelho, conecte ao computador e autorize a conexão.
3. Execute `adb reverse tcp:8018 tcp:8018`.
4. Instale o APK com `adb install -r artifacts/mobile/nexus-rotafy-debug.apk` a partir da raiz do projeto.
5. Entre com usuário motorista ou guia da empresa, carregue suas viagens e prepare ida/volta separadamente.
6. Em modo avião, leia um bilhete do trecho preparado e confirme o embarque. Reabra o app e confira a fila. Reconecte e sincronize; confirme a presença no painel web.

O APK local aponta para `127.0.0.1:8018` e precisa do encaminhamento USB. Não utiliza automaticamente a VPS. No emulador, pode trocar a URL por `http://10.0.2.2:8018/api/v1`. O `WEB_ORIGIN` deve estar entre as origens permitidas da API; no ambiente local é `http://localhost:5178`.

## Um app por empresa

Copie `config/company.example.json` e preencha nome, identificador Android exclusivo, slug, API e origem web. Compile usando `--dart-define-from-file=config/seu-cliente.json`. No Android, `APP_ID` e `APP_NAME` são aplicados ao pacote e nome instalado; `COMPANY_SLUG` fixa a empresa na tela de login. A API continua derivando a empresa da sessão autenticada e validando atribuições. Nenhuma chave ou senha deve ser incluída nesses arquivos.

Assinatura de distribuição, ícone/marca definitiva, publicação e geração iOS por empresa devem ser configurados antes da entrega comercial. O build debug é para homologação. Builds release exigem HTTPS, além de assinatura própria; a configuração gerada não usa chaves debug para assinar release. Compilação e testes iOS exigem macOS/Xcode, provisionamento e conta Apple. Permissão de câmera e entitlements de Keychain já estão preparados.

## Offline e segurança

- Manifestos e comandos são gravados em SQLite com conteúdo criptografado AES-GCM; a chave e a sessão ficam no armazenamento seguro do sistema. A senha só é persistida quando o usuário opta pelo login biométrico, em cofre Android separado cuja chave exige biometria forte a cada operação. Não fica em SQLite nem nas configurações do app. Backup automático Android desativado.
- Cada manifesto pertence à empresa e ao operador. Preparação vale até oito horas, limitada também pela sessão do servidor. Expiração bloqueia novas ações, mas preserva a fila.
- Um comando só sai da fila depois da resposta válida do servidor, na mesma transação da atualização local. Reenvio usa a mesma chave de operação para evitar duplicidade quando a resposta se perde.
- Conflitos/rejeições bloqueiam comandos dependentes do passageiro. **Revisar → Manter servidor** requer confirmação e descarta a cadeia local daquele passageiro/trecho.
- Logout/troca de usuário não apagam registros pendentes. **Renovar acesso** permite autenticar o operador original mantendo a fila.
- QR offline confere empresa, veículo/trecho, hash do bilhete e validade da preparação. Revogação/cancelamento ou alteração em outro aparelho só são conhecidos após conectar; o servidor decide a confirmação.
- Sincronização manual e automática a cada 15 segundos enquanto o app está aberto, e ao voltar ao app. Não há serviço com o app fechado, GPS em segundo plano ou WhatsApp nesta entrega.
- Rotas preparadas abrem por links externos no Google Maps. Não há pesquisa integrada nem chave Google Cloud.

## Homologação pendente

Android 1.5.0 (7): pacotes com vários destinos mostram os deslocamentos atribuídos ao motorista/guia. A agenda inclui etapas futuras nos próximos sete dias, mesmo com o pacote já iniciado. O embarque e QR usam o veículo de cada etapa. Homologar também esse fluxo com troca de veículos em aparelho real; regras em [PACOTES_MULTIDESTINOS.md](../docs/PACOTES_MULTIDESTINOS.md).

Testar em aparelhos reais: permissão e foco da câmera, QR impresso/tela, recusa de câmera com uso da lista, modo avião, fechamento/reabertura, sessão expirada, alteração simultânea por motorista/guia, viagem sem guia e consumo de bateria. Não há aparelho conectado a esta máquina; testes automatizados não substituem essa etapa.

## Entrega HTTPS / Hostinger

Configura??o `config/production.json` usa `https://rotafy.nexusdataanalytics.tech` e pacote `br.com.nexusdataanalytics.rotafy`. A vers?o release ? assinada com chave Nexus privada e permite selecionar a empresa; vers?es por cliente continuam usando configura??o pr?pria. Guia completo em [IMPLANTACAO_E_OPERACAO.md](../docs/IMPLANTACAO_E_OPERACAO.md). A API precisa estar publicada para o login funcionar. iOS n?o ser? gerado nesta etapa.
