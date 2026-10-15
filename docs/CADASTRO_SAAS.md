# Cadastro comercial de empresas

O cadastro de novas empresas pertence exclusivamente ao time Nexus. O login nao oferece autoatendimento, e `/cadastro` apresenta orientacao para procurar o comercial. `POST /api/v1/public/companies` retorna 403, inclusive para pedidos diretos.

## API e permissoes

- `POST /api/v1/nexus/companies`: administrador Nexus ou Equipe Nexus; dados comerciais, documento validado, telefone, perfil operacional, plano e primeiro administrador.
- `POST /api/v1/nexus/companies/{id}/welcome`: mesmos perfis; `operation_key` UUID e `channel` (`email`, `whatsapp`, `both`).
- `GET /api/v1/nexus/companies/{id}/welcome`: historico dos envios de acesso, sem corpo privado ou credenciais.
- `GET /api/v1/public/plans`: catalogo comercial sem dados de empresas; utilizado pelo cadastro operado pela Equipe Nexus.

Empresa, administrador, assinatura e ciclo inicial continuam atomicos. O envio e uma etapa posterior: falha de configuracao nao remove a empresa nem cria outro cadastro. A chave de operacao evita duplicacao quando a resposta se perde; novo envio com outra chave invalida os links anteriores.

A mensagem inclui dados cadastrais, endereco de acesso, identificador e e-mail do primeiro administrador ativo. A senha inicial nunca e enviada em texto: o cliente define sua senha usando um link de uso unico valido por 24 horas. O mesmo link atende ambos os canais.

O e-mail utiliza a fila existente e o remetente configurado. O WhatsApp utiliza a sessao Nexus em `billing_settings.nexus_session_id`, mesmo com cobranca automatica desativada, e marca `nexus_sender=true` na fila existente. O pareamento da nova empresa nao e necessario. O worker verifica sessao, validade do convite, usuario ativo e telefone atual da empresa; convites obsoletos sao descartados. Resultados ambiguos nao sao reenviados automaticamente.

A migracao aditiva `0027_company_welcome` inclui o indicador de remetente e o historico idempotente por empresa, com RLS. Nenhum banco ou dado existente e recriado.
