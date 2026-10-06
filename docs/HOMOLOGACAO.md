# Homologação antes da liberação

Atualizado em 2026-10-06. Implementação e testes locais não significam implantação na VPS nem aceite em aparelhos físicos.

| Verificação | Situação | Evidência ou próximo passo |
| --- | --- | --- |
| Isolamento de duas empresas e permissões | Automatizado local | Testes backend e jornada de carga |
| Reserva familiar, ida/volta, capacidade e concorrência | Automatizado local | Regressões de reservas/operações |
| Página pública, PAGO manual, bilhete e embarque | Automatizado local | Playwright Chromium |
| Offline, fila, perda de resposta e conflitos | Automatizado local | Backend e Playwright; servidor continua autoridade |
| Relatórios, CSV e filtros | Automatizado local | Testes de relatórios e screenshots desktop/mobile |
| Edição de viagens/reservas e realocação com histórico | Automatizado local | Testes backend e jornadas Chromium ampliadas |
| Convites e recuperação por Resend | Transporte simulado local; envio real pendente | Configurar chave/remetente verificado; conferir recebimento, spam, expiração, uso único e sessões revogadas |
| Restauração de snapshot consistente | Ensaio local aprovado | RESTORE_DRILL_RESULT.json; container isolado |
| Carga de duas empresas e 20 veículos | Medida local | LOAD_TEST_RESULT.json; repetir na VPS |
| Compose, Caddy e serviço de backup | Preparados/validados localmente | Configuração, build e validação sem publicação |
| Instalação/câmera/offline Android real | Pendente | HTTPS; executar roteiro abaixo |
| Instalação/câmera/offline iPhone real | Pendente | Safari/HTTPS; executar roteiro abaixo |
| Inventário, DNS e HTTPS na Hostinger | Pendente | Acesso e configuração do servidor |
| Backup externo, agenda e recuperação desse storage | Pendente | Definir repositório, primeiro envio e ensaio |
| Aceite da agência e carga na VPS | Pendente | Piloto com responsáveis dos quatro perfis |

## Roteiro para cada aparelho físico

Registrar modelo, versão do sistema/navegador, data e operador. Em HTTPS:

1. Entrar como guia, preparar ida e volta do veículo atribuído e instalar/adicionar a PWA à tela de início.
2. Autorizar a câmera e ler bilhete válido na tela e impresso; conferir trecho/veículo errado e passageiro cancelado.
3. Ativar modo avião, fechar e reabrir a PWA; confirmar lista preparada, QR e registro manual, desembarque e reversão.
4. Recarregar/reabrir e reiniciar o aparelho mantendo ações pendentes. Confirmar fila preservada e estado marcado como local.
5. Reconectar com sessão válida e depois com sessão expirada, usando o usuário original. Conferir sincronização única e proteção ao trocar usuário/sair com fila.
6. Com dois aparelhos, alterar presença no servidor enquanto o outro está sem rede; revisar conflito, manter servidor/reaplicar e conferir histórico.
7. Revogar bilhete e cancelar viagem enquanto outro aparelho está sem rede; reconectar e conferir rejeição sem registrar uma ação inválida.
8. Conferir limpeza/expiração dos manifestos e consulta do motorista sem botões de alteração.

Fila local depende do armazenamento do navegador. GPS em segundo plano, rastreamento e WhatsApp não fazem parte desse roteiro nem desta entrega.

## Piloto na VPS

Validar com dados de teste de duas empresas, conta de administrador/atendente, guia, motorista e comprador. Repetir reserva concorrente pela última vaga, cancelamento/estorno do ciclo e todas as jornadas comerciais. Medir erro/latência e disco sob carga representativa. Confirmar que apenas o proxy publica portas, o cookie é Secure, a origem é validada e um backup do storage externo realmente restaura em outro ambiente.

Registrar resultado e pendências antes de liberar clientes reais. Seguir [IMPLANTACAO_E_OPERACAO.md](IMPLANTACAO_E_OPERACAO.md) para preparação e atualização.
