# Operação de viagem no Android — versão 1.1.0

Na versão 1.1.1, viagens concluídas deixam de aparecer em Minhas viagens e nos trechos preparados. O fechamento local remove o trecho imediatamente; a conclusão geral oculta todos os trechos da viagem e persiste após reabrir o app. Conclusões feitas por outro usuário são reconhecidas ao atualizar as viagens ou sincronizar com conexão. Registros locais pendentes são preservados em um acesso de revisão, sem permitir operação da viagem encerrada. Foram aprovados 18 testes Flutter para esta atualização.

Motorista e guia têm os mesmos controles, limitados aos veículos atribuídos ao usuário e à sua empresa. Uma viagem pode funcionar somente com motorista.

## Saída e chegada

O controle pertence ao veículo e ao trecho selecionado. Iniciar a ida de um ônibus não inicia outros ônibus. Registrar a chegada da ida não fecha a volta. A viagem geral passa para em andamento na primeira saída e para concluída quando todos os veículos terminarem todos os trechos.

Iniciar viagem e Fechar viagem exigem conexão e confirmação. A volta exige que o trecho anterior daquele veículo tenha sido fechado. Antes de registrar chegada, desembarque os passageiros a bordo e sincronize ou revise todos os registros locais do trecho. O servidor impede fechar com passageiros a bordo. Depois da chegada, o trecho fica disponível para consulta e não aceita novos embarques/desembarques. Repetir a mesma confirmação não altera o horário registrado.

## Passageiros

Desembarcar todos pede confirmação e considera somente passageiros a bordo daquele veículo e trecho, incluindo embarques pendentes no próprio celular. Quem ainda não embarcou continua aguardando. O lote é gravado em uma transação local; conflitos existentes nos passageiros selecionados bloqueiam o lote antes de gravar qualquer comando.

O desembarque funciona offline com preparação válida e fica na fila criptografada. A confirmação no sistema ocorre na sincronização, sujeita à validação de cada passageiro. Alterações de outro aparelho podem exigir revisão.

A lista pode ser recolhida e expandida, mantendo o resumo de passageiros e os controles disponíveis. Todos mostra todos os estados; Não embarcados mostra quem aguarda embarque; Embarcados mostra quem está a bordo. Desembarcados aparecem em Todos. Os filtros consideram também os registros locais pendentes.

## Atualização

Atualize a VPS antes de instalar o APK novo: `cd /opt/nexus-rotafy` e `bash scripts/install_vps.sh`. A migração 0015 adiciona o histórico de saída/chegada aos veículos alocados, preservando os cadastros e reservas existentes. Viagens abertas anteriores começam com os trechos não iniciados.

Instale o APK 1.1.0 (código 2) sobre o aplicativo de produção existente, com a mesma assinatura, para preservar registros locais. Não é necessário desinstalar.

Validação automatizada: 180 testes da API e 16 testes Flutter, incluindo ida/volta, múltiplos veículos, isolamento de empresas, motorista/guia, desembarque em lote, filtros e lista recolhível. O fluxo completo deve ser homologado no aparelho com a API atualizada; a câmera e a navegação externa não foram testadas fisicamente nesta alteração.
