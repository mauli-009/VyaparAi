# 🧠 Vyapar AI — Natural Language Analytics for Business Data

> **Ask your CSV anything. No SQL. No code. Just plain English.**

Vyapar AI is a full-stack SaaS analytics platform that lets business users query their CSV datasets using natural language. Under the hood, it runs a multi-step agentic pipeline — intent extraction → semantic field resolution → pandas aggregation — powered by an LLM and a self-learning semantic registry.

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js-black?style=flat&logo=next.js)](https://nextjs.org/)
[![MongoDB](https://img.shields.io/badge/Database-MongoDB-47A248?style=flat&logo=mongodb)](https://www.mongodb.com/)
[![Groq](https://img.shields.io/badge/LLM-Groq-F55036?style=flat)](https://groq.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python)](https://www.python.org/)

---

## ✨ What It Does

| User Query | What Happens |
|---|---|
| *"Total revenue for electronics in Q1 2024"* | Extracts intent → resolves fields → applies filters → runs aggregation |
| *"Average rating by month"* | Groups by `month(transaction_date)` → returns time-series results |
| *"Top products by sales"* | Routes to recommendation pipeline → ranks with scores |
| *"What should I analyze?"* | Returns contextual suggestions with execution plans |

No SQL. No manual field selection. No coding required.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js)                            │
│                                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────────────┐│
│  │  Upload +   │  │  Chat Query  │  │  ResultCard · SuggestionCards   ││
│  │  Mapping UI │  │  Interface   │  │  RecommendationCard · ChartView ││
│  │  (Sidebar)  │  │              │  │  (bar / line / pie / stat)      ││
│  └──────┬──────┘  └──────┬───────┘  └─────────────────────────────────┘│
└─────────┼───────────────┼──────────────────────────────────────────────┘
          │  REST API      │  REST API
          ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                               │
│                                                                         │
│   POST /upload         POST /mapping         POST /query               │
│       │                     │                     │                     │
│       ▼                     ▼                     ▼                     │
│  IngestionService    RegistryMapping         IntentService              │
│  - CSV parsing       Service                 - LLM prompt               │
│  - Metadata          - Exact match           - Field resolution         │
│    extraction        - Fuzzy match           - Fallback synonyms        │
│                      - LLM disambig.              │                     │
│                      - Self-learning              ▼                     │
│                        registry            AggregationService           │
│                                            - pandas groupby             │
│                                            - filter engine              │
│                                            - time-series support        │
│                                                   │                     │
│                                                   ▼                     │
│                                       VisualizationService              │
│                                       - detect_chart_type()             │
│                                         bar / line / pie / stat         │
│                                       - build_chart_config()            │
│                                         Recharts-compatible JSON        │
│                                       - unit inference (₹, %, units)   │
│                                       - large number formatting         │
│                                         (1.2M, 450K)                   │
└──────────────────┬──────────────────────────────┬────────────────────── ┘
                   │                              │
         ┌─────────▼──────────┐        ┌──────────▼──────────┐
         │      MongoDB       │        │      Groq LLM        │
         │                    │        │                      │
         │  datasets          │        │  Intent extraction   │
         │  semantic_registry │        │  Column mapping      │
         │  (alias store)     │        │  Disambiguation      │
         └────────────────────┘        └──────────────────────┘
```

---

## 🔑 Key Technical Features

### 1. Self-Learning Semantic Registry
A MongoDB-backed column alias store that gets smarter over time.
- New columns are mapped using **exact match → fuzzy match (RapidFuzz) → LLM disambiguation** — in that priority order
- Once resolved, the column alias is persisted via `$addToSet` so future uploads skip the LLM call entirely
- Prevents semantic key collisions using `BANNED_GENERIC_KEYS` and batch-LLM column mapping (all columns sent in one prompt, preventing "Total Revenue", "Total Cost", "Total Profit" from collapsing to the same key)

### 2. Agentic Multi-Step Query Pipeline
Hand-rolled multi-step orchestration (no framework dependencies):
```
User Question
    → extract_intent()        — LLM extracts metric, field, group_by, filters
    → resolve_field()         — grounds LLM output against actual semantic fields
    → apply_filters()         — pandas filter engine (equals, between, gt/lt, etc.)
    → run_aggregation()       — sum / avg / count, with time-series grouping
    → result                  — structured JSON returned to frontend
```

### 3. Robust Dirty Data Handling
- `force_numeric()` helper strips ₹ symbols, commas, and percent signs before aggregation
- Alphanumeric ID columns detected via digit-ratio checks to avoid misclassification
- Date columns auto-parsed with `pd.to_datetime(..., errors="coerce")`

### 4. Batch LLM Column Mapping
All columns are sent to the LLM in a single prompt during the mapping phase — not per-column loops. This prevents semantic drift where distinct columns (e.g., `Total Revenue`, `Total Cost`, `Total Profit`) get incorrectly mapped to the same key.

---

## 📁 Project Structure

```
vyapar-ai/
│
├── app/
│   ├── api/
│   │   ├── upload.py               # POST /upload — CSV ingestion
│   │   ├── mapping.py              # POST /mapping — semantic mapping
│   │   └── query.py                # POST /query — NL query handler
│   │
│   ├── services/
│   │   ├── ingestion_service.py    # CSV parsing + metadata extraction
│   │   ├── intent_service.py       # LLM intent extraction + field resolution
│   │   ├── aggregation_service.py  # pandas aggregation + filter engine
│   │   ├── registry_mapping_service.py  # exact/fuzzy/LLM column mapping
│   │   ├── llm_service.py          # Groq API wrapper
│   │   └── mapping_service.py      # Internal schema definitions
│   │
│   ├── repositories/
│   │   ├── dataset_repo.py         # datasets collection CRUD
│   │   ├── semantic_registry_repo.py  # registry read/write/alias update
│   │   └── registry_repo.py        # base registry access
│   │
│   ├── db/
│   │   └── database.py             # MongoDB connection + collections
│   │
│   └── utils/
│       ├── file_utils.py           # UUID file ID + upload path management
│       └── validation_utils.py     # Input validation helpers
│
├── frontend/                       # Next.js app
│   └── ...
│
├── uploads/                        # Uploaded CSVs (gitignored)
├── .env
├── requirements.txt
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB (local or Atlas)
- [Groq API key](https://console.groq.com/)

### 1. Clone the repo

```bash
git clone https://github.com/your-username/vyapar-ai.git
cd vyapar-ai
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:

```env
MONGO_URI=mongodb://localhost:27017
DB_NAME=vyapar_ai
GROQ_API_KEY=your_groq_api_key_here
```

Run the FastAPI server:

```bash
uvicorn app.main:app --reload
```

API will be live at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will be live at `http://localhost:3000`.

### 4. Seed the semantic registry (optional but recommended)

```bash
python scripts/seed_registry.py
```

This pre-populates the registry with common business column patterns so the first upload doesn't need full LLM disambiguation.

---

## 🔌 API Reference

### `POST /upload`
Upload a CSV file for analysis.

**Request:** `multipart/form-data` with `file` field

**Response:**
```json
{
  "file_id": "uuid-string",
  "columns": ["Product Name", "Revenue", "Date", "..."],
  "preview_rows": [{ "Product Name": "Widget A", "Revenue": 5000 }]
}
```

---

### `POST /mapping`
Generate semantic mapping for uploaded dataset.

**Request:**
```json
{ "file_id": "uuid-string" }
```

**Response:**
```json
{
  "file_id": "uuid-string",
  "semantic_mapping": {
    "Product Name": "product_name",
    "Revenue": "revenue",
    "Date": "transaction_date"
  },
  "message": "Mapping generated successfully"
}
```

---

### `POST /query`
Query the dataset in plain English.

**Request:**
```json
{
  "file_id": "uuid-string",
  "question": "What is the total revenue for electronics in 2024?"
}
```

**Response:**
```json
{
  "intent": {
    "metric": "sum",
    "field": "revenue",
    "group_by": null,
    "filters": [
      { "field": "category", "operator": "equals", "value": "electronics" },
      { "field": "transaction_date", "operator": "between", "value": ["2024-01-01", "2024-12-31"] }
    ]
  },
  "result": {
    "results": [{ "value": 128450.75 }]
  }
}
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js, Tailwind CSS |
| **Backend** | FastAPI (Python) |
| **Database** | MongoDB |
| **LLM** | Groq (Llama 3 / GPT-OSS) |
| **Fuzzy Matching** | RapidFuzz |
| **Data Processing** | pandas |
| **Auth / File ID** | UUID |

---

## 🧩 How the Semantic Registry Works

```
Column: "Gross Sales Amount"
         │
         ▼
  1. Exact alias match?  ─── YES ──► return key (e.g., "revenue")
         │ NO
         ▼
  2. Fuzzy match ≥ 90%?  ─── YES ──► return key + learn alias
         │ NO
         ▼
  3. LLM disambiguation  ─── picks existing key OR creates new one
         │
         ▼
  4. Persist alias in MongoDB
     (next upload skips all the above)
```

This means Vyapar AI gets **faster and more accurate** with every new dataset uploaded.

---

## 📊 Supported Query Types

- **Aggregation** — `sum`, `avg`, `count` on any numeric field
- **Filtered aggregation** — with `equals`, `not_equals`, `greater_than`, `less_than`, `between` operators
- **Time-series** — group by month using `month(transaction_date)`
- **Category filters** — filter by any categorical column value
- **Date range filters** — filter by date using natural language ranges

---

## 🗺️ Roadmap

- [ ] Multi-dataset join queries
- [ ] LangGraph-based orchestration for complex multi-hop queries
- [ ] Chart export (PNG/CSV)
- [ ] User auth + per-user dataset isolation
- [ ] Streaming LLM responses for real-time feedback
- [ ] Support for Excel (.xlsx) uploads

---

## 🤝 Contributing

PRs welcome. Please open an issue first to discuss the change.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
