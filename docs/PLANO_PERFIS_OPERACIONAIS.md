# Plano de melhoria — Turismo e Transporte regular

Status: implementado. Migração `0018_operational_profiles`; entrega mantém o Android operacional existente, pois suas funções são compartilhadas entre os dois perfis.

## Objetivo

Manter uma plataforma SaaS compartilhada e oferecer duas experiências operacionais por empresa: Turismo e transfers (`tourism`) e Transporte regular (`regular`). O perfil pertence à empresa, é independente do plano comercial e deve orientar telas e regras da API.

## Escopo desta etapa

1. Acrescentar perfil operacional à empresa com migração, valores válidos e preenchimento de empresas existentes como Turismo e transfers. Preservar viagens, reservas, equipe, planos, franquia e histórico.
2. Exigir escolha explícita no cadastro inicial público e no cadastro pela Nexus, com descrição dos dois perfis. Exibir perfil na lista de empresas, na gestão Nexus e no painel da empresa.
3. Centralizar capacidades por perfil. Combinar perfil operacional com permissões de admin, atendente, motorista e guia; o perfil não concede funções administrativas.
4. Ajustar navegação, atalhos, formulários, dashboard e página pública para a experiência escolhida. Turismo mantém pacotes, atividades e roteiros completos; Regular usa viagens avulsas, Rotas, frota, equipe, passageiros e venda de bilhetes já existentes. Não mostrar cadastros de pacotes ou contratação de novos pacotes em Regular.
5. Validar no backend as operações exclusivas de Turismo, inclusive chamadas diretas, criação/edição/duplicação de viagens e venda pelos canais público e externo. A empresa consultada pelo backend determina o perfil; parâmetros enviados pelo app não podem liberá-lo.
6. Permitir mudança apenas pela Nexus, com análise de impacto e registro de auditoria. Bloquear mudança para Regular enquanto houver saídas de pacotes agendadas ou em andamento. Preservar consulta do histórico e os dados dos modelos; não converter ou excluir roteiros automaticamente. Mudanças usam bloqueio transacional da empresa para evitar concorrência com criação de pacotes.
7. Preparar a API para informar perfil e capacidades aos aplicativos. Adaptar o Android de motorista/guia apenas onde houver apresentação específica. Embarque, QR, início/conclusão, GPS de chegada e agenda continuam comuns; dados offline e filas pendentes devem ser preservados. O futuro app do passageiro consumirá esse mesmo perfil.
8. Testar os dois perfis e atualizar documentação de implantação. Se houver alteração do Android, gerar APK assinado de atualização após as verificações.

## Matriz funcional

| Recurso | Turismo e transfers | Transporte regular |
|---|---|---|
| Rotas, cidades/UFs, endereços e paradas | Sim | Sim |
| Viagem avulsa de ida ou ida e volta | Sim | Sim |
| Frota, equipe e alocação | Sim | Sim |
| Reservas, famílias e passageiros | Sim | Sim |
| Venda manual e página pública | Sim | Sim, com fluxo atual de viagem avulsa |
| Bilhetes QR, embarque e desembarque | Sim | Sim |
| Agenda, chegada e relatórios | Sim | Sim |
| Pacotes com vários destinos e atividades | Sim | Não para novas operações |
| Linhas e recorrência automática | Etapa futura, se aplicável | Etapa futura |
| Venda de trechos independentes de uma linha | Etapa futura, se aplicável | Etapa futura |

## Compatibilidade e limites

- As empresas atuais recebem Turismo, preservando o comportamento existente.
- Basic, Professional e Enterprise mantêm suas regras comerciais. Não haverá preços, franquias ou módulos definidos apenas pelo novo perfil nesta etapa.
- O consumo atual permanece: viagem avulsa consome uma unidade; pacote turístico consome uma por destino comercial, com retorno e paradas incluídos.
- Regular nesta entrega significa segregação da experiência disponível, não implantação de um sistema completo de linhas regulares. Recorrência, linhas e venda independente por trecho precisam de planejamento próprio.
- Não implementar app do passageiro, contas de clientes, WhatsApp ou notificações nesta etapa.
- Não criar perfil misto agora. Se surgir necessidade comprovada, planejar sua inclusão sem substituir os dois perfis iniciais.

## Ordem de execução

1. Banco, esquema da empresa e capacidades centralizadas.
2. Cadastro inicial, gestão Nexus e mudança controlada de perfil.
3. Restrições da API e canais de venda.
4. Painel web e página pública por perfil.
5. Compatibilidade Android e preparação do contrato para o app do passageiro.
6. Testes, migração local, documentação e entrega para atualização da VPS.

## Critérios de aceite

- Cadastro público e Nexus exigem seleção do perfil e salvam corretamente a opção.
- Empresa atual continua vendo a experiência Turismo após a migração.
- Regular não cria, altera ou vende novos pacotes, mesmo chamando a API diretamente.
- Regular continua cadastrando viagens avulsas, alocando veículos e vendendo bilhetes pelo fluxo existente.
- Turismo mantém pacotes completos, capacidades por deslocamento, cobrança por destino e QR.
- Histórico permanece consultável e não é reclassificado ou apagado na troca de perfil.
- Troca incompatível é bloqueada com mensagem objetiva; troca permitida é auditada.
- Perfil de uma empresa não altera permissões ou dados de outra.
- Android permanece compatível com ambos os perfis e preserva registros locais.

## Homologação sugerida

Usar uma empresa de cada perfil. Conferir cadastro e login, navegação, viagem avulsa, reserva familiar, QR, operação sem guia, página pública, tentativa direta de pacote em Regular, pacote completo em Turismo e mudança de perfil com/sem pacote ativo.

## Como utilizar

No cadastro inicial ou pela Nexus, selecione **Perfil operacional** e depois o plano comercial. Empresas anteriores à migração recebem Turismo automaticamente. O perfil aparece abaixo do nome da empresa no painel e na lista de empresas da Nexus.

Para alterar, entre em **Nexus → Empresas → Editar dados → Perfil operacional**. A operação exige o perfil anterior para detectar alterações concorrentes. Viagens vinculadas a pacotes agendadas/em andamento bloqueiam a mudança para Regular, incluindo pacotes antigos sem roteiro multi-destino. O histórico permanece consultável; modelos antigos de pacotes ficam preservados para eventual retorno ao perfil Turismo. A alteração e seus perfis anterior/novo são registrados nas atividades.

O endpoint `GET /api/v1/company` informa `operational_profile` e `capabilities`, com linhas recorrentes e venda independente por trecho desabilitadas. O cadastro pela API exige `operational_profile` (`tourism` ou `regular`). Integrações que criam empresas precisam enviar esse campo. Os aplicativos operacionais existentes continuam usando os mesmos endpoints, contas e bilhetes.

Atualize a VPS pelo fluxo existente, que executa backup e migrações:

```bash
cd /opt/nexus-rotafy
bash scripts/install_vps.sh
```

Não é necessário reinstalar o banco ou o APK do motorista/guia nesta entrega. O app do passageiro continua em uma etapa posterior.
