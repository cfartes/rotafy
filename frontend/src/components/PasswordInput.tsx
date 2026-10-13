import { useState, type InputHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";

export function PasswordInput(
  props: Omit<InputHTMLAttributes<HTMLInputElement>, "type">,
) {
  const [visible, setVisible] = useState(false);
  const action = visible ? "Ocultar senha" : "Mostrar senha";
  return (
    <span className="password-input">
      <input
        {...props}
        type={visible ? "text" : "password"}
        spellCheck={false}
        autoCapitalize="none"
        autoCorrect="off"
      />
      <button
        type="button"
        className="password-toggle"
        aria-label={action}
        title={action}
        aria-pressed={visible}
        disabled={props.disabled}
        onClick={(event) => {
          event.preventDefault();
          setVisible(!visible);
        }}
      >
        {visible ? (
          <EyeOff size={20} aria-hidden="true" />
        ) : (
          <Eye size={20} aria-hidden="true" />
        )}
      </button>
    </span>
  );
}
