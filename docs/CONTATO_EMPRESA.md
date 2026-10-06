# Cadastro e contato da empresa

Cadastro Nexus e primeiro acesso público usam formulário com até 960px, campos em duas colunas e uma coluna no celular. O cabeçalho fica acessível durante a rolagem; dados do administrador também seguem a grade. Edição da empresa usa a mesma largura.

Telefone / WhatsApp é contato da empresa cliente, com máscara nacional e suporte a números internacionais iniciados por +. O campo é opcional para preservar compatibilidade com cadastros e integrações existentes. Quando informado, a API exige número válido, sem ramal, e grava o formato E.164 (exemplo: +5547999999999).

O contato pode ser criado e editado pela Nexus; também é recebido no cadastro público. Não é exibido no retorno público do cadastro ou em catálogos de viagens. A leitura autenticada mantém o escopo de empresa/perfil existente. Atualizações antigas que omitem o campo preservam o número; envio vazio remove o contato.

Migração `0014_company_contact` adiciona coluna nullable a empresas, sem modificar registros anteriores. O instalador da VPS aplica a migração durante a atualização:

```sh
bash /opt/nexus-rotafy/scripts/install_vps.sh
```

O número prepara o cadastro para a etapa WhatsApp; não representa conexão do número a um provedor nem ativa envio de mensagens. O telefone dos compradores/famílias já é registrado nas reservas. Mensagens de compra/passagens deverão usar esses destinatários e a conexão WhatsApp da agência quando essa integração for implementada.

Validação: 177 testes funcionais backend e um cenário de carga aprovados em Linux (178 no total), build web e jornada Chromium com telefone, largura desktop e ausência de rolagem horizontal no celular aprovados. Migração aplicada ao banco local. Nenhuma atualização remota executada nesta entrega.
