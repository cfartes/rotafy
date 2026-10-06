import { Field } from "./ui";
export type PassengerDocuments = {
  is_foreign?: boolean;
  under_five?: boolean;
  birth_date?: string | null;
};
export function PassengerExceptions({
  value,
  index,
  onChange,
}: {
  value: PassengerDocuments;
  index: number;
  onChange: (change: PassengerDocuments) => void;
}) {
  return (
    <div>
      <label className="operation-checkbox">
        <input
          type="checkbox"
          checked={!!value.is_foreign}
          onChange={(e) => onChange({ is_foreign: e.target.checked })}
        />
        Estrangeiro · passageiro {index + 1}
      </label>
      <label className="operation-checkbox">
        <input
          type="checkbox"
          checked={!!value.under_five}
          onChange={(e) => onChange({ under_five: e.target.checked })}
        />
        Menor de 5 anos · passageiro {index + 1}
      </label>
      {value.under_five && (
        <Field label={`Nascimento do passageiro ${index + 1}`}>
          <input
            type="date"
            required
            value={value.birth_date || ""}
            onChange={(e) => onChange({ birth_date: e.target.value || null })}
          />
        </Field>
      )}
    </div>
  );
}
