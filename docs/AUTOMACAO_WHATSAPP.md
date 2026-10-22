# Comandos e bilhetes automáticos

## Configuração pelo administrador

Em **WhatsApp → Atendimento e bilhetes automáticos**, o administrador pode ativar separadamente os comandos e o envio antecipado de bilhetes. Ambos começam desabilitados. Escolha os comandos disponíveis, personalize a mensagem do menu e clique em **Salvar automações**.

O recebimento dos comandos é configurado automaticamente no serviço de mensagens, sem copiar URLs ou chaves. A conexão da empresa precisa estar válida e com envios habilitados. A chave OpenWA configurada pela Nexus precisa permitir leitura e criação de webhooks. O endereço público do Rotafy deve usar HTTPS e ser alcançável pelo OpenWA. A tela mostra se o recebimento está configurado, pendente ou indisponível.

## Comandos para o passageiro

| Comando | Resposta |
| --- | --- |
| `/menu` | Orientação e comandos habilitados pela empresa |
| `/qrcode` ou `/bilhete` | Link do bilhete individual, com o QR Code para os trechos contratados |
| `/onibus` ou `/ônibus` | Veículo, placa e informações de embarque dos trechos reservados |
| `/dados` | Responsável, passageiros, viagem, valor e situação do pagamento |
| `/embarque` | Local e horário previsto de embarque |
| `/atendimento` | Registra solicitação para a equipe na tela Conversas WhatsApp |

Somente reservas confirmadas de viagens ativas vinculadas ao telefone do remetente são consultadas. Nenhum comando recebe um telefone ou código de reserva para consultar outra pessoa. CPF completo e dados de outros clientes não são enviados. Grupos, status, mensagens do próprio número e eventos antigos são ignorados.

Com várias reservas ou passageiros, são apresentadas opções numeradas, válidas por 10 minutos. A escolha é novamente validada contra o telefone e a reserva atual. Volumes grandes são encaminhados para atendimento humano. Se o serviço não conseguir resolver o telefone real de um identificador privado do WhatsApp, os dados não são liberados.

Solicitações humanas aparecem em **Conversas WhatsApp → Solicitações de atendimento**. Abra a conversa para responder e use **Concluir atendimento** ao finalizar. Enquanto a solicitação estiver aberta, os comandos de consulta de dados ficam pausados. O menu continua disponível.

Em embarques em hotéis ou endereços personalizados, a resposta informa o local e pede confirmação do horário específico à equipe; o horário geral de saída do trecho não é apresentado como horário exato da coleta no hotel.

## Bilhetes 24 horas antes

Ao habilitar a função, cada passageiro de uma reserva confirmada fica elegível quando faltam até 24 horas para o **primeiro embarque contratado**, considerando o horário da parada quando existir. Reservas feitas dentro desse período também entram na fila. O mesmo bilhete atende todos os trechos contratados; não é criado um envio por trecho.

A fila de bilhetes automáticos é compartilhada entre todas as viagens e empresas. Há um intervalo mínimo de **3 minutos** entre os envios automáticos, inclusive quando existem vários processos do worker. Isso limita a vazão a aproximadamente 20 mensagens por hora. As respostas aos comandos e o botão de envio manual continuam independentes dessa cadência.

As 24 horas representam a entrada na fila. Em caso de volume elevado ou indisponibilidade, o envio ocorre posteriormente; bilhetes cujo embarque já passou são descartados. Por isso, acompanhe a fila em operações com muitos passageiros no mesmo horário.

Antes de enviar, o sistema confere novamente a reserva, telefone, sessão, viagem, módulos e configurações. Cancelamento, desativação ou mudança de sessão impedem o envio pendente. Alterações de data são reavaliadas; um bilhete não enviado pode voltar à fila quando a nova data entrar na janela. Envios concluídos ou incertos não são automaticamente repetidos.

O acompanhamento apresenta mensagens na fila, enviando, aceitas pelo serviço, com falha, incertas, descartadas ou que precisam de atenção. Aceite pelo serviço não confirma entrega ou leitura.

## Preservação dos bilhetes

Novos bilhetes têm uma cópia da credencial protegida por criptografia para reenvio do mesmo link. O comando ou envio automático pode emitir um bilhete ainda inexistente para a reserva confirmada. Um bilhete já emitido ou revogado não é substituído silenciosamente.

Bilhetes antigos que só possuem o hash, sem cópia recuperável da credencial, aparecem como **Precisa de atenção**. O envio manual com o link original passa a guardar essa cópia protegida e libera a tentativa automática ainda válida. Também é possível reemitir conscientemente pela reserva; nesse caso, os links anteriores são substituídos conforme a regra existente de reemissão. A função automática nunca faz essa substituição sozinha.

## Operação técnica

- Migração incremental: `0042_whatsapp_automation`. Nenhum banco é recriado.
- Worker existente: `python -m app.whatsapp_worker`, com `PUBLIC_BASE_URL` do ambiente.
- Eventos: `POST /api/v1/webhooks/openwa/{company_id}`, autenticados por HMAC-SHA256 no corpo bruto com `X-OpenWA-Signature`. Não usa a sessão do navegador.
- A associação da empresa e sessão é conferida no servidor. Há deduplicação por sessão/mensagem, limites de frequência e expiração dos comandos pendentes em 30 minutos.
- O cadastro do webhook é reconciliado antes da criação para recuperar respostas perdidas sem multiplicar os cadastros.
- O worker confirma a gravação da tentativa antes do POST. Timeout ou aceite ambíguo gera **Envio incerto**, sem repetição automática; confira a conversa antes de enviar novamente.
- Corpos pendentes e credenciais recuperáveis ficam criptografados. Corpos de tentativas finalizadas são removidos, mantendo os metadados de acompanhamento.
- Configuração e acompanhamento exigem administrador; atendimento humano admite administrador e atendente. Chaves de integração de parceiros não liberam esses endpoints internos.

Referências de compatibilidade: [coleção oficial OpenWA v0.24.0](https://github.com/rmyndharis/OpenWA/blob/v0.24.0/docs/07-api-collection.md) e [assinatura oficial dos eventos](https://github.com/rmyndharis/OpenWA/blob/v0.24.0/src/modules/webhook/utils/deliver-once.ts).
