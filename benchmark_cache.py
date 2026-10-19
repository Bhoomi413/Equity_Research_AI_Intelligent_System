import os
import time
import pickle
import statistics
import hashlib
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from backend.utils.cache_manager import vectorstore_cache

user_id = 1
filename = "Amazon-2025-Annual-Report.pdf"  
user_pdf_dir = os.path.join("UploadedPDF", f"user_{user_id}")
pdf_path=None
for root, dirs, files in os.walk(user_pdf_dir):
    if filename in files:
        pdf_path= os.path.join(root, filename)
        break
if pdf_path is None:
    raise FileNotFoundError(f"{filename} not found for user {user_id}")
with open(pdf_path,"rb") as f:
    file_hash = hashlib.sha256(f.read()).hexdigest()
kb_path = os.path.join("knowledgebase", f"user_{user_id}", file_hash)
print("Selected PDF:", os.path.abspath(pdf_path))
print("Generated SHA-256:", file_hash)
print("Expected knowledgebase: ", os.path.abspath(kb_path))


cache_key = f"user_{user_id}:{file_hash}"

embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
def load_from_disk():
    start = time.perf_counter()

    vector_store = FAISS.load_local(
        kb_path,
        embeddings_model,
        allow_dangerous_deserialization=True,
    )

    with open(os.path.join(kb_path, "chunks.pkl"), "rb") as f:
        text_chunks = pickle.load(f)

    return time.perf_counter() - start, vector_store, text_chunks


_, vector_store, text_chunks = load_from_disk()
vectorstore_cache.put(cache_key, (vector_store, text_chunks))

disk_times = []
ram_times = []

for i in range(30):
    disk_load_time, _, _ = load_from_disk()
    disk_times.append(disk_load_time * 1000)

    start = time.perf_counter()
    cached_data = vectorstore_cache.get(cache_key)
    ram_times.append((time.perf_counter() - start) * 1000)

    assert cached_data is not None, "Unexpected cache miss"

disk_median = statistics.median(disk_times)
ram_median = statistics.median(ram_times)



print(f"Disk load median: {disk_median:.2f} ms")
print(f"RAM cache hit median: {ram_median:.2f} ms")
print(f"speedup:{disk_median / ram_median:.2f}x")
print(f"time saved per load:{disk_median - ram_median:.2f} ms")

