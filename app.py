import streamlit as st
from rag import load_pdf, get_text_chunks, get_vectorstore, handle_userinput

def main():
    st.set_page_config(page_title="EQUITY RESEARCH")
    st.header("compare company's given annual report to facts")
    user_question=st.text_input("Ask queries related to the uploaded documents")
    # if user_question:
    #     handle_userinput(user_question)

    with st.sidebar:
        st.subheader("Your Documets")
        pdfs=st.file_uploader("Click to upload your document and then Click on 'PROCESS'")
        company_name=st.text_input("Write Company Name")
        if st.button("PROCESS"):
            with st.spinner("Processing"):
                #get the text which is inside pdf
                raw_text=load_pdf(pdfs)

                #get the text chunks
                text_chunks=get_text_chunks(raw_text)

                #get the embeddings and vector store
                vectorstore=get_vectorstore(text_chunks)

                st.session_state.vectorstore = vectorstore

    if user_question:
        if "vectorstore" in st.session_state:
            result = handle_userinput(user_question, st.session_state.vectorstore, company_name)
            st.text(result)

if __name__=='__main__':
    main()