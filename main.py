import os
import json
import time
from datetime import datetime, timedelta
import streamlit as st

# Safe import for Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

st.set_page_config(
    page_title="Auto-Nivaran | AI Consumer Grievance Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Global App Background and Typography */
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    
    /* Main Header Banner Style */
    .main-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 24px 28px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .main-title {
        color: #0EA5E9;
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .main-subtitle {
        color: #94A3B8;
        font-size: 15px;
        line-height: 1.5;
    }

    /* Metric Visual Cards */
    .metric-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        transition: transform 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #0EA5E9;
    }
    .metric-value {
        font-size: 32px;
        font-weight: 700;
        color: #38BDF8;
        margin-bottom: 4px;
    }
    .metric-label {
        font-size: 13px;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        font-weight: 600;
    }

    /* SLA Status Badges */
    .badge-l1 {
        background-color: #0284C7;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-l2 {
        background-color: #DC2626;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-closed {
        background-color: #16A34A;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }

    /* Custom Input and Form Styling */
    div[data-baseweb="input"] {
        background-color: #1E293B !important;
        border-color: #334155 !important;
        color: #F8FAFC !important;
    }
    .stButton>button {
        background: linear-gradient(135deg, #0EA5E9 0%, #0284C7 100%);
        color: white;
        border: none;
        font-weight: 600;
        border-radius: 8px;
        padding: 10px 24px;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        opacity: 0.9;
        box-shadow: 0 4px 12px rgba(14, 165, 233, 0.4);
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_gemini_client():
    """Initializes and returns Google GenAI client using Streamlit Secrets or OS Environment."""
    if not GENAI_AVAILABLE:
        return None
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
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

def call_gemini(prompt_text, system_instruction=""):
    """
    Executes a prompt against Gemini Flash model with exponential backoff for 503 errors.
    """
    if not GENAI_AVAILABLE:
        return "⚠️ `google-genai` library is missing. Install via `pip install google-genai`."
        
    if not client:
        return "⚠️ API Key Error: GEMINI_API_KEY is not configured in secrets or environment variables."
    
    master_prompt = f"""
    SYSTEM GUARDRAIL INSTRUCTIONS:
    {system_instruction}
    
    STRICT ANTI-HALLUCINATION RULES:
    1. Do NOT invent synthetic ticket IDs, fake reference dates, or unauthorized commitments.
    2. Stick strictly to facts provided in the user complaint context.
    
    USER COMPLAINT / PROMPT:
    {prompt_text}
    """
    
    max_retries = 3
    backoff_delay = 1.5
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=master_prompt
            )
            return response.text
        except Exception as e:
            err_str = str(e)
            if ("503" in err_str or "overloaded" in err_str.lower()) and attempt < max_retries - 1:
                time.sleep(backoff_delay * (attempt + 1))
                continue
            return f"⚠️ AI Generation Error: {err_str} (Attempt {attempt + 1}/{max_retries})"

DB_FILE = "complaints.json"

def get_initial_seed_data():
    """Provides seed complaint data if local database does not exist."""
    now = datetime.now()
    return [
        {
            "ticket_id": "AN-1725732001",
            "consumer_name": "Rajesh Kumar",
            "email": "rajesh@example.com",
            "category": "Banking & Finance",
            "priority": "High",
            "description": "Unauthorized transaction of ₹15,000 debited from account despite failed OTP verification.",
            "ai_summary": "Category: Banking Fraud. Action Required: Freeze transaction path and trigger bank audit.",
            "timestamp": (now - timedelta(hours=52)).isoformat(), # Escalated (>48h)
            "status": "Level 1 Active",
            "elapsed_hours": 52.0
        },
        {
            "ticket_id": "AN-1725732002",
            "consumer_name": "Priya Sharma",
            "email": "priya@example.com",
            "category": "E-Commerce & Delivery",
            "priority": "Medium",
            "description": "Received damaged laptop screen. Return window requested 3 days ago but no pickup scheduled.",
            "ai_summary": "Category: Product Defect. Action Required: Issue return shipping label to buyer.",
            "timestamp": (now - timedelta(hours=12)).isoformat(), # L1 Active (<48h)
            "status": "Level 1 Active",
            "elapsed_hours": 12.0
        }
    ]

def load_complaints():
    """Loads complaints from local JSON file or initializes default dataset."""
    if not os.path.exists(DB_FILE):
        seed_data = get_initial_seed_data()
        save_complaints(seed_data)
        return seed_data
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_complaints(data):
    """Saves complaint state to local JSON file safely."""
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        st.error(f"Error writing to local JSON storage: {e}")

def process_sla_rules(complaints):
    """
    Enforces SLA Rules:
    - SLA Breach Rule: > 48 Hours in 'Level 1 Active' -> Auto-Escalates to 'Level 2 Escalated'.
    - Auto-Closure Rule: > 168 Hours (7 days) -> Auto-Marks as 'Closed'.
    """
    now = datetime.now()
    updated = False
    
    for item in complaints:
        try:
            filed_time = datetime.fromisoformat(item["timestamp"])
            elapsed_hours = (now - filed_time).total_seconds() / 3600.0
            item["elapsed_hours"] = round(elapsed_hours, 1)
            
            # SLA Rule 1: 48-Hour Level 1 Breach -> Level 2 Nodal Escalation
            if elapsed_hours >= 48.0 and item["status"] == "Level 1 Active":
                item["status"] = "Level 2 Escalated"
                item["escalated_at"] = now.isoformat()
                updated = True
                
            # SLA Rule 2: 168-Hour Window -> Auto Closure for Resolved/Inactive
            if elapsed_hours >= 168.0 and item["status"] in ["Resolved", "Level 1 Active"]:
                item["status"] = "Closed"
                updated = True
        except Exception:
            continue
            
    if updated:
        save_complaints(complaints)
    return complaints

# Initialize & Process SLA Clock on Load
complaints_data = load_complaints()
complaints_data = process_sla_rules(complaints_data)

st.markdown("""
<div class="main-header">
    <div class="main-title">🛡️ Auto-Nivaran Portal</div>
    <div class="main-subtitle">AI-Powered Consumer Grievance Escalation & Real-Time SLA Tracking Platform</div>
</div>
""", unsafe_allow_html=True)

# Metrics Grid Calculation
total_count = len(complaints_data)
l1_count = sum(1 for c in complaints_data if c["status"] == "Level 1 Active")
l2_count = sum(1 for c in complaints_data if c["status"] == "Level 2 Escalated")
closed_count = sum(1 for c in complaints_data if c["status"] in ["Closed", "Resolved"])

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total_count}</div><div class="metric-label">Total Grievances</div></div>', unsafe_allow_html=True)
with col_m2:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#38BDF8;">{l1_count}</div><div class="metric-label">L1 Active (&lt;48h)</div></div>', unsafe_allow_html=True)
with col_m3:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#EF4444;">{l2_count}</div><div class="metric-label">L2 SLA Breached (&gt;48h)</div></div>', unsafe_allow_html=True)
with col_m4:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#22C55E;">{closed_count}</div><div class="metric-label">Resolved / Closed</div></div>', unsafe_allow_html=True)

st.write("")

tab_file, tab_tracker, tab_ai, tab_analytics = st.tabs([
    "📝 File New Grievance", 
    "📊 Live Complaint Tracker & SLA Clock", 
    "🤖 AI Resolution Draft Generator",
    "📈 Analytics Dashboard"
])

with tab_file:
    st.subheader("Submit Consumer Complaint")
    st.markdown("All complaints submitted are automatically assigned a **48-Hour SLA Clock**.")
    
    with st.form("grievance_submission_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            consumer_name = st.text_input("Consumer Full Name *", placeholder="e.g. Ananya Roy")
            category = st.selectbox("Grievance Category *", [
                "Banking & Finance", 
                "E-Commerce & Delivery", 
                "Telecommunications", 
                "Public Utilities", 
                "Insurance & Investments",
                "Other Consumer Services"
            ])
        with col_b:
            email = st.text_input("Email Address *", placeholder="ananya@example.com")
            priority = st.select_slider("Priority Level", options=["Low", "Medium", "High", "Critical"], value="Medium")
            
        complaint_text = st.text_area("Detailed Complaint Description *", placeholder="Explain the issue clearly with relevant order/account IDs...", height=120)
        
        submitted = st.form_submit_button("🚀 Submit Complaint & Start SLA Clock")
        
        if submitted:
            if not consumer_name.strip() or not complaint_text.strip() or not email.strip():
                st.error("⚠️ Please fill in all mandatory fields before submitting.")
            else:
                with st.spinner("AI Categorizing and Analyzing Grievance via Gemini 2.5 Flash..."):
                    system_instructions = "You are an expert consumer grievance officer. Summarize the issue in 2 clear sentences and suggest 3 key resolution steps."
                    ai_analysis = call_gemini(f"Category: {category}\nDetails: {complaint_text}", system_instruction=system_instructions)
                    
                    ticket_id = f"AN-{int(time.time())}"
                    new_entry = {
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
                    
                    complaints_data.append(new_entry)
                    save_complaints(complaints_data)
                    
                    st.success(f"✅ Grievance Filed Successfully! Ticket ID: **{ticket_id}**")
                    st.info(f"**AI Initial Triage Summary:**\n\n{ai_analysis}")
                    st.rerun()

with tab_tracker:
    st.subheader("Live Grievance Tracker & SLA Board")
    
    # Filter Controls
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        search_query = st.text_input("🔍 Search by Ticket ID, Name or Keyword", placeholder="e.g. AN-1725732001 or Banking")
    with col_f2:
        status_filter = st.selectbox("Filter Status", ["All Statuses", "Level 1 Active", "Level 2 Escalated", "Closed"])
    
    # Apply Filtering Logic
    filtered_list = complaints_data
    if status_filter != "All Statuses":
        filtered_list = [c for c in filtered_list if c["status"] == status_filter]
    if search_query.strip():
        sq = search_query.lower()
        filtered_list = [
            c for c in filtered_list 
            if sq in c["ticket_id"].lower() or sq in c["consumer_name"].lower() or sq in c["description"].lower() or sq in c["category"].lower()
        ]
        
    if not filtered_list:
        st.info("No matching complaints found in the database.")
    else:
        for item in reversed(filtered_list):
            badge_class = "badge-l1"
            if item["status"] == "Level 2 Escalated":
                badge_class = "badge-l2"
            elif item["status"] == "Closed":
                badge_class = "badge-closed"
                
            elapsed = item.get("elapsed_hours", 0.0)
            
            with st.expander(f"🎫 #{item['ticket_id']} | {item['consumer_name']} | {item['category']}"):
                col_c1, col_c2 = st.columns([2, 1])
                with col_c1:
                    st.markdown(f"**Grievance Details:**\n{item['description']}")
                    st.markdown(f"**AI Triage:**\n{item.get('ai_summary', 'N/A')}")
                with col_c2:
                    st.markdown(f"**Status:** <span class='{badge_class}'>{item['status']}</span>", unsafe_allow_html=True)
                    st.write(f"**Filed Date:** {item['timestamp'][:16].replace('T', ' ')}")
                    st.write(f"**SLA Clock Elapsed:** `{elapsed} Hours`")
                    st.write(f"**Priority:** `{item.get('priority', 'Medium')}`")
                    
                    # Status Action Buttons
                    if item["status"] != "Closed":
                        if st.button(f"Mark as Resolved #{item['ticket_id']}", key=f"res_{item['ticket_id']}"):
                            item["status"] = "Closed"
                            save_complaints(complaints_data)
                            st.success("Ticket status updated to Closed.")
                            st.rerun()

with tab_ai:
    st.subheader("🤖 AI Resolution Letter & Response Generator")
    st.markdown("Enter a Ticket ID to generate an authoritative, empathetic resolution response.")
    
    ticket_search = st.text_input("Enter Ticket ID", placeholder="e.g. AN-1725732001")
    
    if st.button("Generate Official Response Draft"):
        clean_id = ticket_search.strip()
        matched = next((c for c in complaints_data if c["ticket_id"].lower() == clean_id.lower()), None)
        
        if not matched:
            st.error("❌ Anti-Hallucination Guardrail Active: Ticket ID not found in local database. AI will not generate unverified statements.")
        else:
            with st.spinner("Generating official redressal letter using Gemini 2.5 Flash..."):
                prompt = f"""
                Draft an official consumer redressal letter for the following complaint:
                
                Ticket ID: {matched['ticket_id']}
                Consumer Name: {matched['consumer_name']}
                Category: {matched['category']}
                Priority: {matched['priority']}
                Issue Description: {matched['description']}
                Current SLA Status: {matched['status']} (Elapsed Time: {matched.get('elapsed_hours', 0)} hrs)
                
                Instructions:
                - Tone: Formal, empathetic, authoritative.
                - Address the root issue directly.
                - Provide concrete next steps and escalation contacts if breached.
                """
                response = call_gemini(prompt, system_instruction="You are a Senior Consumer Redressal Officer writing an official resolution letter.")
                st.markdown("### 📄 Generated Response Letter:")
                st.info(response)

with tab_analytics:
    st.subheader("📈 System SLA Metrics & Category Distribution")
    
    if complaints_data:
        categories = {}
        for c in complaints_data:
            cat = c.get("category", "Unassigned")
            categories[cat] = categories.get(cat, 0) + 1
            
        st.write("### Category Breakdown")
        for cat, count in categories.items():
            pct = round((count / len(complaints_data)) * 100, 1)
            st.write(f"**{cat}:** {count} complaints ({pct}%)")
            st.progress(count / len(complaints_data))
    else:
        st.info("No data available for analytics yet.")