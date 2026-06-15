import streamlit as st
import requests
from dotenv import load_dotenv
import json
import os

load_dotenv()

API_BASE= os.getenv("API_URL")
 
 
 
def auth_headers():
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"}
 
 
def show_login():
    st.subheader("Login")
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
 
    if st.button("Login"):
        if not username or not password:
            st.warning("Please fill both fields.")
            return
        try:
            resp = requests.post(
                f"{API_BASE}/auth/login",
                data={"username": username, "password": password},
                timeout=30,
            )
            if resp.status_code == 200:
                st.session_state["token"] = resp.json()["access_token"]
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error(resp.json().get("detail", "Login failed"))
        except requests.exceptions.ConnectionError:
            st.error("Cannot reach backend. Make sure FastAPI is running on port 8000.")
 
 
def show_register():
    st.subheader("Create an Account")
    username = st.text_input("Username", key="reg_user")
    email = st.text_input("Email", key="reg_email")
    password = st.text_input("Password", type="password", key="reg_pass")
 
    if st.button("Register"):
        if not username or not email or not password:
            st.warning("Please fill all fields.")
            return
        try:
            resp = requests.post(
                f"{API_BASE}/auth/register",
                json={"username": username, "email": email, "password": password},
                timeout=30,
            )
            if resp.status_code == 201:
                st.success("Account created! You can now log in.")
            else:
                st.error(resp.json().get("detail", "Registration failed"))
        except requests.exceptions.ConnectionError:
            st.error("Cannot reach backend. Make sure FastAPI is running on port 8000.")
 
 
def show_main_app():
    st.header("compare company's given annual report to facts")
 
    user_question = st.text_input("Ask queries related to the uploaded documents")
 
    with st.sidebar:
        st.write(f"Logged in as **{st.session_state.get('username')}**")
        if st.button("Logout"):
            for key in ["token", "username", "file_hash", "company_name"]:
                st.session_state.pop(key, None)
            st.rerun()
 
        st.markdown("---")
        st.subheader("Your Documents")
 
        pdf = st.file_uploader("Click to upload your document and then Click on 'PROCESS'")
        company_name = st.text_input("Write Company Name")
 
        if st.button("PROCESS"):
            if pdf is None:
                st.warning("Please upload a PDF first.")
            elif not company_name.strip():
                st.warning("Please enter the company name.")
            else:
                with st.spinner("Processing"):
                    try:
                        resp = requests.post(
                            f"{API_BASE}/documents/upload",
                            files={"file": (pdf.name, pdf.getvalue(), "application/pdf")},
                            data={"company_name": company_name},
                            headers=auth_headers(),
                            timeout=300,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state["file_hash"] = data["file_hash"]
                            st.session_state["company_name"] = company_name
                            cached = "Loaded from cache" if data["hash_exists"] else "Embedded and saved"
                            st.success(f"{cached} chunks ready")
                        else:
                            st.error(resp.text)
                    except requests.exceptions.ConnectionError:
                        st.error("Cannot reach backend.")
 
        st.markdown("---")
        st.subheader("Previously uploaded docs")
        if st.button("Refresh list"):
            try:
                resp = requests.get(
                    f"{API_BASE}/documents/my",
                    headers=auth_headers(),
                    timeout=30,
                )
                if resp.status_code == 200:
                    docs = resp.json()
                    if docs:
                        for d in docs:
                            label = f"{d['filename']} ({d['company_name']})"
                            if st.button(label, key=f"doc_{d['id']}"):
                                st.session_state["file_hash"] = d["file_hash"]
                                st.session_state["company_name"] = d["company_name"]
                                st.info(f"Switched to: {d['filename']}")
                    else:
                        st.write("No documents uploaded yet.")
            except requests.exceptions.ConnectionError:
                st.error("Cannot reach backend.")
 
    if user_question:
        if "file_hash" not in st.session_state:
            st.warning("Please upload and process a document first.")
        else:
            with st.spinner("Thinking..."):
                try:
                    resp = requests.post(
                        f"{API_BASE}/query",
                        json={
                            "question": user_question,
                            "company_name": st.session_state.get("company_name", ""),
                            "file_hash": st.session_state["file_hash"],
                        },
                        headers=auth_headers(),
                        timeout=300,
                    )
                    if resp.status_code == 200:
                        result = resp.json()
                        raw_content = result.get("content", "")
 
                        try:
                            parsed = json.loads(raw_content)
                            st.markdown("### Research Report")
                            st.write("**Snapshot:**", parsed.get("snapshot", ""))
                            st.write("**Financials:**", parsed.get("financials", ""))
                            st.write("**News Sentiment:**", parsed.get("news_sentiment", ""))
                            st.write("**Conflicts:**", parsed.get("conflict", ""))
                            st.write("**Risks:**")
                            for risk in parsed.get("risks", []):
                                st.write(f"- {risk}")
                            st.write("**Verdict:**", parsed.get("verdict", ""))
                        except (json.JSONDecodeError, TypeError):
                            st.text(raw_content)
 
                        st.markdown("---")
                        for citation in result.get("citations", []):
                            st.write(f"file-{citation['file']} page-{citation['page']}\npreview-{citation['preview']}")
                            with st.expander("View full source chunk"):
                                st.write(citation["chunk"])
 
                    elif resp.status_code == 403:
                        st.error("You don't have access to that document.")
                    else:
                        st.error(resp.json().get("detail", "Query failed"))
                except requests.exceptions.ConnectionError:
                    st.error("Cannot reach backend.")
 
 
def main():
    st.set_page_config(page_title="EQUITY RESEARCH")
 
    if "token" not in st.session_state:
        st.title("Equity Research — Annual Report Analyser")
        tab1, tab2 = st.tabs(["Login", "Register"])
        with tab1:
            show_login()
        with tab2:
            show_register()
    else:
        show_main_app()
 
 
if __name__ == "__main__":
    main()