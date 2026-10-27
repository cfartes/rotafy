# Realocação após cancelamento — operação e implantação

Implementado em 26/10/2026, conforme o [plano aprovado](PLANO_REALOCACAO_APOS_CANCELAMENTO.md).

## Uso

O cancelamento mostra o impacto antes da confirmação. Para cancelamentos realizados após a atualização, reservas confirmadas e bloqueios provisórios ainda válidos originam pendências da própria empresa. Não há criação retroativa para viagens canceladas anteriormente.

Administradores e atendentes veem o aviso em Visão geral e Viagens. **Revisar passageiros e alternativas** abre as famílias afetadas. As sugestões mostram cinco viagens por página, com origem/destino, sequência dos trechos e vagas compatíveis. A ordenação usa a diferença absoluta de partida em relação à original; permite antecipar ou postergar desde que a alternativa ainda não tenha iniciado. No empate, prefere a partida posterior.

O operador seleciona a alternativa, revisa veículo, horários e endereços, confere os valores e registra duas declarações: logística revisada e concordância do cliente. Esses registros são declarações do atendente, com responsável e data; não constituem assinatura digital do passageiro.

A confirmação cria outra reserva, mantém a anterior cancelada e emite novos bilhetes quando o módulo de embarque está habilitado. Os novos links ficam disponíveis na própria tela para compartilhamento, com as regras de envio e armazenamento seguro existentes. Não se reutilizam tokens da reserva cancelada. O motorista/guia precisa sincronizar e preparar o manifesto da viagem de destino.

## Dinheiro e crédito

- `paid_cents`: dinheiro/pagamento reconhecido na reserva. Os registros PAGO anteriores à migração são preservados e preenchidos com seu valor total.
- `credit_cents`: crédito aplicado de outra reserva; não é um novo recebimento.
- Saldo a pagar: `total_cents - paid_cents - credit_cents`.
- Na transferência, a equipe pode reconhecer pagamento parcial externo, dentro do valor original, com justificativa obrigatória quando alterar o valor registrado.
- O crédito disponível combina dinheiro reconhecido e crédito anterior. Aplica-se até o novo valor. O excedente permanece como saldo a favor para revisão manual.
- Marcar PAGO na nova reserva registra somente a diferença que falta, preservando o crédito. Não é possível desmarcar um pagamento de origem já vinculado a uma realocação resolvida nem remover uma quitação integral por crédito pela ação comum de pagamento.
- Crédito não dispara mensagem de “novo pagamento recebido”. A confirmação informa o crédito e o saldo. Cancelar posteriormente uma reserva que contém crédito mantém seu valor pago sinalizado para revisão financeira, sem gerar cobrança de saldo da reserva cancelada.
- O sistema não executa cobrança, estorno ou devolução. **Como o saldo foi tratado** registra a solução realizada pela equipe fora do sistema e encerra o alerta financeiro, mantendo os valores e a justificativa no histórico.

Os relatórios operacionais expõem total, crédito, pagamento recebido e saldo. O painel gerencial considera valores efetivamente cobertos por pagamento/crédito e o saldo restante das reservas confirmadas. Consultar receitas por pagamento recebido não deve somar créditos como dinheiro novo nem interpretar o total histórico de reservas canceladas como venda ativa. A cobrança da assinatura Rotafy não foi alterada.

Viagens parcialmente realizadas exigem revisão manual, sem transferência integral ou crédito integral presumido. Reservas provisórias continuam provisórias; se houver valores a transferir em uma provisória, a confirmação exige tratamento financeiro manual, sem converter automaticamente o bloqueio em venda confirmada. Bloqueios expirados e reservas canceladas anteriormente não geram pendências.

## Concorrência, histórico e segurança

A transferência usa bloqueio transacional da empresa, chave de operação, vínculo único da reserva de origem e revalidação de preço, versão, vagas e itinerário. Duplo clique ou repetição da mesma solicitação não criam outra reserva, crédito ou mensagem. Se faltar vaga ou os dados mudarem, a transação falha e a pendência permanece aberta.

Os pontos da rota são mapeados para as paradas da nova viagem, sem reutilizar índices de outra rota. Hotéis e locais personalizados são reapresentados para revisão. Mudanças feitas pelo atendente precisam formar um itinerário válido e são submetidas novamente à disponibilidade da reserva. A família permanece inteira em cada trecho; pacotes mantêm a sequência completa de cidades.

O histórico fica dentro de Viagens, sem menu lateral novo. Listas usam páginas de cinquenta registros e os contadores consideram todas as pendências, independentemente da página ou da consulta histórica. **Encerrar sem realocar** exige motivo e saldo revisado; fechar a janela não resolve o caso.

RLS é forçada para as conexões de leitura e de comandos. Referências compostas com empresa e reserva/viagem impedem vínculos entre empresas. As rotas exigem administrador ou atendente e o módulo de vendas. Contrato, situação financeira e demais bloqueios operacionais continuam vigentes. Chaves de integração dos parceiros não ganharam novos escopos ou acesso a essas rotas internas.

## API interna

| Rota | Uso |
| --- | --- |
| `GET /api/v1/trips/{id}/cancellation-impact` | Quantidade de famílias confirmadas, bloqueios válidos e passageiros |
| `GET /api/v1/reaccommodations?history=false&offset=0` | Pendências, contadores globais e `has_more`; histórico com `history=true` |
| `GET /api/v1/reaccommodations/{id}/suggestions?offset=0&limit=5` | Alternativas compatíveis, preço, viagens, embarques e veículos disponíveis |
| `POST /api/v1/reaccommodations/{id}/transfer` | Transferência com versão/preço esperados, chave de operação, valores conferidos, declarações e novos embarques |
| `POST /api/v1/reaccommodations/{id}/close` | Encerramento sem realocar, com motivo e saldo a revisar |
| `POST /api/v1/reaccommodations/{id}/financial-resolution` | Registro do tratamento manual do saldo, sem executar transação financeira |

Detalhes dos campos são publicados pelo OpenAPI da versão instalada. As rotas utilizam sessão autenticada e a proteção CSRF existente.

## Atualização

```bash
cd /opt/rotafy-tech &&
git pull --ff-only origin main &&
bash scripts/update_vps.sh
```

A migração incremental `0049_reaccommodations` adiciona os campos de pagamento/crédito e a tabela de pendências, preenchendo os valores pagos legados sem recriar o banco. O atualizador mantém o processo de backup e migrações existente. Não há novo APK: sincronização e preparação do manifesto continuam pelo aplicativo atual.

## Validação

Foram verificados cancelamento com e sem reservas, bloqueios expirados, sugestões antes/depois, capacidade, preço alterado, crédito integral/parcial, diferenças positivas e negativas, repetição, concorrência, bilhetes antigos/novos, isolamento entre empresas, perfis e registro financeiro. A migração foi testada em banco temporário separado, incluindo uma reserva PAGO legada, e sem acesso à VPS.

Também foram executados testes de interface, acessibilidade e regressão da aplicação web. O cancelamento offline só é conhecido ao reconectar; ações locais ficam sujeitas à validação do servidor. Não foram enviados WhatsApps reais nem realizados pagamentos ou reembolsos durante os testes.
