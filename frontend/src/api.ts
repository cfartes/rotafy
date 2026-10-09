export type Role = "nexus" | "admin" | "attendant" | "guide" | "driver";
export type User = {
  contact_phone?: string | null;
  id: string;
  company_id: string | null;
  full_name: string;
  email: string;
  role: Role;
  is_active: boolean;
};
export type Company = {
  operational_profile?: "tourism" | "regular";
  capabilities?: {
    packages: boolean;
    multi_destination: boolean;
    recurring_lines: boolean;
    independent_segments: boolean;
  };
  id: string;
  slug: string;
  trade_name: string;
  corporate_name: string;
  cnpj: string | null;
  contact_phone: string | null;
  primary_color: string;
  accent_color: string;
  is_active: boolean;
  created_at: string;
};
export type AuditEvent = {
  id: string;
  action: string;
  created_at: string;
  company_id: string | null;
  target_id: string | null;
};

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type ValidationIssue = {
  loc?: unknown[];
  type?: string;
  msg?: string;
  ctx?: Record<string, unknown>;
};
const fieldNames: Record<string, string> = {
  trade_name: "Nome comercial",
  corporate_name: "Razão social",
  slug: "Identificador de acesso",
  cnpj: "CPF/CNPJ",
  plan_id: "Plano escolhido",
  operational_profile: "Perfil operacional",
  expected_profile: "Perfil anterior da empresa",
  full_name: "Nome completo",
  email: "E-mail",
  password: "Senha",
  current_password: "Senha atual",
  new_password: "Nova senha",
  company: "Identificador da empresa",
  contact_name: "Nome do responsável",
  phone: "Telefone",
  contact_phone: "Telefone / WhatsApp",
  cpf: "CPF",
  name: "Nome",
  starts_at: "Saída",
  ends_at: "Chegada",
  capacity: "Quantidade de lugares",
};

function validationMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail))
    return "Não foi possível concluir a operação. Tente novamente.";
  const messages = detail.slice(0, 8).map((issue: ValidationIssue) => {
    const location = Array.isArray(issue?.loc) ? issue.loc : [];
    const field = location
      .filter((part) => typeof part === "string" && part !== "body")
      .at(-1);
    const label = fieldNames[String(field)] || "Campo do formulário";
    const prefix = location.includes("admin") ? "Administrador — " : "";
    let explanation = "Confira o valor informado.";
    if (
      issue.type === "value_error" &&
      typeof issue.msg === "string" &&
      issue.msg.startsWith("Value error, ")
    )
      explanation = issue.msg.slice("Value error, ".length);
    else if (issue.type === "missing") explanation = "Preencha este campo.";
    else if (issue.type === "string_too_short")
      explanation = `Use pelo menos ${Number(issue.ctx?.min_length) || 1} caracteres.`;
    else if (issue.type === "string_too_long")
      explanation = `Use no máximo ${Number(issue.ctx?.max_length) || 128} caracteres.`;
    else if (field === "email")
      explanation = "Informe um endereço de e-mail válido.";
    else if (field === "slug")
      explanation =
        "Use somente letras minúsculas sem acentos e números, de 2 a 50 caracteres. Não use espaços, sublinhado, hífen ou outros caracteres especiais.";
    else if (
      issue.type === "value_error" &&
      typeof issue.msg === "string" &&
      issue.msg.startsWith("Value error, ")
    )
      explanation = issue.msg.slice("Value error, ".length);
    return `${prefix}${label}: ${explanation}`;
  });
  return (
    [...new Set(messages)].join(" ") ||
    "Confira os campos preenchidos e tente novamente."
  );
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const csrf = document.cookie
    .split("; ")
    .find((c) => c.startsWith("rotafy_csrf="))
    ?.split("=")[1];
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      signal: options.signal ?? AbortSignal.timeout(20000),
      credentials: "same-origin",
      headers: {
        ...(options.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...(csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(
      0,
      "Não foi possível conectar. Verifique sua conexão e tente novamente.",
    );
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      validationMessage(payload.detail),
      response.headers.get("X-Rotafy-Error") || undefined,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const post = <T>(path: string, data: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(data) });
export const patch = <T>(path: string, data: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(data) });
export const roleName: Record<Role, string> = {
  nexus: "Administrador Nexus",
  admin: "Administrador",
  attendant: "Atendente",
  guide: "Guia",
  driver: "Motorista",
};
