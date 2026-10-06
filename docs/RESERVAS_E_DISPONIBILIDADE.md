# Reservas familiares e disponibilidade

Implementado em ambiente local. Para acessar: **Frota, pacotes e viagens → Detalhes → Reservas e lugares**. Administradores e atendentes operam este módulo; guias e motoristas acessam os manifestos das viagens atribuídas.

## Cadastro manual

- Uma reserva tem responsável, telefone compartilhado e de 1 a 200 passageiros. O responsável só ocupa um lugar se também for incluído na lista de passageiros.
- CPF é obrigatório para todos os passageiros quando algum trecho cruza UFs, exceto estrangeiros e menores de cinco anos com nascimento informado. Em viagens dentro da mesma UF é opcional. Quando informado, seus dígitos são validados; não pode repetir entre passageiros de reservas ativas da mesma viagem. Consulte [GEOGRAFIA_E_ROTAS.md](GEOGRAFIA_E_ROTAS.md).
- Para telefone nacional, informe a sigla ISO do país. Também é possível informar `+` e código internacional. O telefone é armazenado normalizado; números internacionais não são tratados automaticamente como brasileiros. A validação usa [python-phonenumbers](https://github.com/daviddrysdale/python-phonenumbers).
- A reserva inclui todos os trechos da viagem. Ida/volta deve ter embarque e desembarque selecionados para ambos os trechos; trecho único usa somente uma seleção.
- Origem e destino são opções implícitas. Paradas intermediárias respeitam sua operação de embarque, desembarque ou ambos. O desembarque deve estar depois do embarque.
- Valor total é o preço por passageiro da viagem multiplicado pela quantidade de passageiros e fica preservado na reserva. Confirmar uma reserva não significa marcar PAGO.

## Lugares e família

A ocupação é calculada para cada segmento entre pontos consecutivos. Quem desembarca antes libera o lugar para outro passageiro que embarca naquele ponto. Ida e volta são verificadas juntas.

Uma família inteira usa o mesmo veículo nos trechos reservados. A sugestão escolhe, entre os veículos que comportam a família, aquele que deixa menos lugares livres no itinerário escolhido. Empates usam nome/identificador para manter o resultado determinístico.

Ter lugares suficientes somando vários ônibus não garante que uma família caiba inteira em um deles. Nesse caso o sistema informa a indisponibilidade e não divide a família automaticamente. O atendente também pode escolher outro veículo elegível.

A tela mostra lugares disponíveis para a rota completa e permite abrir a ocupação por segmento de cada trecho. No formulário, a disponibilidade corresponde aos pontos escolhidos. Consultas não bloqueiam lugares; a gravação sempre verifica novamente a ocupação.

## Situações e concorrência

- **Confirmada:** mantém os lugares ocupados até cancelamento.
- **Bloqueio pendente:** ocupa lugares por 15 minutos, contados da criação. Pode ser confirmado antes do vencimento.
- **Expirada:** não ocupa lugares e não pode ser confirmada. Crie uma nova reserva se ainda houver disponibilidade.
- **Cancelada:** libera todos os lugares; repetir o cancelamento não gera outro evento nem reativa a reserva.

O worker local verifica expirações a cada 60 segundos. As consultas de ocupação já desconsideram bloqueios vencidos imediatamente, mesmo antes do worker atualizar sua situação física. Comandos de reserva também fazem essa atualização. A auditoria de expiração identifica a ação automática sem inventar um usuário.

Comandos são serializados por empresa na mesma transação da verificação e gravação. Duas solicitações simultâneas pela última vaga não ultrapassam a capacidade. Repetir uma criação com a mesma chave de operação retorna a reserva original; reutilizar a chave com outros dados retorna conflito. A mesma família ativa não pode ser cadastrada novamente silenciosamente.

A realocação muda o veículo da família inteira, exige lugares em todos os segmentos reservados e mantém passageiros, valor e prazo original. Reservas canceladas/expiradas não podem ser realocadas.

Novas reservas exigem viagem agendada, ainda não iniciada. Realocações permitem viagens agendadas ou em andamento, desde que ninguém da família esteja a bordo; preservam o histórico concluído no veículo original. Cancelar uma viagem cancela suas reservas ativas e estorna o consumo da viagem na mesma transação. Criar, confirmar, cancelar ou realocar somente uma reserva não muda a franquia da Nexus. Correções cadastrais e pontos podem ser feitas no editor, conforme [as regras de edição](EDICAO_E_EMAILS.md).

## Importação CSV/XLSX

O botão **Baixar modelo CSV** gera o cabeçalho:

```csv
familia,responsavel,telefone,pais,passageiro,cpf,estrangeiro,menor_5_anos,nascimento
FAM001,Família Exemplo,+5511999999999,BR,Passageiro Exemplo,,nao,nao,
```

- Uma linha por passageiro. Repita o identificador da família, responsável e telefone para agrupá-los. CPF vazio segue as regras da viagem; exceções usam `sim`/`nao` e nascimento `AAAA-MM-DD`. Arquivos antigos com seis colunas continuam aceitos, com as mesmas validações.
- CSV deve ser UTF-8; vírgula e ponto e vírgula são aceitos. XLSX deve ter uma única aba e células de texto, inclusive para telefone/CPF; fórmulas e macros não são aceitas.
- Limites: 2 MB, 500 linhas de passageiros e até 200 passageiros por família. XLSX também tem limites de quantidade de arquivos internos e 20 MB descompactados. A leitura usa o modo [read-only do openpyxl](https://openpyxl.readthedocs.io/en/stable/optimized.html) com proteção XML.
- A prévia mostra famílias válidas e erros por linha. Nenhuma reserva é criada nessa etapa. Todos os erros devem ser corrigidos antes da confirmação.
- A prévia vale por 30 minutos e não bloqueia lugares. Reenviar o mesmo arquivo renova uma prévia expirada ainda não aplicada.
- Ao confirmar, são criadas reservas confirmadas, para a rota completa de todos os trechos, mantendo cada família inteira. Para pontos intermediários específicos, use o cadastro manual.
- A confirmação é atômica: se qualquer família não couber, ou já estiver cadastrada/importada, nenhuma reserva daquele lote é criada. A mensagem identifica a família que impediu a operação.
- Repetir a confirmação ou reenviar o mesmo arquivo aplicado retorna o resultado existente. O identificador de família não pode ser importado novamente na mesma viagem, mesmo com um arquivo alterado. O histórico é preservado após cancelamento.

Prévia e reservas ficam isoladas por empresa com RLS forçado e vínculos compostos. Arquivos não são guardados no disco da aplicação; a prévia normalizada fica no banco. As telas e a API administrativas expõem dados pessoais somente a administrador/atendente da empresa. Senhas, telefones e CPF não são gravados em eventos de auditoria.

## API

- `POST /api/v1/trips/{id}/availability`: quantidade da família e seleções de trecho opcionais; retorna ocupação e sugestão.
- `GET/POST /api/v1/trips/{id}/reservations`: lista e cadastro manual. Criação exige `operation_key` UUID.
- `GET /api/v1/reservations/{id}`: passageiros e itinerário da reserva.
- `PATCH /api/v1/reservations/{id}/status`: confirmar ou cancelar.
- `PATCH /api/v1/reservations/{id}/vehicle`: realocar toda a família.
- `POST /api/v1/trips/{id}/reservation-imports/preview`: arquivo multipart CSV/XLSX.
- `POST /api/v1/reservation-imports/{id}/apply`: confirmar a prévia sem duplicações.

Os pontos da API usam posições: origem `0`, paradas `1..N`, destino `N+1`. Contrato completo em `http://localhost:8018/docs`.

## Próxima entrega e limites

Página pública, integração de reservas com sites externos, acompanhamento do comprador, avisos para agência e marcação manual **PAGO** estão disponíveis. Edição de reservas respeita o histórico de embarque. Bilhetes QR, manifestos e preparação offline são descritos nos guias próprios. Não há integração financeira, rastreamento ou WhatsApp.
