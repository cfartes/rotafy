import { Field } from "./components/ui";
import { type Company } from "./api";

export type OperationalProfile = "tourism" | "regular";
export const profileName = (profile?: OperationalProfile) =>
  profile === "regular" ? "Transporte regular" : "Turismo e transfers";
export function companyCapabilities(company?: Company) {
  return {
    packages:
      company?.operational_profile !== "regular" &&
      company?.capabilities?.packages !== false,
  };
}
export function ProfileField({
  initial = "",
  editing = false,
}: {
  initial?: OperationalProfile | "";
  editing?: boolean;
}) {
  return (
    <Field label="Perfil operacional">
      <select
        name="operational_profile"
        aria-label="Perfil operacional"
        required
        defaultValue={initial}
      >
        <option value="" disabled>
          Selecione o tipo de operação
        </option>
        <option value="tourism">Turismo e transfers</option>
        <option value="regular">Transporte regular</option>
      </select>
      <small className="muted">
        Turismo: viagens avulsas e pacotes com vários destinos. Regular: viagens
        avulsas e bilhetes; linhas recorrentes e venda independente por trecho
        serão disponibilizadas em uma etapa futura. O perfil é independente do
        plano.
      </small>
      {editing && (
        <small className="muted">
          A mudança preserva o histórico. Para mudar para Regular, conclua ou
          cancele as viagens vinculadas a pacotes.
        </small>
      )}
    </Field>
  );
}
