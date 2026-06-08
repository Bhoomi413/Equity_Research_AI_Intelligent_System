import streamlit as st
from rag import file_hashing, load_pdf, get_text_chunks, get_vectorstore, handle_userinput

def main():
    st.set_page_config(page_title="EQUITY RESEARCH")
    st.header("compare company's given annual report to facts")
    user_question=st.text_input("Ask queries related to the uploaded documents")
    # if user_question:
    #     handle_userinput(user_question)

    with st.sidebar:
        st.subheader("Your Documets")
        pdf=st.file_uploader("Click to upload your document and then Click on 'PROCESS'")
        company_name=st.text_input("Write Company Name")
        if st.button("PROCESS"):
            with st.spinner("Processing"):
                #check does file already embedded
                hash_exists,file_hash_value,embedded_file_path=file_hashing(pdf)
                if hash_exists:
                    vectorstore=get_vectorstore(text_chunks=None, hash_exists=True,file_hash_value=file_hash_value,embedded_file_path= embedded_file_path)

                else:
                    #get the text which is inside pdf
                    raw_text=load_pdf(pdf, company_name)

                    #get the text chunks
                    text_chunks=get_text_chunks(raw_text)

                    #get the embeddings and vector store
                    vectorstore=get_vectorstore(text_chunks,hash_exists,file_hash_value,embedded_file_path)

                    st.session_state.vectorstore = vectorstore

    if user_question:
        if "vectorstore" in st.session_state:
            result = handle_userinput(user_question, st.session_state.vectorstore, company_name, text_chunks)
            st.text(result)

if __name__=='__main__':
    main()