# Contratos de utilização e aceite eletrônico

## Estado da entrega

A versão **2026-10-21-r2 foi aprovada em 21/10/2026**, após revisão do exemplo personalizado. O texto aprovado está em `CONTRATO_ROTAFY_APROVADO.md` e `CONTRATO_ROTAFY_APROVADO.pdf`. As minutas anteriores permanecem como histórico da revisão.

O script de atualização publica somente o texto com SHA-256 `47e971c9151041c2a7ac79a65b3a56095284e9d44523350577cef0db1872da3d`. A publicação exige e-mail configurado e chave de proteção válida; não envia mensagens nem aceita contrato em nome do cliente. A identidade técnica de auditoria é `00000000-0000-4000-8000-000000000035`, ação `contract.published_approved_release`, sem atribuir a publicação a um usuário que não a executou pelo painel.

A rotina é idempotente e preserva uma versão diferente selecionada no painel. Se o texto r2 tiver sido alterado, a publicação automática é recusada. Empresas antigas não são vinculadas retroativamente; novos cadastros passam a exigir o aceite após a ativação.

## Ativação

1. Atualize a VPS pelo script existente. A migração `0034_contract_acceptance` adiciona endereço, número, complemento, bairro, cidade, UF e CEP, além das tabelas de versões, documentos, desafios, aceites e e-mails. As migrações `0035_plan_addenda` e `0036_preserve_plan_terms` acrescentam propostas de mudança e preservam as condições comerciais em ciclos futuros. Nenhum banco é recriado.
2. Entre com um administrador Nexus completo em **Configurações → Contrato de utilização**. A equipe Nexus restrita não pode publicar nem consultar evidências financeiras do contrato.
3. A atualização ativa a r2 aprovada após conferir o hash e os pré-requisitos. Confira a indicação de versão ativa no painel. Para revisões futuras, salve uma **nova versão em rascunho** com identificação própria.
4. Para versões futuras, somente após a aprovação do texto marque a declaração de revisão e publique a versão correta. A publicação confere a configuração de e-mail e a chave de proteção antes de ativar o fluxo.
5. Apenas empresas criadas após a publicação ficam vinculadas à versão ativa. Empresas existentes não são inscritas retroativamente; publicar outra versão não invalida aceites anteriores.

## Primeiro acesso

O primeiro administrador recebe as credenciais pelo fluxo existente. Ao entrar em uma empresa vinculada ao contrato, deve confirmar o endereço, informar nome, CPF e função do representante e declarar poderes para representá-la. O sistema prepara um PDF personalizado com identificador único, versão, dados cadastrais e condições comerciais do momento.

O representante pode abrir o texto integral e baixar o PDF antes do aceite. O código só pode ser solicitado após abrir o contrato. A caixa final fica desmarcada e exige manifestação explícita. O código de seis dígitos é enviado ao e-mail do próprio usuário autenticado, vale por dez minutos e permite até cinco tentativas. O documento e o desafio estão vinculados ao usuário, à empresa e à sessão. Nova sessão ou alteração dos dados cadastrais/comerciais exige nova preparação.

A pendência é validada no backend. O cliente não obtém acesso operacional burlando a interface. A Nexus não pode aceitar pelo representante. O Financeiro e os recursos necessários para regularização e aceite continuam disponíveis. O aceite não reinicia o teste nem muda a data de contratação ou as regras de cobrança já vigentes.

## Documento e evidências

- O SHA-256 é calculado sobre os bytes exatos do PDF apresentado. O identificador e os dados personalizados tornam cada documento próprio, mesmo quando duas empresas usam a mesma versão do texto.
- O PDF aceito não é reescrito para inserir seu próprio hash. O comprovante separado contém o SHA-256 do contrato, versão, identificação e declaração do representante, e-mail confirmado, usuário, sessão, data/hora do servidor em UTC, IP e navegador.
- São preservados também o JSON canônico das evidências, seu SHA-256 e uma autenticação HMAC com a chave persistente da instalação. Essa chave deve integrar o backup protegido existente; não é enviada ao cliente.
- Documentos e aceites possuem proteção contra UPDATE/DELETE e privilégios de aplicação apenas de leitura/inserção. Versões publicadas não podem ser alteradas. Isso não equivale a proteção absoluta contra um administrador da infraestrutura com poderes para reconfigurar o banco.
- IP é obtido do cliente identificado pelo servidor. Não são lidos cabeçalhos encaminhados arbitrariamente pela aplicação; em produção, mantenha a confiança restrita ao proxy já configurado.
- O registro de abertura comprova a ação de abrir a leitura, não que o usuário compreendeu ou efetivamente leu cada cláusula.

O fluxo documenta aceite eletrônico e integridade. Não fornece assinatura qualificada ICP-Brasil, carimbo de tempo independente ou garantia de decisão judicial. A confirmação por e-mail demonstra acesso ao e-mail, não comprova por si os poderes societários declarados pelo representante.

## Cópia e consulta

O aceite e o pedido de envio da cópia são gravados na mesma transação. O worker de e-mail envia o PDF original e o comprovante em anexos, com o hash no texto da mensagem. Falhas mantêm o aceite e os arquivos, com novas tentativas. O histórico diferencia envio pendente, falha e envio aceito pelo provedor; aceite do provedor não significa entrega na caixa de entrada.

Em **Meu contrato**, o administrador consulta a cópia aceita, o comprovante, hash, versão, data e situação do e-mail. Pode reenviar a cópia ao e-mail confirmado no aceite. Editar o cadastro depois não altera o documento anterior. Em **Empresas → Contrato**, o administrador Nexus completo consulta as evidências e baixa contrato e comprovante. PDFs são privados, com isolamento por empresa e sem cache público.

Os arquivos são guardados no próprio banco e acompanham seus backups. Códigos não são armazenados em texto aberto: o desafio usa HMAC e a mensagem pendente é cifrada; a mensagem é apagada após envio, descarte ou falha definitiva.

## Atualização

```bash
cd /opt/rotafy-tech
git pull --ff-only origin main
bash scripts/update_vps.sh
```

Não exige novo APK. A aprovação da r2 está registrada nesta entrega; o script de atualização ativa somente esse texto aprovado após verificar o hash, o e-mail e a chave de proteção. Outras versões continuam dependendo de aprovação e publicação explícita no painel. Se faltar configuração, os serviços continuam atualizados e o script informa que o contrato ainda não foi ativado.


## Mudança de plano e aditivo

A versão aprovada `2026-10-21-r2` inclui as cláusulas 3.6 a 3.9 e é ativada pela atualização após conferir seus pré-requisitos. A ativação não substitui documentos já aceitos. Mudanças de plano continuam exigindo aceite individual do aditivo.

Em Planos e assinaturas, **Enviar aditivo para aceite** fixa a versão atual do plano escolhido e cria uma proposta. O convite é colocado na fila de e-mails para o administrador ativo, preferindo o e-mail do aceite original. A tela distingue envio pendente, falha e aceitação pelo provedor. A simples solicitação não preenche o novo plano agendado na assinatura.

O representante abre **Meu contrato**, confere a proposta, informa seus dados, lê e baixa o aditivo personalizado e confirma por código recebido no próprio e-mail. O aditivo identifica o contrato inicial por hash, quando existente, plano anterior, plano novo, valores, franquia e vigência. Cadastros legados não recebem um aceite inicial fictício: o aditivo declara a ausência de aceite eletrônico anterior.

A confirmação e o agendamento são atômicos. Somente após o aceite a assinatura recebe a versão fixada e a data de início do próximo ciclo. O ciclo em andamento e as faturas anteriores não mudam. Não há proporcional, novo setup ou reinício do teste. Não há mudança durante o teste ou antes do início da assinatura; o fluxo exige um ciclo pago em andamento.

Se a vigência passar antes da confirmação, o documento antigo é rejeitado. O cliente deve gerar e ler outro aditivo, com a próxima data válida, antes de solicitar um novo código. Sessão, usuário, dados cadastrais e condições comerciais continuam sendo conferidos. Outra pessoa não pode reutilizar o documento preparado por um representante.

Uma proposta aguardando aceite pode ser cancelada pela Nexus; seus códigos e convites deixam de ser utilizáveis. Após o aceite, não se remove unilateralmente a mudança pelo botão de cancelamento da proposta. Outra alteração exige novo aditivo após a vigência. Encerrar a assinatura continua sendo uma operação distinta, com histórico de auditoria.

Os documentos anteriores, aceites e hashes são preservados. O cliente encontra os aditivos em **Meu contrato**, com download do PDF e comprovante e reenvio da cópia ao e-mail do aceite. O administrador Nexus completo consulta o histórico em **Empresas → Contrato**. A equipe Nexus restrita não recebe esse acesso.

A edição do catálogo de planos não reajusta automaticamente clientes nos ciclos futuros. Novas condições exigem proposta e aceite. O marco `terms_locked_at` preserva a regra histórica no processamento de ciclos anteriores à implantação, sem reescrever períodos ou faturas já materializados. Alterações que já estavam agendadas antes da atualização permanecem preservadas; não se cria assinatura retroativa.


Se a atualização concluir os serviços mas informar falha na ativação, corrija o e-mail ou a proteção da instalação e repita somente a publicação, na pasta da VPS:

```bash
docker compose --env-file .env.production -f compose.production.yaml exec -T api python -m app.approved_contract
```

Esse comando não recria o banco e não envia mensagens. Ele publica a versão geral aprovada; somente contratos preparados e aceitos por representantes geram os respectivos e-mails e registros de aceite.
