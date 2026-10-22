# Módulos por empresa e operação integrada

## Configurar no Superadmin

1. Entrar pelo acesso Nexus com perfil de Superadmin completo.
2. Abrir **Módulos por empresa** e selecionar o cliente.
3. Escolher **Sistema completo**, **WhatsApp e embarque integrado** ou ajustar os módulos individualmente.
4. Conferir a seleção e clicar em **Salvar módulos**.

O perfil integrado mantém Equipe, Veículos e Viagens como base dos dados sincronizados pelo parceiro, além de WhatsApp, Bilhetes/embarque e Integrações. A venda acontece no sistema parceiro. Para importar pacotes multidestino, habilitar também Rotas e Pacotes e usar o perfil Turismo. As dependências são selecionadas automaticamente; desmarcar um módulo também desmarca os que dependem dele.

Financeiro da assinatura, contrato, acesso e ajuda são recursos básicos. As regras do plano, franquia e bloqueio financeiro continuam valendo. Colaboradores Nexus sem permissão de configuração não podem alterar módulos. As empresas existentes mantêm todos os módulos habilitados na atualização.

As permissões são verificadas na API, não apenas nos menus. A sessão do navegador é consultada a cada 30 segundos. Desabilitar WhatsApp solicita a desconexão e descarta mensagens operacionais pendentes; as comunicações da Nexus sobre a assinatura são independentes. Desabilitar Rastreamento encerra as sessões de coleta. Para retirar Viagens ou Embarque, é necessário encerrar os trechos em andamento. Dados e histórico são preservados.

## Conectar o sistema parceiro

1. No acesso do administrador da empresa, cadastrar na **Equipe** um atendente dedicado à integração.
2. Abrir **Integração com parceiros**.
3. Informar um nome, selecionar o atendente, definir a validade e marcar as permissões necessárias.
4. Criar a chave e copiar o segredo, exibido uma única vez. Entregá-lo ao responsável técnico por um canal seguro.
5. Conectar o WhatsApp da empresa, conferir o número e habilitar os envios.
6. Fornecer ao parceiro o [guia técnico](integracao/README.md), [OpenAPI](integracao/openapi.json) e [Postman](integracao/rotafy.postman_collection.json).

O parceiro usa a chave `ri` no servidor dele para sincronizar cadastros, viagens e reservas, emitir bilhetes e solicitar mensagens. Cada função depende das permissões da chave e dos módulos da empresa. A chave não dá acesso ao financeiro da assinatura, configuração global ou gestão de usuários, nem registra embarques em nome dos operadores.

Suspender o atendente ou alterar sua função interrompe o uso das chaves vinculadas a ele. Também é possível revogar cada chave nessa tela; elas expiram após a validade escolhida. Gerar e substituir a credencial antes do vencimento.

## Usar o APK

Motorista/guia entra com sua própria conta, consulta as viagens atribuídas e prepara os trechos com conexão. O passageiro recebe um bilhete individual, com o mesmo QR para os trechos contratados. Ler o QR confere o passageiro; confirmar embarque/desembarque registra a operação e identifica o colaborador.

Os registros offline ficam no aparelho até a sincronização ser aceita. O parceiro consulta os eventos por cursor, sem perder o histórico por causa do limite de uma página. Alterações remotas de permissões só alcançam um aparelho offline quando ele se conecta; a validade do manifesto continua sendo aplicada. Os registros locais pendentes não são apagados ao desabilitar o módulo.

## Atualizar a instalação

Na VPS, atualizar a aplicação pelo script existente:

```bash
cd /opt/rotafy-tech
curl -fSL https://raw.githubusercontent.com/cfartes/rotafy/main/scripts/update_vps.sh -o /tmp/update-rotafy-vps.sh
bash /tmp/update-rotafy-vps.sh
```

As migrações `0039_company_modules` e `0040_integration_boarding_cursor` acrescentam configuração, credenciais e cursor de eventos. Não recriam nem limpam o banco. O procedimento de implantação faz backup antes de migrar. Para uma instalação em outra pasta, executar a atualização dentro da pasta que contém `.env.production`.

Publicar o APK **1.9.0, compilação 14**, em **Superadmin → Configurações → Atualização Android**. Isso disponibiliza o download aos operadores. O servidor atualizado também aplica as permissões às requisições de versões antigas.
