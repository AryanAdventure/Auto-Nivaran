import os
import json
import time
from datetime import datetime, timedelta
import streamlit as st
from google import genai
from google.genai import types

# ==========================================
# 1. PAGE CONFIGURATION & ENTERPRISE STYLING
# ==========================================
st.set_page_config(
    page_title="Auto-Nivaran | AI Grievance Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise CSS Styling (Navy Blue, Slate Gray, Electric Blue)
st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }
    
    /* Header Banner */
    .main-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .main-title {
        color: #0EA5E9;
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .main-subtitle {
        color: #94A3B8;
        font-size: 15px;
    }

    /* Metric Cards */
    .metric-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #38BDF8;
    }
    .metric-label {
        font-size: 13px;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Status Badges */
    .badge-l1 {
        background-color: #0284C7;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-l2 {
        background-color: #DC2626;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-closed {
        background-color: #16A34A;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. GEMINI CLIENT INITIALIZATION
# ==========================================
@st.cache_resource
def get_gemini_client():
    """Initialize Google GenAI client securely using Streamlit Secrets or Environment Variables."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        os.environ["GEMINI_API_KEY"] = api_key
    
    if not api_key:
        return None
    
    try:
        return genai.Client()
    except Exception as e:
        st.error(f"Failed to initialize Gemini Client: {e}")
        return None

client = get_gemini_client()

# High-Resilience Gemini Call with Exponential Backoff for 503 Errors
def call_gemini_lite(prompt_text, system_instruction=""):
    """
    Calls gemini-3.5-flash-lite with automated retries for 503 Service Congestion errors.
    """
    if not client:
        return "⚠️ API Client error: GEMINI_API_KEY is not configured in secrets."
    
    master_prompt = f"""
    STRICT SYSTEM RULE: {system_instruction}
    CRITICAL RULE: DO NOT hallucinate fake ticket IDs, dates, or details.
    
    USER PROMPT: {prompt_text}
    """
    
    max_retries = 3
    backoff_delay = 1.5  # seconds
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=master_prompt
            )
            return response.text
        except Exception as e:
            err_msg = str(e)
            if "503" in err_msg or "overloaded" in err_msg.lower():
                if attempt < max_retries - 1:
                    time.sleep(backoff_delay * (attempt + 1))
                    continue
            return f"⚠️ API Error ({err_msg}). Retried {attempt+1} times."

# ==========================================
# 3. LOCAL PERSISTENCE & SLA LOGIC ENGINE
# ==========================================
DB_FILE = "complaints.json"

def load_complaints():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_complaints(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def process_sla_rules(complaints):
    """
    Calculates SLA breaches & auto-escalates based on mathematical rules:
    - SLA Breach (>48h) -> Escalates L1 to L2 Nodal Officer.
    - Auto Close (>168h) -> Marks inactive/resolved cases as Closed.
    """
    now = datetime.now()
    updated = False
    
    for item in complaints:
        filed_time = datetime.fromisoformat(item["timestamp"])
        elapsed_hours = (now - filed_time).total_seconds() / 3600.0
        item["elapsed_hours"] = round(elapsed_hours, 1)
        
        # Rule 1: 48-Hour SLA Breach Escalation
        if elapsed_hours >= 48.0 and item["status"] == "Level 1 Active":
            item["status"] = "Level 2 Escalated"
            item["escalated_at"] = now.isoformat()
            updated = True
            
        # Rule 2: 168-Hour Auto-Closure Window
        if elapsed_hours >= 168.0 and item["status"] in ["Resolved", "Level 1 Active"]:
            item["status"] = "Closed"
            updated = True
            
    if updated:
        save_complaints(complaints)
    return complaints

# Initialize DB Data
complaints_data = load_complaints()
complaints_data = process_sla_rules(complaints_data)

# ==========================================
# 4. USER INTERFACE
# ==========================================

# Header Banner
st.markdown("""
<div class="main-header">
    <div class="main-title">🛡️ Auto-Nivaran Dashboard</div>
    <div class="main-subtitle">AI-Powered Consumer Grievance Escalation & Real-Time SLA Tracking Platform</div>
</div>
""", unsafe_allow_html=True)

# Top Metric Row
total_count = len(complaints_data)
l1_count = sum(1 for c in complaints_data if c["status"] == "Level 1 Active")
l2_count = sum(1 for c in complaints_data if c["status"] == "Level 2 Escalated")
closed_count = sum(1 for c in complaints_data if c["status"] == "Closed")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total_count}</div><div class="metric-label">Total Grievances</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#38BDF8;">{l1_count}</div><div class="metric-label">L1 Active</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#EF4444;">{l2_count}</div><div class="metric-label">L2 SLA Breached</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#22C55E;">{closed_count}</div><div class="metric-label">Resolved / Closed</div></div>', unsafe_allow_html=True)

st.write("---")

# Navigation Tabs
tab1, tab2, tab3 = st.tabs(["📝 File New Grievance", "📊 Live Complaint Tracker & Escalation Engine", "🤖 AI Resolution Assistant"])

# TAB 1: FILE GRIEVANCE
with tab1:
    st.subheader("Submit Consumer Complaint")
    with st.form("grievance_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            consumer_name = st.text_input("Consumer Name", placeholder="e.g. Rahul Sharma")
            category = st.selectbox("Category", ["Banking & Finance", "E-Commerce & Delivery", "Telecommunications", "Public Utilities", "Other Services"])
        with col_b:
            email = st.text_input("Email Address", placeholder="rahul@example.com")
            priority = st.select_slider("Priority Level", options=["Low", "Medium", "High", "Critical"])
            
        complaint_text = st.text_area("Detailed Grievance Description", placeholder="Describe your issue in detail...", height=120)
        submit_btn = st.form_submit_button("Submit Complaint & Initialize SLA Clock")
        
        if submit_btn:
            if not consumer_name or not complaint_text:
                st.warning("Please fill in all mandatory fields.")
            else:
                with st.spinner("AI Categorizing & Analyzing Grievance via Gemini 3.5 Flash-Lite..."):
                    system_prompt = "You are an expert grievance classifier. Provide a concise 2-sentence executive summary and 3 key action steps for resolving this grievance."
                    ai_analysis = call_gemini_lite(f"Grievance Category: {category}\nDetails: {complaint_text}", system_instruction=system_prompt)
                    
                    ticket_id = f"AN-{int(time.time())}"
                    new_complaint = {
                        "ticket_id": ticket_id,
                        "consumer_name": consumer_name,
                        "email": email,
                        "category": category,
                        "priority": priority,
                        "description": complaint_text,
                        "ai_summary": ai_analysis,
                        "timestamp": datetime.now().isoformat(),
                        "status": "Level 1 Active",
                        "elapsed_hours": 0.0
                    }
                    
                    complaints_data.append(new_complaint)
                    save_complaints(complaints_data)
                    
                    st.success(f"✅ Grievance Registered Successfully! Ticket ID: **{ticket_id}**")
                    st.markdown(f"**AI Initial Assessment:**\n{ai_analysis}")

# TAB 2: LIVE TRACKER & SLA ESCALATION
with tab2:
    st.subheader("Real-Time SLA & Escalation Dashboard")
    
    if not complaints_data:
        st.info("No active grievances found in the system.")
    else:
        for item in complaints_data:
            badge_class = "badge-l1"
            if item["status"] == "Level 2 Escalated":
                badge_class = "badge-l2"
            elif item["status"] == "Closed":
                badge_class = "badge-closed"
                
            with st.expander(f"🎫 Ticket #{item['ticket_id']} — {item['category']} ({item['consumer_name']})"):
                col_x, col_y = st.columns([2, 1])
                with col_x:
                    st.markdown(f"**Description:** {item['description']}")
                    st.markdown(f"**AI Analysis:** {item.get('ai_summary', 'N/A')}")
                with col_y:
                    st.markdown(f"**Status:** <span class='{badge_class}'>{item['status']}</span>", unsafe_allow_html=True)
                    st.write(f"**Filed Time:** {item['timestamp'][:16].replace('T', ' ')}")
                    st.write(f"**Elapsed Time:** `{item.get('elapsed_hours', 0)} hrs`")
                    st.write(f"**Priority:** `{item['priority']}`")

# TAB 3: AI RESOLUTION ASSISTANT
with tab3:
    st.subheader("AI Assistant & Resolution Generator")
    ticket_query = st.text_input("Enter Ticket ID to Generate Redressal Response", placeholder="e.g. AN-1725732000")
    
    if st.button("Generate Resolution Letter"):
        matched = next((c for c in complaints_data if c["ticket_id"] == ticket_query.strip()), None)
        if not matched:
            st.error("Ticket ID not found in local database. Anti-hallucination guardrail active.")
        else:
            with st.spinner("Generating official resolution letter via Gemini 3.5 Flash-Lite..."):
                prompt = f"""
                Draft a professional resolution letter for:
                Ticket ID: {matched['ticket_id']}
                Consumer Name: {matched['consumer_name']}
                Category: {matched['category']}
                Issue: {matched['description']}
                Current Status: {matched['status']}
                
                Ensure the response is empathetic, authoritative, and strictly addresses the user's issue without making fake commitments.
                """
                response_text = call_gemini_lite(prompt, system_instruction="Draft official consumer redressal response.")
                st.markdown("### Generated Response Draft:")
                st.info(response_text)