# Contratos de utilização e aceite eletrônico

## Estado da entrega

A funcionalidade é instalada com uma **minuta em rascunho**, sem publicação e sem exigir aceite de clientes existentes. A minuta revisa o documento fornecido, preservando as regras atuais do aplicativo. A revisão comercial e jurídica da Nexus deve ocorrer antes da publicação. Não foi enviado contrato real nem registrado aceite em nome de cliente nesta implementação.

Arquivos para revisão:

- `CONTRATO_ROTAFY_REVISAO_PARA_APROVACAO.md`: mudanças destacadas e texto integral.
- `CONTRATO_ROTAFY_MINUTA_REVISAO.pdf`: cópia de revisão, identificada como não publicada.

## Ativação

1. Atualize a VPS pelo script existente. A migração `0034_contract_acceptance` adiciona endereço, número, complemento, bairro, cidade, UF e CEP, além das tabelas de versões, documentos, desafios, aceites e e-mails. As migrações `0035_plan_addenda` e `0036_preserve_plan_terms` acrescentam propostas de mudança e preservam as condições comerciais em ciclos futuros. Nenhum banco é recriado.
2. Entre com um administrador Nexus completo em **Configurações → Contrato de utilização**. A equipe Nexus restrita não pode publicar nem consultar evidências financeiras do contrato.
3. Leia a minuta integral. Se precisar ajustar o texto, salve uma **nova versão em rascunho** com identificação própria.
4. Somente após a aprovação do texto, marque a declaração de revisão e publique a versão correta. A publicação confere a configuração de e-mail e a chave de proteção antes de ativar o fluxo.
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

Não exige novo APK. **Atualizar o código não publica nem aprova a minuta.** A ativação ocorre apenas pela publicação explícita da versão aprovada no painel Nexus.


## Mudança de plano e aditivo

A minuta `2026-10-21-r2` permanece em rascunho e inclui as cláusulas 3.6 a 3.9. A atualização não publica essa versão nem substitui um contrato aceito. A Nexus deve revisar e publicar uma versão aprovada antes de solicitar mudanças.

Em Planos e assinaturas, **Enviar aditivo para aceite** fixa a versão atual do plano escolhido e cria uma proposta. O convite é colocado na fila de e-mails para o administrador ativo, preferindo o e-mail do aceite original. A tela distingue envio pendente, falha e aceitação pelo provedor. A simples solicitação não preenche o novo plano agendado na assinatura.

O representante abre **Meu contrato**, confere a proposta, informa seus dados, lê e baixa o aditivo personalizado e confirma por código recebido no próprio e-mail. O aditivo identifica o contrato inicial por hash, quando existente, plano anterior, plano novo, valores, franquia e vigência. Cadastros legados não recebem um aceite inicial fictício: o aditivo declara a ausência de aceite eletrônico anterior.

A confirmação e o agendamento são atômicos. Somente após o aceite a assinatura recebe a versão fixada e a data de início do próximo ciclo. O ciclo em andamento e as faturas anteriores não mudam. Não há proporcional, novo setup ou reinício do teste. Não há mudança durante o teste ou antes do início da assinatura; o fluxo exige um ciclo pago em andamento.

Se a vigência passar antes da confirmação, o documento antigo é rejeitado. O cliente deve gerar e ler outro aditivo, com a próxima data válida, antes de solicitar um novo código. Sessão, usuário, dados cadastrais e condições comerciais continuam sendo conferidos. Outra pessoa não pode reutilizar o documento preparado por um representante.

Uma proposta aguardando aceite pode ser cancelada pela Nexus; seus códigos e convites deixam de ser utilizáveis. Após o aceite, não se remove unilateralmente a mudança pelo botão de cancelamento da proposta. Outra alteração exige novo aditivo após a vigência. Encerrar a assinatura continua sendo uma operação distinta, com histórico de auditoria.

Os documentos anteriores, aceites e hashes são preservados. O cliente encontra os aditivos em **Meu contrato**, com download do PDF e comprovante e reenvio da cópia ao e-mail do aceite. O administrador Nexus completo consulta o histórico em **Empresas → Contrato**. A equipe Nexus restrita não recebe esse acesso.

A edição do catálogo de planos não reajusta automaticamente clientes nos ciclos futuros. Novas condições exigem proposta e aceite. O marco `terms_locked_at` preserva a regra histórica no processamento de ciclos anteriores à implantação, sem reescrever períodos ou faturas já materializados. Alterações que já estavam agendadas antes da atualização permanecem preservadas; não se cria assinatura retroativa.
