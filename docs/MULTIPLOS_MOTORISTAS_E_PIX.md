# Múltiplos motoristas e Pix Copia e Cola

Migração incremental `0023_multiple_crew`, posterior a `0022_manual_billing`. Não utiliza DROP DATABASE, TRUNCATE ou recriação de tabelas existentes.

## Equipe por veículo/viagem

A nova tabela trip_drivers contém os motoristas atribuídos a uma alocação, com ordem e isolamento por empresa. A migração copia o driver_id de todas as alocações existentes. O campo driver_id permanece como primeiro motorista para compatibilidade com clientes antigos. A API aceita driver_id antigo ou driver_ids com um a vinte motoristas e retorna drivers e driver_ids. Vários guias já eram permitidos por trip_guides e continuam disponíveis.

Criação e edição validam todos os profissionais ativos, papel, empresa e conflito de horário. A substituição preserva os IDs de alocação e passageiros existentes; remoção da equipe revoga acesso aos dados operacionais. Atualizar a versão da Rota preserva todos os motoristas. Listagem, agenda, mapas, manifesto, embarque e jornada verificam também motoristas adicionais. O app Android 1.5.3 (10) inclui a nova filtragem. Clientes antigos mantêm acesso do motorista principal; motoristas adicionais precisam atualizar o APK.

## Pix Copia e Cola

Campo opcional exclusivo das configurações do superadmin. Aceita BR Code Pix estático, sem valor, com verificação CRC16, estrutura, moeda BRL e correspondência com a chave Pix cadastrada. Não verifica titularidade nem existência da conta no banco. CPF/CNPJ e telefone são comparados sem máscara; a chave bancária original permanece intacta no código.

O conteúdo é preservado na cobrança ao fechar o ciclo e acompanha o texto da cobrança e do bloqueio por e-mail e WhatsApp. Não cria QR Code em imagem, não altera cobranças já emitidas e não reconhece pagamentos automaticamente. Requisições antigas de configuração que omitem o campo preservam o código existente; enviar vazio remove o código das próximas cobranças.

## Atualizar o aplicativo e preservar o banco

O atualizador normal aplica as migrações automaticamente, com backup, e atualiza os serviços:

```bash
cd /opt/rotafy-tech &&
git pull --ff-only origin main &&
bash scripts/update_vps.sh
```

## Somente migração do banco

Quando for necessário separar as etapas, o script abaixo reutiliza a imagem já instalada e monta apenas as migrações do checkout atualizado. Faz backup antes de executar Alembic e não recria banco, API, web ou workers:

```bash
cd /opt/rotafy-tech &&
git pull --ff-only origin main &&
bash scripts/migrate_vps.sh
```

A migração isolada prepara o banco, mas não atualiza a interface nem o código da API. Execute depois a atualização normal para disponibilizar os recursos. O Alembic identifica migrações já aplicadas e não as repete. Não use install_clean_vps.sh para esta atualização.
