import json
import os
from io import BytesIO
import re

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

# --- OpenAI client ---
client = OpenAI()

# --- Streamlit page setup ---
st.set_page_config(page_title="AI Job Schema Collector", page_icon="🧠")

st.title("AI Job Schema Collector")
st.write(
    "Give me your job advert in **any format**. I’ll read it, pull out the Civil Service bits, "
    "and ask only for what’s missing."
)

# Debug toggle (so only you see the noisy stuff)
show_debug = st.toggle("Show debug info", value=False)

# warn if API key not configured
if not os.getenv("OPENAI_API_KEY"):
    st.warning("OPENAI_API_KEY not found in environment — OpenAI calls will fail until you set it.")

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

# --- session setup ---
if "schema" not in st.session_state:
    st.session_state["schema"] = TARGET_SCHEMA.copy()

if "pending_fields" not in st.session_state:
    st.session_state["pending_fields"] = list(TARGET_SCHEMA.keys())

if "current_field" not in st.session_state:
    st.session_state["current_field"] = None

if "extracted" not in st.session_state:
    st.session_state["extracted"] = False

if "detected_source" not in st.session_state:
    st.session_state["detected_source"] = None


# -------------------------
# helper functions
# -------------------------
def extract_text_from_upload(uploaded_file):
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()

    # read bytes once
    try:
        data = uploaded_file.read()
    except Exception:
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

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                ' AppleWebKit/537.36 (KHTML, like Gecko)'
                ' Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        res = requests.get(url, timeout=10, headers=headers, verify=True)
        res.raise_for_status()

        if show_debug:
            st.write(f"Response status code: {res.status_code}")
            st.write(f"Response content type: {res.headers.get('content-type', 'unknown')}")

        soup = BeautifulSoup(res.text, "html.parser")

        # remove unwanted elements
        for elem in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            elem.decompose()

        main_content = (
            soup.find('main') or
            soup.find('article') or
            soup.find('div', class_='content') or
            soup
        )

        text = main_content.get_text(separator="\n", strip=True)

        if not text:
            st.warning("No text was extracted from the page")
        else:
            if show_debug:
                st.info(f"Successfully extracted {len(text)} characters of text")
                st.write("Preview:", text[:100] + "...")

        return text

    except requests.exceptions.SSLError as e:
        st.error(f"SSL Certificate Error: {e}")
        return ""
    except requests.exceptions.ConnectionError:
        st.error("Connection error — check the URL and your connection.")
        return ""
    except requests.exceptions.Timeout:
        st.error("The request timed out.")
        return ""
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL: {e}")
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
        if show_debug:
            st.write("OpenAI Response received successfully")
    except Exception as e:
        st.error(f"OpenAI API error: {e}")
        return schema

    raw_json = ""
    try:
        raw_json = resp.choices[0].message.content.strip()
    except Exception:
        try:
            raw_json = str(resp.choices[0].message).strip()
        except Exception:
            raw_json = ""

    if not raw_json:
        try:
            raw_json = json.dumps(resp)
        except Exception:
            return schema

    # attempt to parse
    try:
        parsed = json.loads(raw_json)
        return parsed
    except Exception:
        cleaned = raw_json.strip("` \n")
        try:
            return json.loads(cleaned)
        except Exception:
            return schema


def get_missing_fields(current_schema: dict):
    return [k for k, v in current_schema.items() if not v or not str(v).strip()]


# -------------------------
# Layout: 3 tabs
# -------------------------
tab1, tab2, tab3 = st.tabs(["1. Source", "2. Extract", "3. Complete"])

# -------- TAB 1: SOURCE --------
with tab1:
    st.subheader("1. Provide the job advert")

    source_type = st.radio(
        "How do you want to start?",
        ["Upload a file", "Paste text", "Use a URL"],
        horizontal=True
    )

    uploaded_file = None
    pasted_text = ""
    url = ""

    if source_type == "Upload a file":
        uploaded_file = st.file_uploader("Upload job advert (.txt / .docx / .pdf)", type=["txt", "docx", "pdf"])
    elif source_type == "Paste text":
        pasted_text = st.text_area("Paste the job advert text here", height=160)
    else:
        url = st.text_input("Enter the URL to the job advert")

    st.info("Once you’ve added a source, go to **2. Extract** and let the AI do the first pass.")


# -------- TAB 2: EXTRACT --------
with tab2:
    st.subheader("2. Extract fields from the advert")

    st.write("I’ll read your advert and populate as much of the schema as I can. Then we’ll fill in the gaps.")

    if st.button("Extract from source"):
        # work out which source actually has content
        source_text = ""
        detected_source = None

        if source_type == "Upload a file" and uploaded_file:
            source_text = extract_text_from_upload(uploaded_file)
            detected_source = "file"
        elif source_type == "Paste text" and pasted_text.strip():
            source_text = pasted_text.strip()
            detected_source = "pasted text"
        elif source_type == "Use a URL" and url.strip():
            source_text = extract_text_from_url(url.strip())
            detected_source = "URL"

        if not source_text:
            st.warning("Please provide a source in tab 1 first.")
        else:
            with st.spinner("Extracting fields with OpenAI..."):
                extracted = call_openai_structurer(source_text, TARGET_SCHEMA)

            if isinstance(extracted, dict):
                st.session_state["schema"] = extracted.copy()
                missing_fields = get_missing_fields(extracted)
                st.session_state["pending_fields"] = missing_fields
                st.session_state["current_field"] = None
                st.session_state["extracted"] = True
                st.session_state["detected_source"] = detected_source

                if missing_fields:
                    st.success("Extracted what I could. Head to **3. Complete** to fill in the rest.")
                else:
                    st.success("Successfully extracted all fields! ✅ You can view/download them in **3. Complete**.")
            else:
                st.error("Failed to extract structured data. Please try again.")

    # show detected source (if we have one)
    if st.session_state.get("detected_source"):
        st.caption(f"Detected source: {st.session_state['detected_source']}")


# -------- TAB 3: COMPLETE --------
with tab3:
    st.subheader("3. Complete any missing fields")

    schema = st.session_state["schema"]
    pending = st.session_state["pending_fields"]

    if not st.session_state["extracted"]:
        st.info("Run the extraction in **2. Extract** first.")
    else:
        # Progress bar
        total = len(TARGET_SCHEMA)
        done = sum(1 for v in schema.values() if v and str(v).strip())
        st.progress(done / total)
        st.caption(f"{done} of {total} fields completed")

        # ---------- A) Wizard-style: fill the next missing field ----------
        if pending and any(schema.values()):
            if st.session_state["current_field"] is None:
                st.session_state["current_field"] = pending[0]

            field = st.session_state["current_field"]
            pretty_label = field.replace("_", " ").title()

            st.markdown("#### Quick fix")
            st.info(f"I couldn’t find **{pretty_label}** — can you add it?")

            hint = ""
            if field == "closing_date":
                hint = " (format: YYYY-MM-DD)"
            if field == "salary":
                hint = " (e.g. £38,000 - £44,000 national)"

            user_input = st.text_input(f"{pretty_label}{hint}:", key=f"input_{field}")

            if st.button("Save this field"):
                answer = user_input.strip()

                # simple validation for closing_date
                if field == "closing_date" and answer:
                    import re
                    if not re.match(r"^\d{4}-\d{2}-\d{2}$", answer):
                        st.warning("Please use format YYYY-MM-DD, e.g. 2025-11-07")
                    else:
                        st.session_state["schema"][field] = answer
                        st.session_state["pending_fields"] = [f for f in pending if f != field]
                        st.session_state["current_field"] = None
                        st.rerun()
                else:
                    st.session_state["schema"][field] = answer
                    st.session_state["pending_fields"] = [f for f in pending if f != field]
                    st.session_state["current_field"] = None
                    st.rerun()
        else:
            if all(schema.values()):
                st.success("All fields complete ✅")
            else:
                st.success("No more obvious missing fields. You can still edit below.")

        # ---------- B) Form-style: edit everything ----------
        st.markdown("#### Edit all fields")
        with st.form("full_edit_form"):
            job_title = st.text_input("Job title", value=schema.get("job_title", ""))
            department = st.text_input("Department", value=schema.get("department", ""))
            location = st.text_input("Location", value=schema.get("location", ""))
            salary = st.text_input("Salary", value=schema.get("salary", ""))
            grade = st.text_input("Grade", value=schema.get("grade", ""))
            closing_date = st.text_input("Closing date (YYYY-MM-DD)", value=schema.get("closing_date", ""))
            summary = st.text_area("Summary", value=schema.get("summary", ""), height=80)
            responsibilities = st.text_area("Responsibilities", value=schema.get("responsibilities", ""), height=120)
            essential_criteria = st.text_area("Essential criteria", value=schema.get("essential_criteria", ""), height=120)
            desirable_criteria = st.text_area("Desirable criteria", value=schema.get("desirable_criteria", ""), height=120)

            submitted = st.form_submit_button("Save all")

        if submitted:
            # update schema from form
            updated_schema = {
                "job_title": job_title,
                "department": department,
                "location": location,
                "salary": salary,
                "grade": grade,
                "closing_date": closing_date,
                "summary": summary,
                "responsibilities": responsibilities,
                "essential_criteria": essential_criteria,
                "desirable_criteria": desirable_criteria,
            }
            st.session_state["schema"] = updated_schema
            # recompute pending fields
            st.session_state["pending_fields"] = [
                k for k, v in updated_schema.items() if not v or not str(v).strip()
            ]
            st.session_state["current_field"] = None
            st.success("All changes saved.")
            st.rerun()

        # ---------- C) Display current data + download ----------
        st.markdown("### Current job data")
        with st.expander("Raw JSON"):
            st.json(st.session_state["schema"])

        if any(st.session_state["schema"].values()):
            st.download_button(
                "Download JSON",
                data=json.dumps(st.session_state["schema"], indent=2),
                file_name="job-schema.json",
                mime="application/json"
            )
