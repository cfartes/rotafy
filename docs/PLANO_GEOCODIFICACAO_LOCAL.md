# Geocodificação automática de embarques na VPS

Status: alternativa de hospedagem própria descartada pelo cliente em favor da Google Geocoding API. Documento preservado apenas como histórico técnico; não usar como instrução de instalação. Consulte GEOCODIFICACAO_GOOGLE.md.

## Decisão

Usar Nominatim hospedado na VPS, com dados OpenStreetMap. Não usar o
servidor público de pesquisa nem consultar um provedor pago como fallback.
Cobertura geográfica e recursos disponíveis devem ser definidos antes de
dimensionar e importar a base. Não presumir que o Brasil inteiro caiba na VPS.

## Fluxo

1. Salvar a reserva normalmente, sem aguardar a pesquisa de endereço.
2. Processar endereços pendentes em um worker próprio, separado dos envios
   de WhatsApp. A lentidão do geocodificador não pode atrasar os lembretes.
3. Consultar primeiro locais já identificados na mesma empresa. A chave deve
   considerar endereço normalizado, número e cidade; não nome do passageiro,
   quarto ou complemento pessoal. Não compartilhar endereços residenciais
   entre empresas.
4. Pesquisar o endereço novo no serviço interno, usando a cidade do embarque
   como contexto. Aceitar automaticamente somente resultados específicos e
   compatíveis com o endereço; um único resultado não prova correspondência.
   Não aceitar centro da cidade, CEP ou rua inteira como localização da casa.
5. Persistir coordenadas, origem da localização, endereço pesquisado, data e
   estado: pendente, localizado, revisão necessária ou erro temporário.
6. Reutilizar a localização nas reservas e viagens seguintes. Endereço alterado
   invalida a associação antiga e solicita nova pesquisa. Mudanças somente em
   quarto/complemento não exigem outra consulta geográfica.
7. Preservar ajustes manuais. Um resultado que retornar depois de uma edição
   não pode sobrescrever o endereço novo nem uma correção feita pelo operador.
8. Mostrar revisão somente para locais incompletos, ambíguos ou não encontrados.
   Não impedir venda e lembrete de saída; manter proximidade suspensa até existir
   coordenada válida. Retentar falhas temporárias com espera e limite.

## Integração com o sistema atual

- Reaproveitar `boarding_point` para obter o local efetivo de cada trecho.
- Reaproveitar o controle de mudança de endereço e a associação reserva/trecho
  de `tracking_boardings`, distinguindo localização automática de confirmação
  humana em vez de registrar um funcionário fictício.
- Processar também reservas confirmadas de viagens futuras já existentes,
  progressivamente, sem exigir nova venda.
- Preservar coordenadas e alterações manuais já cadastradas.
- O aviso de proximidade continua exigindo sessão ativa do veículo, posição
  recente, precisão adequada e passageiro aguardando embarque.
- A volta tem local de embarque próprio. Nunca copiar automaticamente a
  localização da ida para o retorno.
- Não mudar o ato de assumir o rastreamento no APK nesta entrega.

## Infraestrutura

- Serviço e volume Docker exclusivos; não usar o PostgreSQL do Rotafy para a
  base OpenStreetMap e não recriar o banco de clientes.
- API de pesquisa acessível somente pela rede privada dos serviços necessários;
  sem porta pública, sem rota Traefik e sem acesso direto pelo navegador.
- Instalação inicial separada da atualização normal: a importação pode levar
  bastante tempo e não deve bloquear o deploy do app.
- Fixar a versão da imagem e definir limites de recursos depois da medição da
  VPS; verificar RAM, CPUs, espaço livre e cobertura antes de importar.
- Informar a cobertura e a data da base; documentar atualização incremental
  compatível com o extrato escolhido e atribuição OpenStreetMap.
- Não registrar endereço completo, nome ou telefone em logs operacionais.

## Verificação necessária

- Endereço exato, hotel com cidade, rua sem número, nome duplicado e cidade
  incorreta; resultados parciais devem ir para revisão.
- Local repetido reutilizado; isolamento entre empresas; edição concorrente;
  ida e volta; preservação de coordenada manual.
- Serviço indisponível não impede venda nem envio dos lembretes de horário.
- Migração incremental, dados existentes preservados e processamento em lote
  limitado; confirmar posição obtida no aviso de proximidade ponta a ponta.

## Fontes técnicas

- https://nominatim.org/release-docs/latest/admin/Installation/
- https://github.com/mediagis/nominatim-docker/blob/master/howto.md
- https://operations.osmfoundation.org/policies/nominatim/

## Informação pendente

Cobertura aprovada: Brasil inteiro. Capacidade total informada: 8 GB RAM,
4 CPUs e 200 GB de armazenamento, compartilhados com os serviços existentes.
Esses totais não comprovam capacidade livre para importar e manter a base.

Antes de habilitar a importação, verificar `free -h`, `nproc`, `df -h /` e
`docker stats --no-stream`. Não iniciar uma importação nacional presumindo
que os 200 GB estejam disponíveis. Se faltar margem, manter o geocodificador
em outra VPS privada ou ampliar recursos; não reduzir a cobertura aprovada
silenciosamente. A alternativa Photon com extrato pré-processado pode evitar
uma importação Nominatim local, mas exige comprovar disponibilidade do extrato
brasileiro, versão compatível e consumo real antes de substituir a arquitetura.
