from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
# import google.generativeai as genai
from google import genai
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import requests
import pymupdf
import base64
import time
from langchain_core.documents import Document
from langchain_pymupdf4llm import PyMuPDF4LLMLoader
from rank_bm25 import BM25Okapi
import numpy as np
import pickle
import os

load_dotenv()
os.getenv("NEWS_API_KEY")
os.getenv("GOOGLE_API_KEY")
# genai.configure(api_key=os.getenv("GOOGLE_API_KEY")) 
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




def load_pdf(file_path, company_name):
    docs = []

    with pymupdf.open(file_path) as pdf_doc:
        for i, page_obj in enumerate(pdf_doc):
            page_num = i + 1
            extracted_text = page_obj.get_text().strip()
            docs.append(Document(
                    page_content=extracted_text,
                    metadata={"page": page_num, "source": file_path, "file_path": file_path, "company": company_name}
                ))

    return docs
        
def get_text_chunks(documents):
    text_splitter= RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks=text_splitter.split_documents(documents)
    return chunks        

def get_vectorstore(text_chunks,hash_exists,embedded_file_path):
    from langchain_huggingface import HuggingFaceEmbeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    # embeddings=GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    if hash_exists:
        vector_store=FAISS.load_local(embedded_file_path,embeddings, allow_dangerous_deserialization=True)
        chunks_file = os.path.join(embedded_file_path, "chunks.pkl")

        with open(chunks_file, "rb") as f:
            text_chunks = pickle.load(f)

        return vector_store, text_chunks
        # return FAISS.load_local(embedded_file_path,embeddings, allow_dangerous_deserialization=True)

    #path is os.path.join("knowledgebase", user_id, file_hash_value)
    path = embedded_file_path
    print("SAVING TO:", path)
    os.makedirs(path, exist_ok=True)
    text_chunks = [chunk for chunk in text_chunks if chunk.page_content.strip()]
    for chunk_id, chunk in enumerate(text_chunks):
        chunk.metadata["chunk_id"] = chunk_id
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


def rewrite_query(original_question: str, history: list) -> str:
    if not history:
        return original_question

    history_text = ""
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    rewrite_prompt = ChatPromptTemplate.from_messages([
        ("system", """
        You rewrite the user's latest question as a fully standalone question using the conversation history.
        Only clarify what "it", "that", "this", or "they" refer to based on the conversation history.
        Do NOT add facts or assumptions that are not in the conversation.
        Do NOT answer the question or change its original meaning.
        Return only the rewritten question, nothing else."""),
           ("human",
            "Conversation history:\n{history}\n\n"
            "Latest question:\n{question}")
    ])

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0)
    chain = rewrite_prompt | model | StrOutputParser()
    rewritten = chain.invoke({
        "history": history_text,
        "question": original_question
    })
    print(f"[rewrite] original: {original_question}")
    print(f"[rewrite] rewritten: {rewritten}")
    return rewritten


def get_conversational_chain():
    prompt=ChatPromptTemplate.from_messages([
        ('system',"""
You are an equity research assistant. Answer the user's question 
using only the provided annual report excerpts. If relevant news 
exists that supports or contradicts the answer, mention it explicitly. 
Be factual, cite what the document says, and flag any contradiction 
with recent news. Never fabricate figures or opinions.

IMPORTANT:Before answering, check whether the "Context" actually contains meaningful annual-report / financial content (business description, financial figures, MD&A, risk factors, etc.).
- If the Context is empty, irrelevant, or does not contain real financial/business content, you MUST NOT invent numbers or a verdict.
- Never fabricate figures, company facts that are not directly supported by the Context.

"""),
        ("human", "Context:\n{context}\n\nRelated_latest_news:\n{Related_latest_news}\n\nQuestion:\n{input}")
    ])

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0.3
    )

    chain = prompt | model | StrOutputParser()

    return chain



#Handle Userinput
def handle_userinput(user_question, vectorstore, company_name, text_chunks, conversation_history=[]):

    user_question=str(user_question).strip()

    # rewrite only when there is history
    retrieval_query = rewrite_query(user_question, conversation_history)

    semantic_docs=vectorstore.similarity_search(
        retrieval_query,
        k=5
    )
    query_tokens=retrieval_query.lower().split()
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
        "input": retrieval_query,  # rewritten standalone query, not original
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