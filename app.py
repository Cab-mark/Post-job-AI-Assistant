import json
import os
from io import BytesIO
import streamlit as st
from openai import OpenAI

import requests
from bs4 import BeautifulSoup

# optional parsers
try:
    import docx  # python-docx
except ImportError:
    docx = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

client = OpenAI()

# warn if API key not configured
if not os.getenv("OPENAI_API_KEY"):
    st.warning("OPENAI_API_KEY not found in environment — OpenAI calls will fail until you set it.")

st.set_page_config(page_title="AI Job Schema Collector", page_icon="🧠")
st.title("AI Job Schema Collector")

st.write(
    "Start with **an upload**, **pasted text**, or **a URL** of a job advert. "
    "I'll extract what I can, then ask you only for the missing bits."
)

# --- define the target schema (example) ---
TARGET_SCHEMA = {
    "job_title": "",
    "department": "",
    "location": "",
    "salary": "",
    "grade": "",
    "closing_date": "",
    "summary": "",
    "responsibilities": "",
    "essential_criteria": "",
    "desirable_criteria": ""
}

# 1) FILE
uploaded_file = st.file_uploader("Upload job advert (txt / docx / pdf)", type=["txt", "docx", "pdf"])

# 2) PASTED TEXT
pasted_text = st.text_area("Or paste the job advert text here", height=160)

# 3) URL
url = st.text_input("Or provide a URL to the job advert")

def extract_text_from_upload(uploaded_file):
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()

    # read bytes once
    try:
        data = uploaded_file.read()
    except Exception:
        # fallback to getvalue for some stream types
        try:
            data = uploaded_file.getvalue()
        except Exception:
            return ""

    if name.endswith(".txt"):
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode("latin-1", errors="ignore")

    if name.endswith(".docx"):
        if not docx:
            st.error("DOCX support not installed. Add python-docx to requirements.")
            return ""
        try:
            document = docx.Document(BytesIO(data))
            return "\n".join(p.text for p in document.paragraphs)
        except Exception as e:
            st.error(f"Could not parse DOCX: {e}")
            return ""

    if name.endswith(".pdf"):
        if not PdfReader:
            st.error("PDF support not installed. Add pypdf to requirements.")
            return ""
        try:
            reader = PdfReader(BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as e:
            st.error(f"Could not parse PDF: {e}")
            return ""

    return ""

def extract_text_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        # remove scripts/styles then get visible text
        for elem in soup(["script", "style", "noscript"]):
            elem.decompose()
        text = soup.get_text(separator="\n")
        return text
    except Exception as e:
        st.error(f"Could not fetch URL: {e}")
        return ""

def call_openai_structurer(raw_text: str, schema: dict) -> dict:
    schema_str = json.dumps(schema, indent=2)
    prompt = f"""
You are an information extraction assistant for UK Civil Service job adverts.
Extract as many fields as you can from the text below and return ONLY valid JSON matching this schema.
If you don't know a field, leave it as an empty string.

Schema:
{schema_str}

Text:
\"\"\"{raw_text}\"\"\"
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You convert unstructured job adverts into structured JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        st.write("OpenAI Response received successfully")
    except Exception as e:
        st.error(f"OpenAI API error: {e}")
        return schema

    # robustly get the model's content
    raw_json = ""
    try:
        raw_json = resp.choices[0].message.content.strip()
    except Exception:
        try:
            raw_json = str(resp.choices[0].message).strip()
        except Exception:
            raw_json = ""

    if not raw_json:
        # last resort: stringify whole response
        try:
            raw_json = json.dumps(resp)
        except Exception:
            return schema

    try:
        parsed = json.loads(raw_json)
        return parsed
    except Exception:
        # if the model returns markdown-wrapped json, try to fix quickly
        cleaned = raw_json.strip("` \n")
        try:
            return json.loads(cleaned)
        except Exception:
            return schema

def get_missing_fields(current_schema: dict):
    return [k for k, v in current_schema.items() if not v or not str(v).strip()]

# --- session setup ---
if "schema" not in st.session_state:
    st.session_state["schema"] = TARGET_SCHEMA.copy()

if "pending_fields" not in st.session_state:
    st.session_state["pending_fields"] = list(TARGET_SCHEMA.keys())

if "current_field" not in st.session_state:
    st.session_state["current_field"] = None

# --- trigger extraction ---
if st.button("Extract from source"):
    # priority: file > pasted > url
    source_text = ""
    if uploaded_file:
        source_text = extract_text_from_upload(uploaded_file)
    elif pasted_text.strip():
        source_text = pasted_text.strip()
    elif url.strip():
        source_text = extract_text_from_url(url.strip())

    if not source_text:
        st.warning("Please upload, paste, or provide a URL first.")
    else:
        with st.spinner("Extracting fields with OpenAI..."):
            extracted = call_openai_structurer(source_text, TARGET_SCHEMA)
            st.write("Extracted data:", extracted)  # Debug output

            if isinstance(extracted, dict):
                st.session_state["schema"] = extracted.copy()
                st.session_state["pending_fields"] = get_missing_fields(extracted)
                st.session_state["current_field"] = None
                st.success("Extracted what I could. Let's fill the rest.")
            else:
                st.error("Failed to extract structured data. Please try again.")

# --- conversational filling of blanks ---
schema = st.session_state["schema"]
pending = st.session_state["pending_fields"]

if pending and ("schema" in st.session_state and any(st.session_state["schema"].values())):
    if st.session_state["current_field"] is None:
        st.session_state["current_field"] = pending[0]

    field = st.session_state["current_field"]
    pretty_label = field.replace("_", " ").title()

    st.subheader("Missing information")
    hint = ""
    if field == "closing_date":
        hint = " (format: YYYY-MM-DD)"
    if field == "salary":
        hint = " (e.g. £38,000 - £44,000 national)"

    user_input = st.text_input(f"{pretty_label}{hint}:", key=f"input_{field}")

    if st.button("Save this field"):
        answer = user_input.strip()
        st.session_state["schema"][field] = answer
        st.session_state["pending_fields"] = [f for f in pending if f != field]
        st.session_state["current_field"] = None
        st.rerun()
elif "schema" in st.session_state and any(st.session_state["schema"].values()):
    # Only show completion message if we have started the extraction process
    # and all fields are actually complete
    if all(st.session_state["schema"].values()):
        st.success("All fields complete ✅")
    
st.subheader("Current schema")
st.json(st.session_state["schema"])