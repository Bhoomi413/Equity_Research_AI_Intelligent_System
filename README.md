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