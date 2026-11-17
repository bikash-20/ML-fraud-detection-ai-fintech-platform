# Wallet

## Digital AI Money Movement & Fraud Intelligence Platform

Wallet is a voice-first, chat-enabled money movement and fraud surveillance platform for everyday financial actions. It combines a deterministic financial ledger with local AI conversation, speech recognition, natural voice output, explicit transaction confirmation, split payments, requests, festival savings goals, browser-side biometric confirmation via Face ID, an autonomous **Financial Intelligence Layer**, and an enterprise-grade **Admin Fraud Intelligence Platform**.

The system is designed around one non-negotiable rule:

> The AI may understand language, explain risk, and make the experience feel human, but it never owns the ledger and never invents financial facts.

Balances, recipients, amounts, transaction state, idempotency, and money movement are strictly controlled by deterministic Python and SQLAlchemy code.

---

## Capabilities

### 1. Everyday Money Movement
- **Voice and text conversation** with natural-language commands and casual small-talk support.
- **Voice input & transcription** through browser microphone and local Faster-Whisper.
- **Voice responses** via browser SpeechSynthesis and optional server-side TTS engines.
- **Wake-word listening** ("Hey Wallet") via openWakeWord running entirely in the browser.
- **Explicit Confirmation Safety**: Transactions create a review card first; execution requires explicit button tap, voice "yes", or biometric verification.
- **Send, Request & Split Money**: Transfer funds to known contacts, request funds with payer notifications, or divide a bill equally among multiple recipients in a single atomic transaction.
- **Festival Savings Goals**: Create dedicated savings pockets (Eid, Durga Puja, Pohela Boishakh, Valentine's Day, or custom goals) with progress tracking.
- **Strict Recent History Lifecycle**: Recent history **only reflects confirmed, completed transactions** really executed in the database. Pending, cancelled, or network-disconnected transfers are excluded.

### 2. Autonomous Financial Intelligence Layer
- **Financial Health Scoring**: Real-time budget health score (0–100 scale: *Excellent, Good, Moderate, Needs Attention*) computed from 30-day outflows, savings pace, and velocity.
- **30-Day Spending Category Breakdown**: Visual spending distribution across categorized expenses (food, bills, festival savings, transfers, other).
- **7-Day Spending Velocity Tracking**: Percentage comparison of weekly spending against the 30-day baseline to detect elevated spending velocity early.
- **Personalized Budget Recommendations**: AI-generated suggestions with interactive **"Ask AI Guide"** panels that expand inline with word-by-word streaming advice, actionable roadmaps, and voice playback.
- **Financial Literacy Assistant**: Interactive literacy guides on emergency funds, the 50/30/20 rule, smart festival savings, and debt management.

### 3. Dedicated Admin Fraud Intelligence & Surveillance Platform
- **Secure Admin Authentication**: Dedicated admin login flow (`/admin/login`) with bcrypt password verification, JWT sessions, and role-based access control (`super_admin`, `fraud_analyst`, `compliance_auditor`).
- **Live Database Overview**: Real-time KPIs for registered users, active accounts, completed transaction volume, suspicious event counts, and pending investigations.
- **Explainable Fraud Risk Assessment**: Hybrid rule + anomaly detection engine scoring every transaction (*Low, Medium, High*) with explainable risk factors, velocity spikes, and drain ratio metrics.
- **Alert Triage & Investigation Workflow**: Update alert status (`new`, `investigating`, `resolved`, `false_positive`) with administrative investigation notes and immutable security audit logs.
- **Account Actions**: One-click **Account Freeze** and **Security Watch** controls to immediately block unauthorized funds movement.
- **Admin Intelligence AI Assistant**: Live database-grounded conversational assistant featuring word-by-word streaming typewriter animation for operational queries without hallucinations.

---

## Architecture

```text
Browser voice, chat, or admin UI
        │
        ▼
Next.js 14 App Router
   ├── FaceIDEnroll.tsx           Enrolls face via webcam, stores 128-dim embedding
   ├── FaceIDConfirm.tsx          Verifies face before high-value actions are authorized
   ├── FinancialIntelligenceCard  Health score, category breakdown, recommendations & AI guide
   ├── openWakeWord.ts            Always-on "Hey Wallet" trigger word
   ├── useVoiceLoop.ts            Wake-word -> STT -> /agent/act -> confirm pipeline
   └── /admin                     Dedicated Fraud Intelligence & Monitoring Platform
        │
        │ HTTP / REST / SSE
        ▼
FastAPI Application Cluster
   ├── Fast-Path Intent Router
   │      ├── Casual Small Talk   ──► Pure LLM Cascade (0 DB load, fast conversational reply)
   │      └── Operational Query   ──► Targeted Live DB Query ──► Grounded LLM Response
   ├── Multi-Model AI Cascade
   │      ├── Local Ollama (Qwen 2.5 7B / DeepSeek)
   │      ├── Grok (xAI API)
   │      ├── OpenRouter Cloud Fallback
   │      └── Deterministic Rule/Regex Fallback
   ├── Fraud Detection Engine
   │      ├── Rule-based risk evaluation (<1.5ms latency)
   │      ├── Behavioral anomaly detection (velocity, drain ratio, spikes)
   │      └── Explainable risk score & alert generation
   ├── Financial Intelligence Engine
   │      ├── 30-day category spend aggregation & health scoring
   │      ├── Weekly velocity baseline calculations
   │      └── Personalized recommendation & literacy guide generation
   ├── Transaction & Ledger Engine
   │      ├── Atomic debit/credit mutations (ACID)
   │      ├── Idempotency enforcement & replay protection
   │      └── Pending TTL sweeper & account freeze enforcement
   └── SQLAlchemy + SQLite / MySQL Ledger State
```

### Senior Architectural Separation: Chat vs. Database Operations

```text
Incoming Message
       │
       ├─ Casual Greeting / Small Talk ("hi", "salam", "how are you", "who are you")
       │     └─► Pure LLM Cascade (0 DB Queries, Zero Connection Overhead, No Data-Dumping)
       │
       └─ Operational / Financial Query ("highest risk txns", "spending where", "pace eid goal")
             └─► Targeted Single-Table DB Query ──► Grounded Multi-Model LLM Response
```

---

## Safety Boundary & Transaction Lifecycle

Every money-moving action follows this strict lifecycle:

```text
user speech/text
  -> intent parsing (regex + LLM cascade)
  -> deterministic validation & recipient resolution
  -> pre-transaction fraud risk assessment (Low, Medium, High)
  -> pending transaction record created in database (status="pending")
  -> review card rendered in UI & spoken via TTS
  -> user confirmation (Confirmation toggle button, voice "yes", or biometric Face ID)
  -> if confirmed:
       -> atomic ledger execution (status="completed", completed_at=now)
       -> funds debited/credited atomically
       -> background categorizer tags transaction
       -> appears in Recent History
  -> if declined / disconnected / timed out:
       -> status="cancelled", zero money moved
       -> strictly excluded from Recent History
```

---

## Admin Fraud Intelligence Platform

Access the administrative monitoring console at:
**`http://localhost:3000/admin`**

- **Login Route**: `/admin/login`
- **Default Credentials**:
  - **Phone**: `01926240062`
  - **Password**: `1234`
  - **Admin Name**: `talukder` (Super Admin)

### Console Modules:
1. **Overview Dashboard**: Live KPIs (users, volume, completed transfers, suspicious events, pending investigations), 14-day volume timeline, and risk level distributions.
2. **Fraud Intelligence**: Live assessment feed displaying risk score (0.00–1.00), risk tier (*Low*, *Medium*, *High*), triggered rules, drain ratio, and investigation triage dialogs.
3. **Transaction Monitoring**: Complete transaction history with multi-criteria filters (risk tier, status, user, date range) and transaction detail modals.
4. **User Surveillance**: Directory of accounts, balances, fraud flag counters, and one-click **Account Freeze** toggles.
5. **Alerts Management**: Incident queue (`new`, `investigating`, `resolved`, `false_positive`) with persistent analyst notes and audit logs.
6. **System Telemetry**: Real-time status of database WAL, fraud latency, API health, and multi-model cascade availability.
7. **Admin AI Assistant**: Word-by-word streaming conversational assistant for natural queries against the live database (*"How many suspicious transactions today?"*, *"Which users have repeated flags?"*).

---

## Project Structure

```text
wallet/
├── README.md                          Comprehensive system documentation
├── AUDIT.md                           Security & code audit report
├── docs/
│   └── SCALING_ARCHITECTURE.md        Enterprise 1M+ user scaling roadmap
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── config.py                  Cascading models, timeouts & environment config
│   │   ├── db.py                      SQLAlchemy engine & schema bootstrap
│   │   ├── engine.py                  Atomic ledger mutations, states & freeze checks
│   │   ├── llm.py                     Multi-model cascade (Ollama/Grok/OpenRouter), phrasing
│   │   ├── main.py                    FastAPI application setup & lifecycle
│   │   ├── models.py                  User, Account, Transaction, FraudAssessment, FraudAlert, etc.
│   │   ├── resolver.py                Recipient handle & amount validation
│   │   ├── schemas.py                 Pydantic API contracts
│   │   ├── seed.py                    Demo users, billers, and admin account
│   │   ├── services/
│   │   │   ├── admin_ai.py            Grounded Admin AI with casual vs DB separation
│   │   │   ├── categorizer.py         Transaction tagging background worker
│   │   │   ├── financial_intelligence.py Health scores, velocity & recommendations
│   │   │   └── fraud_engine.py        Hybrid rule + ML risk scoring engine
│   │   └── routers/
│   │       ├── accounts.py            Accounts, strictly-completed history, savings goals
│   │       ├── admin.py               Admin auth, KPIs, fraud assessments, alerts, AI query
│   │       ├── agent.py               Agent chat, act, confirm, review cards
│   │       ├── insights.py            Tags, financial intelligence, recommendation advice
│   │       └── voice.py               Whisper transcription & speech endpoints
│   └── tests/
│       ├── conftest.py                Isolated temporary test database fixture
│       ├── test_accounts.py           History completion tests & counterparty verification
│       ├── test_act_send.py           Send-money flow tests
│       ├── test_act_split.py          Split payment tests
│       ├── test_admin_and_fraud.py    Admin auth, fraud tiers, user freeze, Admin AI tests
│       ├── test_agent_chat.py         Casual chat isolation & balance query tests
│       ├── test_engine.py             Atomic balance mutations & insufficient funds tests
│       └── test_financial_intelligence.py Health score, recommendations & advice tests
└── frontend/
    ├── app/
    │   ├── page.tsx                   User dashboard (Wallet, Voice, Intelligence Layer)
    │   ├── login/page.tsx             Demo user switch screen
    │   ├── admin/
    │   │   ├── page.tsx               Admin Intelligence Platform & live charts
    │   │   └── login/page.tsx         Dedicated admin login screen
    │   └── globals.css                Mauve/Plum and Peach glassmorphism styles
    ├── components/
    │   ├── FinancialIntelligenceCard.tsx Health score, category bar, inline AI Guide
    │   ├── HistoryList.tsx            Strictly-completed transaction history feed
    │   ├── ChatBar.tsx                Voice/text input bar with typewriter response
    │   ├── FaceIDEnroll.tsx           Webcam enrollment component
    │   ├── FaceIDConfirm.tsx          Biometric verification modal
    │   └── ReviewCard.tsx             Pre-confirmation transaction review card
    ├── lib/
    │   ├── api.ts                     Typed REST client for user and admin APIs
    │   ├── speech.ts                  TTS speech playback helper
    │   └── face.ts                    Client-side face-api.js detection
    └── voice/
        ├── openWakeWord.ts            "Hey Wallet" wake-word detector
        └── ConfirmListener.ts         Voice "yes" / "no" confirmation listener
```

---

## Setup & Running

### 1. Start Ollama (Local AI Model)
```bash
ollama pull qwen2.5:7b
# or: ollama pull deepseek-coder-v2:16b
ollama serve
```

### 2. Start the Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Run uvicorn server from the backend directory:
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check:
```bash
curl http://127.0.0.1:8000/health
```

### 3. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```

Visit:
- **User Wallet Dashboard**: `http://localhost:3000`
- **Admin Intelligence Platform**: `http://localhost:3000/admin` (Login: `01926240062` / `1234`)

---

## API Overview

### User & Transaction Endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| `GET /health` | `GET` | Health, model readiness, and cascade status |
| `GET /users` | `GET` | Known users and contact directory |
| `GET /users/{id}/history` | `GET` | Confirmed, completed ledger history (pending/cancelled excluded) |
| `GET /users/{id}/requests` | `GET` | Incoming money requests pending user approval |
| `GET /users/{id}/savings-goals`| `GET` | Festival savings pockets and progress |
| `POST /users/{id}/savings-goals`| `POST` | Create a new festival savings goal |
| `POST /users/{id}/savings-goals/{gid}/contribute` | `POST` | Contribute funds to a savings goal |
| `GET /users/{id}/security-preference` | `GET` | User security transparency preference |
| `POST /users/{id}/security-preference` | `POST` | Toggle explainable fraud analysis visibility |
| `POST /agent/act` | `POST` | Parse natural command and create pending review card |
| `POST /agent/confirm` | `POST` | Authorize and execute (or cancel) a pending transaction |
| `POST /agent/chat` | `POST` | Casual conversation (0 DB overhead) or financial advice |
| `POST /voice/transcribe` | `POST` | Faster-Whisper audio transcription |

### Financial Intelligence Endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| `GET /users/{id}/financial-intelligence` | `GET` | Health score, category breakdown, velocity, recommendations |
| `POST /users/{id}/financial-intelligence/advice` | `POST` | Live-DB grounded actionable advice for a recommendation |
| `GET /users/{id}/financial-literacy` | `GET` | Curated guides on emergency funds, 50/30/20 rule, savings |

### Admin Intelligence Endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| `POST /admin/api/auth/login` | `POST` | Admin authentication and JWT token issuance |
| `GET /admin/api/auth/me` | `GET` | Current authenticated admin session profile |
| `GET /admin/api/overview` | `GET` | Live KPIs, volume timeline, risk distributions |
| `GET /admin/api/fraud/assessments` | `GET` | Paginated fraud evaluation records with risk factors |
| `GET /admin/api/fraud/alerts` | `GET` | Open fraud alerts and investigation tickets |
| `PATCH /admin/api/fraud/alerts/{id}`| `PATCH` | Update alert triage status and investigation notes |
| `POST /admin/api/users/{id}/freeze` | `POST` | Freeze or unfreeze an account from moving funds |
| `POST /admin/api/ai/query` | `POST` | Live database-grounded query answering with cascade |

---

## Testing & Quality Assurance

Run the backend test suite:
```bash
cd backend
.venv/bin/pytest -v
```

Verify the frontend production build:
```bash
cd frontend
npm run build
```

---

## License

Proprietary — All rights reserved. Developed by Bikash Talukder.
