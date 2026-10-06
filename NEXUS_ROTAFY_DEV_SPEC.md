# NEXUS ROTAFY — ESPECIFICAÇÃO TÉCNICA E PLANO DE DESENVOLVIMENTO
> Plataforma Web Responsiva White-Label para Embarque Rápido, Telemetria e Rastreamento em Turismo Receptivo e Fretamento.

---

## 1. VISÃO GERAL DO PRODUTO

O **Nexus Rotafy** é uma aplicação web unificada, moderna e responsiva (Mobile-First / PWA), sem necessidade de instalação via lojas de aplicativos (Google Play Store ou Apple App Store). A plataforma atende agências de turismo, empresas de receptivo e fretamento de vans e ônibus.

### Pilares Fundamentais:
1. **Passageiro:** Acesso direto via link exclusivo enviado por WhatsApp, exibindo mapa em tempo real com previsão de chegada (ETA), alertas e bilhete digital com QR Code.
2. **Guia / Operador:** Validação de embarque por leitura de QR Code via câmera do celular ou check-in de contingência em lista offline, acompanhado de painel de presença em tempo real ("28 embarcados / 4 pendentes") e contato rápido via WhatsApp para passageiros ausentes.
3. **Motorista / Telemetria:** Transmissão de localização contínua diretamente pelo navegador do celular do motorista (Modo Viagem) no MVP, com pipeline desacoplado e preparado para recepção de dados via hardware OBD2/GPS fixo.
4. **Agência (White-Label):** Painel web administrativo para gestão de viagens, importação flexível de passageiros (planilha, formulário ou API/Webhook) e personalização da marca com upload de logotipo da empresa contratante.

---

## 2. SISTEMA DE DESIGN & IDENTIDADE VISUAL (60-30-10)

A interface aplica uma hierarquia cromática estrita para manter alto contraste, clareza operacional sob luz solar e identidade visual refinada:

* **60% — Azul Oceano (Dominante / Background e Estrutura):**
  * `Ocean 950`: `#061320` (Fundo primário escuro para navegação e modo noturno).
  * `Ocean 900`: `#0A2540` (Headers institucionais, topbars e tipografia densa).
  * `Ocean 800`: `#153E65` (Bordas de cards, divisórias e superfícies de destaque neutro).
  * `Ocean 50`: `#F0F6FA` (Background de telas claras para passageiro e relatórios).
* **30% — Turquesa / Verde Água (Secundária / Ação Positiva & Status):**
  * `Turquoise 600`: `#0F766E` (Estados de foco e cabeçalhos operacionais secundários).
  * `Turquoise 500`: `#14B8A6` (Status "Embarcado", ícone do veículo ativo no mapa, botões de ação do guia, validações de sucesso).
  * `Turquoise 50`: `#F0FDFA` (Fundo de cards de bilhetes validados e badges neutros).
* **10% — Laranja Coral (Acento / Alertas e Ações Críticas):**
  * `Coral 600`: `#EA580C` (Estados de clique em botões críticos).
  * `Coral 500`: `#FF6B4A` (Status "Pendente", alerta "Chegamos em 5 minutos", botões de chamada urgente de ausentes, mira do scanner QR Code).
  * `Coral 50`: `#FFF7ED` (Fundo de avisos de atenção e atraso).

### Configuração de Estilo (`tailwind.config.js`):
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ocean: {
          50: '#F0F6FA',
          100: '#D9E6F2',
          700: '#1E4E7E',
          800: '#153E65',
          900: '#0A2540',
          950: '#061320',
        },
        turquoise: {
          50: '#F0FDFA',
          100: '#CCFBF1',
          400: '#2DD4BF',
          500: '#14B8A6',
          600: '#0F766E',
        },
        coral: {
          50: '#FFF7ED',
          100: '#FFEDD5',
          400: '#FB923C',
          500: '#FF6B4A',
          600: '#EA580C',
        },
      },
    },
  },
  plugins: [],
}

ARQUITETURA DO SISTEMA E STACK TECNOLÓGICA
+------------------------------------------+
                   |          AGÊNCIA / PASSAGEIRO / GUIA     |
                   |       Web App Responsiva (PWA / Vue 3)    |
                   +---------------------+--------------------+
                                         |
                       HTTPS / REST      |      WebSockets (WSS)
                                         v
                   +------------------------------------------+
                   |             API GATEWAY                  |
                   |      Traefik Reverse Proxy (SSL)         |
                   +---------------------+--------------------+
                                         |
                                         v
                   +------------------------------------------+
                   |           BACKEND FASTAPI                |
                   |       (Python 3.11+ / Async / Celery)    |
                   +----------+--------------------+----------+
                              |                    |
            PostGIS Queries   |                    | Pub/Sub & Telemetry Cache
                              v                    v
                   +--------------------+   +-----------------+
                   |   PostgreSQL 16    |   |     Redis 7     |
                   |   (+ PostGIS)      |   | (Queue / Cache) |
                   +--------------------+   +-----------------+
                                                     ^
                                                     |
                                   +-----------------+-----------------+
                                   |                                   |
                         +-------------------+               +-------------------+
                         | Celery Background |               | Telemetria OBD2   |
                         | Worker (WhatsApp) |               | Ingestor (Futuro) |
                         +-------------------+               +-------------------+
						 
Frontend: Single Page Application (SPA) / Progressive Web App (PWA) em Vue.js 3 (Composition API) ou React com Tailwind CSS e Vite.

Backend: FastAPI (Python 3.11+) com SQLAlchemy 2.0 (Asyncpg) e Pydantic v2.

Banco de Dados Relacional & Espacial: PostgreSQL 16 com extensão PostGIS (cálculo de rotas, geofence de proximidade e coordenadas).

Cache & Message Broker: Redis 7 (broker do Celery para disparos WhatsApp e pub/sub de telemetria em alta frequência).

Mapas e Renderização: MapLibre GL JS / Leaflet com tiles leves vetoriais.

Leitura QR Code no Navegador: html5-qrcode com suporte a WebRTC e aceleração via GPU.

Persistência Offline: Dexie.js (IndexedDB local no browser do guia).

4. MODELO WHITE-LABEL E MULTITENANCY
Toda entidade no banco é vinculada a uma company_id. A renderização das páginas públicas de passageiro e painéis administrativos adapta automaticamente:

Logotipo da Agência: Armazenado em bucket/storage e exibido no topo do bilhete e painéis.

Nome Comercial: Utilizado no corpo das mensagens de WhatsApp e títulos.

Cores Secundárias Customizadas: Variáveis CSS --company-primary e --company-accent injetadas no header da página HTML, mantendo como padrão o design do sistema.

Assinatura Discreta: Selo "Powered by Nexus Rotafy" exibido no rodapé.



MODELAGEM DO BANCO DE DADOS (POSTGRESQL + POSTGIS)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 1. Agências / Empresas (Tenants)
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    corporate_name VARCHAR(150) NOT NULL,
    trade_name VARCHAR(150) NOT NULL,
    cnpj VARCHAR(14) UNIQUE NOT NULL,
    subdomain VARCHAR(50) UNIQUE,
    logo_url TEXT,
    primary_color VARCHAR(7) DEFAULT '#0A2540',
    accent_color VARCHAR(7) DEFAULT '#FF6B4A',
    whatsapp_phone_number_id VARCHAR(50),
    whatsapp_access_token TEXT,
    plan VARCHAR(30) DEFAULT 'basic', -- basic, pro, enterprise
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Veículos da Frota
CREATE TABLE vehicles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    plate VARCHAR(10) NOT NULL,
    model VARCHAR(50) NOT NULL,
    capacity INT NOT NULL,
    tracking_source VARCHAR(20) DEFAULT 'mobile_web', -- 'mobile_web' ou 'obd2_hardware'
    obd2_device_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Viagens / Roteiros
CREATE TABLE trips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    vehicle_id UUID REFERENCES vehicles(id),
    destination VARCHAR(150) NOT NULL,
    trip_date DATE NOT NULL,
    scheduled_departure TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) DEFAULT 'scheduled', -- 'scheduled', 'in_progress', 'completed', 'cancelled'
    trip_token VARCHAR(64) UNIQUE NOT NULL, -- Token de controle para guia e motorista
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Pontos de Embarque (Hotéis, Pousadas, Pontos de Encontro)
CREATE TABLE boarding_points (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    sequence_order INT NOT NULL,
    coordinates GEOGRAPHY(Point, 4326),
    geofence_radius_meters INT DEFAULT 450,
    scheduled_time TIMESTAMP WITH TIME ZONE,
    proximity_alert_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Passageiros / Bilhetes
CREATE TABLE passengers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    boarding_point_id UUID REFERENCES boarding_points(id),
    full_name VARCHAR(150) NOT NULL,
    cpf VARCHAR(11) NOT NULL,
    phone VARCHAR(20) NOT NULL, -- Padrão E.164 (+55...)
    destination VARCHAR(120),
    seat_number VARCHAR(10),
    ticket_token VARCHAR(64) UNIQUE NOT NULL, -- Token criptográfico acessado via link
    boarding_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'boarded', 'absent'
    boarded_at TIMESTAMP WITH TIME ZONE,
    boarded_offline BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Telemetria Unificada (Buffer)
CREATE TABLE vehicle_telemetry (
    id BIGSERIAL PRIMARY KEY,
    vehicle_id UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    trip_id UUID REFERENCES trips(id) ON DELETE SET NULL,
    coordinates GEOGRAPHY(Point, 4326) NOT NULL,
    speed NUMERIC(5,2),
    heading NUMERIC(5,2),
    source VARCHAR(20) NOT NULL, -- 'mobile_web' ou 'obd2_hardware'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_passengers_token ON passengers(ticket_token);
CREATE INDEX idx_telemetry_trip ON vehicle_telemetry(trip_id, created_at DESC);
CREATE INDEX idx_boarding_geofence ON boarding_points USING GIST(coordinates);

MÓDULOS FUNCIONAIS DETALHADOS
MÓDULO 1: Painel Administrativo da Agência (Backoffice Web)
Dashboard de Viagens: Listagem cronológica de saídas, status dos veículos, resumo de passageiros embarcados e pendentes.

Configuração White-Label:

Formulário com upload de imagem para logotipo (PNG/SVG com transparência).

Configuração de dados de contato e dados para envio de mensagens via WhatsApp.

Ingestão Tríplice de Passageiros:

Upload de Planilha (.xlsx ou .csv):

Layout aceito: nome_completo, cpf, destino, telefone, ponto_embarque, poltrona (opcional).

Mapeamento tolerante de colunas e normalização instantânea de número para padrão E.164 internacional (+55...).

Validação estrita de CPF (11 dígitos válidos).

Cadastro Rápido Manual: Modal direto no painel da agência com validações em tempo real para inclusão de passageiros de última hora.

Endpoint Webhook / API REST: Rota POST /api/v1/integrations/trips/{trip_id}/passengers autenticada por X-API-KEY para integração com sistemas de reserva, e-commerce ou landing pages existentes.

Automação de Disparo WhatsApp: Botão com um clique para disparar o lote de mensagens aos passageiros cadastrados com o link do bilhete digital.

MÓDULO 2: Modo Guia de Embarque (Web Mobile-First Offline)
Acesso: URL simplificada autenticada por token operacional: rotafy.app/guia/{trip_token}.

Persistência Offline-First (IndexedDB via Dexie.js):

Ao carregar a viagem com conexão, o navegador baixa o manifesto completo dos passageiros daquele dia.

Em áreas sem sinal de internet (praias isoladas ou serras), as leituras de QR Code e confirmações manuais continuam funcionando normalmente na base local.

Validação por Câmera:

Uso da biblioteca html5-qrcode com feedback sonoro (beep) e tátil (vibração).

Leitura e conferência instantânea do ticket_token no banco local.

Alteração visual imediata do status para "Embarcado" (verde água/turquesa) com indicação da poltrona.

Painel de Chamada ao Vivo:

Indicador no topo da tela: 28 embarcados / 4 pendentes.

Busca e filtro rápido por nome ou poltrona.

Check-in de contingência manual: toque de confirmação na lista para casos de passageiro sem bateria ou sem celular.

Acionamento direto de ausentes: botão individual que abre diretamente o WhatsApp no contato do passageiro (wa.me/55...) com texto pronto de chamada.

Motor de Sincronização:

Fila de eventos sync_queue no IndexedDB.

O navegador detecta o retorno de rede (navigator.onLine) e envia os check-ins acumulados de forma idempotente para o endpoint POST /api/v1/trips/{id}/sync-boardings.

MÓDULO 3: Modo Motorista (Transmissor de Telemetria Web)
Acesso: rotafy.app/motorista/{trip_token} com interface minimalista focada em segurança.

Operação em Dois Toques: Botão central "INICIAR ROTA" e "FINALIZAR ROTA".

Captura Contínua de GPS:

Utilização da Web Geolocation API: navigator.geolocation.watchPosition com enableHighAccuracy: true.

Filtro inteligente: emissão das coordenadas via WebSocket ou POST leve apenas a cada 4 segundos ou 15 metros de deslocamento real, evitando tráfego de dados desnecessário.

Screen WakeLock API:

Implementação de navigator.wakeLock.request('screen') para impedir que o sistema operacional (Android ou iOS) desligue a tela do celular durante o trajeto, evitando a suspensão de segundo plano do navegador.

Preparação para Hardware OBD2:

A API de telemetria processa a mensagem de forma unificada. Se o veículo for migrado para rastreador veicular OBD2 fixo, basta apontar o fluxo de dados para a mesma rota sem alterar a experiência do passageiro ou do guia.

MÓDULO 4: Tela do Passageiro (PWA / Link Direto)
Acesso: rotafy.app/p/{ticket_token} (Acesso direto sem necessidade de criação de usuário ou download em lojas).

Identidade White-Label:

Logotipo da agência de turismo no cabeçalho superior.

Cores de destaque da agência aplicadas aos elementos do ingresso.

Rodapé institucional: "Powered by Nexus Rotafy".

Cartão de Embarque Inteligente:

QR Code de alto contraste para leitura pela câmera do guia.

Nome do passageiro, CPF com máscara de segurança, destino e indicação de poltrona.

Badge de status em tempo real: "Embarque Pendente" (Laranja Coral) ou "Embarcado" (Turquesa).

Mapa de Rastreamento ao Vivo:

Renderização fluida da posição da van ou ônibus via WebSocket em tempo real.

Marcador fixo do ponto/hotel de embarque do passageiro.

Painel de estimativa: Tempo Estimado de Chegada (ETA) atualizado dinamicamente.

7. ESPECIFICAÇÃO DA API REST & WEBSOCKETS (FASTAPI)
A. Autenticação e White-Label
GET /api/v1/public/branding/{tenant_identifier}: Retorna logo, nome comercial e cores da agência.

POST /api/v1/auth/login: Autenticação administrativa da agência.

POST /api/v1/company/settings: Upload de logotipo e definição de chaves da Meta WhatsApp API.

B. Gestão de Viagens e Ingestão
POST /api/v1/trips: Criação de viagem com definição de veículo, motorista, guia e pontos de parada.

POST /api/v1/trips/{trip_id}/upload-manifest: Recebe arquivo .xlsx ou .csv multipart; valida campos, formata números de telefone e gera os bilhetes com tokens individuais criptográficos.

POST /api/v1/trips/{trip_id}/passengers: Cadastro manual unitário de passageiro.

POST /api/v1/integrations/trips/{trip_id}/passengers: Endpoint externo autenticado por API Key para recepção de reservas vindas de websites de venda.

C. WhatsApp Cloud API (Workers Celery)
POST /api/v1/trips/{trip_id}/dispatch-tickets:

Enfileira disparos automáticos via WhatsApp Cloud API para todos os passageiros da rota com seus respectivos links diretos.

Template oficial homologado:

"Olá {{1}}, seu embarque com a {{2}} está confirmado! Acompanhe o veículo em tempo real e acesse seu QR Code de embarque no link: {{3}}"

D. Operação Guia & Motorista
GET /api/v1/trips/{trip_id}/offline-package: Retorna lista integral de passageiros, hashes dos bilhetes e pontos para cache no IndexedDB.

POST /api/v1/trips/{trip_id}/sync-boardings: Recebe array de check-ins realizados localmente no formato:

JSON
[
  {
    "passenger_id": "uuid",
    "boarded_at": "2026-10-03T08:35:10Z",
    "boarded_offline": true
  }
]
POST /api/v1/telemetry/push: Receptor de telemetria agnóstico:

JSON
{
  "vehicle_id": "uuid",
  "trip_id": "uuid",
  "latitude": -26.9187,
  "longitude": -49.0660,
  "speed": 45.2,
  "heading": 182.0,
  "source": "mobile_web"
}
WS /api/v1/telemetry/stream/{trip_id}: Canal WebSocket bidirecional para atualização de coordenadas nos mapas de passageiros conectados.

8. MOTOR DE GEOFENCING E ALERTA DE PROXIMIDADE
A cada lote de coordenadas recebido pela rota de telemetria, o backend verifica o próximo ponto de embarque ordenado na rota com passageiros pendentes.

O PostGIS calcula a distância euclidiana/rota entre o veículo e o ponto:

SQL
ST_Distance(
    v_coordinates::geography,
    bp.coordinates::geography
)
Se o veículo entrar no raio configurado (ex: distância estimada correspondente a 5 minutos de trajeto) e a flag proximity_alert_sent estiver como FALSE:

Dispara a tarefa no Celery para envio de mensagem via WhatsApp para os passageiros vinculados àquele ponto específico:

"Atenção {{1}}: seu transporte da {{2}} está se aproximando do seu ponto de embarque e chegará em aproximadamente 5 minutos! Prepare-se."

Atualiza proximity_alert_sent = TRUE no banco de dados.

9. ROTEIRO DE DESENVOLVIMENTO (SPRINTS DE IMPLEMENTAÇÃO)
Sprint 1: Fundação, Modelagem e White-Label (Dias 1 a 5)
Inicialização do ambiente Docker Compose (FastAPI, PostgreSQL 16 + PostGIS, Redis 7).

Criação das migrações Alembic com suporte a multi-tenancy e branding por agência.

Implementação dos endpoints de CRUD de agências, veículos e configuração visual de logo e cores.

Sprint 2: Ingestão de Passageiros e Geração de Bilhetes (Dias 6 a 10)
Desenvolvimento do parser de planilhas (.xlsx e .csv) com validação de colunas (nome_completo, cpf, destino, telefone, ponto_embarque, poltrona).

Sanitização automática de telefones para E.164 e checagem matemática de CPF.

Criação dos endpoints para inclusão manual e Webhook externo via API Key.

Geração do token criptográfico e hash único por passageiro.

Sprint 3: Modo Motorista & Barramento de Telemetria (Dias 11 a 15)
Construção da interface web mobile do motorista com suporte à WakeLock API (tela sempre ativa).

Captura de geolocalização com throttling e transmissão de coordenadas.

Endpoint de recepção genérico no backend persistindo no Redis e publicando via WebSocket.

Validação da estrutura para recepção futura de hardware OBD2 sem mudanças de contrato.

Sprint 4: Modo Guia Offline-First & Scanner de Câmera (Dias 16 a 20)
Desenvolvimento da interface web do guia utilizando a paleta 60-30-10.

Integração da biblioteca html5-qrcode para leitura via câmera do navegador com feedback imediato.

Configuração do Dexie.js (IndexedDB) para cache local do manifesto e operação 100% offline.

Painel de chamada com métricas de presença, check-in manual e deep-link para WhatsApp de passageiros pendentes.

Mecanismo de fila e sincronização automática ao restabelecer conectividade de rede.

Sprint 5: PWA do Passageiro & Disparos WhatsApp (Dias 21 a 25)
Construção da tela do passageiro adaptada à marca da agência (white-label).

Renderização do mapa ao vivo consumindo WebSocket de telemetria com cálculo de ETA.

Apresentação nítida do QR Code de embarque e status visual dinâmico.

Integração com Meta WhatsApp Cloud API via Celery para envio de bilhetes e alertas de 5 minutos.

Sprint 6: Testes Integrados, Homologação e Deploy (Dias 26 a 30)
Testes de perda súbita de conectividade celular durante a leitura de embarques.

Testes de carga nas conexões WebSocket simulando frotas ativas com múltiplos passageiros acompanhando.

Validação de responsividade e permissões de câmera e localização em dispositivos iOS (Safari) e Android (Chrome).

Configuração de produção com proxy reverso Traefik, certificados SSL automatizados e rotinas de backup.