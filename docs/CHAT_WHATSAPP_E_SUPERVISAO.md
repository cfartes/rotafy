# Conversas e conexões WhatsApp

## Atendimento pelo cliente

O menu **Conversas WhatsApp** está disponível para administradores e atendentes de empresas com o módulo WhatsApp habilitado. Usa exclusivamente a sessão vinculada à empresa. A chave do serviço permanece no servidor.

É possível pesquisar conversas, consultar mensagens, responder a uma mensagem específica, iniciar conversa por telefone e enviar texto ou anexos. A lista consulta o serviço a cada 10 segundos e a conversa aberta, a cada 5 segundos. Em telas pequenas, o botão de voltar alterna entre lista e conversa.

O histórico combina mensagens arquivadas com o histórico disponível na sessão. A disponibilidade de mensagens antigas e mídias depende do que o OpenWA mantém; anexos ausentes recebem uma mensagem explicativa. Canais, status e listas de transmissão não integram esta tela.

Anexos enviados têm limite de 2 MB: imagens JPEG/PNG/GIF/WebP, PDF, áudio MP3/OGG/WAV e vídeo MP4. A consulta de mídia limita downloads a 10 MB. Não são aceitos HTML ou SVG. Textos comportam até 4.096 caracteres; legendas, até 1.024.

O envio entra em uma fila com validade de 30 minutos. O servidor revalida empresa, módulo, colaborador, bloqueio financeiro e sessão antes de enviar. O identificador da operação evita duplicação em tentativas repetidas do navegador. Em caso de **Envio incerto**, confira a conversa antes de enviar novamente: o servidor não repete automaticamente uma solicitação cujo aceite não foi confirmado. Aceite pelo serviço não comprova entrega ou leitura.

## Aviso global de atendimento pendente

Administradores e atendentes com WhatsApp habilitado veem, em qualquer tela do painel, um alerta com a quantidade de atendimentos humanos abertos. A consulta ocorre a cada dez segundos, sem consultar o histórico completo das conversas. **Atender** abre diretamente o chat correspondente, inclusive fora da primeira página da lista. **Concluir atendimento** atualiza o aviso imediatamente. O alerta não aparece para Nexus, motoristas, guias, empresas sem o módulo ou administradores restritos ao Financeiro. Não requer permissão de notificações do navegador nem alteração no banco.

## Atendimento automático e transferência humana

Qualquer texto abre o menu numerado personalizado quando a automação está habilitada. Uma resposta manual na tela de conversas assume o atendimento e cancela respostas automáticas e despedidas pendentes. Solicitações humanas também pausam o bot. Use **Concluir atendimento** para liberar a automação; a despedida de um minuto não encerra conversas assumidas pela equipe. Detalhes e filas em [AUTOMACAO_WHATSAPP.md](AUTOMACAO_WHATSAPP.md).

## Supervisão pela Nexus

O menu **Conexões WhatsApp**, exclusivo do Superadmin completo, reúne as empresas, seus números cadastrados, sessões, estado local, estado informado pelo serviço e última verificação. A atualização ocorre a cada 30 segundos, com atualização manual, pesquisa e filtro de problemas.

- **Retomar conexão:** solicita a recuperação da sessão e prepara QR Code quando necessário.
- **Reiniciar sessão:** interrompe a sessão da empresa e solicita nova conexão após concluir a interrupção. Pode exigir leitura do QR Code novamente.
- **Desconectar:** interrompe a conexão e desabilita os envios.
- **QR Code:** permite acompanhar a autenticação pendente da empresa.

A opção de permitir envios após conectar só produz efeito depois da conferência do número. Empresas inativas ou sem o módulo não podem ser reconectadas. Desativação da empresa ou módulo cancela uma retomada pendente. As solicitações ficam registradas na auditoria.

Se a API inteira estiver indisponível, o painel identifica a falha e mantém a lista das empresas. As ações tratam sessões individuais; reiniciar o processo/container OpenWA exige intervenção na VPS. A aplicação não recebe acesso ao Docker.

## Atualização e dados

A migração incremental `0041_whatsapp_chat` adiciona o controle de reinício de sessão e a fila privada do chat, com isolamento por empresa. Não recria o banco nem apaga dados existentes. Execute a atualização habitual pelo `scripts/update_vps.sh` e mantenha o worker WhatsApp ativo.

Conteúdo pendente fica criptografado na fila; após conclusão, falha definitiva ou descarte, é removido dessa fila, preservando apenas metadados de acompanhamento. O histórico das conversas é consultado no OpenWA. Limites de frequência são aplicados por usuário e empresa. Credenciais de integração de parceiros não dão acesso a essas telas ou endpoints de atendimento humano.

Rotas internas autenticadas:

| Finalidade | Método e caminho |
| --- | --- |
| Conversas | `GET /api/v1/whatsapp/chat/chats` |
| Histórico | `GET /api/v1/whatsapp/chat/messages` |
| Consultar telefone | `POST /api/v1/whatsapp/chat/resolve` |
| Enfileirar mensagem | `POST /api/v1/whatsapp/chat/send` |
| Mídia | `GET /api/v1/whatsapp/chat/media` |
| Supervisão Nexus | `GET /api/v1/nexus/whatsapp/connections` |
| Ação na conexão | `POST /api/v1/nexus/whatsapp/connections/{company_id}/action` |
| QR Code pendente | `GET /api/v1/nexus/whatsapp/connections/{company_id}/qr` |

Compatibilidade baseada na [documentação oficial OpenWA v0.24.0](https://github.com/rmyndharis/OpenWA/blob/v0.24.0/docs/07-api-collection.md).
