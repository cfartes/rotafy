# Planos, assinaturas e franquia mensal

Revisado em 22/10/2026. Regras atuais de contratação, consumo e cobrança da assinatura; condições históricas permanecem preservadas.

## Operação no painel

No painel Nexus, abra **Planos e assinaturas**. Basic, Professional e Enterprise são criados sem preços/franquias: configure-os antes de contratar. Também é possível cadastrar outros planos, editar o nome e as condições, consultar versões e arquivar.

Selecione uma empresa em **Assinatura e consumo**, escolha um plano e a data de início. Só há uma assinatura ativa por empresa. A agência consulta seu demonstrativo em **Meu plano**, disponível ao administrador da empresa.

Valores monetários são enviados à API como inteiros em centavos. A interface aceita reais com vírgula ou ponto decimal, sem arredondar valores com mais de duas casas.

## Ciclos e histórico

- Novas contratações seguem teste configurável e ciclos pagos fixos de 30 dias após o teste. O setup é separado e cobrado somente no fim do teste; mensalidade e excedentes, no fim de cada ciclo.
- Exemplo: contratação em 10/10 com sete dias de teste → setup em 17/10 → primeira mensalidade em 16/11. Assinaturas históricas preservam seu calendário registrado; os intervalos incluem o início e excluem o fim.
- Sem acumulação de franquia. Assinatura futura tem primeiro período reservado, mas não autoriza consumo antes do início.
- Condições de cada período apontam para uma versão imutável do plano. Publicar condições novas não altera períodos já criados.
- A renovação preserva as condições contratadas. Editar o catálogo não reajusta automaticamente clientes. Períodos históricos não recebem preços atuais retroativamente.
- Uma mudança de plano exige proposta e aditivo aceito pelo representante, com confirmação por e-mail, antes de agendar o próximo ciclo. Não há novo setup nem proporcional. Propostas ainda não aceitas podem ser canceladas; um agendamento aceito não é removido pelo cancelamento de proposta.
- Arquivar um plano impede novas contratações e novas escolhas; assinaturas existentes mantêm sua renovação.
- Encerrar assinatura bloqueia novos consumos e novas renovações, preservando ciclos e lançamentos. Contratar novamente cria outro registro; não apaga o contrato anterior.
- Há emissão de cobranças, avisos e links de pagamento quando habilitados. Não há pró-rata nem reembolso automático. Consulte [cobranças mensais](COBRANCAS_MENSAIS.md), [pagamentos e teste](INFINITEPAY_E_TESTE.md) e [contratos](CONTRATOS_E_ACEITE.md).

## Consumo e estorno

O serviço interno de consumo está ligado à criação e ao cancelamento de viagens comerciais, na mesma transação. Falhas revertem tanto a operação comercial quanto seu lançamento. Não há edição manual do livro de consumo. Regras operacionais em [FROTA_E_VIAGENS.md](FROTA_E_VIAGENS.md).

Viagem simples consome uma unidade, independentemente dos veículos/trechos; pacotes consomem uma unidade por destino comercial, com retorno incluído. A mesma operação pode ser repetida sem duplicar o lançamento. Outro consumo da mesma viagem é recusado enquanto não houver estorno; reativação após estorno exige nova operação.

Cancelamento gera um evento negativo no período original. Não transfere crédito para o ciclo atual. O banco valida a relação entre estorno, empresa, viagem e período e impede estornar o mesmo consumo duas vezes.

Demonstrativo: viagens extras = máximo(consumo líquido - franquia, 0); total = mensalidade + extras × preço da viagem extra. Cancelamentos atualizam o consumo líquido do ciclo original. Ajustes em valores já faturados externamente exigem conciliação manual; o sistema não altera documentos de cobrança de terceiros.

## Isolamento e manutenção

- Catálogo de planos é global da Nexus. Assinaturas, períodos e lançamentos têm company_id e RLS forçado.
- Papel da empresa tem acesso somente de leitura a sua assinatura e seus demonstrativos; não publica preços nem lança consumos.
- Papel da plataforma pode inserir versões, períodos e lançamentos, mas não editar ou excluir esses históricos.
- Trava transacional por empresa protege renovação, contratação e consumo concorrentes.
- Container `billing` verifica ciclos a cada 60 segundos. Consultas autenticadas de demonstrativo também atualizam o ciclo para a empresa autorizada.
- Marcador de saúde do worker detecta rodadas sem sucesso; logs não expõem parâmetros de conexão ou dados pessoais.
- A atualização Docker aplica a migração 0003_billing sem substituir dados das empresas existentes.

A integração de pagamento da assinatura é separada da reserva do passageiro. **PAGO** já permite registrar manualmente o pagamento da reserva; não representa baixa da assinatura da empresa.
