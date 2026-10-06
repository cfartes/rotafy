# Página pública e integrações — etapa 5

A agência publica suas viagens em **Página pública e integrações**. Novas viagens são privadas por padrão. A página `/comprar/{slug}` mostra nome, cores e logo da empresa; `/comprar/{slug}/{trip_id}` recebe solicitações familiares. Somente viagens publicadas, futuras e agendadas aceitam novas solicitações.

Administrador e atendente podem publicar viagens, confirmar reservas, registrar PAGO e tratar alertas. Apenas o administrador gerencia logo e chaves de integração. Guia e motorista não recebem acesso comercial.

## Reserva pública

O comprador informa responsável, telefone compartilhado, passageiros e pontos de embarque/desembarque de todos os trechos. CPF é opcional. Números nacionais exigem país; números internacionais podem usar `+` e o código do país.

A sugestão procura um veículo com lugares suficientes para manter toda a família junta nos segmentos selecionados de ida e volta. A família nunca é dividida automaticamente. A capacidade é conferida novamente na transação de criação, com bloqueio por empresa para impedir excesso de reservas simultâneas.

A solicitação cria uma reserva **pendente**, bloqueando lugares por 15 minutos. A agência precisa confirmá-la dentro desse prazo. Expiração libera lugares; o worker registra as expirações. Reservas não consomem novas viagens da franquia.

Se não houver lugares, o comprador pode usar **Avisar agência**. A agência recebe um alerta no painel, com viagem e quantidade da família, sem dados pessoais. Avisos públicos iguais são agrupados por cinco minutos. Uma tentativa de reserva recusada por capacidade também registra alerta na mesma transação. Não há envio por WhatsApp ou e-mail.

## PAGO e acompanhamento

Em **Detalhes da reserva**, **Marcar PAGO** registra manualmente a informação de pagamento. Isso não confirma uma reserva pendente nem prorroga o bloqueio. Não existe cobrança, checkout financeiro, gateway ou transferência neste módulo. Uma reserva cancelada/expirada não pode receber uma nova marcação PAGO. Um pagamento registrado antes do cancelamento permanece no histórico; eventual devolução é responsabilidade da agência.

Após solicitar, o comprador recebe `/acompanhar#token=rt.{company_id}.{segredo}`. O link mostra somente essa família, valor, veículo, itinerário e situação. Não mostra CPF, telefone, placas, equipe, outras reservas ou credenciais. O segredo é gerado com 32 bytes aleatórios e armazenado no banco apenas como SHA-256. O fragmento do link não é enviado na URL HTTP; a consulta envia o token no corpo de uma requisição POST. Respostas usam `no-store` e `no-referrer`.

Quem possui o link pode consultar a família. Compartilhe por canal seguro. A agência pode gerar um novo link ou revogá-lo; gerar outro invalida o anterior. Não há login público de passageiro nesta etapa; a conta do passageiro será tratada com os aplicativos futuros.

## Integração de sites externos

Crie uma chave nomeada no painel da empresa. A validade padrão é 90 dias, configurável de 1 a 365 dias. O token `rk.{company_id}.{segredo}` é exibido uma única vez, armazenado apenas como hash e revogável. **Guarde no servidor do parceiro**, nunca no JavaScript público, HTML ou aplicativo distribuído.

O catálogo e os detalhes publicados podem ser consultados nas rotas públicas:

```text
GET /api/v1/public/{slug}/catalog
GET /api/v1/public/{slug}/trips/{trip_id}
```

Para criar uma solicitação, o servidor parceiro chama:

```text
POST /api/v1/external/reservations
Authorization: Bearer rk.{company_id}.{segredo_da_chave}
Content-Type: application/json
```

```json
{
  "operation_key": "UUID gerado para esta solicitação",
  "trip_id": "UUID da viagem publicada",
  "access_token": "rt.{company_id}.{32_bytes_aleatorios_em_base64url_sem_padding}",
  "contact_name": "Família Silva",
  "phone": "+5511999999999",
  "passengers": [
    {"full_name": "Ana Silva"},
    {"full_name": "Bruno Silva"}
  ]
}
```

Os placeholders acima devem ser substituídos por UUIDs válidos e segredos reais. O parceiro gera e guarda o `access_token` antes de enviar; pode montar o link privado retornando esse token à família. `journeys` pode informar `leg_id`, `boarding_position` e `dropoff_position` em cada trecho; sem esse campo, a reserva considera os percursos completos. `allocation_id` é opcional: sem ele, usa a sugestão de capacidade.

Repita exatamente o mesmo payload, `operation_key` e `access_token` após erro de rede. A resposta devolve a mesma reserva e não duplica ocupação. Modificar o payload ou tentar reutilizar a operação com outro token produz conflito. Um link revogado/rotacionado não pode ser restaurado pela repetição da solicitação.

```text
GET /api/v1/external/reservations/{reservation_id}
Authorization: Bearer rk.{company_id}.{segredo_da_chave}
```

Essa consulta só acessa reservas criadas pela mesma chave. Chaves de outra integração ou empresa não acessam os dados. O parceiro não pode definir status, PAGO ou empresa no payload. A confirmação continua manual no painel da agência.

Respostas principais: `201` reserva criada/repetida; `401` chave inválida, expirada ou revogada; `404` oferta/reserva indisponível; `409` conflito ou falta de lugares; `422` campos inválidos; `429` limite de requisições. A chave funciona em chamadas servidor a servidor, sem depender dos cookies de usuários.

## Logo e limites

PNG/JPEG estático, até 512 KB e 4096 pixels por lado. O backend decodifica, reduz para até 512 pixels e gera um PNG novo removendo metadados. SVG, imagens animadas e formatos inválidos são recusados. O logo fica no PostgreSQL e participa do backup.

Catálogo/acompanhamento: 120 consultas/minuto por IP e categoria; criação pública: 20/minuto; avisos explícitos: 10/minuto; integração: 60/minuto. Os limites são persistidos no banco. O IP é o observado pela API, sem aceitar um `X-Forwarded-For` arbitrário. Na produção, configurar corretamente o proxy confiável para evitar agrupar visitantes sob o mesmo IP e revisar os limites conforme uso real.

Tabelas novas possuem RLS forçada e vínculos compostos com a empresa. Migração: `0008_public_sales`. Neste momento, tudo está no Docker local, sem implantação na Hostinger. Rastreamento, WhatsApp e integração de pagamentos permanecem fora da entrega.
