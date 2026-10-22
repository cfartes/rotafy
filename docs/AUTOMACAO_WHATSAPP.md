# Comandos e bilhetes automáticos

## Configuração pelo administrador

Em **WhatsApp → Atendimento e bilhetes automáticos**, o administrador pode ativar separadamente o atendimento automático e o envio antecipado de bilhetes. Ambos começam desabilitados. Escolha as opções disponíveis, preencha uma mensagem complementar opcional e clique em **Salvar automações**.

O recebimento dos comandos é configurado automaticamente no serviço de mensagens, sem copiar URLs ou chaves. A conexão da empresa precisa estar válida e com envios habilitados. A chave OpenWA configurada pela Nexus precisa permitir leitura e criação de webhooks. O endereço público do Rotafy deve usar HTTPS e ser alcançável pelo OpenWA. A tela mostra se o recebimento está configurado, pendente ou indisponível.

## Atendimento para o passageiro

| Entrada ou opção | Resposta |
| --- | --- |
| Qualquer texto não vazio | Abre o atendimento ou reapresenta o menu numerado |
| Número de **Bilhete de embarque** | Link do bilhete individual, com o QR Code para os trechos contratados |
| Número de **Meu veículo** | Veículo, placa e informações de embarque dos trechos reservados |
| Número de **Minha reserva** | Responsável, passageiros, viagem, valor e situação do pagamento |
| Número de **Local e horário de embarque** | Local e horário previsto de embarque |
| Número de **Falar com a equipe** | Registra solicitação para a equipe na tela Conversas WhatsApp |

A saudação é **“Olá, Nome do cliente, em que podemos ajudar?”**, usando o responsável pela reserva confirmada de viagem ativa vinculada ao telefone. Sem esse nome, consulta o nome público do perfil no WhatsApp. Sem nome disponível, utiliza **“Olá, em que podemos ajudar?”**. A mensagem complementar configurada pelo administrador é exibida em seguida, antes das opções. A mensagem padrão antiga é substituída pela saudação automática.

Somente reservas confirmadas de viagens ativas vinculadas ao telefone do remetente são consultadas. Nenhum comando recebe um telefone ou código de reserva para consultar outra pessoa. CPF completo e dados de outros clientes não são enviados. Grupos, status, mensagens do próprio número e eventos antigos são ignorados.

A busca prioriza o telefone exato. Para celulares brasileiros apresentados com ou sem o nono dígito, a variante cadastrada só é utilizada após confirmação de que os identificadores retornados pelo OpenWA representam o mesmo contato. Não há busca por sufixo, aproximação ou telefone de outra empresa. Falhas nessa confirmação adiam a consulta, sem enviar uma resposta falsa de reserva inexistente.

Para diagnosticar uma consulta que não encontra a reserva, após atualizar a VPS, execute na pasta da instalação, substituindo `IDENTIFICADOR` e `TELEFONE_COM_DDI`:

```bash
docker compose --env-file .env.production -f compose.production.yaml exec -T whatsapp \
  python - --company IDENTIFICADOR --phone TELEFONE_COM_DDI \
  < scripts/diagnose_whatsapp_commands.py
```

O diagnóstico usa apenas consultas ao banco e GETs no serviço, sem enviar mensagens. Mostra se há reserva ativa, se o telefone recebido coincide com o cadastrado, se há uma variante brasileira confirmada e se a sessão pertence à empresa atual. Os números são mascarados; chaves, links e mensagens não são exibidos.

Não é necessário utilizar palavras específicas. Durante o atendimento, cada número aciona a opção apresentada. A correspondência dos números é preservada durante a seleção; opções desabilitadas pelo administrador são recusadas. Fora de um atendimento ativo, até uma mensagem numérica inicia um novo menu, sem executar a seleção anterior.

Com várias reservas ou passageiros, são apresentadas opções numeradas durante o atendimento. A escolha é novamente validada contra o telefone e a reserva atual. Volumes grandes são encaminhados para atendimento humano. Se o serviço não conseguir resolver o telefone real de um identificador privado do WhatsApp, os dados não são liberados.

Solicitações humanas aparecem em **Conversas WhatsApp → Solicitações de atendimento**. Abra a conversa para responder e use **Concluir atendimento** ao finalizar. Enquanto a solicitação estiver aberta, o atendimento automático fica pausado, sem reapresentar o menu ou enviar despedidas. Depois da conclusão pela equipe, a próxima mensagem do cliente pode iniciar novo atendimento automático.

Uma resposta enviada manualmente pela equipe na tela Conversas WhatsApp também assume o atendimento, quando a automação está habilitada, cancelando respostas automáticas e despedidas ainda pendentes daquela conversa. Use **Concluir atendimento** para liberar a automação novamente.

### Encerramento por inatividade

Após 10 minutos sem nova mensagem do cliente, o servidor coloca na fila a despedida:

> Oi! Como não nos falamos há um tempinho, estamos fechando essa conversa por agora. Se precisar de mais alguma coisa, é só nos chamar novamente por aqui, tá bom? Tenha um ótimo dia! ✨

O processamento ocorre no worker, normalmente a cada 5 segundos, e depende da disponibilidade da conexão. O timer é persistido no banco; fechar a tela ou reiniciar o processo não perde o controle. Uma nova mensagem reinicia o prazo e invalida uma despedida ainda não enviada. A sessão, a configuração e a transferência para atendimento humano são novamente verificadas antes de enviar. O envio não utiliza a cadência configurada pela Nexus (padrão: 30 segundos) dos bilhetes.

Cada atendimento recebe no máximo uma despedida automática. Um resultado incerto não é repetido. Depois do encerramento, a seleção anterior é removida. Conversas antigas após indisponibilidade prolongada não recebem despedidas tardias; mensagens de despedida pendentes expiram em 2 minutos.

Em embarques em hotéis ou endereços personalizados, a resposta informa o local e pede confirmação do horário específico à equipe; o horário geral de saída do trecho não é apresentado como horário exato da coleta no hotel.

## Bilhetes 24 horas antes

Ao habilitar a função, cada passageiro de uma reserva confirmada fica elegível quando faltam até 24 horas para o **primeiro embarque contratado**, considerando o horário da parada quando existir. Reservas feitas dentro desse período também entram na fila. O mesmo bilhete atende todos os trechos contratados; não é criado um envio por trecho.

A fila de bilhetes automáticos é compartilhada entre todas as viagens e empresas. O intervalo entre os envios automáticos é configurado pelo Superadmin (padrão: **30 segundos**), inclusive quando existem vários processos do worker. Com o padrão, a capacidade teórica é de até 120 mensagens por hora, antes dos tempos de processamento e de comunicação. As respostas aos comandos e o botão de envio manual continuam independentes dessa cadência.

As 24 horas representam a entrada na fila. Em caso de volume elevado ou indisponibilidade, o envio ocorre posteriormente; bilhetes cujo embarque já passou são descartados. Por isso, acompanhe a fila em operações com muitos passageiros no mesmo horário.

Antes de enviar, o sistema confere novamente a reserva, telefone, sessão, viagem, módulos e configurações. Cancelamento, desativação ou mudança de sessão impedem o envio pendente. Alterações de data são reavaliadas; um bilhete não enviado pode voltar à fila quando a nova data entrar na janela. Envios concluídos ou incertos não são automaticamente repetidos.

O acompanhamento apresenta mensagens na fila, enviando, aceitas pelo serviço, com falha, incertas, descartadas ou que precisam de atenção. Aceite pelo serviço não confirma entrega ou leitura.

## Preservação dos bilhetes

Novos bilhetes têm uma cópia da credencial protegida por criptografia para reenvio do mesmo link. O comando ou envio automático pode emitir um bilhete ainda inexistente para a reserva confirmada. Um bilhete já emitido ou revogado não é substituído silenciosamente.

Bilhetes antigos que só possuem o hash, sem cópia recuperável da credencial, aparecem como **Precisa de atenção**. O envio manual com o link original passa a guardar essa cópia protegida e libera a tentativa automática ainda válida. Também é possível reemitir conscientemente pela reserva; nesse caso, os links anteriores são substituídos conforme a regra existente de reemissão. A função automática nunca faz essa substituição sozinha.

## Operação técnica

- Migrações incrementais: `0042_whatsapp_automation` e `0043_whatsapp_conversations`. Nenhum banco é recriado.
- Worker existente: `python -m app.whatsapp_worker`, com `PUBLIC_BASE_URL` do ambiente.
- Eventos: `POST /api/v1/webhooks/openwa/{company_id}`, autenticados por HMAC-SHA256 no corpo bruto com `X-OpenWA-Signature`. Não usa a sessão do navegador.
- A associação da empresa e sessão é conferida no servidor. Há deduplicação por sessão/mensagem, limites de frequência e expiração dos comandos pendentes em 30 minutos.
- O cadastro do webhook é reconciliado antes da criação para recuperar respostas perdidas sem multiplicar os cadastros.
- O worker confirma a gravação da tentativa antes do POST. Timeout ou aceite ambíguo gera **Envio incerto**, sem repetição automática; confira a conversa antes de enviar novamente.
- Corpos pendentes e credenciais recuperáveis ficam criptografados. Corpos de tentativas finalizadas são removidos, mantendo os metadados de acompanhamento.
- Configuração e acompanhamento exigem administrador; atendimento humano admite administrador e atendente. Chaves de integração de parceiros não liberam esses endpoints internos.

Referências de compatibilidade: [coleção oficial OpenWA v0.24.0](https://github.com/rmyndharis/OpenWA/blob/v0.24.0/docs/07-api-collection.md) e [assinatura oficial dos eventos](https://github.com/rmyndharis/OpenWA/blob/v0.24.0/src/modules/webhook/utils/deliver-once.ts).


## Intervalo configurável das filas

O Superadmin define `whatsapp_queue_interval_seconds` em `PUT /api/v1/nexus/integrations`, mantendo `expected_version` e a proteção de concorrência. `GET` devolve o valor salvo. Padrão de 30 segundos; inteiro entre 5 e 3600. Omitir o campo preserva o valor atual. Apenas o Superadmin completo pode alterar.

Os workers leem a configuração persistida a cada reserva de envio. Bilhetes e NPS conservam relógios globais independentes e bloqueios transacionais, sem disparar toda a fila de uma vez. Ao salvar outro intervalo, os relógios pendentes são deslocados pela diferença entre o novo e o antigo, respeitando o instante atual; mudar apenas chaves ou e-mail não altera os relógios. A conclusão de um envio de bilhete também respeita o intervalo vigente.

A migração incremental 0046 adiciona somente a coluna, sua validação e ajusta os relógios do antigo intervalo de 180 segundos para 30 segundos. Não recria banco nem apaga dados. O script normal `scripts/update_vps.sh` aplica a migração. Respostas interativas, envios manuais e mensagens de outras filas não são retardados por essa configuração.
