export function DataUseNotice({ purpose = "processar esta solicitação e operar os cadastros, acessos e serviços contratados", basis = "execução do contrato e cumprimento das obrigações legais aplicáveis" }: { purpose?: string; basis?: string }) {
  return <p className="data-use-notice">Finalidade: {purpose}. Base legal: {basis}. Informe somente os dados necessários e não inclua dados sensíveis nos campos livres. <a href="/privacidade" target="_blank" rel="noopener noreferrer">Como seus dados são tratados</a>.</p>;
}
