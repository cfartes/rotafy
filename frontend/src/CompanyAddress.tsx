import { useState } from "react";
import { Field } from "./components/ui";

export const addressKeys = ["address", "address_number", "address_complement", "neighborhood", "city", "state", "postal_code"] as const;
export type CompanyAddress = Partial<Record<typeof addressKeys[number], string | null>>;
export const addressPayload = (form: FormData) => Object.fromEntries(addressKeys.map((key) => [key, form.get(key) || null]));

export function AddressFields({ company = {}, required = true }: { company?: CompanyAddress; required?: boolean }) {
  const [postal, setPostal] = useState(company.postal_code || "");
  return <fieldset className="package-route-card"><legend>Endereço da empresa</legend><div className="form-grid">
    <Field label="Endereço"><input name="address" defaultValue={company.address || ""} required={required} maxLength={250} /></Field>
    <Field label="Número"><input name="address_number" defaultValue={company.address_number || ""} required={required} maxLength={30} placeholder="Número ou S/N" /></Field>
    <Field label="Complemento (opcional)"><input name="address_complement" defaultValue={company.address_complement || ""} maxLength={150} /></Field>
    <Field label="Bairro"><input name="neighborhood" defaultValue={company.neighborhood || ""} required={required} maxLength={100} /></Field>
    <Field label="Cidade"><input name="city" defaultValue={company.city || ""} required={required} maxLength={100} /></Field>
    <Field label="UF"><select name="state" defaultValue={company.state || ""} required={required}><option value="">Selecione</option>{"AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ").map((uf) => <option key={uf}>{uf}</option>)}</select></Field>
    <Field label="CEP"><input name="postal_code" value={postal.replace(/^(\d{5})(\d)/, "$1-$2")} onChange={(e) => setPostal(e.target.value.replace(/\D/g, "").slice(0, 8))} required={required} pattern="[0-9]{5}-?[0-9]{3}" inputMode="numeric" maxLength={9} placeholder="00000-000" /></Field>
  </div></fieldset>;
}
