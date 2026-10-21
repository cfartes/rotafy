import {
  BookOpen,
  Download,
  FileText,
  Presentation,
  ArrowLeft,
} from "lucide-react";
import "./documentation.css";
import { useEffect, useState } from "react";

function AndroidDownload({ nexus }: { nexus: boolean }) {
  const [release, setRelease] = useState<{ version: string; download_url: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/v1/public/mobile-version?package_id=br.com.nexusdataanalytics.rotafy", { cache: "no-store", credentials: "omit", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error("unavailable");
        const { android } = await response.json();
        if (android && typeof android.version === "string" && typeof android.download_url === "string" && android.download_url.startsWith("/api/v1/public/mobile/download?")) setRelease(android);
      })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
  return <section className="documentation-card" aria-labelledby="android-title">
    <Download size={32} aria-hidden="true" />
    <p className="eyebrow">APLICATIVO DO MOTORISTA E GUIA</p>
    <h2 id="android-title">Aplicativo Android</h2>
    <p>Consulte suas viagens e realize o embarque dos passageiros pelo celular.</p>
    {release ? <>
      <p>Versão disponível: <strong>{release.version}</strong></p>
      <a className="button primary" href={release.download_url} download>Baixar APK Android</a>
      <p>Após baixar, abra o arquivo e autorize a instalação no Android. Para atualizar, sincronize os registros pendentes e instale por cima, sem desinstalar.</p>
      <p className="muted">Este arquivo é compatível com Android. Não instala em iPhone ou iPad.</p>
    </> : <p role="status">{loading ? "Consultando versão disponível…" : failed ? "Não foi possível consultar o download. Confira sua conexão e tente novamente mais tarde." : "O aplicativo estará disponível para download assim que a Nexus publicar a versão."}</p>}
    {nexus && <p>Para disponibilizar o arquivo, publique o APK em <strong>Configurações → Atualizações do aplicativo Android</strong>.</p>}
  </section>;
}

export function Documentation({ nexus = false }: { nexus?: boolean }) {
  const manual = nexus ? "manual-superadmin" : "manual";
  const title = nexus ? "Manual do superadmin Nexus" : "Manual da empresa";
  return (
    <main className="documentation-page">
      <a className="documentation-back" href={nexus ? "/nexus" : "/"}>
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar ao app
      </a>
      <header className="documentation-hero">
        <p className="eyebrow">NEXUS ROTAFY · CENTRAL DE DOCUMENTAÇÃO</p>
        <h1>
          Conheça o sistema.
          <br />
          Prepare sua equipe.
        </h1>
        <p>
          Apresentação das funcionalidades e manual de utilização com
          orientações para gestão, atendimento e operação das viagens.
        </p>
        <span>Edição 2026.10 · Revisão 4 · Atualizado em 15/10/2026</span>
      </header>
      <div className="documentation-grid">
        <AndroidDownload nexus={nexus} />
        <section className="documentation-card" aria-labelledby="manual-title">
          <BookOpen size={32} aria-hidden="true" />
          <p className="eyebrow">CONSULTA E TREINAMENTO</p>
          <h2 id="manual-title">{title}</h2>
          <p>
            {nexus
              ? "Empresas, planos, assinaturas, consumo, atividades e configurações de comunicação."
              : "Instruções para a equipe: cadastros, vendas, operação Android, relatórios e solução de problemas."}
          </p>
          <a className="button primary" href={`/documentacao/${manual}.html`}>
            Ler manual online
          </a>
          <div className="documentation-downloads">
            <a href={`/documentacao/${manual}.pdf`} download={`${manual}.pdf`}>
              <Download size={16} aria-hidden="true" />
              Baixar manual PDF
            </a>
            <a
              href={`/documentacao/${manual}.html`}
              download={`${manual}.html`}
            >
              <FileText size={16} aria-hidden="true" />
              Baixar manual HTML
            </a>
          </div>
          {nexus ? (
            <ul>
              <li>Cadastro e gestão de empresas</li>
              <li>Planos, assinaturas e consumo</li>
              <li>Configurações de comunicação e atividades</li>
            </ul>
          ) : (
            <ul>
              <li>Empresa, equipe, frota, Rotas e viagens</li>
              <li>Reservas, bilhete único, PAGO e mensagens</li>
              <li>Embarque, offline, chegada e relatórios</li>
              <li>Plano contratado e rotina da empresa</li>
            </ul>
          )}
        </section>
        <section
          className="documentation-card"
          aria-labelledby="presentation-title"
        >
          <Presentation size={32} aria-hidden="true" />
          <p className="eyebrow">VISÃO DO PRODUTO</p>
          <h2 id="presentation-title">Apresentação do sistema</h2>
          <p>
            20 slides para apresentar a jornada operacional, os módulos e os
            recursos disponíveis para Turismo e Transporte regular.
          </p>
          <a className="button primary" href="/documentacao/apresentacao.html">
            Ver apresentação online
          </a>
          <div className="documentation-downloads">
            <a
              href="/documentacao/apresentacao.pdf"
              download="apresentacao.pdf"
            >
              <Download size={16} aria-hidden="true" />
              Baixar apresentação PDF
            </a>
            <a
              href="/documentacao/apresentacao.pptx"
              download="apresentacao.pptx"
            >
              <Presentation size={16} aria-hidden="true" />
              Baixar PowerPoint editável
            </a>
            <a
              href="/documentacao/apresentacao.html"
              download="apresentacao.html"
            >
              <FileText size={16} aria-hidden="true" />
              Baixar apresentação HTML
            </a>
          </div>
          <ul>
            <li>Do planejamento à finalização</li>
            <li>Painel multiempresa e Android operacional</li>
            <li>Indicadores e administração SaaS</li>
            <li>Benefícios para a operação</li>
          </ul>
        </section>
      </div>
      <aside className="documentation-scope">
        <strong>Conteúdo da versão atual</strong>
        <p>
          Os materiais apresentam as funcionalidades disponíveis e orientam o
          uso diário do sistema. As imagens e números são demonstrativos. A
          apresentação destaca os benefícios para a empresa, e o manual traz
          instruções para cada perfil de usuário.
        </p>
      </aside>
      <footer className="documentation-footer">
        Nexus Rotafy · Planejamento, atendimento e equipe conectados.
      </footer>
    </main>
  );
}
