# Planos, assinaturas e franquia mensal

Implementação da etapa 2 em 2026-10-05.

## Operação no painel

No painel Nexus, abra **Planos e assinaturas**. Basic, Professional e Enterprise são criados sem preços/franquias: configure-os antes de contratar. Também é possível cadastrar outros planos, editar o nome e as condições, consultar versões e arquivar.

Selecione uma empresa em **Assinatura e consumo**, escolha um plano e a data de início. Só há uma assinatura ativa por empresa. A agência consulta seu demonstrativo em **Meu plano**, disponível ao administrador da empresa.

Valores monetários são enviados à API como inteiros em centavos. A interface aceita reais com vírgula ou ponto decimal, sem arredondar valores com mais de duas casas.

## Ciclos e histórico

- Ciclo mensal calculado pelo aniversário da data original, à meia-noite de America/Sao_Paulo; intervalos incluem o início e excluem o fim.
- Exemplo: início em 31/01 -> 28/02 ou 29/02 -> 31/03. Não há deslocamento permanente para o dia 28.
- Sem acumulação de franquia. Assinatura futura tem primeiro período reservado, mas não autoriza consumo antes do início.
- Condições de cada período apontam para uma versão imutável do plano. Publicar condições novas não altera períodos já criados.
- Renovação usual usa a versão publicada antes do começo de cada ciclo. O serviço recupera ciclos perdidos sem aplicar preços atuais retroativamente a todos os meses.
- Uma troca agendada fixa a versão selecionada para o próximo ciclo; pode ser desmarcada antes de entrar em vigor. Nos ciclos posteriores, aplica-se o catálogo vigente na virada.
- Arquivar um plano impede novas contratações e novas escolhas; assinaturas existentes mantêm sua renovação.
- Encerrar assinatura bloqueia novos consumos e novas renovações, preservando ciclos e lançamentos. Contratar novamente cria outro registro; não apaga o contrato anterior.
- Sem pró-rata, reembolso financeiro automático ou emissão de cobrança/fatura. O demonstrativo é administrado manualmente pela Nexus.

## Consumo e estorno

O serviço interno de consumo está ligado à criação e ao cancelamento de viagens comerciais, na mesma transação. Falhas revertem tanto a operação comercial quanto seu lançamento. Não há edição manual do livro de consumo. Regras operacionais em [FROTA_E_VIAGENS.md](FROTA_E_VIAGENS.md).

Cada viagem comercial consome uma unidade, independente dos veículos/trechos. A mesma operação pode ser repetida sem duplicar o lançamento. Outro consumo da mesma viagem é recusado enquanto não houver estorno; reativação após estorno exige nova operação.

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

Não há integração com sistemas de pagamento. O futuro marcador **PAGO** é da reserva do comprador e será implementado no módulo de reservas, separado destes demonstrativos SaaS.
