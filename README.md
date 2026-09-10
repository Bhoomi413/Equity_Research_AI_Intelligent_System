# Equity Research Intelligent System

A RAG application designed to ingest multi-page corporate annual reports, cross-reference with real-time market news, and form institutional-grade investment views.

## Working
- User uploads annual report
- Cross reference with today's news
- Then form an investment view

## Technical Decisions

### 1. Vector Storage Strategy
* Each document’s embeddings are stored separately in a structured directory: knowledgebase for persistence across application restarts.

### 2. Hybrid Retrieval 
* implements manual reciprocal rank fusion based hybrid retrieval, with chunk id maetadata mapping and custom fusion logic replacing LangChain EnsembleRetriever, combines BM25 (keyword-based search) and semantic search (embeddings) to improve document retrieval accuracy.

### 3. Hash-Based Caching System
* each PDF is identified using a SHA-256 hash.
* If document has already been processed,system skips embedding generation and loads directly
* This avoids repeated embedding computation and reduces document re-processing latency.

### 4. Embedding Layer

* Switched from Gemini embeddings to a local HuggingFace model (all-MiniLM-L6-v2) to eliminate dependency on external embedding API calls, reduce latency, and avoid API quota issues during embedding. The tradeoff is vector dimensions (384 vs 3072) but all-MiniLM-L6-v2 is a well established model for semantic similarity tasks.

### 5. Real-Time Market Intelligence Integration
* Correlates report data with real-time news retrieval to highlight divergence between corporate management guidance and current market realities.

### 5. Eliminating OCR

Annual reports filed with SEBI (India) and SEC (US) are mandatorily submitted as electronic documents, meaning they are born-digital PDFs where PyMuPDF extracts text directly without OCR.

OCR using Gemini Vision was added under an incorrect assumption about document format. Removed to eliminate processing delays and external API dependency during document loading.

### 6. Authentication & Per-User Data Isolation

* JWT-based authentication using OAuth2 with bcrypt password hashing — passwords are never stored in plain text
* Every protected API route verifies the JWT server-side; `user_id` is always derived from the verified token, never trusted from the frontend
* PostgreSQL stores user accounts and document metadata with a foreign key ownership constraint on every document record
* All user data is isolated at the filesystem level — PDFs and vector stores are stored under user-scoped paths (`UploadedPDF/user_{id}/` and `knowledgebase/user_{id}/`)
* Every query verifies both JWT identity and database ownership before loading any embeddings — a user cannot access another user's documents even with a known file hash

---

## Ingestion Pipeline: Evolution & Benchmarking

The ingestion engine processes multi-page corporate annual report containing dense financial statements, multi-column reading flows, and tabular data. 

Between v1.0 and v2.0, the pipeline underwent significant performance profiling and refactoring to eliminate API bottlenecks and reduce end-to-end ingestion latency.

### Pipeline Architecture Comparison

| Metric / Parameter | v1.0 (Prototype) | v2.0 (Refactor) |
| :--- | :--- | :--- |
| **Primary Parser** | `PyMuPDF4LLM` | Native `PyMuPDF` |
| **PDF Parsing/Extraction Latency** | 10.11s–92.09s for tested 28–123 page PDFs | 0.36–0.61s for tested PDFs |
| **Fallback Mechanism** | Vision LLM OCR via API | None (strict digital PDF focus) |
| **Failure Modes** | HTTP timeouts, 429 Quota exhaustion | No external API/network dependency; avoids API rate limits and network failures |

---

#### PDF Parsing/Extraction Latency Benchmark
| **Document Size** | **PyMuPDF4LLM Loader** | **Native PyMuPDF Loader** | **Speedup** |
|---|---:|---:|---:|
| **28 Pages** | 10.11s | **0.36s** | **28×** |
| **92 Pages** | 72.17s | **1.36s** | **53×** |
| **123 Pages** | 92.09s | **0.61s** | **151x** |
**Each PDF was processed 3 times per implementation and the reported value is the arithmetic mean of the three runs.**

### Engineering Decisions & Post-Mortem

#### 1. Transition from `PyMuPDF4LLM` to Native `PyMuPDF`
* **Initial Hypothesis**: `PyMuPDF4LLM` was chosen to preserve layout and structure of complex PDFs for RAG retrieval.
* **Bottleneck**: Benchmark testing revealed up to 80+ seconds on 100+ page reports triggering latency.
* **Resolution**: Replaced with native `PyMuPDF` extraction.

#### 2. Deprecation of Vision-Based OCR Fallback
* **Initial Hypothesis**: Annual reports might contain scanned/rasterized pages requiring multimodal LLM extraction (Gemini Vision).
* **Bottleneck**: Real-world audit of corporate filings showed most of the modern reports are digitally rendered vector PDFs. It triggeres massive latencies and  timeout errors.
* **Resolution**: Stripped external OCR dependencies from the primary parsing path. Eliminating the Vision OCR ingestion makes the document loading deterministic, free from external API COST, and offline-capable.

---

## Project Structure

```text
project/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── auth.py
│   └── rag/
│       ├── __init__.py
│       └── rag.py
│
├── frontend/
│   └── app.py
│
├── UploadedPDF/
│   └── <user_id>/
│       └── <hash_value>
│           └── filename.pdf
├── knowledgebase/
│   └── <user_id>/
│       └── <hash_value>/
│           ├── chunks.pkl
│           ├── index.faiss
│           └── index.pkl
│
├── requirements.txt
├── .env.example
└── .gitignore
```

### Getting Started
#### Prerequisites
* Python 3.14
* Google Gemini API Key

#### Installation and Setup

1. **Clone the repository:**
git clone https://github.com/Bhoomi413/Equity_Research_AI_Intelligent_System.git
cd Equity_Research_AI_Intelligent_System


2. **Set up a virtual environment:**
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt

3. **Configure environment variables:**
copy .env.example .env
Add your Google Gemini API key to the .env file.

4. **Launch the application:**
* **Terminal 1: Backend**
uvicorn backend.main:app --reload

* **Terminal 2: Frontend**
streamlit run frontend/app.py

---

## Repository Status & Access

This project is actively used as part of my professional portfolio and B.Tech major project evaluation. 

**Recruiters & Hiring Managers:** You are welcome to clone, explore, and test the RAG pipeline. If you have questions about the system architecture or AI integration, feel free to reach out!
**Students & Peer Reviewers:** This code is indexed for academic evaluation. Please use it for inspiration or reference only. To maintain academic integrity, do not copy or replicate these files for university submissions.


### Future Improvements
- Add Alembic for database schema migrations