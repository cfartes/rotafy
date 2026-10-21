import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Company, type User } from "./api";
import { AddressFields, addressPayload } from "./CompanyAddress";
import { Alert, Field, Modal } from "./components/ui";
import { Collections } from "./Collections";

type Document = { id: string; sha256: string; content: string };
type Acceptance = { document_id: string; sha256: string; accepted_at: string; email: string; email_status?: string; code: string; evidence?: string };
const contractPdf = (id: string) => `/api/v1/company/contract/documents/${id}/pdf`;
const errorMessage = (e: unknown) => e instanceof Error ? e.message : "Não foi possível concluir a operação.";

function ContractWizard({ user }: { user: User }) {
  const cache = useQueryClient();
  const company = useQuery({ queryKey: ["company"], queryFn: () => api<Company>("/company") });
  const [document, setDocument] = useState<Document | null>(null);
  const [reading, setReading] = useState(false), [read, setRead] = useState(false), [sent, setSent] = useState(false);
  const [agreed, setAgreed] = useState(false), [code, setCode] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [email, setEmail] = useState(user.email);
  const data = () => ({ document_id: document!.id, sha256: document!.sha256 });
  async function generate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!company.data) return;
    setBusy(true); setError("");
    const form = new FormData(e.currentTarget);
    try {
      const c = company.data;
      await api("/company", { method: "PATCH", body: JSON.stringify({ trade_name: c.trade_name, corporate_name: c.corporate_name, cnpj: c.cnpj, contact_phone: c.contact_phone, primary_color: c.primary_color, accent_color: c.accent_color, ...addressPayload(form) }) });
      const prepared = await api<Document>("/company/contract/prepare", { method: "POST", body: JSON.stringify({ representative_name: form.get("representative_name"), representative_cpf: form.get("representative_cpf"), representative_role: form.get("representative_role"), authority: form.get("authority") === "on" }) });
      setDocument(prepared); setRead(false); setSent(false); setAgreed(false); setCode("");
      await cache.invalidateQueries({ queryKey: ["company"] });
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  async function open() {
    setBusy(true); setError("");
    try { await api("/company/contract/viewed", { method: "POST", body: JSON.stringify(data()) }); setRead(true); setReading(true); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  async function sendCode() {
    setBusy(true); setError("");
    try { const result = await api<{ email: string }>("/company/contract/code", { method: "POST", body: JSON.stringify(data()) }); setSent(true); setEmail(result.email); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  async function accept() {
    setBusy(true); setError("");
    try {
      await api("/company/contract/accept", { method: "POST", body: JSON.stringify({ ...data(), code, accepted: agreed }) });
      await cache.invalidateQueries({ queryKey: ["contract"] });
      await cache.invalidateQueries({ queryKey: ["session"] });
      await cache.invalidateQueries({ queryKey: ["company"] });
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <section className="operation-card modal-form">
    <h2>Leia e aceite o contrato de utilização</h2>
    <p>Confira os dados da empresa e do representante. Você poderá ler o texto integral e baixar o PDF antes de aceitar. O aceite será confirmado pelo e-mail do seu acesso.</p>
    {company.error && <Alert>{errorMessage(company.error)}</Alert>}
    {error && <Alert>{error}</Alert>}
    {company.data && !document && <form className="modal-form" onSubmit={generate}>
      <p><strong>{company.data.corporate_name}</strong> · CPF/CNPJ: {company.data.cnpj} · E-mail: {user.email}</p>
      <p className="muted">Se a razão social, documento ou e-mail estiver incorreto, solicite a correção à Nexus antes do aceite.</p>
      <AddressFields company={company.data} />
      <div className="form-grid">
        <Field label="Nome do representante"><input name="representative_name" defaultValue={user.full_name} required minLength={3} maxLength={150} /></Field>
        <Field label="CPF do representante"><input name="representative_cpf" required inputMode="numeric" maxLength={20} /></Field>
        <Field label="Função do representante"><input name="representative_role" required minLength={2} maxLength={80} /></Field>
      </div>
      <label className="operation-checkbox"><input type="checkbox" name="authority" required />Declaro que tenho poderes para representar esta empresa.</label>
      <button className="button primary" disabled={busy}>{busy ? "Preparando…" : "Conferir dados e preparar contrato"}</button>
    </form>}
    {document && <div className="modal-form">
      <div className="row-actions"><button className="button primary" onClick={open} disabled={busy}>Ler contrato completo</button><a className="button secondary" href={contractPdf(document.id)} download>Baixar PDF antes de aceitar</a><button className="text-button" onClick={() => { setDocument(null); setRead(false); setSent(false); }}>Corrigir dados e gerar nova cópia</button></div>
      <p className="muted">SHA-256 desta cópia: <code className="contract-hash">{document.sha256}</code></p>
      {!read && <p>Abra o contrato completo antes de solicitar o código e registrar seu aceite.</p>}
      <button type="button" className="button secondary" onClick={sendCode} disabled={busy || !read}>{sent ? "Reenviar código por e-mail" : "Enviar código de confirmação por e-mail"}</button>
      {sent && <><p>Código encaminhado para envio a <strong>{email}</strong>. Validade de dez minutos; confira também o spam.</p><Field label="Código recebido por e-mail"><input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} autoComplete="one-time-code" inputMode="numeric" maxLength={6} /></Field></>}
      <label className="operation-checkbox"><input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} disabled={!read} />Li e aceito o contrato integral apresentado e declaro poderes para representar a empresa.</label>
      <button className="button primary" type="button" onClick={accept} disabled={busy || !read || !sent || !agreed || code.length !== 6}>{busy ? "Confirmando…" : "Confirmar aceite do contrato"}</button>
      <p className="muted">A cópia aceita e o comprovante serão enviados ao e-mail confirmado e ficarão disponíveis em Meu contrato.</p>
    </div>}
    {reading && document && <Modal title="Contrato de utilização — leitura integral" onClose={() => setReading(false)} wide><div className="modal-form"><article className="contract-text" aria-label="Texto integral do contrato">{document.content}</article><a className="button secondary" href={contractPdf(document.id)} download>Baixar este contrato em PDF</a><button type="button" className="button primary" onClick={() => setReading(false)}>Voltar para confirmar o aceite</button></div></Modal>}
  </section>;
}

export function ContractGate({ user, onLogout }: { user: User; onLogout: () => void }) {
  return <main className="contract-gate"><header className="row-actions"><h1>Contrato de utilização Nexus Rotafy</h1><button className="button secondary" onClick={async () => { await api("/auth/logout", { method: "POST" }); onLogout(); }}>Sair da conta</button></header>
    {user.role === "admin" ? <><ContractWizard user={user} /><details><summary>Consultar Financeiro da empresa</summary><Collections nexus={false} /></details></> : <Alert>O representante da empresa deve concluir o aceite do contrato no primeiro acesso de um administrador. Entre em contato com o responsável.</Alert>}
  </main>;
}

export function CompanyContract() {
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["contract"], queryFn: () => api<{ required: boolean; pending: boolean; acceptance: Acceptance | null }>("/company/contract"), refetchInterval: 15000 });
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const a = query.data?.acceptance;
  return <section className="operation-card modal-form"><h2>Meu contrato</h2>{query.isPending && <p>Consultando contrato…</p>}{(error || query.error) && <Alert>{error || errorMessage(query.error)}</Alert>}
    {a ? <><p>Contrato aceito em {new Date(a.accepted_at).toLocaleString("pt-BR")} · Versão {a.code}</p><p>SHA-256: <code className="contract-hash">{a.sha256}</code></p><p>Cópia para {a.email} · {a.email_status === "sent" ? "Envio aceito pelo provedor de e-mail" : a.email_status === "failed" ? "Falha no envio — solicite reenvio" : "Envio pendente"}</p><div className="row-actions"><a className="button primary" href={contractPdf(a.document_id)} download>Baixar contrato aceito</a><a className="button secondary" href="/api/v1/company/contract/receipt" download>Baixar comprovante do aceite</a><button className="button secondary" disabled={busy} onClick={async () => { setBusy(true); setError(""); try { await api("/company/contract/resend", { method: "POST" }); await cache.invalidateQueries({ queryKey: ["contract"] }); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }}>Reenviar cópia ao e-mail do aceite</button></div><p className="muted">Alterações cadastrais posteriores não modificam este documento.</p></> : query.data && <p>{query.data.pending ? "O aceite está pendente no primeiro acesso do representante." : "Não há aceite eletrônico exigido para este cadastro anterior à ativação. Nenhum aceite retroativo foi criado."}</p>}
  </section>;
}

type Version = { id: string; code: string; title: string; body: string; sha256: string; status: string };
export function NexusContracts() {
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["contract-versions"], queryFn: () => api<{ active_version_id: string | null; versions: Version[] }>("/nexus/contracts") });
  const [approved, setApproved] = useState<string | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  return <section className="operation-card modal-form"><h2>Contrato de utilização</h2><p>A publicação ativa o aceite somente para empresas cadastradas depois dela. Empresas anteriores não recebem aceite retroativo. Revise o texto comercial e jurídico antes de publicar. Versões publicadas não podem ser alteradas.</p>{!query.data?.active_version_id && <p className="reservation-suggestion">Nenhuma versão ativa: a minuta está em revisão e não está sendo apresentada aos clientes para aceite.</p>}
    {(error || query.error) && <Alert>{error || errorMessage(query.error)}</Alert>}
    {query.data?.versions?.map((v) => <article className="package-route-card modal-form" key={v.id}><h3>{v.title} · {v.code}</h3><p>{v.status === "published" ? "Publicada" : "Rascunho para aprovação"}{query.data.active_version_id === v.id ? " · versão ativa para novos cadastros" : ""}</p><details><summary>Ler texto integral desta versão</summary><div className="contract-text">{v.body}</div></details><code className="contract-hash">SHA-256 do texto: {v.sha256}</code>{v.status === "draft" && <><label className="operation-checkbox"><input type="checkbox" checked={approved === v.id} onChange={(e) => setApproved(e.target.checked ? v.id : null)} />Revisei e aprovo este texto para novos contratos.</label><button className="button primary" disabled={approved !== v.id || busy} onClick={async () => { if (!window.confirm("Publicar esta versão aprovada e exigir o aceite para os próximos cadastros?")) return; setBusy(true); setError(""); try { await api(`/nexus/contracts/${v.id}/publish`, { method: "POST", body: JSON.stringify({ sha256: v.sha256, approved: true }) }); await cache.invalidateQueries({ queryKey: ["contract-versions"] }); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }}>Publicar versão aprovada</button></>}</article>)}
    <details><summary>Preparar nova versão em rascunho</summary><form className="modal-form" onSubmit={async (e) => { e.preventDefault(); const form = new FormData(e.currentTarget); setBusy(true); setError(""); try { await api("/nexus/contracts", { method: "POST", body: JSON.stringify(Object.fromEntries(form)) }); await cache.invalidateQueries({ queryKey: ["contract-versions"] }); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }}><Field label="Identificação da versão"><input name="code" required maxLength={50} pattern="[A-Za-z0-9.-]+" placeholder="2026-10-21-r2" /></Field><Field label="Título do contrato"><input name="title" defaultValue="Contrato de utilização Nexus Rotafy" required maxLength={200} /></Field><Field label="Texto integral da nova versão"><textarea name="body" defaultValue={query.data?.versions?.[0]?.body || ""} required minLength={100} maxLength={100000} rows={18} /></Field><button className="button secondary" disabled={busy}>Salvar nova versão como rascunho</button></form></details>
  </section>;
}

export function NexusCompanyContract({ company, onClose }: { company: Company; onClose: () => void }) {
  const query = useQuery({ queryKey: ["company-contract", company.id], queryFn: () => api<{ acceptance: Acceptance | null; pending: boolean }>(`/nexus/companies/${company.id}/contract`) });
  const a = query.data?.acceptance;
  return <Modal title={`Contrato · ${company.trade_name}`} onClose={onClose} wide><div className="modal-form">{query.error && <Alert>{errorMessage(query.error)}</Alert>}{a ? <><p>Aceito em {new Date(a.accepted_at).toLocaleString("pt-BR")} · {a.email} · Versão {a.code}</p><code className="contract-hash">SHA-256: {a.sha256}</code><a className="button primary" href={`/api/v1/nexus/companies/${company.id}/contract/pdf`} download>Baixar cópia preservada do contrato</a><a className="button secondary" href={`/api/v1/nexus/companies/${company.id}/contract/receipt`} download>Baixar comprovante do aceite</a><details><summary>Dados registrados no aceite</summary><pre className="contract-text">{a.evidence ? JSON.stringify(JSON.parse(a.evidence), null, 2) : ""}</pre></details></> : query.data ? <p>{query.data.pending ? "Aguardando o aceite do representante no primeiro acesso." : "Aceite não exigido para este cadastro. Nenhum aceite retroativo criado."}</p> : <p>Consultando…</p>}</div></Modal>;
}
