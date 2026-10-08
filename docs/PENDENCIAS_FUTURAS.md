# Pendências para próximas etapas

Atualizado em 08/10/2026. Este arquivo registra trabalho futuro; não representa funcionalidades já implementadas.

## App Android do passageiro

- Criar aplicativo separado do motorista/guia no mesmo projeto, utilizando o backend compartilhado e o isolamento por empresa.
- Configurar empresa, nome, ícone e cores antes de disponibilizar o APK. O passageiro não informa a empresa; o backend valida o vínculo.
- Criar contas de clientes, login com CPF e senha e cadastro diretamente no app.
- Definir envio de senha temporária, troca no primeiro acesso, confirmação do telefone e recuperação de acesso.
- Selecionar o serviço/API de WhatsApp e configurar o número de cada empresa. A integração de envio ainda precisa ser implementada.
- Definir acesso do responsável aos bilhetes de toda a família e vínculo de reservas existentes com verificação de titularidade.
- Definir acesso de estrangeiros sem CPF; proposta: documento estrangeiro/passaporte e telefone verificado. Menores vinculados ao responsável.
- Definir escopo inicial: somente consultar viagens contratadas ou também solicitar contratação pelo catálogo, mantendo confirmação/PAGO manual.
- Exibir próximas viagens, histórico, roteiro dos pacotes e bilhetes QR compatíveis com o app operacional.
- Disponibilizar QR offline após carregamento, sem invalidar credenciais já preparadas pelo motorista/guia ao simplesmente abrir o bilhete.
- Definir lembretes: 24 horas antes ou horário fixo no dia anterior; início do pacote ou cada deslocamento. Implementar permissões, atualização/cancelamento de lembretes e comportamento offline.
- Usar o perfil Turismo/Regular da empresa para orientar a experiência do passageiro.
- Homologar acesso, reservas familiares, QR e lembretes em aparelho real. iOS permanece fora do escopo atual.

## Transporte regular

- Planejar cadastro de linhas e horários recorrentes e geração das saídas.
- Implementar venda independente por origem/destino/trecho e disponibilidade entre pontos, com regras próprias de preço e ocupação.
- Definir franquia para saídas recorrentes antes de implantar essa operação, preservando os contratos existentes.
- Evoluir a experiência do passageiro para linhas regulares compartilhando a base técnica; não criar outro produto independente nesta etapa.

## Homologação do perfil operacional

- Publicar a atualização dos perfis Turismo/Regular na VPS pelo instalador existente, caso ainda não tenha sido aplicada.
- Homologar uma empresa de cada perfil, cadastro inicial, navegação e alteração controlada pela Nexus.
- Homologar pacote com troca de veículos em aparelho real.

## Integrações e recursos adiados

- Consulta de duração/rota pela API Google; atualmente a duração é manual e a navegação abre o Google Maps externo.
- Rastreamento contínuo por dispositivo OBD2/GPS ou celular, incluindo captura em segundo plano com tela desligada. O registro pontual de coordenadas de chegada já existe.
- Mensagens WhatsApp de contratação e comunicações operacionais por empresa, além dos fluxos de acesso do passageiro.
- Integração com meios de pagamento permanece fora do escopo atual; hoje existe marcação manual PAGO.

## Decisões preservadas

- Perfil operacional e plano Basic/Professional/Enterprise são independentes.
- Pacotes turísticos são vendidos completos, com retorno incluído. Destinos separados exigem outro pacote.
- Cada destino comercial do pacote consome uma unidade da franquia; retorno e paradas não acrescentam consumo. Cancelamento estorna o consumo original.
- Motorista e guia compartilham as funções operacionais; guia é opcional.
