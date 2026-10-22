import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  MessageCircle,
  Paperclip,
  RefreshCw,
  Reply,
  Search,
  Send,
  X,
} from "lucide-react";
import { api, post } from "./api";
import { Alert, Field, Modal } from "./components/ui";
import { PhoneInput } from "./components/PhoneInput";
import "./whatsapp-chat.css";

type Chat = {
  id: string;
  name: string;
  is_group: boolean;
  unread_count: number;
  timestamp: number;
  preview: string;
};
type Message = {
  id: string;
  body: string;
  type: string;
  timestamp: number;
  created_at: string;
  from_me: boolean;
  status: string;
  author: string;
  has_media: boolean;
  mimetype: string;
};
type Delivery = {
  id: string;
  operation_key: string;
  status: string;
  attempts: number;
  error_code: string | null;
  created_at: string;
};
type History = {
  messages: Message[];
  next_cursor: string | null;
  deliveries: Delivery[];
  can_send: boolean;
  notice?: string | null;
};
type Attachment = { filename: string; mimetype: string; base64: string };
type Draft = { text: string; attachment?: Attachment; quote?: Message };
const deliveryLabel: Record<string, string> = {
  pending: "Na fila",
  sending: "Enviando",
  sent: "Aceita pelo WhatsApp",
  failed: "Falha no envio",
  uncertain: "Envio incerto — confira a conversa antes de enviar novamente",
  discarded: "Envio cancelado ou expirado",
};
const errorText = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Não foi possível concluir a operação.";
const stamp = (m: Pick<Message, "timestamp" | "created_at">) =>
  m.timestamp ? m.timestamp * 1000 : Date.parse(m.created_at) || 0;
const clock = (value: number) =>
  value
    ? new Date(value).toLocaleTimeString("pt-BR", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";
const date = (value: number) =>
  value ? new Date(value).toLocaleDateString("pt-BR") : "";
const normalize = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
const emptyDraft: Draft = { text: "" };

function MessageMedia({ chat, message }: { chat: string; message: Message }) {
  const [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const url = `/api/v1/whatsapp/chat/media?${new URLSearchParams({ chat, message: message.id })}`;
  const kind = message.mimetype.split("/")[0] || message.type;
  if (error) return <p className="chat-media-notice">{error}</p>;
  if (!open)
    return (
      <button className="chat-media-button" onClick={() => setOpen(true)}>
        {kind === "image" || message.type === "sticker"
          ? "Ver imagem"
          : ["audio", "voice", "ptt"].includes(kind)
            ? "Ouvir áudio"
            : kind === "video"
              ? "Ver vídeo"
              : "Abrir anexo"}
      </button>
    );
  const unavailable = () =>
    setError("Esta mídia não está disponível no histórico do serviço.");
  if (kind === "image" || message.type === "sticker")
    return (
      <a href={url} target="_blank" rel="noreferrer">
        <img
          className="chat-image"
          src={url}
          alt="Imagem da conversa"
          onError={unavailable}
        />
      </a>
    );
  if (["audio", "voice", "ptt"].includes(kind))
    return (
      <audio
        controls
        preload="none"
        src={url}
        onError={unavailable}
        aria-label="Áudio da conversa"
      />
    );
  if (kind === "video")
    return (
      <video
        className="chat-image"
        controls
        preload="metadata"
        src={url}
        onError={unavailable}
      />
    );
  return (
    <a
      className="chat-media-button"
      href={url}
      target="_blank"
      rel="noreferrer"
    >
      Baixar anexo
    </a>
  );
}

export function WhatsAppChat({
  canConfigure,
  onConfigure,
}: {
  canConfigure: boolean;
  onConfigure: () => void;
}) {
  const cache = useQueryClient();
  const [limit, setLimit] = useState(50),
    [search, setSearch] = useState(""),
    [messageSearch, setMessageSearch] = useState("");
  const [selected, setSelected] = useState<Chat | null>(null),
    [newChat, setNewChat] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [older, setOlder] = useState<{
    rows: Message[];
    cursor?: string | null;
  }>({ rows: [] });
  const [sending, setSending] = useState(false),
    [loadingOlder, setLoadingOlder] = useState(false);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const submission = useRef<{ payload: string; key: string } | null>(null);
  const currentChat = useRef<string | null>(null);
  currentChat.current = selected?.id || null;
  const scroller = useRef<HTMLDivElement>(null),
    file = useRef<HTMLInputElement>(null),
    pinned = useRef(true);
  const chats = useQuery({
    queryKey: ["whatsapp-chats", limit],
    queryFn: () =>
      api<{ chats: Chat[]; can_send: boolean; has_more: boolean }>(
        `/whatsapp/chat/chats?limit=${limit}`,
      ),
    refetchInterval: 10000,
    retry: false,
  });
  const handoffs = useQuery({
    queryKey: ["whatsapp-handoffs"],
    queryFn: () =>
      api<{ chat_id: string; phone: string | null; handoff_at: string }[]>(
        "/whatsapp/chat/handoffs",
      ),
    refetchInterval: 10000,
  });
  async function finishHandoff(chat_id: string) {
    try {
      await post("/whatsapp/chat/handoffs/close", { chat_id });
      await cache.invalidateQueries({ queryKey: ["whatsapp-handoffs"] });
    } catch (e) {
      setError(errorText(e));
    }
  }
  const history = useQuery({
    queryKey: ["whatsapp-messages", selected?.id],
    queryFn: () =>
      api<History>(
        `/whatsapp/chat/messages?${new URLSearchParams({ chat: selected!.id })}`,
      ),
    enabled: !!selected,
    refetchInterval: 5000,
    retry: false,
  });
  const draft = selected ? drafts[selected.id] || emptyDraft : emptyDraft;
  function updateDraft(value: Partial<Draft>) {
    if (selected)
      setDrafts((previous) => ({
        ...previous,
        [selected.id]: { ...(previous[selected.id] || emptyDraft), ...value },
      }));
  }
  function choose(chat: Chat) {
    setSelected(chat);
    setOlder({ rows: [] });
    setMessageSearch("");
    setError("");
    setNotice("");
    pinned.current = true;
  }
  const list = useMemo(
    () =>
      chats.data?.chats.filter((c) =>
        normalize(`${c.name} ${c.id} ${c.preview}`).includes(normalize(search)),
      ) || [],
    [chats.data, search],
  );
  const messages = useMemo(() => {
    const rows = new Map<string, Message>();
    for (const m of [...older.rows, ...(history.data?.messages || [])])
      rows.set(m.id, m);
    return [...rows.values()]
      .sort((a, b) => stamp(a) - stamp(b) || a.id.localeCompare(b.id))
      .filter((m) => normalize(m.body).includes(normalize(messageSearch)));
  }, [history.data, older.rows, messageSearch]);
  const messageTail = messages.at(-1)?.id;
  useEffect(() => {
    if (pinned.current && scroller.current && !messageSearch)
      scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [selected?.id, messageTail, messageSearch]);
  async function refresh() {
    await Promise.all([
      chats.refetch(),
      selected ? history.refetch() : Promise.resolve(),
    ]);
  }
  async function loadOlder() {
    const cursor =
      older.cursor === undefined ? history.data?.next_cursor : older.cursor;
    if (!selected || !cursor) return;
    const active = selected.id;
    setLoadingOlder(true);
    setError("");
    try {
      const page = await api<History>(
        `/whatsapp/chat/messages?${new URLSearchParams({ chat: active, after: cursor })}`,
      );
      if (currentChat.current !== active) return;
      setOlder((previous) => ({
        rows: [...page.messages, ...previous.rows],
        cursor: page.next_cursor === cursor ? null : page.next_cursor,
      }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoadingOlder(false);
    }
  }
  async function attach(chosen?: File) {
    if (!chosen) return;
    setError("");
    if (chosen.size > 2 * 1024 * 1024) {
      setError("O anexo pode ter até 2 MB.");
      return;
    }
    const mimetype = chosen.type === "audio/x-wav" ? "audio/wav" : chosen.type;
    try {
      const content = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1]);
        reader.onerror = reject;
        reader.readAsDataURL(chosen);
      });
      updateDraft({
        attachment: { filename: chosen.name, mimetype, base64: content },
      });
    } catch {
      setError("Não foi possível abrir o anexo.");
    }
    if (file.current) file.current.value = "";
  }
  async function send(event?: FormEvent) {
    event?.preventDefault();
    if (!selected || sending || (!draft.text.trim() && !draft.attachment))
      return;
    const id = selected.id;
    const payload = {
      chat_id: id,
      text: draft.text.trim(),
      attachment: draft.attachment || null,
      quoted_message_id: draft.quote?.id || null,
    };
    const encoded = JSON.stringify(payload);
    if (submission.current?.payload !== encoded)
      submission.current = { payload: encoded, key: crypto.randomUUID() };
    setSending(true);
    setError("");
    setNotice("");
    try {
      await post("/whatsapp/chat/send", {
        ...payload,
        operation_key: submission.current!.key,
      });
      setDrafts((previous) => ({ ...previous, [id]: emptyDraft }));
      submission.current = null;
      setNotice(
        "Mensagem adicionada à fila. Acompanhe o envio abaixo; novas mensagens aparecerão automaticamente.",
      );
      await cache.invalidateQueries({ queryKey: ["whatsapp-messages", id] });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSending(false);
    }
  }
  return (
    <section
      className={`whatsapp-chat ${selected ? "has-selection" : ""}`}
      aria-label="Conversas WhatsApp"
    >
      <header className="chat-toolbar">
        <div>
          <h2>Conversas WhatsApp</h2>
          <p>
            Atendimento pelo número conectado da empresa. As mensagens são
            atualizadas automaticamente.
          </p>
        </div>
        <div className="chat-tools">
          <button
            className="button secondary"
            onClick={() => setNewChat(true)}
            disabled={!chats.data}
          >
            <MessageCircle size={17} />
            Nova conversa
          </button>
          <button
            className="button secondary"
            onClick={() => void refresh()}
            disabled={chats.isFetching || history.isFetching}
          >
            <RefreshCw size={17} />
            Atualizar
          </button>
          {canConfigure && (
            <button className="button secondary" onClick={onConfigure}>
              Conexão WhatsApp
            </button>
          )}
        </div>
      </header>
      {!!handoffs.data?.length && (
        <div className="chat-handoffs" role="status">
          <strong>Solicitações de atendimento</strong>
          {handoffs.data.map((h) => (
            <div key={h.chat_id}>
              <button
                className="button secondary"
                onClick={() =>
                  choose(
                    chats.data?.chats.find((c) => c.id === h.chat_id) || {
                      id: h.chat_id,
                      name: h.phone || "Cliente",
                      preview: "",
                      is_group: false,
                      unread_count: 0,
                      timestamp: 0,
                    },
                  )
                }
              >
                Abrir conversa de {h.phone || "cliente"}
              </button>
              <button
                className="button secondary"
                onClick={() => void finishHandoff(h.chat_id)}
              >
                Concluir atendimento de {h.phone || "cliente"}
              </button>
            </div>
          ))}
        </div>
      )}
      {chats.error && <Alert>{errorText(chats.error)}</Alert>}
      <div className="chat-workspace">
        <aside className="chat-sidebar" aria-label="Lista de conversas">
          <label className="chat-search">
            <Search size={17} />
            <input
              aria-label="Pesquisar conversas"
              placeholder="Nome, telefone ou conversa"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <div className="chat-contact-list">
            {chats.isPending && (
              <p className="chat-empty">Carregando conversas…</p>
            )}
            {list.map((c) => (
              <button
                key={c.id}
                className={`chat-contact ${selected?.id === c.id ? "selected" : ""}`}
                onClick={() => choose(c)}
              >
                <span className="chat-avatar" aria-hidden="true">
                  {c.is_group ? "G" : c.name.slice(0, 2).toUpperCase()}
                </span>
                <span className="chat-contact-text">
                  <strong>{c.name}</strong>
                  <small>
                    {c.preview || (c.is_group ? "Grupo" : "Conversa")}
                  </small>
                </span>
                <span className="chat-contact-meta">
                  <time>{clock(c.timestamp * 1000)}</time>
                  {c.unread_count > 0 && (
                    <span
                      className="chat-unread"
                      aria-label={`${c.unread_count} não lidas`}
                    >
                      {c.unread_count}
                    </span>
                  )}
                </span>
              </button>
            ))}
            {!chats.isPending && !chats.error && !list.length && (
              <p className="chat-empty">
                Nenhuma conversa encontrada. Você pode iniciar uma nova pelo
                telefone.
              </p>
            )}
            {chats.data?.has_more && limit < 500 && (
              <button
                className="button secondary"
                onClick={() => setLimit((n) => Math.min(n + 50, 500))}
              >
                Carregar mais conversas
              </button>
            )}
          </div>
        </aside>
        <div className="chat-thread">
          {!selected ? (
            <div className="chat-empty chat-welcome">
              <MessageCircle size={42} />
              <h3>Selecione uma conversa</h3>
              <p>Leia o histórico e responda aos clientes por aqui.</p>
            </div>
          ) : (
            <>
              <header className="chat-thread-heading">
                <button
                  className="icon-button chat-mobile-back"
                  aria-label="Voltar às conversas"
                  onClick={() => setSelected(null)}
                >
                  <ArrowLeft size={20} />
                </button>
                <div>
                  <h3>{selected.name}</h3>
                  <small>
                    {selected.is_group
                      ? "Grupo"
                      : selected.id.endsWith("@lid")
                        ? "Contato WhatsApp"
                        : `+${selected.id.split("@")[0]}`}
                  </small>
                </div>
                <label className="chat-search">
                  <Search size={16} />
                  <input
                    aria-label="Pesquisar no histórico carregado"
                    placeholder="Pesquisar no histórico"
                    value={messageSearch}
                    onChange={(e) => setMessageSearch(e.target.value)}
                  />
                </label>
              </header>
              {history.error && <Alert>{errorText(history.error)}</Alert>}
              {history.data?.notice && (
                <p className="chat-notice">{history.data.notice}</p>
              )}
              <div
                className="chat-messages"
                ref={scroller}
                onScroll={() => {
                  const el = scroller.current!;
                  pinned.current =
                    el.scrollHeight - el.scrollTop - el.clientHeight < 80;
                }}
                aria-label="Histórico da conversa"
              >
                {(older.cursor === undefined
                  ? history.data?.next_cursor
                  : older.cursor) && (
                  <button
                    className="button secondary chat-load-older"
                    disabled={loadingOlder}
                    onClick={() => void loadOlder()}
                  >
                    {loadingOlder
                      ? "Carregando…"
                      : "Carregar mensagens anteriores"}
                  </button>
                )}
                {history.isPending && (
                  <p className="chat-empty" role="status">
                    Carregando histórico…
                  </p>
                )}
                {!history.isPending && !history.error && !messages.length && (
                  <p className="chat-empty">
                    Nenhuma mensagem no histórico carregado.
                  </p>
                )}
                {messages.map((m, i) => (
                  <div key={m.id}>
                    {(i === 0 ||
                      date(stamp(messages[i - 1])) !== date(stamp(m))) && (
                      <div className="chat-date">{date(stamp(m))}</div>
                    )}
                    <article
                      className={`chat-bubble ${m.from_me ? "outgoing" : "incoming"}`}
                      aria-label={
                        m.from_me ? "Mensagem enviada" : "Mensagem recebida"
                      }
                    >
                      {selected.is_group && !m.from_me && m.author && (
                        <small className="chat-author">
                          {m.author.split("@")[0]}
                        </small>
                      )}
                      {m.has_media && (
                        <MessageMedia chat={selected.id} message={m} />
                      )}
                      {m.body && <p>{m.body}</p>}
                      {!m.body && !m.has_media && (
                        <p className="muted">
                          {m.type === "revoked"
                            ? "Mensagem apagada no WhatsApp"
                            : "Mensagem disponível no WhatsApp"}
                        </p>
                      )}
                      <footer>
                        <time>{clock(stamp(m))}</time>
                        {m.from_me && (
                          <span>
                            {(
                              {
                                sent: "Enviada",
                                delivered: "Entregue",
                                read: "Lida",
                                pending: "Pendente",
                                failed: "Falhou",
                              } as Record<string, string>
                            )[m.status] || ""}
                          </span>
                        )}
                        <button
                          type="button"
                          aria-label={`Responder à mensagem ${m.body.slice(0, 40) || "com anexo"}`}
                          onClick={() => updateDraft({ quote: m })}
                        >
                          <Reply size={15} />
                        </button>
                      </footer>
                    </article>
                  </div>
                ))}
              </div>
              <form className="chat-composer" onSubmit={(e) => void send(e)}>
                {(error || notice) && (
                  <div
                    role={error ? "alert" : "status"}
                    className="chat-notice"
                  >
                    {error || notice}
                  </div>
                )}
                {history.data?.deliveries.slice(0, 3).map((d) => (
                  <p className={`chat-send-status ${d.status}`} key={d.id}>
                    {clock(Date.parse(d.created_at))} ·{" "}
                    {deliveryLabel[d.status] || d.status}
                    {d.status === "pending" &&
                    d.error_code === "session_not_ready"
                      ? " · aguardando conexão"
                      : ""}
                  </p>
                ))}
                {draft.quote && (
                  <div className="chat-draft-note">
                    <Reply size={16} />
                    <span>Respondendo: {draft.quote.body || "Anexo"}</span>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label="Cancelar resposta"
                      onClick={() => updateDraft({ quote: undefined })}
                    >
                      <X size={16} />
                    </button>
                  </div>
                )}
                {draft.attachment && (
                  <div className="chat-draft-note">
                    <Paperclip size={16} />
                    <span>{draft.attachment.filename}</span>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label="Remover anexo"
                      onClick={() => updateDraft({ attachment: undefined })}
                    >
                      <X size={16} />
                    </button>
                  </div>
                )}
                {history.data?.can_send === false && (
                  <p className="chat-notice">
                    Envios desabilitados. Peça ao administrador para conferir a
                    conexão do WhatsApp.
                  </p>
                )}
                <div className="chat-compose-row">
                  <input
                    ref={file}
                    type="file"
                    accept="image/jpeg,image/png,image/gif,image/webp,application/pdf,audio/mpeg,audio/ogg,audio/wav,video/mp4"
                    hidden
                    onChange={(e) => void attach(e.target.files?.[0])}
                  />
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Anexar arquivo de até 2 MB"
                    title="Imagens, PDF, áudio ou MP4 — até 2 MB"
                    disabled={sending || !history.data?.can_send}
                    onClick={() => file.current?.click()}
                  >
                    <Paperclip size={21} />
                  </button>
                  <textarea
                    aria-label="Mensagem"
                    placeholder="Digite uma mensagem…"
                    rows={2}
                    maxLength={draft.attachment ? 1024 : 4096}
                    value={draft.text}
                    disabled={sending || !history.data?.can_send}
                    onChange={(e) => updateDraft({ text: e.target.value })}
                    onKeyDown={(e) => {
                      if (
                        e.key === "Enter" &&
                        !e.shiftKey &&
                        !e.nativeEvent.isComposing
                      ) {
                        e.preventDefault();
                        void send();
                      }
                    }}
                  />
                  <button
                    className="button primary"
                    aria-label="Enviar mensagem"
                    disabled={
                      sending ||
                      !history.data?.can_send ||
                      (!draft.text.trim() && !draft.attachment)
                    }
                  >
                    <Send size={20} />
                    <span>{sending ? "Enfileirando…" : "Enviar"}</span>
                  </button>
                </div>
                <small className="chat-compose-help">
                  Enter envia · Shift + Enter quebra a linha · Anexos até 2 MB ·
                  Envios pendentes expiram em 30 minutos
                </small>
              </form>
            </>
          )}
        </div>
      </div>
      {newChat && (
        <NewConversation
          onClose={() => setNewChat(false)}
          onChoose={(c) => {
            choose(c);
            setNewChat(false);
          }}
        />
      )}
    </section>
  );
}

function NewConversation({
  onClose,
  onChoose,
}: {
  onClose: () => void;
  onChoose: (chat: Chat) => void;
}) {
  const [pending, setPending] = useState(false),
    [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setPending(true);
    setError("");
    try {
      onChoose(
        await post<Chat>("/whatsapp/chat/resolve", {
          contact_phone: data.get("contact_phone"),
        }),
      );
    } catch (e) {
      setError(errorText(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title="Nova conversa WhatsApp" onClose={onClose}>
      <form className="modal-form" onSubmit={(e) => void submit(e)}>
        <p>
          Informe o telefone com DDD. O número será conferido no WhatsApp antes
          de abrir a conversa.
        </p>
        <Field label="Telefone do contato">
          <PhoneInput required />
        </Field>
        {error && <Alert>{error}</Alert>}
        <button className="button primary" disabled={pending}>
          {pending ? "Conferindo…" : "Abrir conversa"}
        </button>
      </form>
    </Modal>
  );
}
