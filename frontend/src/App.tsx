import { Reaccommodations } from "./Reaccommodations";
import { DataUseNotice } from "./components/DataUseNotice";
import { MobileRelease } from "./MobileRelease";
import { CompanyModules } from "./CompanyModules";
import { PartnerIntegration } from "./PartnerIntegration";
import { hasModule, menuModule } from "./modules";
import { Tracking } from "./Tracking";
import { EditCollaborator } from "./EditCollaborator";
import { CompanyAccess } from "./CompanyAccess";
import { CompanyWhatsApp } from "./CompanyWhatsApp";
import { WhatsAppChat } from "./WhatsAppChat";
import { Nps } from "./Nps";
import { BusinessHours } from "./BusinessHours";
import { NpsQualityAlert } from "./NpsQuality";
import { WhatsAppHandoffAlert, type Handoff } from "./WhatsAppHandoffAlert";
import { NexusWhatsApp } from "./NexusWhatsApp";
import { BillingUpcoming } from "./BillingUpcoming";
import { AddressFields, addressPayload } from "./CompanyAddress";
import { CompanyContract, PlanChangeNotice, ContractGate, NexusContracts, NexusCompanyContract } from "./Contracts";
import { Collections } from "./Collections";
import { PaymentReturn } from "./PaymentReturn";
import { PasswordInput } from "./components/PasswordInput";
import { useEffect, useState, lazy, Suspense, type FormEvent } from "react";
import { NexusTeam } from "./NexusTeam";
import { Billing } from "./billing/Billing";
import { money, type Plan } from "./billing/types";
import { Sales } from "./Sales";
import { IntegrationSettings } from "./IntegrationSettings";
import { LegalPage } from "./Privacy";
import { Documentation } from "./Documentation";
import { TicketSales } from "./TicketSales";
import { Reports } from "./Reports";
import { DocumentInput } from "./components/DocumentInput";
import { PhoneInput } from "./components/PhoneInput";
import {
  ProfileField,
  profileName,
  companyCapabilities,
} from "./operationalProfiles";
import {
  ForgotPassword,
  EmailDeliveries,
  InvitationModal,
} from "./AccessEmail";
import { TicketPage } from "./Tickets";
const OfflineHub = lazy(() =>
  import("./offline/OfflineHub").then((module) => ({
    default: module.OfflineHub,
  })),
);
import { RouteCatalog } from "./RouteCatalog";
import { Operations } from "./Operations";
import { PublicBooking, TrackingPage } from "./PublicBooking";
import "./operations.css";
import { Alert, Modal, Field } from "./components/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  ChartColumn,
  CreditCard,
  Check,
  ChevronRight,
  CircleCheck,
  Compass,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Phone,
  Route,
  Search,
  ShieldCheck,
  Users,
  BookOpen,
  Ticket,
} from "lucide-react";
import {
  api,
  ApiError,
  patch,
  post,
  roleName,
  type AuditEvent,
  type Company,
  type Role,
  type User,
} from "./api";

// Visibilidade temporária; preserva o módulo para reativação futura.
const SHOW_PUBLIC_SALES_MENU = false;

const message = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Não foi possível concluir a operação.";
const date = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
const initials = (name: string) =>
  name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();

function Logo({ light = false }: { light?: boolean }) {
  return (
    <div className={`logo ${light ? "light" : ""}`}>
      <span className="logo-mark">
        <Route size={24} />
      </span>
      <span>
        <b>
          rotafy<span className="logo-dot">.</span>
        </b>
        <small>NEXUS</small>
      </span>
    </div>
  );
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const isNexus = window.location.pathname.startsWith("/nexus");
  const [forgot, setForgot] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const data = new FormData(event.currentTarget);
    try {
      const { activateOfflineUser, withOfflineLock } =
        await import("./offline/store");
      const user = await withOfflineLock(async () => {
        const result = await post<User>(
          isNexus ? "/auth/nexus/login" : "/auth/login",
          {
            email: data.get("email"),
            password: data.get("password"),
            ...(isNexus ? {} : { company: data.get("company") }),
          },
        );
        try {
          await activateOfflineUser(result);
        } catch (e) {
          await post("/auth/logout", {});
          throw e;
        }
        return result;
      });
      onLogin(user);
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  return (
    <main className="login-layout">
      <section className="login-story">
        <Logo light />
        <div className="story-body">
          <span className="eyebrow">
            <span className="live-dot" /> CADA VIAGEM, BEM ORGANIZADA
          </span>
          <h1>
            Uma operação
            <br />
            mais tranquila.
            <br />
            <em>Do início ao destino.</em>
          </h1>
          <p>Sua equipe, seus passageiros e suas viagens no mesmo lugar.</p>
          <div className="route-illustration" aria-hidden="true">
            <div className="route-node">
              <Building2 size={20} />
              <span>Sua empresa</span>
            </div>
            <div className="route-line">
              <span />
              <span />
              <span />
            </div>
            <div className="route-node destination">
              <Compass size={22} />
              <span>Próximo destino</span>
            </div>
          </div>
        </div>
        <footer>
          Nexus Rotafy <span>Gestão que acompanha você.</span>
        </footer>
      </section>
      <section className="login-form-side">
        <div className="mobile-logo">
          <Logo />
        </div>
        <div className="login-form">
          <span className="section-kicker">
            {isNexus ? "ADMINISTRAÇÃO DA PLATAFORMA" : "PORTAL DA EMPRESA"}
          </span>
          <h2>Bem-vindo de volta</h2>
          <p className="muted">
            {isNexus
              ? "Entre para administrar as empresas da Nexus."
              : "Entre para acessar o espaço da sua empresa."}
          </p>
          <form onSubmit={submit}>
            <DataUseNotice />
            {!isNexus && (
              <Field label="Identificador da empresa">
                <input
                  name="company"
                  defaultValue={
                    new URLSearchParams(window.location.search).get(
                      "empresa",
                    ) || ""
                  }
                  autoComplete="organization"
                  placeholder="Ex.: receptivo-sul"
                  required
                  pattern="[a-z0-9]+(-[a-z0-9]+)*"
                  maxLength={50}
                />
              </Field>
            )}
            <Field label="E-mail">
              <input
                name="email"
                type="email"
                autoComplete="username"
                placeholder="voce@empresa.com.br"
                required
                maxLength={254}
              />
            </Field>
            <Field label="Senha">
              <PasswordInput
                name="password"
                autoComplete="current-password"
                placeholder="Sua senha"
                required
                maxLength={128}
              />
            </Field>
            {error && <Alert>{error}</Alert>}
            <button className="button primary full" disabled={pending}>
              {pending ? "Entrando…" : "Acessar painel"}
              <ArrowRight size={18} />
            </button>
            <a className="button secondary full" href="/offline" target="_blank" rel="noopener noreferrer">
              Abrir operação offline preparada
            </a>
          </form>
          <button
            className="text-button login-help"
            onClick={() => setForgot(true)}
          >
            <KeyRound size={15} /> Esqueci minha senha
          </button>
          <a className="portal-link" href="/ajuda" target="_blank" rel="noopener noreferrer">
            <BookOpen size={15} /> Manual e apresentação
          </a>
          <a className="portal-link" href={isNexus ? "/" : "/nexus"}>
            {isNexus ? "Acessar portal da empresa" : "Administração Nexus"}
            <ChevronRight size={15} />
          </a>
        </div>
        <div id="login-privacy" />
        <footer className="login-footer">
          <ShieldCheck size={16} /> Acesso exclusivo à sua operação
        </footer>
      </section>
      {forgot && (
        <ForgotPassword nexus={isNexus} onClose={() => setForgot(false)} />
      )}
    </main>
  );
}

function Reset() {
  const token =
    new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (data.get("password") !== data.get("confirm")) {
      setError("As senhas precisam ser iguais.");
      return;
    }
    setPending(true);
    setError("");
    try {
      await post("/auth/reset-password", {
        token,
        new_password: data.get("password"),
      });
      setDone(true);
      history.replaceState(null, "", "/redefinir");
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  return (
    <main className="reset-layout">
      <div className="reset-card">
        <Logo />
        <h1>Redefinir senha</h1>
        {done ? (
          <>
            <p>Sua senha foi alterada. Entre novamente na sua empresa.</p>
            <a className="button primary" href="/">
              Ir para o login
            </a>
          </>
        ) : !token ? (
          <Alert>
            Solicite um link válido ao administrador da sua empresa.
          </Alert>
        ) : (
          <form onSubmit={submit}>
            <DataUseNotice />
            <p className="muted">
              Escolha uma senha com pelo menos 8 caracteres, incluindo uma letra
              maiúscula e um caractere especial.
            </p>
            <Field label="Nova senha">
              <PasswordInput
                name="password"
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                required
              />
            </Field>
            <Field label="Confirmar senha">
              <PasswordInput
                name="confirm"
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                required
              />
            </Field>
            {error && <Alert>{error}</Alert>}
            <button className="button primary full" disabled={pending}>
              {pending ? "Salvando…" : "Salvar nova senha"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}

function CreateCompany({
  onClose,
  restricted = false,
}: {
  onClose: () => void;
  restricted?: boolean;
}) {
  const client = useQueryClient();
  const plans = useQuery({
    queryKey: restricted ? ["signup", "plans"] : ["billing", "plans"],
    queryFn: () => api<Plan[]>(restricted ? "/public/plans" : "/nexus/plans"),
  });
  const [created, setCreated] = useState<
    (Company & { admin_email?: string }) | null
  >(null);
  const availablePlans = (plans.data || []).filter(
    (plan) => plan.is_active && plan.version_id,
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await post<Company>("/nexus/companies", {
        ...addressPayload(data),
        trade_name: data.get("trade_name"),
        corporate_name: data.get("corporate_name"),
        slug: data.get("slug"),
        cnpj: String(data.get("cnpj") || "").trim() || null,
        contact_phone: String(data.get("contact_phone") || "").trim() || null,
        plan_id: data.get("plan_id"),
        operational_profile: data.get("operational_profile"),
        admin: {
          full_name: data.get("full_name"),
          email: data.get("email"),
          password: data.get("password"),
          role: "admin",
        },
      });
      await client.invalidateQueries({ queryKey: ["companies"] });
      await client.invalidateQueries({ queryKey: ["billing"] });
      setCreated({ ...result, admin_email: String(data.get("email") || "") });
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  if (created) return <CompanyAccess company={created} onClose={onClose} />;
  return (
    <Modal title="Cadastrar empresa" onClose={onClose} wide>
      <form onSubmit={submit} className="modal-form">
        <DataUseNotice />
        <p className="muted">
          Crie o espaço da empresa e seu primeiro administrador. Escolha o plano
          conforme as condições de contratação e teste configuradas. O CPF/CNPJ
          é obrigatório para cobrança. Preencha todos os campos obrigatórios;
          o complemento do endereço é opcional.
        </p>
        <div className="form-grid">
          <Field label="Nome comercial">
            <input name="trade_name" required minLength={2} maxLength={150} />
          </Field>
          <Field label="Razão social">
            <input
              name="corporate_name"
              required
              minLength={2}
              maxLength={150}
            />
          </Field>
          <Field label="Identificador de acesso">
            <input
              name="slug"
              placeholder="receptivosul"
              required
              pattern="[a-z0-9]+"
              title="Use somente letras minúsculas sem acentos e números, de 2 a 50 caracteres. Não use espaços, sublinhado, hífen ou outros caracteres especiais."
              aria-describedby="company-slug-help"
              aria-label="Identificador de acesso"
              minLength={2}
              maxLength={50}
            />
            <small id="company-slug-help" className="muted">
              Use somente letras minúsculas sem acentos e números (2 a 50
              caracteres). Não use espaços, sublinhado (_), hífen (-) ou outros
              caracteres especiais. Exemplo: receptivosul.
            </small>
          </Field>
          <Field label="CPF/CNPJ">
            <DocumentInput required />
            <small id="document-help" className="muted">
              CPF: 11 dígitos. CNPJ: 14 caracteres. A máscara não substitui a
              conferência dos dígitos verificadores.
            </small>
          </Field>
          <div className="company-contact">
            <Field label="Telefone / WhatsApp">
              <PhoneInput required />
              <small className="muted">
                Contato da empresa. Use DDD ou + e código do país.
              </small>
            </Field>
          </div>
        </div>
        <AddressFields />
        <h3 className="form-section">Tipo de operação</h3>
        <p className="muted">O representante da empresa poderá ler e baixar o contrato antes de aceitar no primeiro acesso. O aceite não pode ser marcado pela equipe Nexus.</p>
        <ProfileField />
        <h3 className="form-section">Plano da empresa</h3>
        <Field label="Plano escolhido">
          <select
            name="plan_id"
            required
            defaultValue=""
            disabled={plans.isPending || availablePlans.length === 0}
          >
            <option value="" disabled>
              Selecione um plano
            </option>
            {availablePlans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name} · {money(plan.price_cents!)} / mês ·{" "}
                {plan.included_trips} viagens · extra{" "}
                {money(plan.extra_trip_cents!)}
              </option>
            ))}
          </select>
        </Field>
        {plans.error && <Alert>{message(plans.error)}</Alert>}
        {!plans.isPending && !plans.error && availablePlans.length === 0 && (
          <Alert>
            Configure e ative um plano em Planos e assinaturas antes de
            cadastrar uma empresa.
          </Alert>
        )}
        <h3 className="form-section">Administrador da empresa</h3>
        <div className="form-grid">
          <Field label="Nome completo">
            <input name="full_name" required minLength={2} maxLength={150} />
          </Field>
          <Field label="E-mail">
            <input name="email" type="email" autoComplete="off" required />
          </Field>
          <Field label="Senha inicial">
            <PasswordInput
              name="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
            />
          </Field>
        </div>
        <small className="muted">
          Mínimo de 8 caracteres, com uma letra maiúscula e um caractere
          especial. Compartilhe o acesso por um canal seguro.
        </small>
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button
            className="button primary"
            disabled={pending || plans.isPending || availablePlans.length === 0}
          >
            {pending ? "Cadastrando…" : "Cadastrar empresa"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function EditCompany({
  company,
  onClose,
}: {
  company: Company;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await patch(`/nexus/companies/${company.id}/details`, {
        ...addressPayload(form),
        trade_name: form.get("trade_name"),
        corporate_name: form.get("corporate_name"),
        slug: form.get("slug"),
        cnpj: String(form.get("cnpj") || "").trim() || null,
        contact_phone: String(form.get("contact_phone") || "").trim() || null,
        operational_profile: form.get("operational_profile"),
        expected_profile: company.operational_profile || "tourism",
      });
      await client.invalidateQueries({ queryKey: ["companies"] });
      await client.invalidateQueries({ queryKey: ["audit"] });
      onClose();
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Editar empresa" onClose={onClose} wide>
      <form className="modal-form" onSubmit={submit}>
        <DataUseNotice />
        <p className="muted">
          Ao alterar o identificador de acesso, informe o novo identificador à
          equipe e atualize os links públicos da empresa.
        </p>
        <div className="form-grid">
          <Field label="Nome comercial">
            <input
              name="trade_name"
              defaultValue={company.trade_name}
              required
              minLength={2}
              maxLength={150}
            />
          </Field>
          <Field label="Razão social">
            <input
              name="corporate_name"
              defaultValue={company.corporate_name}
              required
              minLength={2}
              maxLength={150}
            />
          </Field>
          <Field label="Identificador de acesso">
            <input
              name="slug"
              defaultValue={company.slug}
              required
              minLength={2}
              maxLength={50}
              pattern={`[a-z0-9]+|${company.slug}`}
              title="Para alterar, use somente letras minúsculas sem acentos e números, sem espaços ou caracteres especiais."
              aria-describedby="company-edit-slug-help"
              aria-label="Identificador de acesso"
            />
            <small id="company-edit-slug-help" className="muted">
              Para alterar, use somente letras minúsculas sem acentos e números
              (2 a 50 caracteres), sem espaços, sublinhado (_), hífen (-) ou
              outros caracteres especiais.
            </small>
          </Field>
          <Field label="CPF/CNPJ">
            <DocumentInput initialValue={company.cnpj || ""} required />
            <small id="document-help" className="muted">
              Informe um CPF ou CNPJ válido para cobrança.
            </small>
          </Field>
          <Field label="Telefone / WhatsApp">
            <PhoneInput initialValue={company.contact_phone || ""} />
            <small className="muted">
              Contato da empresa com DDD ou código internacional.
            </small>
          </Field>
        </div>
        <AddressFields company={company} required={false} />
        <ProfileField
          initial={company.operational_profile || "tourism"}
          editing
        />
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={pending}>
            {pending ? "Salvando…" : "Salvar empresa"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function CreateUser({ onClose }: { onClose: () => void }) {
  const [invitation, setInvitation] = useState(false);
  const [channel, setChannel] = useState("email");
  const client = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (invitation) {
        delete data.password;
        data.channel = channel;
      }
      await post(invitation ? "/users/invitations" : "/users", data);
      await client.invalidateQueries({ queryKey: ["users"] });
      onClose();
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Adicionar à equipe" onClose={onClose}>
      <form className="modal-form" onSubmit={submit}>
        <DataUseNotice />
        <Field label="Nome completo">
          <input name="full_name" minLength={2} maxLength={150} required />
        </Field>
        <Field label="E-mail">
          <input name="email" type="email" required />
        </Field>
        <Field label="Telefone/WhatsApp do colaborador">
          <PhoneInput required={invitation && channel !== "email"} />
        </Field>
        <Field label="Perfil">
          <select name="role" defaultValue="attendant">
            {Object.entries(roleName)
              .filter(([role]) => role !== "nexus" && role !== "nexus_staff")
              .map(([role, name]) => (
                <option key={role} value={role}>
                  {name}
                </option>
              ))}
          </select>
        </Field>
        <label>
          <input
            type="checkbox"
            checked={invitation}
            onChange={(e) => setInvitation(e.target.checked)}
          />{" "}
          Enviar convite para a pessoa definir sua senha
        </label>
        {invitation && (
          <Field label="Enviar convite por">
            <select
              value={channel}
              onChange={(event) => setChannel(event.target.value)}
            >
              <option value="email">E-mail</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="both">E-mail e WhatsApp</option>
            </select>
          </Field>
        )}
        {!invitation && (
          <Field label="Senha inicial">
            <PasswordInput
              name="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
            />
          </Field>
        )}
        <small className="muted">
          {invitation
            ? "Convite válido por 24 horas. A pessoa define sua própria senha."
            : "Mínimo de 8 caracteres, com uma letra maiúscula e um caractere especial."}
        </small>
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={pending}>
            {pending ? "Salvando…" : "Adicionar pessoa"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function PasswordModal({
  onClose,
  onLogout,
}: {
  onClose: () => void;
  onLogout: () => void;
}) {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(event.currentTarget);
    if (data.get("new_password") !== data.get("confirm")) {
      setError("As senhas precisam ser iguais.");
      setPending(false);
      return;
    }
    try {
      await post("/auth/password", {
        current_password: data.get("current_password"),
        new_password: data.get("new_password"),
      });
      onLogout();
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Alterar minha senha" onClose={onClose}>
      <form className="modal-form" onSubmit={submit}>
        <DataUseNotice />
        <p className="muted">
          Após a alteração, entre novamente. Suas outras sessões também serão
          encerradas.
        </p>
        <Field label="Senha atual">
          <PasswordInput
            name="current_password"
            autoComplete="current-password"
            required
            maxLength={128}
          />
        </Field>
        <Field label="Nova senha">
          <PasswordInput
            name="new_password"
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
          />
        </Field>
        <Field label="Confirmar nova senha">
          <PasswordInput
            name="confirm"
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
          />
        </Field>
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={pending}>
            {pending ? "Salvando…" : "Alterar senha"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

const actionNames: Record<string, string> = {
  "auth.login": "Acesso realizado",
  "auth.logout": "Sessão encerrada",
  "company.branding_updated": "Identidade da empresa atualizada",
  "company.created": "Empresa cadastrada",
  "company.access_sent": "Envio dos dados de acesso solicitado",
  "company.updated": "Dados da empresa atualizados",
  "company.activated": "Empresa ativada",
  "company.suspended": "Empresa suspensa",
  "user.created": "Pessoa adicionada à equipe",
  "user.updated": "Cadastro da equipe atualizado",
  "auth.reset_issued": "Link de recuperação emitido",
  "auth.reset_email_queued": "Recuperação por e-mail solicitada",
  "user.invited": "Pessoa convidada para definir senha",
  "user.invitation_resent": "Convite de acesso reenviado",
  "trip.updated": "Viagem atualizada",
  "reservation.updated": "Reserva atualizada",
  "auth.password_changed": "Senha alterada",
  "auth.password_reset": "Senha redefinida",
  "plan.created": "Plano cadastrado",
  "plan.version_published": "Condições de plano publicadas",
  "plan.activated": "Plano ativado",
  "plan.archived": "Plano arquivado",
  "subscription.created": "Assinatura vinculada à empresa",
  "subscription.plan_scheduled": "Alteração de plano agendada",
  "subscription.plan_unscheduled": "Alteração de plano desmarcada",
  "subscription.cancelled": "Assinatura encerrada",
  "vehicles.created": "Veículo cadastrado",
  "vehicles.updated": "Veículo atualizado",
  "packages.created": "Pacote cadastrado",
  "packages.updated": "Pacote atualizado",
  "trip.created": "Viagem criada",
  "trip.in_progress": "Viagem iniciada",
  "trip.completed": "Viagem concluída",
  "trip.cancelled": "Viagem cancelada e consumo estornado",
  "reservation.created": "Reserva familiar criada",
  "trip.published": "Viagem publicada na página pública",
  "trip.routes_refreshed": "Rotas da viagem atualizadas com o catálogo atual",
  "integrations.configured": "Configuração das integrações atualizada",
  "whatsapp.session_configured": "Sessão WhatsApp da empresa configurada",
  "whatsapp.connection_requested":
    "Conexão do WhatsApp solicitada pelo administrador",
  "whatsapp.connection_paused":
    "Tentativas de conexão do WhatsApp interrompidas",
  "whatsapp.disconnect_requested": "Desconexão do WhatsApp solicitada",
  "whatsapp.disconnected": "WhatsApp desconectado",
  "whatsapp.queued": "Mensagem WhatsApp adicionada à fila",
  "whatsapp.chat_queued": "Mensagem de atendimento WhatsApp adicionada à fila",
  "whatsapp.automation_updated": "Automações WhatsApp atualizadas",
  "nps.settings_updated": "Configuração das pesquisas NPS atualizada",
  "whatsapp.hours_updated": "Horários de atendimento atualizados",
  "nps.quality_reviewed": "Avaliação NPS analisada pela equipe de qualidade",
  "whatsapp.handoff_closed": "Atendimento humano WhatsApp concluído",
  "whatsapp.nexus_reconnect_requested": "Nexus solicitou reconexão do WhatsApp",
  "whatsapp.nexus_restart_requested": "Nexus solicitou reinício da sessão WhatsApp",
  "whatsapp.nexus_disconnect_requested": "Nexus solicitou desconexão do WhatsApp",
  "trip.unpublished": "Viagem retirada da página pública",
  "reservation.paid": "Reserva marcada PAGO",
  "reservation.unpaid": "Marcação PAGO removida",
  "reservation.tracking_issued": "Link privado de acompanhamento gerado",
  "reservation.tracking_revoked": "Link privado de acompanhamento revogado",
  "availability.unavailable": "Falta de lugares informada pela família",
  "availability.acknowledged": "Alerta de disponibilidade visto",
  "integration.key_created": "Chave de integração criada",
  "integration.key_revoked": "Chave de integração revogada",
  "integration.service_key_created": "Chave operacional de integração criada",
  "integration.service_key_revoked": "Chave operacional de integração revogada",
  "company.modules_updated": "Módulos da empresa atualizados",
  "company.logo_updated": "Logo enviado",
  "company.logo_removed": "Logo removido",
  "ticket.issued": "Bilhete individual emitido ou reemitido",
  "ticket.revoked": "Bilhete individual revogado",
  "boarding.board": "Embarque registrado",
  "boarding.disembark": "Desembarque registrado",
  "boarding.reverse": "Presença revertida",
  "reservation.confirmed": "Reserva confirmada",
  "reservation.cancelled": "Reserva cancelada",
  "reservation.cancelled_with_trip": "Reserva cancelada com a viagem",
  "reservation.expired": "Bloqueio de lugares expirado",
  "reservation.reallocated": "Família realocada para outro veículo",
  "reservation_import.previewed": "Prévia de importação preparada",
  "reservation_import.applied": "Famílias importadas",
};

function BrandingModal({
  company,
  onClose,
}: {
  company: Company;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await patch(
        "/company",
        Object.fromEntries(new FormData(event.currentTarget)),
      );
      await client.invalidateQueries({ queryKey: ["company"] });
      await client.invalidateQueries({ queryKey: ["company-whatsapp"] });
      await client.invalidateQueries({ queryKey: ["audit"] });
      onClose();
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Cadastro da empresa" onClose={onClose} wide>
      <form className="modal-form" onSubmit={submit}>
        <DataUseNotice />
        <Field label="Identificador de acesso">
          <input value={company.slug} readOnly />
        </Field>
        <Field label="Nome comercial">
          <input
            name="trade_name"
            defaultValue={company.trade_name}
            required
            minLength={2}
            maxLength={150}
          />
        </Field>
        <Field label="Razão social">
          <input
            name="corporate_name"
            defaultValue={company.corporate_name}
            required
            minLength={2}
            maxLength={150}
          />
        </Field>
        <div className="form-grid">
          <Field label="CPF/CNPJ">
            <DocumentInput initialValue={company.cnpj || ""} required />
          </Field>
          <Field label="Telefone/WhatsApp">
            <PhoneInput initialValue={company.contact_phone || ""} required />
          </Field>
        </div>
        <AddressFields company={company} required={false} />
        <p className="muted">Ao alterar o telefone, confira a conexão no menu WhatsApp. Os envios pelo número anterior serão suspensos.</p>
        <div className="form-grid">
          <Field label="Cor principal">
            <input
              name="primary_color"
              type="color"
              defaultValue={company.primary_color}
            />
          </Field>
          <Field label="Cor de destaque">
            <input
              name="accent_color"
              type="color"
              defaultValue={company.accent_color}
            />
          </Field>
        </div>
        {error && <Alert>{error}</Alert>}
        <footer className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={pending}>
            {pending ? "Salvando…" : "Salvar cadastro"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function Dashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  const client = useQueryClient();
  const isNexus = user.role === "nexus" || user.role === "nexus_staff";
  const fullNexus = user.role === "nexus";
  const isAdmin = user.role === "admin";
  const financialOnly = isAdmin && !!user.financial_blocked;
  const [requestedChat, setRequestedChat] = useState<Handoff | null>(null);
  const [operationModule, setOperationModule] = useState("trips");
  const [ticketSalesVisit, setTicketSalesVisit] = useState(0);
  const [reportTripId, setReportTripId] = useState<string | null>(null);
  const [page, setPage] = useState<
    | "overview"
    | "directory"
    | "audit"
    | "billing"
    | "operations"
    | "sales"
    | "routes"
    | "tracking"
    | "ticket-sales"
    | "reports"
    | "integrations"
    | "modules"
    | "collections"
    | "nexus-team"
    | "whatsapp"
    | "whatsapp-chat"
    | "nps"
    | "company-settings"
    | "whatsapp-connections"
    | "contract"
  >(financialOnly ? "collections" : isAdmin && new URLSearchParams(window.location.search).get("view") === "contract" ? "contract" : "overview");
  const [menu, setMenu] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editingCollaborator, setEditingCollaborator] = useState<User | null>(
    null,
  );
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [accessCompany, setAccessCompany] = useState<Company | null>(null);
  const [billingCompany, setBillingCompany] = useState("");
  const [companyPlanOnly, setCompanyPlanOnly] = useState(false);
  const [password, setPassword] = useState(false);
  const [brandingOpen, setBrandingOpen] = useState(false);
  const [contractCompany, setContractCompany] = useState<Company | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [resetLink, setResetLink] = useState("");
  const [deliveries, setDeliveries] = useState(false);
  const [invitingUser, setInvitingUser] = useState<User | null>(null);
  const [busyId, setBusyId] = useState("");
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => api<Company[]>("/nexus/companies"),
    enabled: isNexus,
  });
  const team = useQuery({
    queryKey: ["users"],
    queryFn: () => api<User[]>("/users"),
    enabled: isAdmin && !financialOnly && hasModule(user, "team"),
  });
  const company = useQuery({
    queryKey: ["company"],
    queryFn: () => api<Company>("/company"),
    enabled: !isNexus,
  });
  const audit = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<AuditEvent[]>("/audit"),
    enabled: isNexus || (isAdmin && !financialOnly),
  });
  const rows = isNexus ? companies.data || [] : team.data || [];
  const active = rows.filter((row) => row.is_active).length;
  const canManage = isNexus || (isAdmin && !financialOnly);
  const loading = isNexus
    ? companies.isPending
    : isAdmin
      ? hasModule(user, "team") && team.isPending
      : company.isPending;
  const queryError =
    companies.error || (!financialOnly && hasModule(user, "team") && team.error) || company.error || (!financialOnly && audit.error);
  useEffect(() => {
    if (!isNexus) {
      const id = page === "operations" && operationModule !== "trips" ? operationModule : page;
      if (menuModule[id] && !hasModule(user, menuModule[id])) setPage("overview");
      if (!hasModule(user, "team")) { setCreating(false); setEditingCollaborator(null); }
    }
  }, [isNexus, page, operationModule, user.enabled_modules]);
  useEffect(() => {
    if (financialOnly) {
      setPage("collections");
      setCreating(false);
      setBrandingOpen(false);
      setEditingCollaborator(null);
    }
  }, [financialOnly]);
  useEffect(() => {
    if (queryError instanceof ApiError && queryError.status === 401) onLogout();
  }, [queryError, onLogout]);
  async function toggle(row: Company | User) {
    const label = "trade_name" in row ? row.trade_name : row.full_name;
    if (
      !window.confirm(
        `${row.is_active ? "Suspender" : "Ativar"} o acesso de ${label}?`,
      )
    )
      return;
    setError("");
    setBusyId(row.id);
    try {
      await patch(isNexus ? `/nexus/companies/${row.id}` : `/users/${row.id}`, {
        is_active: !row.is_active,
      });
      await client.invalidateQueries();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusyId("");
    }
  }
  async function reset(id: string) {
    setError("");
    setBusyId(id);
    try {
      const result = await post<{ token: string }>(
        `/users/${id}/password-reset`,
        {},
      );
      setResetLink(
        `${window.location.origin}/redefinir#token=${encodeURIComponent(result.token)}`,
      );
      await client.invalidateQueries({ queryKey: ["audit"] });
    } catch (err) {
      setError(message(err));
    } finally {
      setBusyId("");
    }
  }
  async function logout() {
    try {
      const { clearOfflineCache } = await import("./offline/store");
      await clearOfflineCache();
      await post("/auth/logout", {});
      onLogout();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onLogout();
      else setError(message(err));
    }
  }
  const subtitle = isNexus
    ? "Administração Nexus"
    : company.data?.trade_name || "Sua empresa";
  const title =
    page === "company-settings" ? "Configurações da empresa" :
    page === "nps" ? "NPS e satisfação" :
    page === "whatsapp-chat" ? "Conversas WhatsApp" : page === "whatsapp-connections" ? "Conexões WhatsApp" : page === "modules" ? "Módulos por empresa" : page === "tracking" ? "Rastreamento" : page === "contract" ? "Meu contrato" : page === "whatsapp"
      ? "WhatsApp"
      : page === "nexus-team"
        ? "Equipe Nexus"
        : page === "collections"
          ? "Financeiro e cobranças"
          : page === "integrations"
            ? isNexus ? "Configurações" : "Integração com parceiros"
            : page === "routes"
              ? "Rotas"
              : page === "ticket-sales"
                ? "Vender bilhete"
                : page === "sales"
                  ? "Página pública e integrações"
                  : page === "reports"
                    ? "Relatórios"
                    : page === "operations"
                      ? {
                          vehicles: "Veículos",
                          trips: "Viagens",
                          packages: "Pacotes",
                          allocations: "Alocar veículos em viagens",
                          passengers: "Passageiros",
                        }[operationModule] || "Operação de viagens"
                      : page === "overview"
                        ? "Visão geral"
                        : page === "billing"
                          ? isNexus
                            ? companyPlanOnly
                              ? "Plano da empresa"
                              : "Planos e assinaturas"
                            : "Meu plano"
                          : page === "audit"
                            ? "Histórico de atividades"
                            : isNexus
                              ? "Empresas"
                              : "Equipe";
  function menuActive(id: string) {
    if (page === "operations")
      return id === "operations"
        ? operationModule === "trips"
        : id === operationModule;
    return page === id;
  }
  const companyMenuOrder = [
    "overview",
    "directory",
    "vehicles",
    "routes",
    "packages",
    "operations",
    "tracking",
    "ticket-sales",
    "allocations",
    "passengers",
    "sales",
    "reports",
    "collections",
    "billing",
    "whatsapp",
    "whatsapp-chat",
    "nps",
    "company-settings",
    "integrations",
    "contract",
    "audit",
  ];
  return (
    <div className="app-layout">
      <a className="skip-link" href="#main-content">
        Ir para o conteúdo
      </a>
      {menu && (
        <button
          className="sidebar-backdrop"
          aria-label="Fechar navegação"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <Logo light />
        <div className="workspace">
          {isAdmin && !financialOnly && company.data && (
            <button
              type="button"
              className="workspace-edit"
              aria-label="Editar cadastro da empresa"
              title="Editar cadastro da empresa"
              onClick={() => { setBrandingOpen(true); setMenu(false); }}
            >
              <span aria-hidden="true">✎</span>
            </button>
          )}
          <span
            className="workspace-icon"
            style={
              company.data
                ? {
                    backgroundColor: company.data.primary_color,
                    border: "1px solid " + company.data.accent_color,
                  }
                : undefined
            }
          >
            <Building2 size={19} />
          </span>
          <div>
            <strong>{subtitle}</strong>
            <small>
              {isNexus
                ? "Gestão da plataforma"
                : profileName(company.data?.operational_profile)}
            </small>
          </div>
        </div>
        <span className="nav-label">ESPAÇO DE TRABALHO</span>
        <nav>
          {[
            { id: "overview", label: "Visão geral", icon: LayoutDashboard },
            ...(!isNexus && (isAdmin || user.role === "attendant") ? [{ id: "whatsapp-chat", label: "Conversas WhatsApp", icon: Phone }] : []),
            ...(!isNexus && (isAdmin || user.role === "attendant") ? [{ id: "nps", label: "NPS e satisfação", icon: ChartColumn }] : []),
            ...(isAdmin ? [{ id: "company-settings", label: "Configurações", icon: KeyRound }] : []),
            ...(fullNexus ? [{ id: "whatsapp-connections", label: "Conexões WhatsApp", icon: Phone }] : []),
            ...(isAdmin
              ? [{ id: "whatsapp", label: "WhatsApp", icon: Phone }, { id: "contract", label: "Meu contrato", icon: BookOpen }]
              : []),
            ...(fullNexus || isAdmin || user.role === "attendant"
              ? [{ id: "reports", label: "Relatórios", icon: ChartColumn }]
              : []),
            ...(!isNexus
              ? [
                  {
                    id: "operations",
                    label:
                      user.role === "guide" || user.role === "driver"
                        ? "Minhas viagens"
                        : "Viagens",
                    icon: Route,
                  },
                ]
              : []),
            ...(!isNexus && (isAdmin || user.role === "attendant")
              ? [
                  ...(SHOW_PUBLIC_SALES_MENU
                    ? [
                        {
                          id: "sales",
                          label: "Página pública e integrações",
                          icon: Compass,
                        },
                      ]
                    : []),
                  { id: "routes", label: "Rotas", icon: Route },
                  ...(isAdmin ? [{ id: "tracking", label: "Rastreamento", icon: Route }] : []),
                  { id: "vehicles", label: "Veículos", icon: Route },
                  ...(companyCapabilities(company.data).packages
                    ? [{ id: "packages", label: "Pacotes", icon: Route }]
                    : []),
                  { id: "allocations", label: "Alocar veículos", icon: Route },
                  { id: "passengers", label: "Passageiros", icon: Users },
                  { id: "ticket-sales", label: "Vender bilhete", icon: Ticket },
                ]
              : []),
            ...(fullNexus || isAdmin
              ? [
                  {
                    id: "collections",
                    label: "Financeiro e cobranças",
                    icon: BookOpen,
                  },
                ]
              : []),
            ...(fullNexus
              ? [{ id: "integrations", label: "Configurações", icon: KeyRound }]
              : []),
            ...(fullNexus ? [{ id: "modules", label: "Módulos por empresa", icon: Building2 }] : []),
            ...(isAdmin ? [{ id: "integrations", label: "Integração com parceiros", icon: KeyRound }] : []),
            ...(fullNexus
              ? [{ id: "nexus-team", label: "Equipe Nexus", icon: Users }]
              : []),
            ...(canManage
              ? [
                  {
                    id: "directory",
                    label: isNexus ? "Empresas" : "Equipe",
                    icon: isNexus ? Building2 : Users,
                  },
                  ...(fullNexus || isAdmin
                    ? [
                        {
                          id: "billing",
                          label: isNexus ? "Planos e assinaturas" : "Meu plano",
                          icon: CreditCard,
                        },
                      ]
                    : []),
                  { id: "audit", label: "Atividades", icon: ShieldCheck },
                ]
              : []),
          ]
            .filter((item) => isNexus || !menuModule[item.id] || hasModule(user, menuModule[item.id]))
            .filter((item) => !financialOnly || item.id === "collections")
            .sort((a, b) =>
              isNexus
                ? 0
                : companyMenuOrder.indexOf(a.id) -
                  companyMenuOrder.indexOf(b.id),
            )
            .map((item) => (
              <button
                key={item.id}
                className={menuActive(item.id) ? "active" : ""}
                onClick={() => {
                  if (item.id === "ticket-sales")
                    setTicketSalesVisit((v) => v + 1);
                  if (
                    [
                      "vehicles",
                      "packages",
                      "allocations",
                      "passengers",
                    ].includes(item.id)
                  ) {
                    setPage("operations");
                    setOperationModule(item.id);
                    setReportTripId(null);
                  } else setPage(item.id as typeof page);
                  if (item.id === "billing") setCompanyPlanOnly(false);
                  if (item.id === "operations") {
                    setOperationModule("trips");
                    setReportTripId(null);
                  }
                  setSearch("");
                  setMenu(false);
                }}
              >
                <item.icon size={19} />
                {item.label}
                {menuActive(item.id) && <span className="nav-active-dot" />}
              </button>
            ))}
          {!financialOnly && <a
            className="documentation-nav-link"
            href={isNexus ? "/nexus/ajuda" : "/ajuda"}
          >
            <BookOpen size={19} /> <span>Ajuda e manuais</span>
          </a>}
        </nav>
        <div className="sidebar-bottom">
          <span className="secure-note">
            <ShieldCheck size={16} /> Espaço exclusivo da empresa
          </span>
          <button onClick={logout}>
            <LogOut size={18} />
            Sair da conta
          </button>
          <small>Powered by Nexus Rotafy</small>
        </div>
      </aside>
      <div className="main-layout">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button menu-button"
              aria-label="Abrir navegação"
              onClick={() => setMenu(true)}
            >
              <Menu size={22} />
            </button>
            <span>Nexus Rotafy</span>
            <ChevronRight size={14} />
            <strong>{title}</strong>
          </div>
          <button
            className="profile-button"
            onClick={() => setPassword(true)}
            title="Alterar minha senha"
          >
            <div className="profile-text">
              <strong>{user.full_name}</strong>
              <small>{roleName[user.role]}</small>
            </div>
            <span className="avatar">{initials(user.full_name)}</span>
          </button>
        </header>
        <main className="content" id="main-content" tabIndex={-1}>
          <div className="page-heading">
            <div>
              <span className="section-kicker">
                {isNexus ? "NEXUS ROTAFY" : subtitle.toUpperCase()}
              </span>
              <h1>{title}</h1>
              <p className="muted">
                {page === "reports"
                  ? isNexus
                    ? "Acompanhe o consumo por empresa e ciclo."
                    : "Consulte ocupação, reservas e presença da empresa."
                  : page === "billing"
                    ? isNexus
                      ? "Configure planos e acompanhe as assinaturas das empresas."
                      : "Consulte sua franquia mensal e os demonstrativos da empresa."
                    : page === "audit"
                      ? "Acompanhe as ações realizadas no seu espaço."
                      : isNexus
                        ? "Organize as empresas e os acessos da plataforma."
                        : canManage
                          ? "Sua equipe conectada à operação."
                          : `Olá, ${user.full_name.split(" ")[0]}. Seu acesso à empresa está ativo.`}
              </p>
            </div>
            {canManage && (isNexus || hasModule(user, "team")) && (page === "overview" || page === "directory") && (
              <button
                className="button primary"
                onClick={() => setCreating(true)}
              >
                <Plus size={18} />
                {isNexus ? "Nova empresa" : "Adicionar pessoa"}
              </button>
            )}
          </div>
          {(error || queryError) && (
            <Alert>{error || message(queryError)}</Alert>
          )}
          {user.financial_blocked && (
            <Alert>
              {financialOnly
                ? "Há cobrança vencida. Seu acesso está restrito ao Financeiro. Gere ou abra o link da fatura pendente para regularizar o pagamento."
                : "Há cobrança vencida. Novas operações estão bloqueadas; as viagens já vendidas permanecem disponíveis para motorista e guia."}
            </Alert>
          )}
          {isAdmin && page !== "collections" && <BillingUpcoming notice />}
          {!isNexus && !financialOnly && (isAdmin || user.role === "attendant") && hasModule(user, "sales") && (page === "overview" || (page === "operations" && operationModule === "trips")) && <Reaccommodations allowHistory={page === "operations"} />}
          {!isNexus && !financialOnly && page !== "nps" && (isAdmin || user.role === "attendant") && hasModule(user, "whatsapp") && <NpsQualityAlert onOpen={() => setPage("nps")} />}
          {!isNexus && !financialOnly && (isAdmin || user.role === "attendant") && hasModule(user, "whatsapp") && (
            <WhatsAppHandoffAlert onOpen={handoff => {
              setRequestedChat({ ...handoff });
              setPage("whatsapp-chat");
              setMenu(false);
            }} />
          )}
          {page === "collections" && (fullNexus || isAdmin) && (
            <Collections nexus={isNexus} />
          )}
          {page === "nexus-team" && fullNexus && (
            <NexusTeam currentUserId={user.id} />
          )}
          {page === "integrations" && fullNexus && <IntegrationSettings />}
          {page === "integrations" && fullNexus && <NexusContracts />}
          {page === "integrations" && fullNexus && <MobileRelease />}
          {page === "modules" && fullNexus && <CompanyModules companies={companies.data || []} />}
          {page === "integrations" && isAdmin && <PartnerIntegration />}
          {page === "overview" && isAdmin && <PlanChangeNotice onOpen={() => setPage("contract")} />}
          {page === "contract" && isAdmin && <CompanyContract user={user} />}
          {page === "whatsapp" && isAdmin && <CompanyWhatsApp />}
          {page === "whatsapp-chat" && !isNexus && (isAdmin || user.role === "attendant") && <WhatsAppChat requestedChat={requestedChat} canConfigure={isAdmin} onConfigure={() => setPage("whatsapp")} />}
          {page === "nps" && !isNexus && !financialOnly && (isAdmin || user.role === "attendant") && hasModule(user, "whatsapp") && <Nps canConfigure={isAdmin} />}
          {page === "company-settings" && isAdmin && !financialOnly && hasModule(user, "whatsapp") && <BusinessHours />}
          {page === "whatsapp-connections" && fullNexus && <NexusWhatsApp />}
          {page === "billing" && (fullNexus || isAdmin) && (
            <Billing
              isNexus={isNexus}
              onLogout={onLogout}
              initialCompanyId={billingCompany}
              companyOnly={companyPlanOnly}
            />
          )}
          {page === "reports" && (fullNexus || !isNexus) && (
            <Reports
              user={user}
              companies={companies.data || []}
              onOpenTrip={(id) => {
                setReportTripId(id);
                setOperationModule("trips");
                setPage("operations");
              }}
            />
          )}
          {page === "sales" && company.data && (
            <Sales company={company.data} isAdmin={isAdmin} />
          )}
          {page === "ticket-sales" &&
            !isNexus &&
            (isAdmin || user.role === "attendant") && (
              <TicketSales key={ticketSalesVisit} onLogout={onLogout} />
            )}
          {page === "routes" &&
            !isNexus &&
            (isAdmin || user.role === "attendant") && <RouteCatalog />}
          {page === "tracking" && isAdmin && <Tracking />}
          {page === "operations" && (
            <Operations
              key={`${operationModule}:${reportTripId || ""}`}
              initialTripId={reportTripId}
              initialTab={
                operationModule === "vehicles"
                  ? "vehicles"
                  : operationModule === "packages"
                    ? "packages"
                    : "trips"
              }
              action={
                operationModule === "passengers" ||
                operationModule === "allocations"
                  ? operationModule
                  : undefined
              }
              manage={isAdmin || user.role === "attendant"}
              allowPackages={companyCapabilities(company.data).packages && hasModule(user, "packages")}
              user={user}
              onLogout={onLogout}
            />
          )}
          {page === "overview" && (
            <>
              <div className="stats-grid">
                <div className="stat-card">
                  <span className="stat-icon">
                    <Building2 size={20} />
                  </span>
                  <small>
                    {isNexus
                      ? "Empresas cadastradas"
                      : canManage
                        ? "Pessoas na equipe"
                        : "Empresa"}
                  </small>
                  <strong>
                    {loading
                      ? "—"
                      : canManage
                        ? rows.length
                        : company.data?.trade_name || "—"}
                  </strong>
                  <p>
                    {isNexus
                      ? "Espaços independentes na plataforma"
                      : "Conectados à sua operação"}
                  </p>
                </div>
                <div className="stat-card">
                  <span className="stat-icon green">
                    <CircleCheck size={20} />
                  </span>
                  <small>
                    {isNexus
                      ? "Empresas ativas"
                      : canManage
                        ? "Acessos ativos"
                        : "Seu perfil"}
                  </small>
                  <strong>
                    {loading ? "—" : canManage ? active : roleName[user.role]}
                  </strong>
                  <p>
                    {canManage
                      ? "Com acesso liberado"
                      : "Permissões conforme sua função"}
                  </p>
                </div>
                <div className="stat-card">
                  <span className="stat-icon coral">
                    <ShieldCheck size={20} />
                  </span>
                  <small>
                    {canManage
                      ? "Acessos suspensos"
                      : "Identificador da empresa"}
                  </small>
                  <strong>
                    {loading
                      ? "—"
                      : canManage
                        ? rows.length - active
                        : company.data?.slug || "—"}
                  </strong>
                  <p>
                    {canManage
                      ? "Histórico preservado"
                      : "Use este identificador ao entrar"}
                  </p>
                </div>
              </div>
              <section className="welcome-banner">
                <div>
                  <span className="section-kicker">
                    TUDO COMEÇA COM UMA BOA EQUIPE
                  </span>
                  <h2>
                    {isNexus
                      ? "Cada empresa, seu próprio espaço."
                      : "Prontos para o próximo destino."}
                  </h2>
                  <p>
                    {isNexus
                      ? "Cadastre uma empresa e defina seu primeiro administrador."
                      : "Mantenha os acessos da equipe organizados e atualizados."}
                  </p>
                </div>
                <div className="banner-art" aria-hidden="true">
                  <Route size={72} strokeWidth={1.3} />
                </div>
              </section>
            </>
          )}
          {canManage && (isNexus || hasModule(user, "team")) && (page === "overview" || page === "directory") && (
            <section className="panel">
              <header className="panel-header">
                <div>
                  <h2>
                    {isNexus ? "Empresas da plataforma" : "Pessoas da equipe"}
                  </h2>
                  <p className="muted">
                    {rows.length}{" "}
                    {isNexus ? "empresas cadastradas" : "pessoas cadastradas"}
                  </p>
                </div>
                <label className="search-field">
                  <Search size={17} />
                  <input
                    aria-label={isNexus ? "Buscar empresa" : "Buscar pessoa"}
                    placeholder={isNexus ? "Buscar empresa…" : "Buscar pessoa…"}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                {!isNexus && (
                  <button
                    className="button secondary"
                    onClick={() => setDeliveries(true)}
                  >
                    E-mails de acesso
                  </button>
                )}
              </header>
              {loading ? (
                <div className="empty-state">Carregando…</div>
              ) : rows.length === 0 ? (
                <div className="empty-state">
                  <Building2 size={34} />
                  <h3>
                    {isNexus
                      ? "Sua primeira empresa começa aqui"
                      : "Organize sua equipe"}
                  </h3>
                  <p>
                    {isNexus
                      ? "Cadastre uma empresa para liberar seu espaço de trabalho."
                      : "Adicione as pessoas que participam da operação."}
                  </p>
                  <button
                    className="button secondary"
                    onClick={() => setCreating(true)}
                  >
                    <Plus size={16} />
                    {isNexus ? "Cadastrar empresa" : "Adicionar pessoa"}
                  </button>
                </div>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>{isNexus ? "Empresa" : "Pessoa"}</th>
                        <th>{isNexus ? "Identificador" : "Perfil"}</th>
                        <th>Status</th>
                        <th className="text-right">Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows
                        .filter((row) =>
                          ("trade_name" in row
                            ? `${row.trade_name} ${row.slug}`
                            : `${row.full_name} ${row.email}`
                          )
                            .toLocaleLowerCase("pt-BR")
                            .includes(search.toLocaleLowerCase("pt-BR")),
                        )
                        .map((row) => (
                          <tr key={row.id}>
                            <td>
                              <div className="identity-cell">
                                <span className="table-avatar">
                                  {initials(
                                    "trade_name" in row
                                      ? row.trade_name
                                      : row.full_name,
                                  )}
                                </span>
                                <div>
                                  <strong>
                                    {"trade_name" in row
                                      ? row.trade_name
                                      : row.full_name}
                                  </strong>
                                  <small>
                                    {"trade_name" in row
                                      ? row.corporate_name
                                      : row.email}
                                  </small>
                                  {"trade_name" in row && (
                                    <small>
                                      {profileName(row.operational_profile)}
                                    </small>
                                  )}
                                </div>
                              </div>
                            </td>
                            <td>
                              {"slug" in row ? (
                                <code>{row.slug}</code>
                              ) : (
                                roleName[row.role]
                              )}
                            </td>
                            <td>
                              <span
                                className={`status-badge ${row.is_active ? "active" : "inactive"}`}
                              >
                                <span />
                                {row.is_active ? "Ativo" : "Suspenso"}
                              </span>
                              {"trial_ends_on" in row && row.trial_ends_on && (
                                <small className="muted">
                                  {" "}
                                  · Teste até{" "}
                                  {row.trial_ends_on
                                    .split("-")
                                    .reverse()
                                    .join("/")}
                                </small>
                              )}
                            </td>
                            <td>
                              <div className="row-actions">
                                {isNexus && "trade_name" in row && (
                                  <>
                                    <button
                                      className="text-button"
                                      onClick={() => setEditingCompany(row)}
                                    >
                                      Editar dados
                                    </button>
                                    <button
                                      className="text-button"
                                      onClick={() => setAccessCompany(row)}
                                    >
                                      Enviar acesso
                                    </button>
                                    {fullNexus && (
                                      <button className="text-button" onClick={() => setContractCompany(row)}>Contrato</button>
                                    )}
                                    {fullNexus && (
                                      <button
                                        className="text-button"
                                        onClick={() => {
                                          setBillingCompany(row.id);
                                          setCompanyPlanOnly(true);
                                          setPage("billing");
                                        }}
                                      >
                                        Gerenciar plano
                                      </button>
                                    )}
                                  </>
                                )}
                                {!isNexus && "full_name" in row && (
                                  <button
                                    className="text-button"
                                    onClick={() => setEditingCollaborator(row)}
                                  >
                                    Editar colaborador
                                  </button>
                                )}
                                {!isNexus && row.is_active && (
                                  <button
                                    className="icon-button"
                                    disabled={busyId === row.id}
                                    onClick={() => reset(row.id)}
                                    aria-label={`Gerar link de recuperação para ${(row as User).full_name}`}
                                    title="Gerar link de recuperação"
                                  >
                                    <KeyRound size={17} />
                                  </button>
                                )}
                                {!isNexus && row.is_active && (
                                  <button
                                    className="text-button"
                                    disabled={busyId === row.id}
                                    onClick={() => setInvitingUser(row as User)}
                                  >
                                    Enviar convite
                                  </button>
                                )}
                                <button
                                  className="text-button"
                                  disabled={
                                    busyId === row.id || row.id === user.id
                                  }
                                  onClick={() => toggle(row)}
                                >
                                  {busyId === row.id
                                    ? "Aguarde…"
                                    : row.is_active
                                      ? "Suspender"
                                      : "Ativar"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                  {search &&
                    !rows.some((row) =>
                      ("trade_name" in row
                        ? `${row.trade_name} ${row.slug}`
                        : `${row.full_name} ${row.email}`
                      )
                        .toLocaleLowerCase("pt-BR")
                        .includes(search.toLocaleLowerCase("pt-BR")),
                    ) && (
                      <div className="empty-state">
                        Nenhum resultado para esta busca.
                      </div>
                    )}
                </div>
              )}
            </section>
          )}
          {page === "audit" && (
            <section className="panel">
              <header className="panel-header">
                <h2>Últimas atividades</h2>
                <span className="muted">Até 100 registros recentes</span>
              </header>
              {audit.isPending ? (
                <div className="empty-state">Carregando…</div>
              ) : (
                <div className="activity-list">
                  {audit.data?.map((event) => (
                    <div className="activity" key={event.id}>
                      <span className="activity-icon">
                        <Check size={16} />
                      </span>
                      <div>
                        <strong>
                          {actionNames[event.action] ||
                            (event.action.startsWith("company.profile_changed.")
                              ? `Perfil alterado: ${event.action.endsWith(".regular") ? "Turismo → Regular" : "Regular → Turismo"}`
                              : event.action)}
                        </strong>
                        <small>{date(event.created_at)}</small>
                      </div>
                    </div>
                  ))}
                  {audit.data?.length === 0 && (
                    <div className="empty-state">
                      Nenhuma atividade registrada.
                    </div>
                  )}
                </div>
              )}
            </section>
          )}
          <footer className="content-footer">
            Nexus Rotafy{" "}
            <span>Uma operação mais tranquila, a cada viagem.</span>
          </footer>
        </main>
      </div>
      {brandingOpen && company.data && (
        <BrandingModal
          company={company.data}
          onClose={() => setBrandingOpen(false)}
        />
      )}
      {contractCompany && fullNexus && <NexusCompanyContract company={contractCompany} onClose={() => setContractCompany(null)} />}
      {accessCompany && (
        <CompanyAccess
          company={accessCompany}
          onClose={() => setAccessCompany(null)}
        />
      )}
      {editingCollaborator && (
        <EditCollaborator
          user={editingCollaborator}
          currentUserId={user.id}
          onClose={() => setEditingCollaborator(null)}
          onLogout={onLogout}
        />
      )}
      {editingCompany && (
        <EditCompany
          company={editingCompany}
          onClose={() => setEditingCompany(null)}
        />
      )}
      {creating &&
        (isNexus ? (
          <CreateCompany
            restricted={!fullNexus}
            onClose={() => setCreating(false)}
          />
        ) : (
          <CreateUser onClose={() => setCreating(false)} />
        ))}
      {password && (
        <PasswordModal onClose={() => setPassword(false)} onLogout={onLogout} />
      )}
      {deliveries && <EmailDeliveries onClose={() => setDeliveries(false)} />}
      {invitingUser && (
        <InvitationModal
          user={invitingUser}
          onClose={() => setInvitingUser(null)}
          onSent={() => {
            setInvitingUser(null);
            setDeliveries(true);
            void client.invalidateQueries({ queryKey: ["users"] });
          }}
        />
      )}
      {resetLink && (
        <Modal title="Link de recuperação" onClose={() => setResetLink("")}>
          <div className="modal-form">
            <p>
              Compartilhe este link diretamente com a pessoa por um canal
              seguro. Ele expira em 30 minutos e pode ser utilizado uma única
              vez.
            </p>
            <Field label="Link">
              <textarea
                readOnly
                value={resetLink}
                rows={4}
                onFocus={(event) => event.currentTarget.select()}
              />
            </Field>
            <button className="button primary" onClick={() => setResetLink("")}>
              Concluir
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

export function App() {
  const client = useQueryClient();
  useEffect(() => {
    if (window.location.pathname === "/" && !navigator.onLine)
      window.location.replace("/offline");
  }, []);
  const session = useQuery({
    queryKey: ["session"],
    refetchInterval: 30000,
    enabled: !["/offline", "/ajuda"].includes(window.location.pathname),
    queryFn: async () => {
      try {
        return await api<User>("/auth/me");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
  });
  function loggedOut() {
    client.removeQueries({
      predicate: (query) => query.queryKey[0] !== "session",
    });
    client.setQueryData(["session"], null);
  }
  if (["/privacidade", "/termos", "/cancelamento-reembolso", "/privacidade/solicitacao"].includes(window.location.pathname)) return <LegalPage />;
  if (window.location.pathname === "/ajuda") return <Documentation />;
  if (window.location.pathname === "/cadastro")
    return (
      <main className="reset-layout">
        <section className="panel modal-form">
          <h1>Cadastro pela equipe Nexus</h1>
          <p>
            Para contratar o Rotafy, fale com nossa equipe comercial. Seu acesso
            será enviado após o cadastro da empresa.
          </p>
          <a className="button primary" href="/">
            Voltar ao acesso
          </a>
        </section>
      </main>
    );
  if (window.location.pathname === "/redefinir") return <Reset />;
  if (window.location.pathname === "/pagamento-concluido")
    return <PaymentReturn />;
  if (window.location.pathname === "/offline")
    return (
      <Suspense fallback={<p>Preparando operação local…</p>}>
        <OfflineHub />
      </Suspense>
    );
  if (window.location.pathname.startsWith("/comprar/"))
    return <PublicBooking />;
  if (window.location.pathname === "/acompanhar") return <TrackingPage />;
  if (window.location.pathname === "/bilhete" || window.location.pathname.startsWith("/b/")) return <TicketPage />;
  if (session.isPending)
    return (
      <div className="app-loading">
        <Logo />
        <span>Preparando seu espaço…</span>
      </div>
    );
  if (session.isError)
    return (
      <div className="app-loading">
        <Logo />
        <Alert>{message(session.error)}</Alert>
        <a className="button secondary" href="/offline">
          Abrir operação offline preparada
        </a>
        <button className="button primary" onClick={() => session.refetch()}>
          Tentar novamente
        </button>
      </div>
    );
  if (!session.data)
    return (
      <Login
        onLogin={(user) => {
          client.removeQueries({
            predicate: (query) => query.queryKey[0] !== "session",
          });
          client.setQueryData(["session"], user);
        }}
      />
    );
  if (window.location.pathname === "/nexus/ajuda")
    return ["nexus", "nexus_staff"].includes(session.data.role) ? (
      <Documentation nexus editablePresentation={session.data.role === "nexus"} />
    ) : (
      <Documentation />
    );
  if (session.data.contract_pending) return <ContractGate user={session.data} onLogout={loggedOut} />;
  return <Dashboard user={session.data} onLogout={loggedOut} />;
}
