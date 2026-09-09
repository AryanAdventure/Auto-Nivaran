import streamlit as st
import json
import os
from datetime import datetime
import urllib.parse 
import re 
import time
from google import genai
from google.genai import types

# ==========================================
# ⚙️ MODEL CONFIGURATION (Flash Model)
# ==========================================
MODEL_NAME = "gemini-3.5-flash-lite"

# ==========================================
# ⚙️ BACKGROUND API SETTINGS (Silent & Safe)
# ==========================================
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    try:
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = None

if "custom_api_key" in st.session_state and st.session_state.custom_api_key:
    api_key = st.session_state.custom_api_key

# Ignore placeholder dummy text
if api_key and api_key.strip() in ["", "YOUR_GEMINI_API_KEY_HERE"]:
    api_key = None

client = None
if api_key:
    try:
        os.environ["GEMINI_API_KEY"] = api_key
        client = genai.Client()
    except Exception:
        client = None

# --- LOCAL DATABASE SETUPS ---
COMPLAINTS_FILE = "complaints.json"
EMAILS_DB_FILE = "emails_db.json"

def load_email_db():
    if os.path.exists(EMAILS_DB_FILE):
        try:
            with open(EMAILS_DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_to_email_db(brand_or_dept, email):
    db = load_email_db()
    key = re.sub(r'[^a-zA-Z0-9\s]', '', brand_or_dept).lower().strip()
    if key and email and "@" in email:
        db[key] = email.strip()
        with open(EMAILS_DB_FILE, "w") as f:
            json.dump(db, f, indent=4)

def load_complaints():
    if os.path.exists(COMPLAINTS_FILE):
        try:
            with open(COMPLAINTS_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_complaint(complaint_data):
    complaints = load_complaints()
    complaints.append(complaint_data)
    with open(COMPLAINTS_FILE, "w") as f:
        json.dump(complaints, f, indent=4)

def update_complaint_data(complaint_id, updates):
    complaints = load_complaints()
    for c in complaints:
        if c.get("id") == complaint_id:
            c.update(updates)
            break
    with open(COMPLAINTS_FILE, "w") as f:
        json.dump(complaints, f, indent=4)

# ==========================================
# 🤖 GEMINI AI ENGINE FUNCTIONS
# ==========================================
def ask_gemini(prompt_text, image_bytes=None, system_instruction=""):
    if not client:
        return "⚠️ Gemini API client not initialized. Please configure your API key below."
    
    master_prompt = f"""
    STRICT SYSTEM INSTRUCTIONS: {system_instruction}
    CRITICAL RULE: DO NOT hallucinate or invent Ticket IDs, Dates, or synthetic Email Addresses. 
    
    USER PROMPT: {prompt_text}
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if image_bytes:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'), master_prompt]
                )
            else:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=master_prompt
                )
            return response.text
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                time.sleep(2)
                continue
            return f"API Error: {str(e)}"

def get_official_email(target_name, level=1):
    target_clean = re.sub(r'[^a-zA-Z0-9\s]', '', target_name).lower().strip()
    email_db = load_email_db()
    
    if level == 1:
        for key, email in email_db.items():
            if key in target_clean or target_clean in key:
                return email

    role = "Customer Support" if level == 1 else "Grievance / Nodal Officer"
    prompt = f"What is the official {role} email address for '{target_name}' in India? Reply ONLY with the exact email address. Do not hallucinate."
    
    res_text = ask_gemini(prompt)
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', res_text)
    
    if match:
        found_email = match.group(0)
        if level == 1:
            save_to_email_db(target_name, found_email)
        return found_email
    
    prefix = "support" if level == 1 else "grievance"
    return f"{prefix}@{target_clean.replace(' ', '')}.com"

def clean_llm_response(text):
    return re.sub(r'^(Here is|Sure|Certainly|Here\'s|Below is)[^\n]*\n+', '', text, flags=re.IGNORECASE).strip()

def analyze_grievance_multimodal(user_statement, image_bytes=None):
    prompt = f"""
    You are Auto-Nivaran AI, an elite consumer grievance legal assistant in India.
    Analyze this consumer's problem statement and/or uploaded photo (invoice, damaged product, receipt, etc.):
    
    CONSUMER STATEMENT: "{user_statement}"
    
    TASKS:
    1. Identify the Brand / Company or Department Name (e.g. boAt, Flipkart, Amazon, Samsung, PWD Ghaziabad, Zomato, etc.).
    2. Write a professional, high-impact grievance problem description in formal English suitable for official redressal.
    3. List exactly 3 to 4 specific documents/proofs the consumer MUST attach with their email (e.g., Tax Invoice, Unboxing Video, Photo of Defect, Order Confirmation, Warranty Slip).
    
    OUTPUT STRICT JSON ONLY (do not include markdown codeblocks or extra text):
    {{
        "brand": "Extracted Brand or Department Name",
        "description": "Formal problem description for email body",
        "required_documents": [
            "Original Tax Invoice / Bill (PDF / Photo)",
            "Clear photos of the defect / damage",
            "Warranty Card / Order Confirmation"
        ]
    }}
    """
    raw_response = ask_gemini(prompt, image_bytes=image_bytes)
    try:
        clean_json = re.sub(r'```json|```', '', raw_response).strip()
        data = json.loads(clean_json)
        return data
    except Exception:
        brand_guess = "Customer Support"
        for word in user_statement.split():
            if len(word) > 3 and word[0].isupper():
                brand_guess = word
                break
        return {
            "brand": brand_guess,
            "description": clean_llm_response(raw_response),
            "required_documents": [
                "Original Purchase Tax Invoice / Bill",
                "Clear Photos / Video showing the defect",
                "Proof of Purchase or Warranty Card"
            ]
        }

# ==========================================
# 🎨 UI CONFIGURATION & THEME
# ==========================================
st.set_page_config(page_title="Auto-Nivaran AI", page_icon="⚖️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Outfit:wght@600;700;800&display=swap');

    /* --- HIDE DEFAULT STREAMLIT CHROME --- */
    #MainMenu, header, footer, [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], .stDeployButton {
        visibility: hidden !important;
        display: none !important;
        height: 0px !important;
    }

    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 860px !important;
        margin: 0 auto !important;
    }

    /* Ambient soft background */
    .stApp {
        background: radial-gradient(circle at 50% 8%, rgba(56, 189, 248, 0.22) 0%, transparent 55%),
                    radial-gradient(circle at 85% 55%, rgba(45, 212, 191, 0.22) 0%, transparent 50%),
                    radial-gradient(circle at 15% 70%, rgba(14, 165, 233, 0.18) 0%, transparent 45%),
                    linear-gradient(145deg, #cde6ed 0%, #dcf0f5 35%, #c5e6ef 70%, #acd9e8 100%) !important;
        background-attachment: fixed !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    /* Hero Banner */
    .hero-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        margin-top: 0.5rem;
        margin-bottom: 1.5rem;
    }

    .top-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #0E2233 !important;
        color: #FFFFFF !important;
        font-size: 0.85rem;
        font-weight: 800;
        padding: 0.45rem 1.4rem;
        border-radius: 9999px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
        border: 1.5px solid #38BDF8 !important;
        margin-bottom: 0.9rem;
        letter-spacing: 0.3px;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    .hero-title {
        font-family: 'Outfit', sans-serif !important;
        font-size: 3.5rem !important;
        font-weight: 800 !important;
        color: #0F2942 !important;
        letter-spacing: -1px;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.05;
        text-shadow: 0 6px 18px rgba(15, 41, 66, 0.25);
    }

    .hero-subtitle {
        color: #1E293B !important;
        font-size: 1.05rem;
        font-weight: 700;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    /* ========================================================= */
    /* 💥 BULLETPROOF CONTRAST FIX FOR LIGHT & DARK BROWSERS 💥 */
    /* ========================================================= */

    /* 1. ALL CAPSULE BOXES / EXPANDERS */
    div[data-testid="stExpander"] {
        border: 1.5px solid rgba(56, 189, 248, 0.5) !important;
        border-radius: 18px !important;
        background: #0E2233 !important;
        box-shadow: 0 8px 24px rgba(10, 25, 40, 0.25) !important;
        transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        margin-bottom: 1.15rem !important;
        overflow: hidden !important;
    }

    div[data-testid="stExpander"]:hover {
        transform: translateY(-4px) scale(1.01) !important;
        box-shadow: 0 16px 36px rgba(10, 30, 48, 0.45), 0 0 20px rgba(14, 165, 233, 0.4) !important;
        border-color: #38BDF8 !important;
    }

    /* 2. CAPSULE HEADERS - MUST BE PURE WHITE ON BOTH LIGHT & DARK OS/BROWSER */
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] [data-testid="stExpanderHeader"],
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, #132D42 0%, #0D2030 100%) !important;
        padding: 0.95rem 1.6rem !important;
        border: none !important;
        cursor: pointer !important;
    }

    /* Force every text node inside expander header to pure white */
    div[data-testid="stExpander"] summary *,
    div[data-testid="stExpander"] summary p,
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary div,
    .streamlit-expanderHeader *,
    .streamlit-expanderHeader p,
    .streamlit-expanderHeader span {
        color: #FFFFFF !important;
        font-weight: 800 !important;
        font-size: 1.02rem !important;
        opacity: 1 !important;
        letter-spacing: 0.2px !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* Header hover */
    div[data-testid="stExpander"] summary:hover *,
    .streamlit-expanderHeader:hover * {
        color: #38BDF8 !important;
        -webkit-text-fill-color: #38BDF8 !important;
    }

    /* Arrow icon in header */
    div[data-testid="stExpander"] summary svg,
    .streamlit-expanderHeader svg {
        fill: #38BDF8 !important;
        color: #38BDF8 !important;
        min-width: 20px !important;
        min-height: 20px !important;
    }

    /* 3. EXPANDER BODY CONTENT */
    div[data-testid="stExpanderDetails"] {
        background: #081622 !important;
        border-top: 1px solid rgba(56, 189, 248, 0.3) !important;
        padding: 1.6rem !important;
    }

    /* All form labels inside expander body */
    div[data-testid="stExpanderDetails"] label,
    div[data-testid="stExpanderDetails"] label p,
    div[data-testid="stExpanderDetails"] .stMarkdown label p {
        color: #38BDF8 !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        -webkit-text-fill-color: #38BDF8 !important;
    }

    div[data-testid="stExpanderDetails"] p,
    div[data-testid="stExpanderDetails"] span {
        color: #F1F5F9 !important;
        font-weight: 600 !important;
        -webkit-text-fill-color: #F1F5F9 !important;
    }

    /* 4. TEXT INPUTS & TEXTAREAS IN LIGHT & DARK MODE */
    .stTextInput>div>div>input, 
    .stTextArea>div>div>textarea,
    .stDateInput>div>div>input {
        background: #0F2538 !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 1.5px solid rgba(56, 189, 248, 0.45) !important;
        border-radius: 12px !important;
        padding: 0.75rem 1rem !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3) !important;
    }

    .stTextInput>div>div>input:focus, 
    .stTextArea>div>div>textarea:focus {
        border-color: #38BDF8 !important;
        box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.4) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    .stTextInput>div>div>input::placeholder, 
    .stTextArea>div>div>textarea::placeholder {
        color: #94A3B8 !important;
        -webkit-text-fill-color: #94A3B8 !important;
    }

    /* 5. TABS - NO RED LINES, PURE HIGH CONTRAST */
    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
        height: 0 !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        display: flex !important;
        justify-content: center !important;
        gap: 14px !important;
        background: #0E2233 !important;
        padding: 6px 12px !important;
        border-radius: 9999px !important;
        border: 1.5px solid #0EA5E9 !important;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25) !important;
        width: fit-content !important;
        margin: 0 auto 1.8rem auto !important;
    }

    .stTabs [data-baseweb="tab"] {
        height: 42px !important;
        border-radius: 9999px !important;
        padding: 0 1.6rem !important;
        background: transparent !important;
        border: none !important;
    }

    .stTabs [data-baseweb="tab"] * {
        color: #94A3B8 !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        -webkit-text-fill-color: #94A3B8 !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0EA5E9 0%, #0284C7 100%) !important;
        box-shadow: 0 4px 14px rgba(14, 165, 233, 0.6) !important;
    }

    .stTabs [aria-selected="true"] * {
        color: #FFFFFF !important;
        font-weight: 800 !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* 6. 3D POPPING BUTTONS & POPOVER BUTTON */
    div.stButton > button, 
    div.stDownloadButton > button, 
    .stLinkButton > a,
    div[data-testid="stPopover"] > button {
        background: linear-gradient(180deg, #1C3549 0%, #0F2231 100%) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 1.5px solid rgba(56, 189, 248, 0.5) !important;
        border-radius: 9999px !important;
        padding: 0.65rem 1.9rem !important;
        font-size: 0.95rem !important;
        font-weight: 800 !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        box-shadow: 0 5px 15px rgba(15, 23, 42, 0.3) !important;
        transition: all 0.24s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        text-decoration: none !important;
    }

    div.stButton > button:hover, 
    .stLinkButton > a:hover,
    div[data-testid="stPopover"] > button:hover {
        transform: translateY(-4px) scale(1.02) !important;
        background: linear-gradient(180deg, #244662 0%, #11283B 100%) !important;
        box-shadow: 0 12px 26px rgba(15, 23, 42, 0.45), 0 4px 12px rgba(14, 165, 233, 0.35) !important;
        border-color: #38BDF8 !important;
        color: #38BDF8 !important;
        -webkit-text-fill-color: #38BDF8 !important;
    }

    div[data-testid="stPopover"] > button *,
    div.stButton > button * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 800 !important;
    }

    div[data-testid="stPopover"] > button:hover * {
        color: #38BDF8 !important;
        -webkit-text-fill-color: #38BDF8 !important;
    }

    div.stButton > button[kind="primary"],
    .stLinkButton > a[kind="primary"] {
        background: linear-gradient(180deg, #0EA5E9 0%, #0284C7 100%) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.35) !important;
        box-shadow: 0 6px 18px rgba(14, 165, 233, 0.45) !important;
    }

    div.stButton > button[kind="primary"]:hover,
    .stLinkButton > a[kind="primary"]:hover {
        transform: translateY(-4px) scale(1.02) !important;
        background: linear-gradient(180deg, #38BDF8 0%, #0284C7 100%) !important;
        box-shadow: 0 12px 28px rgba(14, 165, 233, 0.65) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* POPOVER DIALOG / FLOATING MODAL (EXTEND TIME) */
    div[data-testid="stPopoverBody"],
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div {
        background: #0A1926 !important;
        border: 1.5px solid #38BDF8 !important;
        border-radius: 16px !important;
        padding: 1.2rem !important;
        box-shadow: 0 16px 36px rgba(0, 0, 0, 0.6) !important;
    }

    div[data-testid="stPopoverBody"] *,
    div[data-baseweb="popover"] * {
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
        font-weight: 600 !important;
    }

    div[data-testid="stPopoverBody"] input,
    div[data-baseweb="popover"] input {
        background: #11283B !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 1.5px solid #38BDF8 !important;
        border-radius: 10px !important;
        font-weight: 800 !important;
        padding: 0.5rem 0.8rem !important;
    }

    /* 7. FILE UPLOADER FIX - NO WHITE-ON-WHITE */
    [data-testid="stFileUploader"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }

    /* The actual dropzone container */
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploadDropzone"] {
        background: #0C1E2C !important;
        border: 1.5px dashed #38BDF8 !important;
        border-radius: 14px !important;
        padding: 1.2rem 1.6rem !important;
    }

    /* The Browse / Upload Button inside File Uploader */
    [data-testid="stFileUploader"] button,
    [data-testid="stFileUploadDropzone"] button {
        background: linear-gradient(135deg, #0EA5E9 0%, #0284C7 100%) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 1.5px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 9999px !important;
        padding: 0.55rem 1.5rem !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        box-shadow: 0 4px 14px rgba(14, 165, 233, 0.45) !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 6px !important;
    }

    [data-testid="stFileUploader"] button *,
    [data-testid="stFileUploadDropzone"] button * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 800 !important;
    }

    [data-testid="stFileUploader"] button:hover,
    [data-testid="stFileUploadDropzone"] button:hover {
        transform: translateY(-2px) scale(1.02) !important;
        background: linear-gradient(135deg, #38BDF8 0%, #0284C7 100%) !important;
        box-shadow: 0 8px 20px rgba(14, 165, 233, 0.6) !important;
    }

    /* File uploader instructions text ("200MB per file • PNG, JPG") */
    [data-testid="stFileUploadDropzone"] span,
    [data-testid="stFileUploadDropzone"] p,
    [data-testid="stFileUploadDropzone"] small,
    [data-testid="stFileUploadDropzone"] div {
        color: #E2E8F0 !important;
        -webkit-text-fill-color: #E2E8F0 !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
    }

    /* Uploaded file preview tag */
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
        background: #0F2538 !important;
        border: 1px solid #38BDF8 !important;
        border-radius: 10px !important;
        color: #FFFFFF !important;
    }
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* 8. DOCUMENT CHECKLIST CARD */
    .doc-checklist-card {
        background: linear-gradient(135deg, #112331 0%, #0D1C28 100%);
        border: 1.5px solid #38BDF8;
        border-radius: 16px;
        padding: 1.2rem 1.6rem;
        margin-top: 1rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
    }
    .doc-checklist-title {
        color: #38BDF8 !important;
        -webkit-text-fill-color: #38BDF8 !important;
        font-weight: 800;
        font-size: 1rem;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .doc-item {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-size: 0.95rem;
        font-weight: 600;
        margin-bottom: 0.4rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Telemetry header inside capsules */
    .telemetry-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.2rem;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid rgba(56, 189, 248, 0.25);
    }
    .telemetry-title {
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 1px;
        color: #94A3B8 !important;
        -webkit-text-fill-color: #94A3B8 !important;
        text-transform: uppercase;
    }
    .telemetry-val {
        font-weight: 800;
        color: #38BDF8 !important;
        -webkit-text-fill-color: #38BDF8 !important;
        font-size: 1rem;
    }
    .pill-tag {
        background: rgba(34, 197, 94, 0.25);
        color: #4ADE80 !important;
        -webkit-text-fill-color: #4ADE80 !important;
        border: 1.5px solid #22C55E;
        padding: 0.25rem 0.85rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 800;
    }
    </style>
""", unsafe_allow_html=True)

# Centered Hero Header
st.markdown("""
<div class="hero-container">
    <div class="top-pill">⚖️ Smart Grievance Redressal</div>
    <h1 class="hero-title">Auto-Nivaran</h1>
    <div class="hero-subtitle">AI-Powered Consumer Escalation & Real-Time SLA Redressal Engine</div>
</div>
""", unsafe_allow_html=True)

# Session state initialization
if "extracted_brand" not in st.session_state:
    st.session_state.extracted_brand = ""
if "extracted_email" not in st.session_state:
    st.session_state.extracted_email = ""
if "auto_description" not in st.session_state:
    st.session_state.auto_description = ""
if "req_docs" not in st.session_state:
    st.session_state.req_docs = []
if "ai_analyzed" not in st.session_state:
    st.session_state.ai_analyzed = False

all_complaints = load_complaints()
active_count = sum(1 for c in all_complaints if "Resolved" not in c.get("status", "") and "Closed" not in c.get("status", ""))

# =======================================================
# 📑 DEDICATED TABS: (Main AI Redressal vs SLA Dashboard)
# =======================================================
tab_file, tab_sla = st.tabs([
    "⚡ Instant AI Grievance (Auto-Fill & Send)",
    f"📊 Live SLA Dashboard ({active_count} Active)"
])

# =======================================================
# TAB 1: INSTANT AI GRIEVANCE ENGINE
# =======================================================
with tab_file:
    # ---------------------------------------------------
    # STEP 1: AI SMART INPUT (PHOTO + PROMPT FIRST)
    # ---------------------------------------------------
    with st.expander("🤖 Step 1: AI Problem Analysis (Upload Photo & Tell What Happened)", expanded=False):
        st.markdown("""
        <div class="telemetry-header">
            <div>
                <div class="telemetry-title">INTELLIGENT MULTIMODAL INGESTION</div>
                <div class="telemetry-val">AI Auto-Detects Brand, Email & Legal Description</div>
            </div>
            <span class="pill-tag">Gemini Vision Active</span>
        </div>
        """, unsafe_allow_html=True)

        user_statement = st.text_area(
            "🗣️ Describe your issue in simple words (Hinglish/English):",
            height=90,
            placeholder="Jaise: Maine Flipkart se boAt earphone order kiya tha, defected nikla aur replace karne se mana kar rahe hain..."
        )

        uploaded_img = st.file_uploader(
            "📸 Upload Bill, Invoice, or Defect Photo (Optional):",
            type=["png", "jpg", "jpeg"]
        )

        if st.button("✨ Auto-Diagnose & Fill Everything with AI", type="primary"):
            if not user_statement and not uploaded_img:
                st.error("⚠️ Kripya apni problem statement likhein ya photo upload karein.")
            else:
                with st.spinner("🧠 Gemini AI analyzing problem, identifying brand, and generating legal draft..."):
                    img_bytes = uploaded_img.getvalue() if uploaded_img else None
                    ai_result = analyze_grievance_multimodal(user_statement, image_bytes=img_bytes)
                    
                    brand = ai_result.get("brand", "Customer Support")
                    target_email = get_official_email(brand, level=1)
                    
                    st.session_state.extracted_brand = brand
                    st.session_state.extracted_email = target_email
                    st.session_state.auto_description = ai_result.get("description", "")
                    st.session_state.req_docs = ai_result.get("required_documents", [])
                    st.session_state.ai_analyzed = True
                    st.toast("✅ AI Analysis Complete! All details populated below.")
                    st.rerun()

    # ---------------------------------------------------
    # STEP 2: USER DETAILS (NAME & CONTACT, ADDRESS OPTIONAL)
    # ---------------------------------------------------
    with st.expander("👤 Step 2: Consumer Contact Information", expanded=False):
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            user_name = st.text_input("Full Name *", placeholder="e.g. Aryan Sharma")
        with col_u2:
            user_contact = st.text_input("Mobile / Contact Number *", placeholder="e.g. +91 9876543210")
        
        user_address = st.text_input("Delivery / Residential Address (Optional):", placeholder="e.g. Flat 402, Sector 62, Noida, UP (Optional)")

    # ---------------------------------------------------
    # STEP 3: AUTOMATIC DRAFT & 1-CLICK SEND
    # ---------------------------------------------------
    if st.session_state.ai_analyzed or st.session_state.auto_description:
        with st.expander("✉️ Step 3: Complete Auto-Draft & 1-Click Send", expanded=False):
            st.markdown("""
            <div class="telemetry-header">
                <div>
                    <div class="telemetry-title">DISPATCH READY</div>
                    <div class="telemetry-val">Review & 1-Click Dispatch</div>
                </div>
                <span class="pill-tag">Auto-Generated</span>
            </div>
            """, unsafe_allow_html=True)

            col_b1, col_b2 = st.columns(2)
            with col_b1:
                target_brand = st.text_input("Brand / Department:", value=st.session_state.extracted_brand)
            with col_b2:
                target_email = st.text_input("Official Support Email (Editable):", value=st.session_state.extracted_email)
                if target_email != st.session_state.extracted_email and target_brand:
                    save_to_email_db(target_brand, target_email)
                    st.session_state.extracted_email = target_email

            # Editable Description
            final_desc = st.text_area(
                "📝 Auto-Generated Legal Grievance Description (Editable):",
                value=st.session_state.auto_description,
                height=150
            )

            # REQUIRED ATTACHMENT ADVICE BOX
            if st.session_state.req_docs:
                docs_html = "".join([f'<div class="doc-item">📌 <b>{doc}</b></div>' for doc in st.session_state.req_docs])
                st.markdown(f"""
                <div class="doc-checklist-card">
                    <div class="doc-checklist-title">📎 Documents you MUST attach in your email:</div>
                    {docs_html}
                </div>
                """, unsafe_allow_html=True)

            # Final Compiled Email Body
            name_val = user_name if user_name else "Consumer"
            contact_val = user_contact if user_contact else "Provided in correspondence"
            addr_val = f"\nAddress: {user_address}" if user_address else ""
            
            full_email_body = f"""Dear {target_brand} Support / Grievance Team,

{final_desc}

Complainant Details:
- Name: {name_val}
- Contact Number: {contact_val}{addr_val}
- Date of Notice: {datetime.now().strftime('%d %B %Y')}

Note: Please find attached supporting evidence (Tax invoice, proof of purchase, and photos of defect) for prompt verification and redressal within the stipulated SLA.

Sincerely,
{name_val}
"""

            mail_subject = urllib.parse.quote(f"Formal Grievance Notice: Issue with {target_brand} [SLA Enforced]")
            mail_body = urllib.parse.quote(full_email_body)
            mailto_link = f"mailto:{target_email}?subject={mail_subject}&body={mail_body}"

            col_btn1, col_btn2 = st.columns([3, 1])
            with col_btn1:
                if st.link_button("✉️ Open Mail & Send Grievance (1-Click)", mailto_link, type="primary"):
                    ticket_id = f"AN-{int(datetime.now().timestamp())}"
                    complaint_obj = {
                        "id": ticket_id,
                        "name": name_val,
                        "contact": contact_val,
                        "location": target_brand,
                        "email": target_email,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "description": final_desc,
                        "status": "Level 1 Active",
                        "level": 1,
                        "sla_hours": 48
                    }
                    save_complaint(complaint_obj)
                    st.toast(f"✅ Ticket {ticket_id} created & SLA started!")
            with col_btn2:
                if st.button("🔄 Reset"):
                    st.session_state.extracted_brand = ""
                    st.session_state.extracted_email = ""
                    st.session_state.auto_description = ""
                    st.session_state.req_docs = []
                    st.session_state.ai_analyzed = False
                    st.rerun()


# =======================================================
# TAB 2: SEPARATE SLA ESCALATION DASHBOARD
# =======================================================
with tab_sla:
    st.markdown("""
    <div class="telemetry-header">
        <div>
            <div class="telemetry-title">SLA ENGINE MONITORING</div>
            <div class="telemetry-val">48-Hour Level 1 to Level 2 Auto-Escalation Engine</div>
        </div>
        <span class="pill-tag">SLA Strict Enforcement</span>
    </div>
    """, unsafe_allow_html=True)

    if not all_complaints:
        st.info("Abhi koi complaint darj nahi hui hai. Tab 1 se complaint file karein.")
    else:
        for c in reversed(all_complaints):
            complaint_id = c.get("id", "UNKNOWN_ID")
            status = c.get("status", "Level 1 Active")
            location = c.get("location", "Unknown Brand")
            
            date_str = c.get("date")
            created_at = None
            if date_str:
                try:
                    created_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    try:
                        created_at = datetime.fromisoformat(date_str)
                    except Exception:
                        created_at = None
            
            if not created_at:
                created_at = datetime.now()

            allowed_hours = c.get("sla_hours", 48)
            time_elapsed = datetime.now() - created_at
            hours_passed = time_elapsed.total_seconds() / 3600
            
            # Auto-Close Logic (168h / 7 days)
            if ("Active" in status or "Pending" in status) and hours_passed >= (allowed_hours + 168):
                update_complaint_data(complaint_id, {"status": "Auto-Closed (No Response)"})
                st.rerun()
            
            status_color = "🟢" if "Resolved" in status else ("🔴" if hours_passed >= allowed_hours else "🟡")
            
            with st.expander(f"{status_color} ID: {complaint_id} | {location} | {round(hours_passed, 1)}h elapsed"):
                st.write(f"**Status:** `{status}` | **Allowed SLA:** {allowed_hours} Hours")
                st.write(f"**Grievance Notice:** {c.get('description', 'N/A')}")
                
                if c.get("escalation_mailto"):
                    st.success("✉️ Level 2 Legal Escalation Ready!")
                    st.link_button("✉️ Open Mail & Send Level 2 Warning", c["escalation_mailto"], type="primary")

                elif ("Active" in status or "Pending" in status) and hours_passed >= allowed_hours:
                    st.error("🚨 **SLA BREACHED! Nodal Escalation Required.**")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("✅ Solved", key=f"sol_{complaint_id}"):
                            update_complaint_data(complaint_id, {"status": "Resolved"})
                            st.rerun()
                    with c2:
                        with st.popover("⏳ Extend Time"):
                            extra_days = st.number_input("Extra Days:", min_value=1, value=3, key=f"num_{complaint_id}")
                            if st.button("Confirm", key=f"ext_{complaint_id}"):
                                update_complaint_data(complaint_id, {
                                    "sla_hours": allowed_hours + (extra_days * 24),
                                    "status": "Level 1 Active"
                                })
                                st.rerun()
                    with c3:
                        if st.button("❌ Escalate", key=f"esc_{complaint_id}"):
                            with st.spinner("🧠 AI drafting strict Level 2 legal warning..."):
                                nodal_email = get_official_email(location, level=2)
                                l2_sys = "You are drafting a legal escalation warning. Do NOT invent synthetic data. Use EXACTLY the provided details."
                                l2_prompt = f"""
                                Draft a strict Level 2 Escalation Email to the Grievance/Nodal Officer of {location}.
                                Ticket ID: {complaint_id}
                                Date of 1st Complaint: {c.get('date', 'N/A')}
                                Name: {c.get('name', 'Consumer')}
                                Issue: {c.get('description', 'Defective service')}
                                Tone: Formal legal escalation, state that 48-hour SLA breached without response, warn about Consumer Court / NCH.
                                Output ONLY email body starting with 'Subject:'.
                                """
                                l2_draft = ask_gemini(l2_prompt, system_instruction=l2_sys)
                                clean_l2 = clean_llm_response(l2_draft)
                                
                                mail_subject = urllib.parse.quote(f"URGENT ESCALATION: SLA Breached for Ticket {complaint_id}")
                                mail_body = urllib.parse.quote(clean_l2)
                                mailto_link = f"mailto:{nodal_email}?subject={mail_subject}&body={mail_body}"
                                
                                update_complaint_data(complaint_id, {
                                    "status": "Escalated Level 2",
                                    "level": 2,
                                    "sla_hours": allowed_hours + 48,
                                    "escalation_mailto": mailto_link
                                })
                                st.rerun()
                elif "Active" in status or "Pending" in status:
                    st.info(f"⏳ SLA active ({round(allowed_hours - hours_passed, 1)} hours remaining before escalation).")