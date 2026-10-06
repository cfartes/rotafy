# Cadastro inicial da empresa SaaS

Em `/`, **Criar minha empresa** abre `/cadastro`. O cliente preenche nome comercial, razão social, identificador, CPF/CNPJ, plano, nome/e-mail do administrador e senha com confirmação. O cadastro pela Nexus usa os mesmos campos de empresa e plano.

O documento da empresa é obrigatório, normalizado e validado por formato, dígitos verificadores e unicidade, incluindo CPF, CNPJ numérico e CNPJ alfanumérico. A validação não consulta a situação cadastral na Receita. O CPF de passageiros continua opcional. Empresas existentes sem documento são preservadas; salvar alterações cadastrais passa a exigir documento válido.

Somente planos ativos com valores e franquia configurados pela Nexus são oferecidos. O cliente vê preço mensal, viagens incluídas e valor de viagem extra. O servidor busca as condições do plano: preços e franquias não são aceitos no payload do cliente.

Empresa, administrador com perfil `admin`, assinatura e primeiro ciclo são criados na mesma transação. O início é hoje, no calendário de São Paulo; o cadastro não consome viagens. Qualquer falha desfaz todos esses registros. A assinatura usa a versão vigente do plano escolhido. Após concluir, o cliente entra pelo identificador, e-mail e senha cadastrados; não recebe privilégios Nexus.

## API

| Endpoint | Acesso | Resultado |
| --- | --- | --- |
| `GET /api/v1/public/plans` | Público | Condições atuais dos planos disponíveis, sem empresas/assinaturas |
| `POST /api/v1/public/companies` | Público, origem permitida e limite de tentativas | Empresa, administrador e assinatura; resposta limitada a ID, identificador e nome |
| `POST /api/v1/nexus/companies` | Nexus autenticada | Cadastro com documento e plano obrigatórios; assinatura automática |

Payload de cadastro: `slug`, `trade_name`, `corporate_name`, `cnpj`, `plan_id` e `admin` (`full_name`, `email`, `password`). O nome `cnpj` no contrato representa CPF ou CNPJ, por compatibilidade com o campo existente.

Tentativas públicas são limitadas por IP e documento, usando identificadores armazenados como hash. Documento/identificador duplicado, plano inexistente, arquivado ou não configurado bloqueiam o cadastro. O usuário mantém os campos preenchidos para corrigir o erro.

Não há pagamento integrado, emissão/envio automático de fatura ou verificação de titularidade do documento nesta entrega. A assinatura registra as condições mensais e o consumo; os dados cadastrais ficam associados à empresa para a cobrança pela Nexus.

## Validação

Testes cobrem campos obrigatórios, documento inválido/duplicado, planos indisponíveis, rejeição de preço enviado pelo cliente, transação revertida após falha do ciclo, limite de tentativas, origem, perfil do administrador e primeiro login. A jornada do navegador exercita o cadastro público e o cadastro Nexus, escolha do plano, assinatura automática e manutenção da empresa.
