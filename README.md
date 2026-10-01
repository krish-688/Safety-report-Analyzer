# SafeTrack AI: Safety Incident Prediction & Root Cause Analysis (NLP)
### Enterprise Petrochemical HSE Management & Predictive Intelligence Platform

**SafeTrack AI** is a production-grade web application tailored for the petrochemical and process manufacturing sectors. It manages the full safety incident lifecycle: reporting, artificial intelligence (NLP) root-cause inference, formal 5-Why investigations, Corrective and Preventive Actions (CAPA), automated safety threshold alerts, and compliance reporting with publication-grade PDF dossiers.

---

## 🏆 Project Completion Status: All 10 Stages Complete (10/10)

| Stage | Milestone | Status | Key Features Delivered |
|---|---|:---:|---|
| **1** | Architecture & Models | ✅ Complete | 14 SQLAlchemy 2.0 tables, SQLite/PostgreSQL/MySQL abstraction, realistic seed data (3 plants, 40 equipment, 5 cause categories, ~300 incidents). |
| **2** | Auth, Security & RBAC | ✅ Complete | Bcrypt/Argon2 password hashing, JWT Bearer tokens (30m expiry), 5-attempt lockout (15m window), plant-scoped data isolation (opaque 404s). |
| **3** | Incident CRUD & NLP Stub | ✅ Complete | Auto-generated sequential references (`INC-YYYY-####`), scoped CSV export, file attachments, NLP inference stub, and human-in-the-loop review. |
| **4** | Streamlit Thin Client | ✅ Complete | Decoupled UI architecture via `api_client.py`, role-based navigation sidebar, dynamic session management, one-click demo credentials. |
| **5** | Interactive HSE Dashboard | ✅ Complete | High-performance aggregation APIs, KPI cue cards, Plotly monthly incident trends, Pareto root-cause chart, equipment watchlist, plant distribution. |
| **6** | Incident Explorer & NLP Playground | ✅ Complete | Filterable incident explorer, paginated catalog, plant equipment selector, interactive raw text NLP analysis playground. |
| **7** | Investigations & CAPA | ✅ Complete | Full investigation workflow, 5-Why methodology, CAPA proposals, Plant Manager approval gating, Safety Manager closure verification. |
| **8** | Alerts & Thresholds | ✅ Complete | Real-time critical/high risk alerts, repeat equipment threshold triggers, background overdue scan, dynamic unread badge, threshold tuning UI. |
| **9** | Administrator Console | ✅ Complete | Enterprise user management (approvals, role/plant assignment, password resets), plant facility management, equipment catalog, compliance audit trail. |
| **10** | Reports & Executive Dossiers | ✅ Complete | ReportLab PDF Investigation Dossier generator, scoped CAPA/Incident CSV downloads, Executive safety briefing, 100% test coverage (71 passing tests). |

---

## 🛠️ Architecture & Technology Stack

```
safety-app/
├── requirements.txt, .env.example, README.md, .gitignore
├── backend/
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py              FastAPI application entrypoint & middleware
│   │   ├── core/                Settings, security (JWT & Bcrypt), dependency injection (RBAC)
│   │   ├── models/              14 SQLAlchemy 2.0 models & enumerated types
│   │   ├── schemas/             Pydantic v2 validation models
│   │   ├── routers/             auth, users, plants, equipment, incidents, dashboard, investigations, alerts, audit
│   │   ├── services/            audit, incident, nlp, alert, report (ReportLab PDF)
│   │   └── db/                  base, session, seed engine (~300 incidents)
│   └── tests/                   71 automated pytest test cases covering stages 1 to 10
└── frontend/
    ├── app.py                   Streamlit main entrypoint & router
    ├── api_client.py            Thin REST client interacting with FastAPI
    ├── components/              auth_view, navigation
    └── pages/                   dashboard, incidents, new_incident, analyze_report, investigations, alerts, reports, admin_users, admin_plants_equipment, system_status
```

- **Backend:** FastAPI, SQLAlchemy 2.0, Pydantic v2, ReportLab 5.0, SQLite (default dev) / PostgreSQL & MySQL compatible.
- **Frontend:** Streamlit Thin Client, Plotly Interactive Visualizations.
- **NLP Pipeline:** Human-in-the-loop root-cause classification and risk estimation stub (easily swappable for transformer/LLM backends).

---

## 🚀 Quickstart Guide

### 1. Environment Setup
```bash
# Clone or navigate to the repository
cd safety-app

# Create and activate a Python 3.10+ virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example backend/.env       # On Windows: copy .env.example backend\.env
```

### 2. Seed the Database
Initialize tables and populate ~300 realistic petrochemical incidents across 18 months:
```bash
cd backend
python -m app.db.seed --reset
```

### 3. Launch the Application (Two Processes)

**Terminal 1 — FastAPI Backend:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
- API Documentation (Swagger UI): `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

**Terminal 2 — Streamlit Frontend:**
```bash
streamlit run frontend/app.py
```
- Web Application: `http://localhost:8501`

### 4. Run Automated Test Suite
Execute all 71 tests across every development stage:
```bash
cd backend
pytest -v
```

---

## 👥 Roles & Demo Credentials

Every state change enforces strict plant scoping. All accounts use demo password: `Password1` (Admin uses `AdminPass1`).

| Role | Email | Scope | Primary Capabilities |
|---|---|---|---|
| **System Administrator** | `admin@safety.local` | System Only | Approves registrations, configures plants & equipment, tunes alert thresholds, audits logs. (Zero incident operational data access). |
| **Safety Manager** | `safety.manager@safety.local` | Global (All Plants) | Full incident overview, cross-plant investigations, final closure verification, executive reports. |
| **Plant Manager (Plant 1)** | `plant.manager@safety.local` | Plant #1 Only | Plant dashboard, approves/rejects CAPA actions, receives plant failure alarms. |
| **Plant Manager (Plant 2)** | `pm.plant2@safety.local` | Plant #2 Only | Plant 2 operational oversight & action approval. |
| **Plant Manager (Plant 3)** | `pm.plant3@safety.local` | Plant #3 Only | Plant 3 operational oversight & action approval. |
| **Safety Officer (Plant 1)** | `safety.officer@safety.local` | Plant #1 Only | Reports incidents, initiates 5-Why investigations, proposes CAPA actions. |
| **Safety Officer (Plant 2)** | `so.plant2@safety.local` | Plant #2 Only | Plant 2 incident reporting & investigation. |
| **Safety Officer (Plant 3)** | `so.plant3@safety.local` | Plant #3 Only | Plant 3 incident reporting & investigation. |
| **Executive Management** | `management@safety.local` | Global (Read-only) | High-level KPI dashboards, trend analysis, safety briefing reports. |

---

## 📡 REST API Directory (`/api/v1`)

| Module | Method & Route | Description |
|---|---|---|
| **Auth** | `POST /auth/register` | Register new user (Pending approval) |
| | `POST /auth/login` | Authenticate and obtain JWT token |
| | `GET /auth/me` | Current authenticated user profile |
| | `POST /auth/logout` | Client logout |
| **Users** | `GET /users` | List users with filters (Admin only) |
| | `POST /users/{id}/approve` | Approve registration with role & plant assignment |
| | `POST /users/{id}/reject` | Reject registration request |
| | `PATCH /users/{id}` | Update user role and plant assignment |
| | `POST /users/{id}/reset-password`| Reset password & clear lockout (Admin only) |
| **Plants & Equipment** | `GET /plants` | List active operating facilities |
| | `GET /plants/all` | List all plants including inactive (Admin) |
| | `POST /plants` | Register new plant facility (Admin) |
| | `PATCH /plants/{id}` | Update plant name, code, or active status (Admin) |
| | `GET /equipment` | List equipment assets with filters |
| | `POST /plants/{id}/equipment` | Register tagged equipment asset (Admin) |
| | `PATCH /equipment/{id}` | Update equipment attributes (Admin) |
| **Incidents** | `GET /incidents` | Scoped, filterable, paginated incident catalog |
| | `POST /incidents` | Record safety incident with equipment tags |
| | `GET /incidents/{id}` | Full incident detail & equipment/root-cause links |
| | `PATCH /incidents/{id}` | Update incident details |
| | `DELETE /incidents/{id}` | Remove incident (Reported status only) |
| | `GET /incidents/export-csv` | Scoped CSV download of incident records |
| | `GET /incidents/{id}/export-pdf` | **Publication-grade PDF Dossier export** |
| | `POST /incidents/{id}/analyze` | Trigger NLP root-cause & risk analysis |
| | `POST /incidents/analyze-text` | Interactive NLP text evaluation playground |
| | `POST /incidents/{id}/attachments`| Upload evidence files & images |
| | `GET /incidents/{id}/attachments/{aid}/download` | Download attachment file |
| **Investigations & CAPA** | `GET /incidents/{id}/investigation` | Fetch 5-Why investigation record |
| | `POST /incidents/{id}/investigation` | Initiate investigation with due date & findings |
| | `PATCH /incidents/{id}/investigation`| Update investigation evidence & timeline |
| | `POST /incidents/{id}/investigation/close` | Safety Manager verification & formal closure |
| | `GET /actions` | List corrective & preventive actions |
| | `POST /incidents/{id}/actions` | Propose new CAPA corrective action |
| | `POST /actions/{id}/approve` | Plant Manager approval / rejection gating |
| | `GET /actions/export-csv` | Scoped CSV export of CAPA action records |
| **Alerts & Thresholds** | `GET /alerts` | User alert notification feed |
| | `GET /alerts/unread-count` | Real-time badge counter |
| | `POST /alerts/{id}/read` | Mark alert as read |
| | `POST /alerts/mark-all-read` | Mark all alerts read |
| | `POST /alerts/scan` | Trigger background overdue scan |
| | `GET /alerts/thresholds` | System escalation rules & thresholds |
| | `PATCH /alerts/thresholds/{key}` | Tune alert thresholds (Admin / Safety Manager) |
| **Dashboard** | `GET /dashboard/summary` | Executive HSE KPIs & active counts |
| | `GET /dashboard/trends` | Monthly incident volume by severity |
| | `GET /dashboard/pareto-causes` | Root-cause Pareto distribution |
| | `GET /dashboard/equipment-watch` | Equipment repeat failure watchlist |
| | `GET /dashboard/plant-distribution`| Incident distribution across facilities |
| **Audit** | `GET /audit-logs` | Immutable system security & change log (Admin) |

---

## 🔒 Security & Data Governance

1. **Plant Data Scoping:** Every operational database query traverses `scope_incident_query(user)`. Attempting to access an incident outside assigned plant boundaries returns HTTP `404 Not Found`, completely concealing the incident's existence.
2. **Admin Segregation:** System Administrators manage users, plants, equipment, and alert thresholds, but have **zero operational incident visibility** (guaranteed via `false()` SQL condition).
3. **Lockout Protection:** User accounts automatically lock for 15 minutes after 5 consecutive failed login attempts.
4. **Audit Compliance:** Every critical mutation (registrations, approvals, incident creation, status changes, CAPA decisions, threshold updates) produces an immutable `AuditLog` entry.

---

## 📄 License
This project is open-source under the MIT License.
