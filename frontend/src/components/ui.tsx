import { useEffect, useRef, useId, type ReactNode } from "react";
import { CircleAlert, X } from "lucide-react";

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="alert" role="alert">
      <CircleAlert size={19} aria-hidden="true" className="alert-icon" />
      <div className="alert-message">{children}</div>
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current!;
    const trigger =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    dialog.showModal();
    return () => {
      dialog.close();
      if (trigger?.isConnected) trigger.focus({ preventScroll: true });
    };
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      aria-labelledby={titleId}
      className={wide ? "rotafy-modal modal-wide" : "rotafy-modal"}
    >
      <header className="modal-header">
        <h2 id={titleId}>{title}</h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Fechar"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
