import { CompanyAccess } from "./CompanyAccess";
import { Collections } from "./Collections";
import { PasswordInput } from "./components/PasswordInput";
import { useEffect, useState, lazy, Suspense, type FormEvent } from "react";
import { NexusTeam } from "./NexusTeam";
import { Billing } from "./billing/Billing";
import { money, type Plan } from "./billing/types";
import { Sales } from "./Sales";
import { IntegrationSettings } from "./IntegrationSettings";
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
  Palette,
  Plus,
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
            <a className="button secondary full" href="/offline">
              Abrir operação offline preparada
            </a>
          </form>
          <button
            className="text-button login-help"
            onClick={() => setForgot(true)}
          >
            <KeyRound size={15} /> Esqueci minha senha
          </button>
          <a className="portal-link" href="/ajuda">
            <BookOpen size={15} /> Manual e apresentação
          </a>
          <a className="portal-link" href={isNexus ? "/" : "/nexus"}>
            {isNexus ? "Acessar portal da empresa" : "Administração Nexus"}
            <ChevronRight size={15} />
          </a>
        </div>
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
        <p className="muted">
          Crie o espaço da empresa e seu primeiro administrador. Escolha o plano
          para iniciar a assinatura mensal hoje. O CPF/CNPJ é obrigatório para
          cobrança. Todos os campos deste cadastro são obrigatórios.
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
        <h3 className="form-section">Tipo de operação</h3>
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
  "whatsapp.queued": "Mensagem WhatsApp adicionada à fila",
  "trip.unpublished": "Viagem retirada da página pública",
  "reservation.paid": "Reserva marcada PAGO",
  "reservation.unpaid": "Marcação PAGO removida",
  "reservation.tracking_issued": "Link privado de acompanhamento gerado",
  "reservation.tracking_revoked": "Link privado de acompanhamento revogado",
  "availability.unavailable": "Falta de lugares informada pela família",
  "availability.acknowledged": "Alerta de disponibilidade visto",
  "integration.key_created": "Chave de integração criada",
  "integration.key_revoked": "Chave de integração revogada",
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
      await client.invalidateQueries({ queryKey: ["audit"] });
      onClose();
    } catch (err) {
      setError(message(err));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Identidade da empresa" onClose={onClose}>
      <form className="modal-form" onSubmit={submit}>
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
            {pending ? "Salvando…" : "Salvar identidade"}
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
  const [operationModule, setOperationModule] = useState("trips");
  const [reportTripId, setReportTripId] = useState<string | null>(null);
  const [page, setPage] = useState<
    | "overview"
    | "directory"
    | "audit"
    | "billing"
    | "operations"
    | "sales"
    | "routes"
    | "ticket-sales"
    | "reports"
    | "integrations"
    | "collections"
    | "nexus-team"
  >("overview");
  const [menu, setMenu] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [accessCompany, setAccessCompany] = useState<Company | null>(null);
  const [billingCompany, setBillingCompany] = useState("");
  const [companyPlanOnly, setCompanyPlanOnly] = useState(false);
  const [password, setPassword] = useState(false);
  const [brandingOpen, setBrandingOpen] = useState(false);
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
    enabled: isAdmin,
  });
  const company = useQuery({
    queryKey: ["company"],
    queryFn: () => api<Company>("/company"),
    enabled: !isNexus,
  });
  const audit = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<AuditEvent[]>("/audit"),
    enabled: isNexus || isAdmin,
  });
  const rows = isNexus ? companies.data || [] : team.data || [];
  const active = rows.filter((row) => row.is_active).length;
  const canManage = isNexus || isAdmin;
  const loading = isNexus
    ? companies.isPending
    : isAdmin
      ? team.isPending
      : company.isPending;
  const queryError =
    companies.error || team.error || company.error || audit.error;
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
    page === "nexus-team"
      ? "Equipe Nexus"
      : page === "collections"
        ? "Financeiro e cobranças"
        : page === "integrations"
          ? "Configurações"
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
                        : companyCapabilities(company.data).packages
                          ? "Frota, pacotes e viagens"
                          : "Frota e viagens",
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
          ].map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "active" : ""}
              onClick={() => {
                setPage(item.id as typeof page);
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
              {page === item.id && <span className="nav-active-dot" />}
            </button>
          ))}
          {isAdmin && (
            <button
              onClick={() => {
                setBrandingOpen(true);
                setMenu(false);
              }}
              disabled={!company.data}
            >
              <Palette size={19} />
              Identidade da empresa
            </button>
          )}
          {!isNexus &&
            (isAdmin || user.role === "attendant") &&
            [
              ["vehicles", "Veículos"],
              ["trips", "Viagens"],
              ["allocations", "Alocar veículos"],
              ["passengers", "Passageiros"],
            ].map(([module, label]) => (
              <button
                key={module}
                className={
                  page === "operations" && operationModule === module
                    ? "active"
                    : ""
                }
                onClick={() => {
                  setOperationModule(module);
                  setReportTripId(null);
                  setPage("operations");
                  setMenu(false);
                }}
              >
                <Route size={19} />
                <span>{label}</span>
              </button>
            ))}
          <a
            className="documentation-nav-link"
            href={isNexus ? "/nexus/ajuda" : "/ajuda"}
          >
            <BookOpen size={19} /> <span>Ajuda e manuais</span>
          </a>
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
            {canManage && (page === "overview" || page === "directory") && (
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
              Há cobrança vencida aguardando confirmação do Pix pela Nexus.
              Novas operações estão bloqueadas; consultas e embarques permanecem
              disponíveis.
            </Alert>
          )}
          {page === "collections" && (fullNexus || isAdmin) && (
            <Collections nexus={isNexus} />
          )}
          {page === "nexus-team" && fullNexus && (
            <NexusTeam currentUserId={user.id} />
          )}
          {page === "integrations" && fullNexus && <IntegrationSettings />}
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
              <TicketSales onLogout={onLogout} />
            )}
          {page === "routes" &&
            !isNexus &&
            (isAdmin || user.role === "attendant") && <RouteCatalog />}
          {page === "operations" && (
            <Operations
              key={`${operationModule}:${reportTripId || ""}`}
              initialTripId={reportTripId}
              initialTab={operationModule === "vehicles" ? "vehicles" : "trips"}
              action={
                operationModule === "passengers" ||
                operationModule === "allocations"
                  ? operationModule
                  : undefined
              }
              manage={isAdmin || user.role === "attendant"}
              allowPackages={companyCapabilities(company.data).packages}
              user={user}
              onLogout={onLogout}
            />
          )}
          {page === "overview" && (
            <>
              {!isNexus && (isAdmin || user.role === "attendant") && (
                <section className="panel">
                  <header className="panel-header">
                    <div>
                      <h2>Cadastros e operação da empresa</h2>
                      <p>Organize a frota, as viagens e os passageiros.</p>
                    </div>
                  </header>
                  <div className="modal-actions">
                    {[
                      ["vehicles", "Gerenciar veículos"],
                      ["trips", "Criar e gerenciar viagens"],
                      ["allocations", "Distribuir veículos nas viagens"],
                      ["passengers", "Cadastrar passageiros"],
                    ].map(([module, label]) => (
                      <button
                        className="button secondary"
                        key={module}
                        onClick={() => {
                          setOperationModule(module);
                          setReportTripId(null);
                          setPage("operations");
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </section>
              )}
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
          {canManage && (page === "overview" || page === "directory") && (
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
      {accessCompany && (
        <CompanyAccess
          company={accessCompany}
          onClose={() => setAccessCompany(null)}
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
  if (window.location.pathname === "/offline")
    return (
      <Suspense fallback={<p>Preparando operação local…</p>}>
        <OfflineHub />
      </Suspense>
    );
  if (window.location.pathname.startsWith("/comprar/"))
    return <PublicBooking />;
  if (window.location.pathname === "/acompanhar") return <TrackingPage />;
  if (window.location.pathname === "/bilhete") return <TicketPage />;
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
      <Documentation nexus />
    ) : (
      <Documentation />
    );
  return <Dashboard user={session.data} onLogout={loggedOut} />;
}
