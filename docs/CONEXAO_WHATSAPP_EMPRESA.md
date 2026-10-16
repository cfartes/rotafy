# Conexão WhatsApp pelo administrador da empresa

Entrega de 16/10/2026. Compatibilidade conferida pelo código e contrato OpenAPI da versão **0.24.0** do serviço utilizado: [SessionController](https://github.com/rmyndharis/OpenWA/blob/v0.24.0/src/modules/session/session.controller.ts) e [OpenAPI](https://github.com/rmyndharis/OpenWA/blob/v0.24.0/openapi.json).

## Funcionamento

- O cadastro de uma empresa grava um pedido durável de criação de sessão na mesma transação. Não faz chamadas externas nem impede o cadastro por indisponibilidade do serviço.
- O worker WhatsApp prepara uma sessão exclusiva com nome estável `rotafy-{company_uuid}`. O ID retornado fica salvo no backend e o vínculo começa com envios desabilitados.
- A sessão não é iniciada automaticamente na criação: o administrador abre **WhatsApp**, confere o telefone obtido do cadastro da empresa e solicita a conexão. O telefone é somente leitura nessa tela.
- Empresas existentes usam o mesmo botão. Se já existe vínculo manual, ele é reutilizado; a empresa não fornece IDs ou credenciais.
- O worker inicia a sessão e acompanha seu estado. O painel consulta o QR Code temporário pelo backend, sem receber a chave global ou o ID.
- O administrador escaneia em WhatsApp → Aparelhos conectados → Conectar aparelho. O worker compara o telefone efetivamente conectado com o informado. Só libera envios após correspondência exata e se a opção de envio estiver marcada.
- Número diferente mantém os envios suspensos. Uma desconexão detectada desabilita o vínculo e requer nova solicitação no botão de conexão. O painel atualiza o estado a cada cinco segundos e o QR a cada quinze segundos enquanto necessário. O worker verifica conexões confirmadas aproximadamente a cada minuto, sujeito à fila.
- Após conectar, a tela oculta as contagens e a espera pelo QR, troca o botão por **Desconectar WhatsApp** e mantém uma consulta silenciosa a cada minuto para detectar perda de conexão. Não inicia reconexões automaticamente nesse estado.
- **Desconectar WhatsApp** suspende os envios imediatamente e grava uma solicitação durável. O worker chama `POST /sessions/{id}/stop` e só registra a conclusão após confirmação; falhas mantêm a solicitação pendente para nova tentativa em um minuto. O comando encerra a conexão sem excluir a sessão ou executar logout do aparelho.
- Desabilitar a empresa agenda a mesma desconexão na transação da suspensão, inclusive para vínculos manuais antigos. O worker processa essa fila também para empresas inativas. Reativar não reconecta: o administrador deve solicitar a conexão.
- Não há exclusão de sessão, leitura de chats ou troca de número da conta por esses endpoints.

## Credencial e requisitos

A chave cadastrada nas configurações Nexus precisa permitir listar sessões, criar e iniciar sessões e consultar QR. Na versão 0.24.0, a criação exige papel **OPERATOR** ou superior e uma chave não restrita a sessões específicas. O serviço deve estar acessível ao worker e à API e ter capacidade para iniciar a sessão. Permissões negadas ou indisponibilidade são exibidas sem revelar a resposta bruta do provedor.

O pareamento pelo celular continua obrigatório. O telefone é consultado diretamente em `companies.contact_phone`, inclusive pelo worker, evitando números antigos na configuração da conexão. Alterar o telefone no cadastro suspende os envios pelo vínculo anterior e invalida resultados pendentes. Os convites iniciais da nova empresa e as cobranças continuam utilizando a sessão da Nexus configurada para essa finalidade.

## Persistência e segurança

A migração incremental `0031_whatsapp_connection` cria `company_whatsapp_connection`, com fila, estado, telefone, sessão, versão e datas. Aplica RLS por empresa. A aplicação operacional recebe somente leitura dessa tabela; alterações passam por endpoints de administrador e transações de plataforma com contexto da empresa. Nenhuma tabela anterior é apagada ou recriada e nenhum vínculo existente é migrado automaticamente.

A migração `0032_whatsapp_disconnect` adiciona somente a coluna booleana `disconnect_requested` à tabela existente, preservando dados. Uma solicitação pendente impede conectar, pausar ou substituir o vínculo até concluir a parada. A versão invalida resultados antigos; sessões criadas enquanto a empresa é suspensa são recuperadas pelo nome estável para parada, sem criar outra sessão.

Endpoints:

- `GET /api/v1/company/whatsapp`: estado sanitizado da própria empresa.
- `POST /api/v1/company/whatsapp/connect`: solicitação autenticada com CSRF, origem permitida e limitação de tentativas. Usa o telefone cadastrado e recebe a opção de envio; rejeita telefone divergente enviado por clientes antigos.
- `POST /api/v1/company/whatsapp/pause`: interrompe tentativas e invalida resultados em processamento. Não desconecta a conta no provedor.
- `POST /api/v1/company/whatsapp/disconnect`: suspende envios e agenda a parada remota da sessão da própria empresa. Somente administrador da empresa; não aceita ID de sessão do navegador.
- `GET /api/v1/company/whatsapp/qr`: QR PNG em base64 da sessão vinculada à própria empresa, somente durante pareamento. Não persiste o QR em banco ou arquivo. Recusa SVG, URLs externas e dados maiores que o limite. Confere novamente o vínculo após a consulta ao provedor.

Motorista, guia, atendente e usuários Nexus não podem usar esses endpoints de empresa. O suporte Nexus mantém suas configurações existentes. Uma alteração manual ou identificação automática pelo suporte interrompe o gerenciamento desse vínculo pelo novo worker até uma nova solicitação explícita do administrador da empresa.

Nome determinístico e consulta antes de criar permitem recuperar uma criação aceita cujo retorno tenha falhado, sem emitir POSTs cegos repetidos. O vínculo é conferido novamente antes de salvar, com trava global compartilhada com as configurações existentes e versão da solicitação. Troca concorrente, suspensão da empresa ou solicitação mais recente impedem uma resposta antiga de substituir a configuração atual.

## Atualização

```bash
cd /opt/rotafy-tech
git pull --ff-only origin main
bash scripts/update_vps.sh
```

A atualização aplica a migração, reconstrói API/painel e atualiza o worker. Não requer reinstalação ou recriação do banco, nem novo APK. No primeiro uso real, conferir as permissões da chave e completar o pareamento no celular. Os testes automatizados usam transporte simulado e não criam sessões nem enviam mensagens no serviço de produção.

## Validação

Foram aprovados 371 testes na suíte backend e, após os ajustes finais de fila e precedência de configuração Nexus, 60 testes direcionados de conexão, identificação de sessão e mensagens. Os testes cobrem criação em segundo plano, recuperação após timeout sem duplicar a sessão, leitura de QR, confirmação do número, desconexão, isolamento e permissões, rejeição de QR externo/inválido e respeito às alterações de suporte. Doze testes de navegador passaram, incluindo conexão do administrador, ausência do menu para atendente, número divergente, navegação, configurações Nexus e documentação. Build web e Ruff aprovados. O pareamento real depende da chave e do aparelho autorizado na instalação.

## Tentativas, pausa e diagnóstico

Validação da desconexão: 81 testes direcionados de mensagens, descoberta, conexão e desconexão; após reforçar as proteções de empresas inativas, 62 testes de desconexão, identidade, equipe Nexus e cadastro. Seis testes de navegador verificam a troca do botão, ausência de contagem após conectar, desconexão e navegação. Build web e Ruff aprovados. Todas as chamadas externas dos testes são simuladas.

A tela mostra separadamente a contagem para a próxima tentativa do worker e para a atualização da consulta. **Interromper tentativas** pausa o processamento e as consultas da tela; **Retomar conexão** registra uma nova solicitação. Uma chamada externa já enviada pode terminar, mas seu resultado antigo não reativa os envios.

Se a consulta de estado retornar 404, o worker confere a lista de sessões. Só recupera ou cria uma substituta quando a sessão anterior realmente não consta nessa lista. Se ela ainda estiver listada, preserva o vínculo e exibe o código de suporte da etapa, como `status_http_404`. Falhas de criação, início e consulta possuem códigos distintos, sem expor respostas ou credenciais.

Diagnóstico somente leitura, sem enviar mensagens ou iniciar sessões:

```bash
docker compose --env-file .env.production -f compose.production.yaml \
exec -T whatsapp python - < scripts/diagnose_whatsapp_connection.py
```
