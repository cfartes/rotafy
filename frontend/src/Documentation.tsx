import {
  BookOpen,
  Download,
  FileText,
  Presentation,
  ArrowLeft,
} from "lucide-react";
import "./documentation.css";

export function Documentation() {
  return (
    <main className="documentation-page">
      <a className="documentation-back" href="/">
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
        <span>Edição 2026.10 · Revisão 1 · Atualizado em 09/10/2026</span>
      </header>
      <div className="documentation-grid">
        <section className="documentation-card" aria-labelledby="manual-title">
          <BookOpen size={32} aria-hidden="true" />
          <p className="eyebrow">CONSULTA E TREINAMENTO</p>
          <h2 id="manual-title">Manual de utilização</h2>
          <p>
            26 capítulos com instruções por perfil, exemplos de pacotes,
            operação Android, checklists e solução de problemas.
          </p>
          <a className="button primary" href="/documentacao/manual.html">
            Ler manual online
          </a>
          <div className="documentation-downloads">
            <a href="/documentacao/manual.pdf" download="manual.pdf">
              <Download size={16} aria-hidden="true" />
              Baixar manual PDF
            </a>
            <a href="/documentacao/manual.html" download="manual.html">
              <FileText size={16} aria-hidden="true" />
              Baixar manual HTML
            </a>
          </div>
          <ul>
            <li>Empresa, equipe, frota, Rotas e viagens</li>
            <li>Reservas, bilhete único, PAGO e mensagens</li>
            <li>Embarque, offline, chegada e relatórios</li>
            <li>Administração Nexus e configurações</li>
          </ul>
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
            <li>Escopo atual e próximas etapas</li>
          </ul>
        </section>
      </div>
      <aside className="documentation-scope">
        <strong>Conteúdo da versão atual</strong>
        <p>
          Os materiais distinguem recursos disponíveis, o módulo de página
          pública com menu oculto e as evoluções ainda planejadas. As imagens e
          números são demonstrativos. A documentação não contém credenciais nem
          links privados de passageiros.
        </p>
      </aside>
      <footer className="documentation-footer">
        Nexus Rotafy · Planejamento, atendimento e equipe conectados.
      </footer>
    </main>
  );
}
