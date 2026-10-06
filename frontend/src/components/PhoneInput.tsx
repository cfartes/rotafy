import { useState } from "react";

function format(value: string) {
  const digits = value.replace(/\D/g, "");
  if (value.trim().startsWith("+")) return `+${digits.slice(0, 15)}`;
  const raw = digits.slice(0, 11);
  if (raw.length < 3) return raw ? `(${raw}` : "";
  const local = raw.slice(2);
  const split = local.length > 8 ? 5 : 4;
  return `(${raw.slice(0, 2)}) ${local.slice(0, split)}${local.length > split ? `-${local.slice(split)}` : ""}`;
}

export function PhoneInput({ initialValue = "" }: { initialValue?: string }) {
  const [value, setValue] = useState(() => format(initialValue));
  return (
    <input
      name="contact_phone"
      type="tel"
      autoComplete="tel"
      placeholder="(47) 99999-9999"
      value={value}
      maxLength={50}
      onChange={(event) => setValue(format(event.currentTarget.value))}
    />
  );
}
