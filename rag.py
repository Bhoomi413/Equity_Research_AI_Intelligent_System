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




def load_pdf(pdf):
    base_name =os.path.basename(pdf.name)
    file_path=os.path.join("UploadedPDF",base_name)
    #writing to UploadedPDF folder
    # with open(file_path, "wb") as f:
    #     f.write(pdf.getbuffer())

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
                metadata={"page": i + 1}
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
        return FAISS.load_local(embedded_file_path,embeddings, allow_dangerous_deserialization=True)
    path = os.path.join("knowledgebase", file_hash_value)
    text_chunks = [chunk for chunk in text_chunks if chunk.page_content.strip()]
    vector_store=FAISS.from_documents(text_chunks,embedding=embeddings)
    vector_store.save_local(path)
    return vector_store

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
def handle_userinput(user_question, vectorstore, company_name):

    user_question=str(user_question).strip()
    docs=vectorstore.similarity_search(
        user_question,
        k=3
    )

    context = "\n\n".join(
        [doc.page_content for doc in docs]
    )

    chain=get_conversational_chain()

    fetched_news=fetch_news(company_name)   
    

    result=chain.invoke({
        "input": user_question,
        "Related_latest_news": fetched_news,
        "context": context
        })
    return result