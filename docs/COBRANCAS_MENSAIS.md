# Cobranças mensais da Nexus

Implementação de 15/10/2026. Migração aditiva `0022_manual_billing`; preservar banco e chave das integrações. A configuração começa desativada. Não exige novo APK.

## Ativação

No acesso superadmin, abrir Configurações e preencher chave Pix, favorecido e sessão WhatsApp da Nexus. Credenciais e remetente de e-mail continuam no formulário de integrações. É necessário salvar os dois canais antes de ativar a cobrança. O superadmin ativa explicitamente a rotina; não há cobrança retroativa de ciclos fechados antes da ativação. Uma reativação inicia nova janela e cancela avisos parciais antigos que já venceram durante a pausa. Desativar não perdoa débitos emitidos.

## Calendário

O ciclo continua ancorado na data original da assinatura; meses curtos preservam a regra 31 → 28/29 → 31 já implementada. O dia anterior ao fechamento recebe um aviso parcial. No fechamento, mensalidade e excedentes são consolidados em uma cobrança única por período. O prazo termina ao fim do segundo dia útil contado depois da data de fechamento, em America/Sao_Paulo. O bloqueio começa à meia-noite seguinte.

O calendário exclui sábados, domingos e feriados do calendário federal, incluindo Paixão de Cristo, calculada pela Páscoa gregoriana. Não inclui pontos facultativos, feriados estaduais ou municipais. Referência: [calendário federal de 2026](https://www.gov.br/cade/pt-br/assuntos/noticias/segunda-feira-20-4-sera-ponto-facultativo-no-cade/).

Valores emitidos são preservados; edições de plano e cancelamentos posteriores de viagens não reescrevem uma cobrança já fechada. Qualquer divergência posterior deve ser conferida pela Nexus antes de confirmar o recebimento. Cancelar uma cobrança preserva o histórico e a retira da restrição, sem representar estorno bancário.

## Pagamento e bloqueio

Financeiro e cobranças permite ao superadmin confirmar o recebimento integral, com data/hora, observação, usuário e horário da confirmação. Repetir a confirmação não duplica auditoria ou mensagens. O sistema não consulta o banco, não valida comprovantes e não reconhece Pix automaticamente.

A restrição é calculada no backend pela existência de cobrança aberta, positiva, além do prazo; independe de o navegador atualizar ou o worker enviar o aviso. A restrição protege mutações autenticadas e criação de reservas públicas/externas. GETs e comandos de viagem/embarque de deslocamentos já vendidos continuam disponíveis, além de logout e troca de senha. As permissões por papel e isolamento de empresa continuam valendo nessas rotas.

A baixa retira apenas aquela dívida. Outras cobranças vencidas mantêm a restrição. A suspensão administrativa (`companies.is_active`) é independente e nunca é revertida por uma baixa.

## Comunicação

Aviso parcial, cobrança definitiva, bloqueio e confirmação geram eventos deduplicados por cobrança, tipo, canal e destinatário. E-mails utilizam administradores ativos; WhatsApp utiliza o telefone de contato da empresa e a sessão de envio da Nexus. Os destinatários são conferidos novamente antes de enviar. Não são utilizadas as sessões dos clientes para cobrar suas próprias assinaturas.

O worker billing executa a rotina periodicamente e processa uma notificação por ciclo, com fila persistente. A leitura e geração de períodos usa trava por empresa; a entrega usa seleção com SKIP LOCKED. Os dois canais podem sair em momentos diferentes conforme a fila e a disponibilidade do serviço.

Conteúdos são cifrados com a mesma chave persistente das integrações. A baixa não depende de o envio funcionar; indisponibilidade da proteção registra a falha sem desfazer o pagamento. Mensagens obsoletas são descartadas antes do envio. E-mail utiliza idempotência e retentativas limitadas. WhatsApp consulta o identificador do destinatário e aceita LID; timeout, falhas de rede e resultado ambíguo não repetem o POST automaticamente. HTTP 429 admite retentativa limitada. Uma interrupção após iniciar o envio vira incerteza, sem reenvio cego.

## Publicação

O compose adiciona ao worker billing a chave de integrações somente para leitura e a rede de saída dos e-mails. Nenhum novo serviço é necessário. O atualizador preserva dados e executa a migração antes de atualizar os serviços:

```bash
cd /opt/rotafy-tech &&
git pull --ff-only origin main &&
bash scripts/update_vps.sh
```

Após publicar, configurar e ativar pelo painel Nexus. Nenhum Pix ou sessão de produção é cadastrado pelo código. Os testes utilizam provedores simulados e não enviam cobranças reais.
