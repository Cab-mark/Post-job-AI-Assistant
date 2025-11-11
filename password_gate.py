# password_gate.py
import os, hmac, hashlib, streamlit as st
PW_HASH = os.getenv("APP_PW_HASH", "")
def require_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("■ Protected PoC")
        pw = st.text_input("Enter password to continue", type="password")
        if st.button("Unlock"):
            if not PW_HASH:
                st.error("No password configured on server")
            else:
                hashed = hashlib.sha256(pw.encode()).hexdigest()
                if hmac.compare_digest(hashed, PW_HASH):
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password")
        st.stop() # stop rest of app until authenticated