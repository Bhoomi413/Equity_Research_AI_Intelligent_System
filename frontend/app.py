
import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_URL", "").rstrip("/")



def auth_headers():
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"}


def api_get(path, timeout=30):
    return requests.get(
        f"{API_BASE}{path}",
        headers=auth_headers(),
        timeout=timeout,
    )


def api_post(path, **kwargs):
    return requests.post(
        f"{API_BASE}{path}",
        headers=auth_headers(),
        timeout=kwargs.pop("timeout", 30),
        **kwargs,
    )

def api_delete(path, timeout=30):
    return requests.delete(
        f"{API_BASE}{path}",
        headers=auth_headers(),
        timeout=timeout,
    )


def load_conversation(conversation_id):
    resp = api_get(f"/conversations/{conversation_id}")

    if resp.status_code == 200:
        data = resp.json()
        st.session_state["conversation_id"]=data["id"]
        st.session_state["messages"] = data.get("messages", [])
        st.session_state["document_id"]= data["document_id"]
        st.session_state["company_name"] = data.get("company_name", "")
        st.session_state["conversation_title"] = data.get(
            "title", "New conversation"
        )
        return True

    st.error(f"Could not load conversation: {resp.text}")
    return False


def create_conversation(document_id):
    resp = api_post(
        "/conversations",
        json={"document_id": document_id},
    )

    if resp.status_code in (200, 201):
        data = resp.json()
        st.session_state["conversation_id"]= data["id"]
        st.session_state["document_id"] = data["document_id"]
        st.session_state["company_name"] = data.get("company_name", "")
        st.session_state["conversation_title"] = (
            data.get("title") or "New conversation"
        )
        st.session_state["messages"] = []
        return True

    st.error(f"Could not create conversation: {resp.text}")
    return False


def clear_active_conversation():
    for key in [
        "conversation_id",
        "messages",
        "conversation_title",
    ]:
        st.session_state.pop(key, None)



def show_login():
    st.subheader("Login")

    username= st.text_input("Username", key="login_user")
    password = st.text_input(
        "Password", type="password", key="login_pass"
    )

    if st.button("Login", use_container_width=True):
        if not username or not password:
            st.warning("Please fill both fields.")
            return

        try:
            resp= requests.post(
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

        except requests.exceptions.RequestException as e:
            st.error(f"Could not connect to backend: {e}")


def show_register():
    st.subheader("Create an Account")
    username = st.text_input("Username", key="reg_user")
    email = st.text_input("Email", key="reg_email")
    password = st.text_input(
        "Password", type="password", key="reg_pass"
    )

    if st.button("Register", use_container_width=True):
        if not username or not email or not password:
            st.warning("Please fill all fields.")
            return

        try:
            resp = requests.post(
                f"{API_BASE}/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password,
                },
                timeout=30,
            )
            if resp.status_code == 201:
                st.success("Account created!You can now log in.")
            else:
                st.error(
                    resp.json().get("detail","Registration failed")
                )

        except requests.exceptions.RequestException as e:
            st.error(f"Could not connect to backend: {e}")



def get_documents():
    resp = api_get("/documents/my")

    if resp.status_code==200:
        return resp.json()

    if resp.status_code==401:
        st.error("Session expired. Please log in again.")
    elif resp.status_code!=200:
        st.error(f"Could not load documents: {resp.text}")

    return []


def get_conversations():
    resp = api_get("/conversations/my")

    if resp.status_code==200:
        return resp.json()

    if resp.status_code ==401:
        st.error("Session expired. Please log in again.")
    elif resp.status_code != 200:
        st.error(f"Could not load conversations: {resp.text}")

    return []



def show_main_app():
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1150px;
            padding-top: 2rem;
        }
        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(128,128,128,0.2);
        }
        .app-subtitle {
            color: #9CA3AF;
            font-size: 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    #load data used by the sidebar.
    try:
        documents = get_documents()
        conversations = get_conversations()
    except requests.exceptions.RequestException as e:
        st.error(f"Could not connect to backend: {e}")
        return


    with st.sidebar:
        st.title("Equity Research")
        st.caption("Annual Report Intelligence")

        st.write(f"Logged in as **{st.session_state.get('username')}**")

        if st.button("Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


        
        with st.expander("Profile & Account"):
            st.caption(f"Username: {st.session_state.get('username', '')}")

            st.markdown("**Change Password**")

            with st.form("change_password_form"):
                current_password = st.text_input(
                    "Current password",
                    type="password",
                )
                new_password = st.text_input(
                    "New password",
                    type="password",
                )
                confirm_password = st.text_input(
                    "Confirm new password",
                    type="password",
                )

                change_submitted = st.form_submit_button(
                    "Change Password",
                    use_container_width=True,
                )

            if change_submitted:
                if not current_password or not new_password or not confirm_password:
                    st.warning("Please fill in all password fields.")
                elif len(new_password) < 8:
                    st.warning("New password must be at least 8 characters.")
                elif new_password != confirm_password:
                    st.warning("New passwords do not match.")
                elif current_password == new_password:
                    st.warning("Choose a different new password.")
                else:
                    try:
                        resp = api_post(
                            "/auth/change-password",
                            json={
                                "current_password": current_password,
                                "new_password": new_password,
                            },
                        )

                        if resp.status_code == 200:
                            st.success("Password changed successfully.")
                        else:
                            try:
                                detail = resp.json().get(
                                    "detail", "Password change failed."
                                )
                            except ValueError:
                                detail = "Password change failed."
                            st.error(detail)

                    except requests.exceptions.RequestException as e:
                        st.error(f"Request failed: {e}")

            st.divider()
            st.markdown("**Delete Account**")
            st.warning(
                "This permanently deletes your account and associated data."
            )

            confirm_delete = st.checkbox(
                "I understand that this action is permanent.",
                key="confirm_delete_account",
            )

            if st.button(
                "Delete My Account",
                type="primary",
                use_container_width=True,
            ):
                if not confirm_delete:
                    st.warning("Please confirm before deleting your account.")
                else:
                    try:
                        resp = api_delete("/auth/delete-account")

                        if resp.status_code == 200:
                            for key in list(st.session_state.keys()):
                                del st.session_state[key]
                            st.rerun()
                        else:
                            try:
                                detail = resp.json().get(
                                    "detail", "Account deletion failed."
                                )
                            except ValueError:
                                detail = "Account deletion failed."
                            st.error(detail)

                    except requests.exceptions.RequestException as e:
                        st.error(f"Request failed: {e}")



        st.divider()

        if st.button("+ New analysis",use_container_width=True,type="primary",):
            clear_active_conversation()
            st.session_state.pop("document_id", None)
            st.session_state.pop("company_name", None)
            st.rerun()

        st.subheader("Your Documents")
        with st.expander("Upload annual report",expanded=False):
            pdf = st.file_uploader(
                "Choose a PDF",
                type=["pdf"],
                key= "report_upload",
            )

            company_name = st.text_input(
                "Company name",
                key="upload_company",
            )

            if st.button("Process document", use_container_width=True):
                if pdf is None:
                    st.warning("Please upload a PDF first.")
                elif not company_name.strip():
                    st.warning("Please enter the company name.")
                else:
                    try:
                        with st.spinner("Processing report..."):
                            resp = requests.post(
                                f"{API_BASE}/documents/upload",
                                files={
                                    "file": (
                                        pdf.name,
                                        pdf.getvalue(),
                                        "application/pdf",
                                    )
                                },
                                data={"company_name": company_name.strip()},
                                headers=auth_headers(),
                                timeout=300,
                            )

                        if resp.status_code != 200:
                            st.error(f"Upload failed: {resp.text}")

                        else:
                            data = resp.json()
                            document_id = data.get("document_id")

                            if document_id is None:
                                st.error(
                                    "The upload response has no "
                                    "document_id. Check the FastAPI "
                                    "upload endpoint response.")
                            else:
                                st.session_state["file_hash"] = data.get(
                                    "file_hash"
                                )
                                st.session_state["document_id"] = (
                                    document_id
                                )

                                if create_conversation(document_id):
                                    cached = (
                                        "Loaded from cache"
                                        if data.get("hash_exists")
                                        else "Embedded and saved"
                                    )
                                    st.success(f"{cached} — ready")
                                    st.rerun()

                    except requests.exceptions.RequestException as e:
                        st.error(f"Upload request failed: {e}")

        if documents:
            for doc in documents:
                is_current = (
                    doc["id"] == st.session_state.get("document_id")
                )

                label = (
                    f"{doc['filename']}"
                    if not is_current
                    else f"{doc['filename']} ✓"
                )

                with st.container(border=True):
                    st.caption(doc.get("company_name", ""))
                    st.write(label)

                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button(
                            "New chat",
                            key=f"new_chat_{doc['id']}",
                            use_container_width=True,
                        ):
                            try:
                                if create_conversation(doc["id"]):
                                    st.rerun()
                            except requests.exceptions.RequestException as e:
                                st.error(str(e))

                    with col2:
                        if st.button(
                            "Delete",
                            key=f"delete_doc_{doc['id']}",
                            use_container_width=True,
                        ):
                            try:
                                del_resp = requests.delete(
                                    f"{API_BASE}/delete/document/{doc['id']}",
                                    headers=auth_headers(),
                                    timeout=30,
                                )

                                if del_resp.status_code== 200:
                                    if (
                                        st.session_state.get("document_id")
                                        == doc["id"]
                                    ):
                                        clear_active_conversation()
                                        for key in [
                                            "document_id",
                                            "file_hash",
                                            "company_name",
                                        ]:
                                            st.session_state.pop(key, None)

                                    st.session_state["notice"] = (
                                        f"{doc['filename']} deleted."
                                    )
                                    st.rerun()
                                else:
                                    st.error(del_resp.text)

                            except requests.exceptions.RequestException as e:
                                st.error(f"Delete failed: {e}")
        else:
            st.caption("No documents uploaded yet.")

        st.divider()
        st.subheader("Recent conversations")

        if conversations:
            for conv in conversations:
                title = conv.get("title") or "New conversation"
                company = conv.get("company_name") or ""

                is_active = (
                    conv["id"]
                    == st.session_state.get("conversation_id")
                )

                label = f"{title}" if is_active else title

                if st.button(
                    label,
                    key=f"conversation_{conv['id']}",
                    use_container_width=True,
                    help=company,
                ):
                    try:
                        if load_conversation(conv["id"]):
                            st.rerun()
                    except requests.exceptions.RequestException as e:
                        st.error(f"Could not open conversation: {e}")
        else:
            st.caption("Your conversations will appear here.")


    if "notice" in st.session_state:
        st.success(st.session_state.pop("notice"))

    st.title("Equity Research")
    st.markdown(
        '<p class="app-subtitle">Analyze annual reports, '
        'understand financial performance, and examine risks.</p>',
        unsafe_allow_html=True,
    )

    conversation_id = st.session_state.get("conversation_id")
    messages = st.session_state.get("messages", [])

    if conversation_id is None:
        st.info(
            "Select a document and click **New chat**, or upload "
            "a report to begin your analysis."
        )

        st.markdown("### What you can analyze")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("- Revenue and profitability")
            st.markdown("- Financial statement comparisons")

        with col2:
            st.markdown("- Business risks and disclosures")
            st.markdown("- Report findings versus related news")

        return

    st.caption(
        f"Company: {st.session_state.get('company_name', 'Not specified')}"
    )

    # Render the existing conversation.
    for message in messages:
        role = message.get("role", "assistant")

        if role not in ("user", "assistant"):
            continue

        with st.chat_message(role):
            st.markdown(message.get("content", ""))

    # Chat input submits only when the user sends a message.
    question = st.chat_input("Ask a question about this annual report...")

    if question:
        try:
            with st.spinner("Analyzing report and related news..."):
                resp = api_post(
                    f"/conversations/{conversation_id}/query",
                    json={"question": question},
                    timeout=300,
                )

            if resp.status_code == 200:
                result = resp.json()

                # Reload from the backend so the stored conversation
                # remains the source of truth.
                with st.spinner("Loading conversation..."):
                    history_resp = api_get(
                        f"/conversations/{conversation_id}"
                    )

                if history_resp.status_code == 200:
                    history_data = history_resp.json()
                    st.session_state["messages"] = history_data.get(
                        "messages", []
                    )
                    st.session_state["conversation_title"] = (
                        history_data.get("title") or "New conversation"
                    )
                else:
                    # Fallback if the query succeeded but history retrieval not.
                    st.session_state["messages"] = messages + [
                        {"role": "user", "content": question},
                        {
                            "role": "assistant",
                            "content": result.get("content", ""),
                        },
                    ]

                st.rerun()

            elif resp.status_code == 403:
                st.error("You don't have access to this document.")
            elif resp.status_code == 404:
                st.error(
                    "This conversation or its document no longer exists. "
                    "Select a document and start a new chat."
                )
            else:
                try:
                    detail = resp.json().get("detail", "Query failed")
                except ValueError:
                    detail = resp.text or "Query failed"

                st.error(detail)

        except requests.exceptions.RequestException as e:
            st.error(f"Query request failed: {e}")



def main():
    st.set_page_config(
        page_title="Equity Research",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if not API_BASE:
        st.error("API_URL is missing from your environment configuration.")
        return

    if "token" not in st.session_state:
        st.title("Equity Research")
        st.caption("Annual Report Intelligence")

        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            show_login()

        with tab2:
            show_register()
    else:
        show_main_app()


if __name__ == "__main__":
    main()