# Endereço da empresa por CEP

O CEP é o primeiro campo da seção **Endereço da empresa**. Ao completar oito dígitos, o formulário consulta o endereço e preenche logradouro, bairro, cidade e UF. O usuário confere os dados e informa número e complemento; esses dois campos não são alterados pela consulta.

O comportamento é compartilhado pelo cadastro Nexus, edição Nexus, edição da própria empresa e confirmação dos dados no primeiro acesso do representante. Endereços já salvos não são consultados ou sobrescritos automaticamente ao abrir o cadastro. Alterar o CEP inicia outra consulta. Correções manuais feitas enquanto a resposta está chegando são preservadas; respostas de um CEP anterior são descartadas.

Se o CEP não existir, o provedor estiver indisponível ou o CEP for genérico e não trouxer logradouro/bairro, os campos permanecem editáveis para preenchimento manual. O preenchimento dos campos obrigatórios continua sendo validado ao salvar.

A consulta usa o ViaCEP pelo backend: somente o CEP é enviado ao provedor, sem dados da empresa, usuário ou credenciais. São aceitos apenas oito dígitos, destino HTTPS fixo sem redirecionamento, resposta limitada e timeout de cinco segundos. Resultados válidos são armazenados em cache limitado, com renovação diária. Não exige API key ou migração do banco.

O endpoint é autenticado. Administradores com aceite contratual pendente podem consultar o CEP para completar o cadastro, preservando a restrição dos módulos operacionais. A consulta não realiza aceite ou alteração cadastral por si só.

Referência do serviço: https://viacep.com.br/
