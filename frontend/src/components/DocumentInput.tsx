import { useState, type ChangeEvent } from "react";

function mask(value: string) {
  const raw = value
    .replace(/[^a-zA-Z0-9]/g, "")
    .toUpperCase()
    .slice(0, 14);
  const cnpj = /[A-Z]/.test(raw) || raw.length > 11;
  const groups = cnpj ? [2, 3, 3, 4, 2] : [3, 3, 3, 2];
  const separators = cnpj ? [".", ".", "/", "-"] : [".", ".", "-"];
  let result = "",
    offset = 0;
  for (let i = 0; i < groups.length && offset < raw.length; i++) {
    if (i > 0) result += separators[i - 1];
    result += raw.slice(offset, offset + groups[i]);
    offset += groups[i];
  }
  return result;
}

export function DocumentInput({
  initialValue = "",
  required = false,
}: {
  initialValue?: string;
  required?: boolean;
}) {
  const [value, setValue] = useState(() => mask(initialValue));
  function change(e: ChangeEvent<HTMLInputElement>) {
    const input = e.currentTarget;
    const position = input.selectionStart ?? input.value.length;
    const count = input.value
      .slice(0, position)
      .replace(/[^a-zA-Z0-9]/g, "").length;
    const formatted = mask(input.value);
    setValue(formatted);
    requestAnimationFrame(() => {
      let consumed = 0,
        caret = 0;
      while (caret < formatted.length && consumed < count) {
        if (/[A-Z0-9]/.test(formatted[caret])) consumed++;
        caret++;
      }
      input.setSelectionRange(caret, caret);
    });
  }
  return (
    <input
      name="cnpj"
      required={required}
      value={value}
      onChange={change}
      maxLength={18}
      placeholder="000.000.000-00 ou 00.000.000/0000-00"
      autoComplete="off"
      autoCapitalize="characters"
      spellCheck={false}
      aria-describedby="document-help"
    />
  );
}
