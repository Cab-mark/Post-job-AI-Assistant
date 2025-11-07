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
        
    try:
        name = uploaded_file.name.lower()
        st.info(f"Processing uploaded file: {name}")
        
        # Seek to start to ensure we can read the full file
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        
        # read bytes once
        try:
            data = uploaded_file.read()
            st.info(f"Successfully read {len(data)} bytes")
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
            # fallback to getvalue for some stream types
            try:
                data = uploaded_file.getvalue()
                st.info(f"Successfully read {len(data)} bytes using getvalue()")
            except Exception as e:
                st.error(f"Could not read file content: {str(e)}")
                return ""

        if name.endswith(".txt"):
            try:
                text = data.decode("utf-8", errors="ignore")
                st.success(f"Successfully extracted {len(text)} characters from text file")
                return text
            except Exception:
                text = data.decode("latin-1", errors="ignore")
                st.success(f"Successfully extracted {len(text)} characters from text file (latin-1)")
                return text

        if name.endswith(".docx"):
            if not docx:
                st.error("DOCX support not installed. Please run: pip install python-docx")
                return ""
            try:
                document = docx.Document(BytesIO(data))
                text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
                st.success(f"Successfully extracted {len(text)} characters from DOCX")
                return text
            except Exception as e:
                st.error(f"Could not parse DOCX: {str(e)}")
                return ""

        if name.endswith(".pdf"):
            if not PdfReader:
                st.error("PDF support not installed. Please run: pip install pypdf")
                return ""
            try:
                reader = PdfReader(BytesIO(data))
                text_parts = []
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                        st.info(f"Extracted page {i+1}/{len(reader.pages)}")
                
                text = "\n".join(text_parts)
                if text.strip():
                    st.success(f"Successfully extracted {len(text)} characters from PDF")
                    return text
                else:
                    st.error("PDF appears to be empty or unreadable")
                    return ""
            except Exception as e:
                st.error(f"Could not parse PDF: {str(e)}")
                return ""

        st.error(f"Unsupported file type: {name}")
        return ""
        
    except Exception as e:
        st.error(f"Unexpected error processing file: {str(e)}")
        return ""

def extract_text_from_url(url: str) -> str:
    if not url:
        return ""
        
    # Add https:// if no protocol specified
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    try:
        st.info("Attempting to fetch URL...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        res = requests.get(url, headers=headers, timeout=15, verify=True)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Remove unwanted elements
        for elem in soup(["script", "style", "noscript", "header", "footer", "nav", "iframe"]):
            elem.decompose()
        
        # Try to find main content first
        main_content = soup.find('main') or soup.find('article') or soup.find('div', {'class': ['content', 'main-content', 'job-description']}) or soup.body or soup
        
        # Get text with better formatting
        text = main_content.get_text(separator="\n", strip=True)
        
        if not text.strip():
            st.warning("No text content found on the page. Please check the URL.")
            return ""
            
        st.success(f"Successfully extracted {len(text)} characters from URL")
        return text
        
    except requests.exceptions.SSLError:
        st.error("Security certificate verification failed. Please check the URL.")
        return ""
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the website. Please check the URL and your internet connection.")
        return ""
    except requests.exceptions.Timeout:
        st.error("Request timed out. The website took too long to respond.")
        return ""
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL: {str(e)}")
        return ""
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
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