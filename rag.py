from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import requests
import fitz
import base64
import time
from langchain_core.documents import Document
import hashlib
import json
from langchain_pymupdf4llm import PyMuPDF4LLMLoader
from rank_bm25 import BM25Okapi
import numpy as np
import streamlit as st
import pickle
import os

load_dotenv()
os.getenv("NEWS_API_KEY")
os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
my_news_api = os.getenv("NEWS_API_KEY")

def fetch_news(company_name):
    url="https://newsapi.org/v2/everything"
    if not my_news_api:
        return "API key is missing"
    params={
        "q":company_name,
        "sortBy": "publishedAt",
        "pageSize":5,
        "apiKey":my_news_api
    }

    response=requests.get(url, params=params)
    data=response.json()
    articles=data.get("articles", [])
    if not articles:
        return "No news found"
    news_text=""
    for article in articles:
        title=article["title"]
        source=article["source"]["name"]
        news_text+=f"{title} ({source})\n"

    return news_text




def file_hashing(pdf):
    base_name =os.path.basename(pdf.name)
    file_path=os.path.join("UploadedPDF",base_name)
    with open(file_path, "wb") as f:
                f.write(pdf.getbuffer())
    with open(file_path,"rb") as f:
        digest=hashlib.file_digest(f,"sha256")
        file_hash_value=digest.hexdigest()
    hashed_file_path=os.path.join("FileHashingStored","file_hash.json")
    try:
        with open(hashed_file_path,"r",encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
            data={}
    if file_hash_value in data:
        return True,file_hash_value,data[file_hash_value]
    else:
        data[file_hash_value]={
                "kb_path": os.path.join("knowledgebase", file_hash_value)
                }
        with open(hashed_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    return False,file_hash_value,data[file_hash_value]["kb_path"]




def load_pdf(pdf, company_name):
    base_name =os.path.basename(pdf.name)
    file_path=os.path.join("UploadedPDF",base_name)
    pymupdf_loader=PyMuPDF4LLMLoader(file_path)
    pymupdf_docs=pymupdf_loader.load()
    text_pages = 0
    total_pages=0
    for pymupdf_doc in pymupdf_docs:
         total_pages+=1
         if len(pymupdf_doc.page_content.strip()) > 100:
             text_pages += 1
    try:
         text_pages_ratio=text_pages/total_pages
    except ArithmeticError:
         text_pages_ratio=0
    if text_pages_ratio>0.85:
         return pymupdf_docs
    
#  OCR FALLBACK
    else:        
        model=genai.GenerativeModel("gemini-2.5-flash-lite")

        pdf_doc=fitz.open(file_path)
        docs=[]

        for i, page in enumerate(pdf_doc):
            #convert page to image and dpi=150 balances OCR accuracy and payload size
            img_bytes=page.get_pixmap(dpi=150).tobytes("png")
            img_base64=base64.b64encode(img_bytes).decode()
            response=model.generate_content([
                {"inline_data": {"mime_type": "image/png", "data": img_base64}},
                "Extract all text from this page. Return only the text."
                ])
            text=response.text.strip()
            if text:
                docs.append(Document(
                    page_content=text,
                    metadata={"page": i + 1,
                              "source": file_path,
                              "file_path": file_path,
                              "company": company_name}
                    ))
            #wait 6 seconds as dont hit gemini free tier rate limit
            time.sleep(6)
        return docs

        
def get_text_chunks(documents):
    text_splitter= RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks=text_splitter.split_documents(documents)
    return chunks        

def get_vectorstore(text_chunks,hash_exists,file_hash_value,embedded_file_path):
    embeddings=GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    if hash_exists:
        vector_store=FAISS.load_local(embedded_file_path,embeddings, allow_dangerous_deserialization=True)
        chunks_file = os.path.join(embedded_file_path, "chunks.pkl")

        with open(chunks_file, "rb") as f:
            text_chunks = pickle.load(f)

        return vector_store, text_chunks
        # return FAISS.load_local(embedded_file_path,embeddings, allow_dangerous_deserialization=True)

    path = os.path.join("knowledgebase", file_hash_value)
    text_chunks = [chunk for chunk in text_chunks if chunk.page_content.strip()]
    vector_store=FAISS.from_documents(text_chunks,embedding=embeddings)
    vector_store.save_local(path)
    with open(os.path.join(path, "chunks.pkl"), "wb") as f:
        pickle.dump(text_chunks, f)
    return vector_store, text_chunks

def bm25_index(chunks):
    texts=[]
    for chunk in chunks:
        texts.append(chunk.page_content)
    corpus_list=[text.lower().split() for text in texts]
    return BM25Okapi(corpus_list)

def reciprocalrankfusioncalc(semantic_docs, keyword_matched_docs, k=60):
    rrf_scores={}
    id_to_docChunk={}

    for rank,doc in enumerate(semantic_docs,start=1):
        chunk_id=doc.metadata["chunk_id"]
        id_to_docChunk[chunk_id]=doc
        rrf_scores[chunk_id]=1/(60+rank)

    for rank,doc in enumerate(keyword_matched_docs,start=1):
        chunk_id=doc.metadata["chunk_id"]
        id_to_docChunk[chunk_id]= doc
        rrf_scores[chunk_id]=rrf_scores.get(chunk_id,0)+(1/(60+rank))

    Descending_sorted_doc=sorted(rrf_scores.items(),key=lambda x:x[1],reverse =True)
    return [id_to_docChunk[chunk_id] for chunk_id,score in Descending_sorted_doc[:5]]

def bm25_search(bm25_obj,text_chunks,query_tokens,n=5):
    scores=bm25_obj.get_scores(query_tokens)
    best_matched_index=np.argsort(scores)[::-1][:n]
    best_matched_docs=[]
    for i in best_matched_index:
        best_matched_docs.append(text_chunks[i])
    return best_matched_docs

def get_conversational_chain():
    prompt=ChatPromptTemplate.from_messages([
        ('system',"""You are a senior equity research analyst.

Based on the annual report excerpts and recent news provided, generate a structured research report.

Return ONLY a JSON object with these exact keys (no markdown, no explanation):

{{
  "snapshot": "2-3 sentence company overview from the report",
  "financials": "Key revenue, profit, growth numbers mentioned in the report",
  "news_sentiment": "Summarize the news tone — positive, negative or mixed and why",
  "conflict": "Does the news contradict the annual report outlook? Explain specifically.",
  "risks": ["risk 1", "risk 2", "risk 3"],
  "verdict": "1 paragraph analyst verdict — BUY / HOLD / CAUTION with reasoning"
}}"""),
        ("human", "Context:\n{context}\n\nRelated_latest_news:\n{Related_latest_news}\n\nQuestion:\n{input}")
    ])

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.3
    )

    chain = prompt | model | StrOutputParser()

    return chain


#Handle Userinput
def handle_userinput(user_question, vectorstore, company_name, text_chunks):

    user_question=str(user_question).strip()
    semantic_docs=vectorstore.similarity_search(
        user_question,
        k=5
    )
    query_tokens=user_question.lower().split()
    bm25_obj=bm25_index(text_chunks)
    keyword_matched_docs=bm25_search(bm25_obj,text_chunks, query_tokens,n=5)
    print("semantic doc metadata:", semantic_docs[0].metadata)
    print("bm25 doc metadata:", keyword_matched_docs[0].metadata)
    # st.write("semantic metadata:", semantic_docs[0].metadata)
    # st.write("bm25 metadata:", keyword_matched_docs[0].metadata)
    final_fused_top_docs = reciprocalrankfusioncalc(semantic_docs, keyword_matched_docs, k=60)

    context = "\n\n".join(
        [doc.page_content for doc in final_fused_top_docs]
    )

    chain=get_conversational_chain()

    fetched_news=fetch_news(company_name)   
    

    result=chain.invoke({
        "input": user_question,
        "Related_latest_news": fetched_news,
        "context": context
        })
    
    # ADDING CITATIONS
    sources = []
    for doc in final_fused_top_docs:
        source = doc.metadata.get("source", "unknown")
        page_no = doc.metadata.get("page", 0)

        file_name = os.path.basename(source)

        print("SOURCE TYPE:", type(source))
        print("SOURCE VALUE:", source)

        sources.append({
                "file": file_name,
                "page": page_no,
                "preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                "chunk": doc.page_content
            })

    return {
        "content": result,
        "citations": sources
    }