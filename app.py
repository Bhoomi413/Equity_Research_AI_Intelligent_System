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
                    vectorstore,text_chunks=get_vectorstore(text_chunks=None, hash_exists=True,file_hash_value=file_hash_value,embedded_file_path= embedded_file_path)
                    for id, chunk in enumerate(text_chunks):
                        chunk.metadata['chunk_id'] = id
                else:
                    #get the text which is inside pdf
                    raw_text=load_pdf(pdf, company_name)

                    #get the text chunks
                    text_chunks=get_text_chunks(raw_text)
                    for id, chunk in enumerate(text_chunks):
                        chunk.metadata['chunk_id']=id

                    #get the embeddings and vector store
                    vectorstore,text_chunks=get_vectorstore(text_chunks,hash_exists,file_hash_value,embedded_file_path)

                    st.session_state.vectorstore = vectorstore
                    st.session_state.text_chunks=text_chunks


    if user_question:
        if "vectorstore" in st.session_state:
            response = handle_userinput(user_question, st.session_state.vectorstore, company_name, st.session_state.text_chunks)
            st.text(response['content'])
            for citation in response['citations']:
                st.write(f"file-{citation['file']} page-{citation['page']}\npreview-{citation['preview']}")
                with st.expander("View full source chunk"):
                    st.write(citation["chunk"])

if __name__=='__main__':
    main()