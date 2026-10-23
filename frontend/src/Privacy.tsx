import { useRef, useState, useEffect, type FormEvent } from "react";
import { api } from "./api";
import { createPortal } from "react-dom";
import { DataUseNotice } from "./components/DataUseNotice";
import "./privacy.css";

export const LEGAL = {
  name: "ANDRADE FARTES TI LTDA",
  cnpj: "65.186.307/0001-74",
  address: "R Jornalista Abdon Foes, 200, anexo 302, Navegantes/SC, CEP 88.372-822",
  email: "contato@nexusdataanalytics.com.br",
};
const VERSION = 1;
const KEY = "rotafy_cookie_preferences";

function savedPreferences() {
  try { return JSON.parse(localStorage.getItem(KEY) || "null")?.version === VERSION; }
  catch { return false; }
}

export function PrivacyCenter() {
  const [acknowledged, setAcknowledged] = useState(savedPreferences);
  const dialog = useRef<HTMLDialogElement>(null);
  const [bannerTarget, setBannerTarget] = useState<HTMLElement | null>(null);
  useEffect(() => setBannerTarget(document.getElementById("privacy-banner")), []);
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify({ version: VERSION, necessary: true, analytics: false, advertising: false, updated_at: new Date().toISOString() })); } catch { /* Browsing remains available with storage disabled. */ }
    setAcknowledged(true); dialog.current?.close();
  }
  return <>
    {!acknowledged && bannerTarget && createPortal(<aside className="cookie-banner" aria-label="Informações sobre cookies">
      <strong>Sua privacidade</strong>
      <p>Usamos cookies necessários para manter sua sessão e proteger os formulários. Não usamos Google Analytics, cookies de publicidade ou pixels de rastreamento. Esses cookies necessários não dependem de consentimento.</p>
      <div><button type="button" className="button primary" onClick={save}>Usar somente necessários</button><button type="button" className="button secondary" onClick={() => dialog.current?.showModal()}>Gerenciar cookies</button><a href="/privacidade#cookies">Ler sobre cookies</a></div>
    </aside>, bannerTarget)}
    <footer className="legal-footer" aria-label="Informações legais">
      <nav aria-label="Privacidade e condições de uso"><a href="/privacidade">Privacidade</a><a href="/termos">Termos de uso</a><a href="/cancelamento-reembolso">Cancelamento e reembolso</a><a href="/privacidade/solicitacao">Exercer meus direitos</a><button type="button" onClick={() => dialog.current?.showModal()}>Preferências de cookies</button></nav>
      <p>{LEGAL.name} · CNPJ {LEGAL.cnpj}</p><p>{LEGAL.address}</p><a href={`mailto:${LEGAL.email}`}>{LEGAL.email}</a>
    </footer>
    <dialog ref={dialog} aria-labelledby="cookie-title" className="cookie-dialog">
      <h2 id="cookie-title">Preferências de cookies</h2>
      <label className="operation-checkbox"><input type="checkbox" checked disabled />Cookies necessários — sempre ativos</label>
      <p>rotafy_session identifica a sessão, fica inacessível ao JavaScript e expira conforme o prazo da sessão. rotafy_csrf protege alterações contra solicitações indevidas. Ambos usam SameSite=Lax e Secure em produção.</p>
      <p>A preferência de cookies fica armazenada somente neste navegador. O aplicativo também utiliza armazenamento local necessário para operação offline e preferências de uso. Sair da conta não equivale a apagar registros operacionais pendentes de sincronização.</p>
      <p>Cookies de análise e publicidade: não utilizados. Não há consentimento opcional ativo para revogar. Caso sejam adicionados, dependerão de escolha específica antes de carregar.</p>
      <button type="button" className="button primary" onClick={save}>Salvar somente necessários</button>
      <button type="button" className="button secondary" onClick={() => dialog.current?.close()}>Fechar preferências</button>
    </dialog>
  </>;
}

const privacySections = [
  ["responsaveis", "Quem é responsável", `A plataforma Rotafy é fornecida por ${LEGAL.name}, CNPJ ${LEGAL.cnpj}, em ${LEGAL.address}. Contato de privacidade: ${LEGAL.email}. A Nexus é controladora dos dados de contratação, contas, cobrança e segurança do seu serviço. A empresa de turismo ou transporte é controladora dos dados dos seus passageiros e colaboradores; a Nexus os trata como operadora, conforme suas instruções e as obrigações aplicáveis. Solicitações sobre uma viagem também podem ser encaminhadas diretamente à empresa responsável.`],
  ["dados", "Dados e finalidades", "Contas e contratação: nome, e-mail, função, telefone e dados cadastrais necessários da empresa e representante. Finalidades: criar e proteger acessos, executar o contrato, faturar e registrar o aceite. Passageiros e reservas: nomes, telefone do responsável, dados dos trechos, embarque e pagamento; documento apenas quando necessário à operação ou obrigação aplicável. Hotel ou endereço de embarque é usado para realizar a coleta. Não solicitamos documentos, senhas ou dados de cartão no formulário de privacidade."],
  ["bases", "Bases legais", "A execução do contrato e os procedimentos solicitados pelo titular fundamentam contas, contratação, reservas e comunicação operacional. Obrigações legais ou regulatórias e exercício regular de direitos fundamentam registros fiscais, contratuais e evidências necessárias. Segurança e prevenção a fraudes podem se apoiar em legítimo interesse, com necessidade e ponderação dos direitos do titular. O cliente controlador deve definir e documentar a base legal da sua própria operação. Consentimento, quando aplicável a uma finalidade opcional, deve ser específico e revogável; ler esta política não significa consentimento geral."],
  ["localizacao", "Localização, crianças e pesquisas", "O rastreamento usa o celular do colaborador responsável, durante uma viagem e com permissão do dispositivo, para acompanhamento e avisos de embarque. O administrador pode desabilitar o recurso. A coleta prevista é a cada cinco minutos e pode variar conforme GPS e conexão. A empresa deve informar o colaborador e fundamentar o tratamento. Reservas de menores exigem a atuação do responsável e a observância do melhor interesse da criança ou adolescente; não use campos livres para informar dados sensíveis. Pesquisas de satisfação são opcionais: o destinatário pode pular ou encerrar e não deve enviar dados sensíveis nos comentários."],
  ["compartilhamento", "Compartilhamento e terceiros", "Os dados operacionais ficam disponíveis somente aos perfis autorizados e necessários da empresa. Mensagens operacionais utilizam WhatsApp/Meta e o serviço de mensageria conectado; e-mails utilizam Resend; cobranças da assinatura utilizam InfinitePay. A consulta de CEP utiliza ViaCEP pelo backend e transmite somente o CEP consultado. São compartilhados os dados necessários ao envio ou pagamento, conforme cada integração. O Rotafy não recebe os dados completos de cartão inseridos no checkout do provedor. Mapas podem carregar tiles do OpenStreetMap, transmitindo IP e área consultada; links do Google Maps só abrem por ação do usuário. Fornecedores podem tratar dados fora do Brasil: as transferências e os instrumentos aplicáveis devem ser avaliados pelo controlador conforme a LGPD. O aplicativo não inclui compartilhamento de cadastros para publicidade."],
  ["cookies", "Cookies e armazenamento local", "Usamos rotafy_session para autenticação e rotafy_csrf para proteção dos formulários. Esses cookies são necessários. Preferências e recursos offline utilizam armazenamento local. Não foram identificados Google Analytics, pixels de publicidade ou ferramentas de gravação de sessão nesta versão. Consulte e reabra as preferências de cookies no rodapé a qualquer momento. Evite usar dispositivos compartilhados para dados operacionais offline."],
  ["retencao", "Conservação e segurança", "Os dados são conservados conforme sua finalidade, o contrato, obrigações legais e necessidade de exercício de direitos; não existe um prazo único para todas as categorias. O encerramento ou pedido de exclusão não implica apagamento imediato de registros cuja conservação seja permitida ou exigida pela lei. Backups e cópias devem ser considerados na avaliação do pedido. Utilizamos controle de acesso, isolamento entre empresas, proteção de sessão e de credenciais e conexões seguras. Nenhum sistema garante segurança absoluta. O prazo e os procedimentos de retenção de cada categoria são avaliados no atendimento do pedido."],
  ["direitos", "Seus direitos e como solicitar", `Você pode solicitar confirmação de tratamento, acesso, correção, informação sobre compartilhamento, portabilidade quando aplicável, oposição, revisão de decisões automatizadas, anonimização, bloqueio ou eliminação de dados desnecessários ou tratados irregularmente e revogação de consentimento quando essa for a base legal. Use o formulário Exercer meus direitos ou envie e-mail a ${LEGAL.email}. O canal é gratuito. A equipe pode confirmar a identidade e encaminhar o pedido ao controlador responsável; não envie cópia de documento antes de receber orientação por canal apropriado. Exclusão não é automática e respeita as hipóteses legais de conservação. Você também pode buscar a ANPD e os órgãos de defesa do consumidor.`],
  ["atualizacoes", "Atualizações", "Esta política descreve a versão disponível em 23/10/2026. Mudanças relevantes serão refletidas neste documento. O contrato individual aceito e a legislação aplicável continuam regendo os direitos e obrigações das partes."],
];
const termsSections = [
  ["servico", "Uso do Rotafy", "O Rotafy é um serviço de gestão de transporte, turismo, reservas, comunicação e embarque. O acesso é criado pela equipe Nexus e depende do perfil, módulos contratados e contrato aceito. O administrador da empresa responde pela autorização dos seus colaboradores e pela legitimidade dos dados cadastrados. Não compartilhe senhas, tente acessar dados de outra empresa nem utilize o serviço para mensagens ilícitas ou não solicitadas."],
  ["contratacao", "Planos e contratação", "Valores, setup, franquia, excedentes e período de teste são os apresentados no Quadro de Contratação do contrato individual. O setup é cobrado ao término do teste. A mensalidade é pós-paga ao final dos ciclos de trinta dias, com os excedentes apurados. Mudanças de plano exigem o fluxo contratual específico, com novo documento para aceite. Não há conversão do contador de doze ciclos em fidelidade automática."],
  ["acesso", "Acesso e limitações", "As regras de vencimento, regularização e bloqueio seguem o contrato individual e a cobrança apresentada. Bloqueios financeiros restringem novas operações, mantendo as opções de pagamento e os acessos operacionais preservados conforme a regra vigente. Rede, aparelho e serviços externos podem afetar mensagens, localização e sincronização. Aceite pelo provedor não comprova entrega ou leitura; o aplicativo não garante funcionamento ininterrupto nem horário exato de entrega."],
  ["responsabilidades", "Responsabilidades e direitos", "A empresa de transporte responde por suas viagens, bilhetes, passageiros, obrigações de transporte e informações comerciais. Estes termos não substituem o contrato individual nem limitam direitos previstos em lei. Não copie ou distribua materiais editáveis internos sem autorização. Solicite suporte, esclarecimentos ou cancelamento pelos canais oficiais."],
];
const refundSections = [
  ["assinatura", "Cancelamento da assinatura Rotafy", `Conforme a cláusula 7 do contrato vigente, o encerramento pode ser solicitado por comunicação escrita a ${LEGAL.email}. A Nexus registra o cancelamento, que interrompe a criação de novos ciclos a partir da efetivação. Não há fidelidade mínima nem aviso automático de trinta dias nesta versão.`],
  ["valores", "Valores e reembolso", "O cancelamento não confirma pagamento, não exclui o histórico e não produz devolução automática. Valores já emitidos e efetivamente contratados devem ser conferidos. Não é cobrada multa sobre um saldo hipotético de doze parcelas futuras. Eventuais acertos são informados e formalizados entre as partes. Reembolso é avaliado conforme os fatos, o contrato e a legislação; esta política não estabelece uma vedação geral de restituição."],
  ["consumidor", "Direitos legais", "Quando a relação for de consumo e estiverem presentes os requisitos legais, aplica-se o direito de arrependimento do artigo 49 do Código de Defesa do Consumidor, no prazo de sete dias previsto em lei, com a restituição cabível. O período de teste e estas condições contratuais não afastam direitos legais. Outras hipóteses de restituição, defeito do serviço e cobranças indevidas são analisadas conforme a legislação aplicável."],
  ["viagens", "Cancelamento de viagens e bilhetes", "Esta política trata da assinatura do Rotafy. Cancelamento, remarcação ou reembolso de uma viagem ou bilhete devem ser solicitados à empresa de turismo ou transporte que realizou a venda, conforme as condições informadas na compra e a legislação aplicável. A Nexus não substitui a transportadora no atendimento desse pedido."],
];

export function LegalPage() {
  const path = window.location.pathname;
  const request = path === "/privacidade/solicitacao";
  const title = request ? "Exercer meus direitos" : path === "/termos" ? "Termos de uso" : path === "/cancelamento-reembolso" ? "Cancelamento e reembolso" : "Política de privacidade";
  const sections = path === "/termos" ? termsSections : path === "/cancelamento-reembolso" ? refundSections : privacySections;
  return <main className="legal-page" id="main-content"><a href="/">Voltar ao app</a><h1>{title}</h1><p>Atualizado em 23/10/2026 · Nexus Rotafy</p>
    {request ? <PrivacyRequestForm /> : <><nav aria-label="Conteúdo desta política">{sections.map(([id, heading]) => <a key={id} href={`#${id}`}>{heading}</a>)}</nav>{sections.map(([id, heading, text]) => <section id={id} key={id}><h2>{heading}</h2><p>{text}</p></section>)}<a className="button primary" href="/privacidade/solicitacao">Solicitar atendimento sobre meus dados</a></>}
  </main>;
}

function PrivacyRequestForm() {
  const [message, setMessage] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); const form = event.currentTarget; const data = new FormData(form);
    try { const result = await api<{ protocol: string; message: string }>("/public/privacy-requests", { method: "POST", body: JSON.stringify(Object.fromEntries(data)) }); setMessage(`Protocolo: ${result.protocol}. ${result.message}`); form.reset(); }
    catch(e) { setError(e instanceof Error ? e.message : "Não foi possível registrar. Use o e-mail de contato."); } finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="modal-form"><p>Canal gratuito para solicitações de acesso, correção ou exclusão. A identidade será confirmada antes do atendimento. Não envie CPF, documentos, senhas ou dados sensíveis. O pedido não apaga dados automaticamente.</p><DataUseNotice purpose="registrar e responder ao seu pedido de privacidade" basis="cumprimento de obrigação legal (direitos do titular)" />
    <label className="field"><span>E-mail para retorno</span><input type="email" name="email" maxLength={254} required autoComplete="email" /></label>
    <label className="field"><span>Tipo de solicitação</span><select name="kind"><option value="access">Acesso aos meus dados</option><option value="correction">Correção</option><option value="deletion">Exclusão</option><option value="portability">Portabilidade</option><option value="objection">Oposição ou revogação</option><option value="other">Outra solicitação</option></select></label>
    <label className="field"><span>Como podemos ajudar? (opcional)</span><textarea name="details" maxLength={2000} rows={4} /></label>
    <button className="button primary" disabled={busy}>Registrar solicitação de privacidade</button>{message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}<a href={`mailto:${LEGAL.email}`}>Ou envie um e-mail para {LEGAL.email}</a>
  </form>;
}

const REQUEST_LABELS: Record<string, string> = { access: "Acesso aos dados", correction: "Correção", deletion: "Exclusão", portability: "Portabilidade", objection: "Oposição ou revogação", other: "Outra solicitação" };
type PrivacyRequest = { id: string; email: string; kind: string; details: string; status: string; created_at: string };
export function PrivacyInbox() {
  const [rows, setRows] = useState<PrivacyRequest[]>([]); const [error, setError] = useState("");
  async function load() { try { setRows(await api<PrivacyRequest[]>("/nexus/privacy-requests")); } catch(e) { setError(e instanceof Error ? e.message : "Não foi possível consultar."); } }
  useEffect(() => { void load(); }, []);
  async function update(id: string, status: string) { try { await api(`/nexus/privacy-requests/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }); await load(); } catch(e) { setError(e instanceof Error ? e.message : "Não foi possível atualizar."); } }
  return <section className="operation-card modal-form"><h2>Solicitações de privacidade</h2><p>Últimos 100 pedidos. Confirme a identidade pelo e-mail antes de atender. A exclusão depende da análise do controlador e das obrigações de conservação. A mudança de situação apenas registra a triagem; não apaga dados nem envia e-mail automaticamente.</p>{error && <p role="alert">{error}</p>}{!rows.length && <p>Nenhuma solicitação disponível.</p>}{rows.map(row => <article className="privacy-request" key={row.id}><h3>{REQUEST_LABELS[row.kind] || "Solicitação"} · {row.email}</h3><p>Protocolo: {row.id} · {new Date(row.created_at).toLocaleString("pt-BR")}</p><p>{row.details || "Sem descrição adicional."}</p><label className="field"><span>Situação do pedido {row.id}</span><select value={row.status} onChange={event => void update(row.id, event.target.value)}><option value="received" disabled>Recebida</option><option value="verifying">Verificando identidade</option><option value="processing">Em análise</option><option value="completed">Concluída</option><option value="rejected">Indeferida</option></select></label><a href={`mailto:${row.email}`}>Responder ao solicitante por e-mail</a></article>)}</section>;
}
