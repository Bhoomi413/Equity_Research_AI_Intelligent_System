# Equity Research Intelligent System

An AI-powered RAG application for analyzing annual reports.

## Features
- User uploads annual report
- Cross reference with today's news
- Then form an investment view

## Technical Decisions

Handling Scanned PDFs
Some annual reports are distributed as scanned image-based PDFs where traditional text extraction methods return no text.
To handle this, each page is converted into an image using PyMuPDF and processed using Gemini Vision OCR. The extracted text is then processed through the RAG pipeline for retrieval.

Hash-Based Caching System
To optimize performance and reduce cost, each PDF is identified using a SHA-256 hash. If a document has already been processed, the system skips OCR and embedding generation and directly loads the stored FAISS index.

Vector Storage Strategy
Each document’s embeddings are stored separately in a structured directory: knowledgebase for persistance across application restarts.

PyMuPDF4LLM was used instead of PyMuPDF
The dataset used in this project consists of company annual reports, which contain structured Financial statements, Multi-column layouts, Tabular data. PyMuPDF4LLM used as it preserves layout and structure of complex PDFs 

hybrid retrieval 
implement manual reciprocal rank fusion based hybrid retrieval, with chunk id maetadata mapping and custom fusion logic replacing LangChain EnsembleRetriever, combines BM25 (keyword-based search) and semantic search (embeddings) to improve document retrieval accuracy.

## AI-Cost-Optimization 
PDF Processing
- Uses PyMuPDF4LLM PDF Loader for free native text extraction from digital PDFs.
- detects whether sufficient text was extracted or not.
- Falls back to Gemini OCR only for scanned or image-based PDFs.
- Reduces OCR API calls, processing time, and overall AI COSTS.
- The system follows a HYBRID INGESTION approach to handle different types of PDF

Hash-Based Caching System
- each PDF is identified using a SHA-256 hash.
- If document has already been processed,system skips OCR, embedding generation and loads directly
- reduce multimodal input token cost


## Project Structure

```text
project/
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── __init__.py
│   ├── database.py
│   ├── auth.py
│   └── rag/
│       ├── __init__.py
│       └── rag.py
│
├── frontend/
│   └── app.py
│
├── knowledgebase/
│   └── userid/
│       ├── index.pkl
│       ├── index.faiss
│       └── chunks.pkl
│
├── uploadedPDF/
│
└── .gitignore


```


## Challenges Faced
JSONDecodeError occurred due to empty files. To handle this, a try/except block was introduced around the JSON loading logic. If the cache file is missing, empty, or corrupted, the system safely initializes an empty dictionary instead of crashing.