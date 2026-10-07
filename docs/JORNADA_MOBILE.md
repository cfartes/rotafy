# Operação de viagem no Android — versão 1.1.0

## Localização da chegada — versão 1.3.0

Ao confirmar a chegada, motorista ou guia pode autorizar a localização do celular. O app solicita apenas a localização em uso e tenta obter uma posição atual por até 15 segundos. Registra latitude, longitude, precisão em metros e horário informado pelo dispositivo. Posições antigas (mais de dois minutos) são descartadas. Localização aproximada também é aceita e a precisão fica visível.

Se a permissão for negada/bloqueada, a localização estiver desativada ou a captura falhar, a chegada continua permitida e o motivo é enviado à API. A chegada exige conexão; esta funcionalidade não realiza rastreamento contínuo. O servidor associa o registro ao usuário autenticado e acrescenta seu próprio horário de recebimento. Repetir a confirmação preserva o primeiro registro e suas coordenadas.

No painel da empresa, abra **Frota, pacotes e viagens → Viagens → Detalhes**. Cada veículo mostra a chegada por trecho, responsável, coordenadas, precisão e link **Ver local da chegada no Google Maps**, ou a justificativa de ausência da localização.

Atualize o backend e o painel na VPS antes do APK 1.3.0: `cd /opt/nexus-rotafy` e `bash scripts/install_vps.sh`. Não há nova migração: os dados ficam no histórico JSON existente da migração 0015, protegido pelo isolamento da empresa. Apps anteriores continuam aceitos e chegadas sem o campo de localização são identificadas como não enviadas. Instale sobre a versão atual para preservar a fila local.

Validação desta versão: 182 testes da API, 30 testes Flutter e build de produção do painel. GPS físico e diálogo de permissão ainda precisam de homologação no aparelho.

Referência da integração de localização: [documentação oficial do Geolocator](https://pub.dev/packages/geolocator).

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
