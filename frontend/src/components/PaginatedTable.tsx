import {
  Children,
  cloneElement,
  isValidElement,
  useId,
  useState,
  type ReactNode,
  type ReactElement,
  type TableHTMLAttributes,
} from "react";

const TABLE_PAGE_SIZE = 20;

// Keep totals and exports outside pagination; only rendered body rows are sliced.
export function PaginatedTable({
  children,
  ...props
}: TableHTMLAttributes<HTMLTableElement>) {
  const id = useId();
  const sections = Children.toArray(children);
  const body = sections.find(
    (child) => isValidElement(child) && child.type === "tbody",
  ) as ReactElement<{ children: ReactNode }> | undefined;
  const rows = Children.toArray(body?.props.children);
  const signature = rows
    .map((row) => (isValidElement(row) ? row.key : ""))
    .join("|");
  const [selection, setSelection] = useState({ signature, page: 1 });
  if (selection.signature !== signature) setSelection({ signature, page: 1 });
  const page = selection.signature === signature ? selection.page : 1;
  const pages = Math.max(1, Math.ceil(rows.length / TABLE_PAGE_SIZE));
  const current = Math.min(page, pages);
  return (
    <>
      <table {...props} id={props.id || id}>
        {sections.map((section) =>
          section === body
            ? cloneElement(
                body!,
                {},
                rows.slice(
                  (current - 1) * TABLE_PAGE_SIZE,
                  current * TABLE_PAGE_SIZE,
                ),
              )
            : section,
        )}
      </table>
      {rows.length > TABLE_PAGE_SIZE && (
        <nav className="table-pagination" aria-label="Paginação da tabela">
          <button
            type="button"
            className="button secondary"
            aria-controls={props.id || id}
            disabled={current === 1}
            onClick={() => setSelection({ signature, page: current - 1 })}
          >
            Anterior
          </button>
          <span role="status">
            Página {current} de {pages} · {(current - 1) * TABLE_PAGE_SIZE + 1}–
            {Math.min(current * TABLE_PAGE_SIZE, rows.length)} de {rows.length}{" "}
            registros
          </span>
          <button
            type="button"
            className="button secondary"
            aria-controls={props.id || id}
            disabled={current === pages}
            onClick={() => setSelection({ signature, page: current + 1 })}
          >
            Próxima página
          </button>
        </nav>
      )}
    </>
  );
}
