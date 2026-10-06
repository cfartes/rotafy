/** Credenciais temporárias separadas por arquivo para respeitar o limite de login. */
export function nexusCredentials(
  file: string,
): { email: string; password: string } | undefined {
  const accounts = process.env.ROTAFY_E2E_NEXUS_ACCOUNTS;
  return accounts ? JSON.parse(accounts)[file] : undefined;
}
