# Horários do atendimento humano

Revisão de 22/10/2026. O administrador da empresa acessa **Configurações → Horários de atendimento humano** ou a mesma seção em **WhatsApp**. Apenas esse perfil altera a agenda. O recurso exige o módulo WhatsApp; permanecem as restrições financeiras e contratuais existentes.

## Regras

- A opção começa desabilitada, preservando o comportamento de empresas existentes.
- Até 42 turnos semanais, com dia de segunda (0) a domingo (6), início e término em `HH:MM`.
- Vários turnos no mesmo dia permitem intervalo para almoço. Dias sem turnos são fechados.
- Término anterior ao início significa o dia seguinte; turnos de domingo podem atravessar a semana.
- Início igual ao término e sobreposições, inclusive atravessando domingo/segunda, são rejeitados. Turnos adjacentes são aceitos.
- Abertura inclusiva e término exclusivo. Fuso configurável: Brasília, Manaus, Rio Branco ou Fernando de Noronha.
- Ao escolher atendimento humano fora do expediente, o bot registra a solicitação e informa todos os turnos, o fuso e a próxima abertura.
- A solicitação permanece aberta na fila humana e no alerta do painel. Não há abandono automático nem novo disparo em massa na abertura.
- A equipe pode responder fora do expediente. O horário não limita menu, bilhetes, NPS nem outras mensagens automáticas.

## API e persistência

`GET/PUT /api/v1/company/whatsapp/hours`, autenticado como administrador. Exemplo:

```json
{
  "enabled": true,
  "timezone": "America/Sao_Paulo",
  "intervals": [
    {"day": 0, "start": "09:00", "end": "12:00"},
    {"day": 0, "start": "13:00", "end": "18:00"}
  ]
}
```

Tabela `company_service_hours`, com RLS obrigatório e escrita pelo papel de plataforma. A alteração registra `whatsapp.hours_updated` na auditoria. A rotina usa o relógio do servidor convertido pelo fuso escolhido, sem depender do navegador.

Migração incremental `0045_service_hours_nps_copy`, aplicada pelo script habitual `scripts/update_vps.sh`, com backup e preservação dos dados. Não exige novo APK. A mesma migração inclui a versão da redação do NPS e o registro da análise de qualidade.

## Validação

Testes cobrem abertura/fechamento, intervalo de almoço, madrugada, virada da semana, fusos, turnos inválidos e sobrepostos, permissões e isolamento. A interação fora do expediente mantém a solicitação humana e seu alerta. Testes de interface verificam edição dos turnos, fuso, gravação e layout móvel.
