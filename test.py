from langchain_pymupdf4llm import PyMuPDF4LLMLoader

print("START")

# # def load_pdf(pdf, company_name):
# #     base_name =os.path.basename(pdf.name)
# #     file_path=os.path.join("UploadedPDF",base_name)
    
file_path="UploadedPDF/test_intro_table_text_annualreport.pdf"
pymupdf_loader=PyMuPDF4LLMLoader(file_path)
print("LOADER CREATED")
pymupdf_docs=pymupdf_loader.load()
text_pages = 0
total_pages=0
for pymupdf_doc in pymupdf_docs:
        total_pages+=1
        if len(pymupdf_doc.page_content.strip()) >=30:
           text_pages += 1
           print("\n")  
           print(pymupdf_doc.page_content.strip())
           print(pymupdf_doc.metadata)
           print("\n NEW PAGE")  
try:
  text_pages_ratio=text_pages/total_pages
except ArithmeticError:
         text_pages_ratio=0
if text_pages_ratio>0.85:
         print("TEXT_DOC")

