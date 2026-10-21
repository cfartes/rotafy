const alphabet = "abcdefghijklmnopqrstuvwxyz234567";

function encodeSecret(secret: string) {
  const binary = atob(secret.replace(/-/g, "+").replace(/_/g, "/") + "=");
  if (binary.length !== 32 || btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "") !== secret) throw new Error("Bilhete inválido.");
  let bits = 0, value = 0, code = "";
  for (const byte of binary) {
    value = (value << 8) | byte.charCodeAt(0); bits += 8;
    while (bits >= 5) { bits -= 5; code += alphabet[(value >>> bits) & 31]; }
    value &= (1 << bits) - 1;
  }
  if (bits) code += alphabet[(value << (5 - bits)) & 31];
  return code;
}

export function ticketUrl(token: string, origin = window.location.origin) {
  const match = /^bt\.([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.([A-Za-z0-9_-]{43})$/i.exec(token);
  if (!match) return `${origin}/bilhete#token=${encodeURIComponent(token)}`;
  return `${origin}/api/v1/public/bilhete/${match[1].replace(/-/g, "").toLowerCase()}${encodeSecret(match[2])}`;
}

export function ticketToken(raw: string, origin = window.location.origin) {
  const input = raw.trim();
  if (!input.startsWith(origin + "/")) return input;
  const url = new URL(input);
  if (url.pathname === "/bilhete") return new URLSearchParams(url.hash.slice(1)).get("token") || "";
  const match = /^\/(?:b|api\/v1\/public\/bilhete)\/([0-9a-f]{32})([a-z2-7]{52})$/i.exec(url.pathname);
  if (!match) return "";
  const company = match[1].toLowerCase();
  let bits = 0, value = 0, binary = "";
  for (const letter of match[2].toLowerCase()) {
    value = (value << 5) | alphabet.indexOf(letter); bits += 5;
    if (bits >= 8) { bits -= 8; binary += String.fromCharCode((value >>> bits) & 255); }
    value &= (1 << bits) - 1;
  }
  if (binary.length !== 32 || value !== 0) return "";
  const uuid = `${company.slice(0, 8)}-${company.slice(8, 12)}-${company.slice(12, 16)}-${company.slice(16, 20)}-${company.slice(20)}`;
  return `bt.${uuid}.${btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")}`;
}
