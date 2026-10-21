import { useEffect, useRef, useState } from "react";
import { Field } from "./components/ui";
import { api } from "./api";

export const addressKeys = ["address", "address_number", "address_complement", "neighborhood", "city", "state", "postal_code"] as const;
export type CompanyAddress = Partial<Record<typeof addressKeys[number], string | null>>;
export const addressPayload = (form: FormData) => Object.fromEntries(addressKeys.map((key) => [key, form.get(key) || null]));

export function AddressFields({ company = {}, required = true }: { company?: CompanyAddress; required?: boolean }) {
  const [postal, setPostal] = useState((company.postal_code || "").replace(/\D/g, ""));
  const [address, setAddress] = useState({ address: company.address || "", neighborhood: company.neighborhood || "", city: company.city || "", state: company.state || "" });
  const edited = useRef({ address: 0, neighborhood: 0, city: 0, state: 0 });
  const previous = useRef(postal);
  const [notice, setNotice] = useState("");
  function change(key: keyof typeof address, value: string) {
    edited.current[key]++;
    setAddress(current => ({ ...current, [key]: value }));
  }
  useEffect(() => {
    if (postal.length !== 8 || postal === previous.current) return;
    const controller = new AbortController();
    const revisions = { ...edited.current };
    let disposed = false;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const timer = setTimeout(async () => {
      previous.current = postal;
      setNotice("Consultando CEP…");
      timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const result = await api<typeof address>(`/locations/postal-code/${postal}`, { signal: controller.signal });
        if (disposed) return;
        if (!result || !Object.keys(revisions).every(key => typeof result[key as keyof typeof address] === "string")) throw new Error("Não foi possível consultar o CEP.");
        setAddress(current => Object.fromEntries(Object.keys(current).map(key => {
          const field = key as keyof typeof address;
          return [field, edited.current[field] === revisions[field] ? result[field] || "" : current[field]];
        })) as typeof address);
        setNotice("CEP consultado. Confira o endereço e informe o número e o complemento, se houver.");
      } catch (e) {
        if (!disposed) setNotice(e instanceof Error ? `${e.message} Os campos continuam disponíveis para preenchimento manual.` : "Não foi possível consultar o CEP. Preencha o endereço manualmente.");
      } finally { if (timeout) clearTimeout(timeout); }
    }, 350);
    return () => { disposed = true; clearTimeout(timer); if (timeout) clearTimeout(timeout); controller.abort(); };
  }, [postal]);
  return <fieldset className="company-address"><legend>Endereço da empresa</legend><div className="form-grid">
    <Field label="CEP"><input name="postal_code" value={postal.replace(/^(\d{5})(\d)/, "$1-$2")} onChange={(e) => { previous.current = ""; setNotice(""); setPostal(e.target.value.replace(/\D/g, "").slice(0, 8)); }} required={required} pattern="[0-9]{5}-?[0-9]{3}" inputMode="numeric" maxLength={9} placeholder="00000-000" autoComplete="postal-code" /></Field>
    <Field label="Endereço"><input name="address" value={address.address} onChange={e => change("address", e.target.value)} required={required} maxLength={250} /></Field>
    <Field label="Número"><input name="address_number" defaultValue={company.address_number || ""} required={required} maxLength={30} placeholder="Número ou S/N" /></Field>
    <Field label="Complemento (opcional)"><input name="address_complement" defaultValue={company.address_complement || ""} maxLength={150} /></Field>
    <Field label="Bairro"><input name="neighborhood" value={address.neighborhood} onChange={e => change("neighborhood", e.target.value)} required={required} maxLength={100} /></Field>
    <Field label="Cidade"><input name="city" value={address.city} onChange={e => change("city", e.target.value)} required={required} maxLength={100} /></Field>
    <Field label="UF"><select name="state" aria-label="UF" value={address.state} onChange={e => change("state", e.target.value)} required={required}><option value="">Selecione</option>{"AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ").map((uf) => <option key={uf}>{uf}</option>)}</select></Field>
  </div>{notice && <p className="muted" role="status">{notice}</p>}</fieldset>;
}
