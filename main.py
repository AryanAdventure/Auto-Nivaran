import streamlit as st
import json
import os
from datetime import datetime
import urllib.parse 
import re 
from google import genai
from google.genai import types

# ==========================================
# ⚙️ BACKGROUND API SETTINGS (Backend)
# ==========================================
# Yahan apni Gemini API Key paste karein!
# ==========================================
# ⚙️ BACKGROUND API SETTINGS (Backend)
# ==========================================
import os

try:
    # Streamlit secrets se key fetch karke environment variable set kar rahe hain
    api_key = st.secrets["GEMINI_API_KEY"]
    os.environ["GEMINI_API_KEY"] = api_key
    client = genai.Client()
except Exception as e:
    client = None
    st.error("⚠️ API Key missing or invalid! Please check Streamlit Secrets.")
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
        if c["id"] == complaint_id:
            c.update(updates)
            break
    with open(COMPLAINTS_FILE, "w") as f:
        json.dump(complaints, f, indent=4)

# ==========================================
# 🤖 GEMINI AI ENGINE FUNCTIONS
# ==========================================
import time

def ask_gemini(prompt_text, image_bytes=None, system_instruction=""):
    if not client: return "Error: Gemini Client not initialized."
    
    master_prompt = f"""
    STRICT SYSTEM INSTRUCTIONS: {system_instruction}
    CRITICAL RULE: DO NOT hallucinate or invent Ticket IDs, Dates, or Email Addresses. If a Ticket ID is not provided in the prompt, ask the user for it.
    
    USER PROMPT: {prompt_text}
    """
    
    # 3 Times Auto-Retry Logic for 503 / Server Overload
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if image_bytes:
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=[types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'), master_prompt]
                )
            else:
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=master_prompt
                )
            return response.text
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                time.sleep(2)  # Server overload hone par 2 second wait karke fir try karega
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

# ==========================================
# 🎨 UI CONFIGURATION & THEME (OPTION A)
# ==========================================
st.set_page_config(page_title="Auto-Nivaran AI", page_icon="⚖️", layout="wide")

# Option A: Clean & Trustworthy Custom CSS
st.markdown("""
    <style>
    /* Background and global text */
    .stApp {
        background-color: #F8F9FA;
        color: #2C3E50;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #0F4C81 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Primary Navy Blue Buttons */
    div.stButton > button:first-child {
        background-color: #0F4C81;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        background-color: #1A365D;
        box-shadow: 0 6px 10px rgba(0,0,0,0.15);
        transform: translateY(-1px);
    }
    
    /* Inputs and Text Areas - Clean Borders */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        border-radius: 6px;
        border: 1px solid #CBD5E1;
        background-color: #FFFFFF;
        color: #1E293B;
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
        color: #475569;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF;
        color: #0F4C81;
        border-bottom: 3px solid #0F4C81;
        font-weight: bold;
    }
    
    /* Chat Form Container Shadow */
    div[data-testid="stForm"] {
        background-color: #FFFFFF;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        border: 1px solid #E2E8F0;
    }
    
    /* Expander styling for Dashboard */
    .streamlit-expanderHeader {
        background-color: #FFFFFF;
        border-radius: 6px;
        color: #1E293B;
        border: 1px solid #E2E8F0;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚖️ Auto-Nivaran: Smart Grievance Assistant")

# Initialize session states
if "draft_ready" not in st.session_state:
    st.session_state.draft_ready = False
if "desc_input" not in st.session_state:
    st.session_state.desc_input = ""
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [{"role": "assistant", "content": "Namaste! Apni problem yahan short mein batayein. Agar aapka koi purana ticket hai, toh kripya apna Ticket ID zaroor batayein."}]

tab1, tab2 = st.tabs(["📝 File Complaint & AI Help", "📊 SLA Dashboard (Auto-Escalation)"])

# ------------------------------------------
# TAB 1: FILE NEW COMPLAINT & INLINE AI CHAT
# ------------------------------------------
with tab1:
    if not st.session_state.draft_ready:
        col_n, col_c = st.columns(2)
        with col_n:
            user_name = st.text_input("👤 Your Full Name:")
        with col_c:
            user_contact = st.text_input("📞 Contact Number:")

        uploaded_file = st.file_uploader("Upload Attachments (Images, Bills, etc.)", type=["png", "jpg", "jpeg"])
        location_input = st.text_input("📍 Brand / Department (e.g., PWD Ghaziabad, boAt):")
        
        selected_date = st.date_input("Date", datetime.now().date())
        time_str = f"{selected_date} {datetime.now().time().strftime('%H:%M:%S')}"
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # --- 🤖 INLINE AI CHAT SECTION ---
        st.markdown("### 🤖 AI Assistant (Chat & Auto-Fill)")
        
        chat_box = st.container(height=220)
        with chat_box:
            for msg in st.session_state.chat_messages:
                if msg["role"] == "assistant":
                    st.info(f"🤖 **AI:** {msg['content']}")
                else:
                    st.success(f"👤 **You:** {msg['content']}")
        
        with st.form(key="chat_form", clear_on_submit=True):
            col_in, col_btn = st.columns([5, 1])
            with col_in:
                user_msg = st.text_input("Chat with AI...", label_visibility="collapsed", placeholder="Jaise: Mera fan kal se kaam nahi kar raha hai...")
            with col_btn:
                send_btn = st.form_submit_button("Send 🚀")
        
        if send_btn and user_msg:
            st.session_state.chat_messages.append({"role": "user", "content": user_msg})
            
            prompt_string = "Conversation:\n"
            for m in st.session_state.chat_messages[-4:]: 
                role = "User" if m["role"] == "user" else "AI"
                prompt_string += f"{role}: {m['content']}\n"
            
            sys_instruct = "You are Auto-Nivaran AI helping an Indian consumer. Talk politely in Hinglish. If they mention an existing complaint, ask for the Ticket ID. Do not invent one."
            
            with st.spinner("🧠 AI is typing..."):
                ai_reply = ask_gemini(prompt_string, system_instruction=sys_instruct)
                st.session_state.chat_messages.append({"role": "assistant", "content": ai_reply})
            st.rerun()

        if len(st.session_state.chat_messages) > 1:
            if st.button("✨ Auto-Fill Description", type="primary"):
                with st.spinner("📝 Writing professional description..."):
                    history = " ".join([m['content'] for m in st.session_state.chat_messages if m["role"] == "user"])
                    fill_prompt = f"Based on this user problem: '{history}', write a highly formal 2-3 line problem description in English suitable for a grievance complaint form."
                    generated_desc = ask_gemini(fill_prompt)
                    st.session_state.desc_input = clean_llm_response(generated_desc)
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        user_problem = st.text_area("✍️ Describe the issue:", key="desc_input", height=120)

        if st.button("🚀 Process Grievance (Level 1)"):
            if not user_name or not user_contact:
                st.error("⚠️ Please enter Name and Contact Number.")
            elif uploaded_file or (st.session_state.desc_input and location_input):
                with st.spinner("🧠 Gemini AI is drafting Level 1 email..."):
                    target_email = get_official_email(location_input, level=1)
                    img_bytes = uploaded_file.getvalue() if uploaded_file else None
                    draft_prompt = f"Draft a formal grievance email to '{location_input}'. Issue: '{st.session_state.desc_input}'. Name: {user_name}, Contact: {user_contact}. Output ONLY the email body starting with 'Subject:'."
                    
                    draft_text = ask_gemini(draft_prompt, img_bytes)

                    st.session_state.draft_ready = True
                    st.session_state.draft = clean_llm_response(draft_text)
                    st.session_state.target_email = target_email
                    st.session_state.location = location_input
                    st.session_state.user_name = user_name
                    st.session_state.user_contact = user_contact
                    st.session_state.time_str = time_str
                    st.rerun()
            else:
                st.error("⚠️ Describe the issue to proceed.")

    else:
        st.success("✅ Level 1 Draft Complete!")
        
        st.markdown("### 🎯 Target Email (Editable)")
        updated_email = st.text_input("Email ID:", value=st.session_state.target_email)
        if updated_email != st.session_state.target_email:
            st.session_state.target_email = updated_email
            save_to_email_db(st.session_state.location, updated_email)
            
        with st.expander("👀 View Level 1 Draft"):
            st.text(st.session_state.draft)

        mail_subject = urllib.parse.quote(f"Formal Grievance: {st.session_state.location}")
        mail_body = urllib.parse.quote(st.session_state.draft)
        mailto_url = f"mailto:{st.session_state.target_email}?subject={mail_subject}&body={mail_body}"
        
        if st.link_button(f"✉️ Open Mail App & Send", mailto_url, type="primary"):
            complaint_obj = {
                "id": f"TKT-{int(datetime.now().timestamp())}", 
                "name": st.session_state.user_name,
                "contact": st.session_state.user_contact,
                "location": st.session_state.location,
                "email": st.session_state.target_email,
                "date": st.session_state.time_str,
                "description": st.session_state.desc_input, 
                "status": "Pending",
                "level": 1,
                "sla_hours": 48
            }
            save_complaint(complaint_obj)
            st.toast("✅ Saved to Dashboard with Generated Ticket ID!")

        if st.button("🔄 File Another Complaint"):
            st.session_state.draft_ready = False
            st.session_state.desc_input = "" 
            st.rerun()

# ------------------------------------------
# TAB 2: LEVEL 2 ESCALATION & SLA TRACKING
# ------------------------------------------
with tab2:
    st.header("📊 SLA Tracking & Actions")
    st.caption("Track 48-hour SLA. Extend time or auto-generate Level 2 Escalation.")
    complaints = load_complaints()
    
    if not complaints:
        st.info("No active complaints tracked yet.")
    else:
        for c in reversed(complaints):
            created_at = datetime.strptime(c["date"], "%Y-%m-%d %H:%M:%S")
            allowed_hours = c.get("sla_hours", 48)
            time_elapsed = datetime.now() - created_at
            hours_passed = time_elapsed.total_seconds() / 3600
            
            # --- AUTO-CLOSE LOGIC (7 DAYS / 168 HOURS NO RESPONSE) ---
            if "Pending" in c["status"] and hours_passed >= (allowed_hours + 168):
                update_complaint_data(c["id"], {"status": "Auto-Closed (No Response)"})
                st.rerun()
            
            status_color = "🟢" if "Resolved" in c["status"] or "Closed" in c["status"] else ("🔴" if hours_passed >= allowed_hours else "🟡")
            
            with st.expander(f"{status_color} ID: {c['id']} | Target: {c['location']} | Status: {c['status']}"):
                st.write(f"**Level:** {c.get('level', 1)} | **Time Elapsed:** {round(hours_passed, 1)} / {allowed_hours} Hrs allowed")
                st.write(f"**Original Issue:** {c.get('description', 'No description found.')}")

                # 48 HOURS CROSS HONE PAR YE 3 BUTTONS DIKHENGE
                if "Pending" in c["status"] and hours_passed >= allowed_hours:
                    st.error("🚨 **SLA BREACHED! Action Required.**")
                    st.warning("⚠️ Agar 7 din tak action nahi liya gaya, toh yeh ticket auto-close ho jayega.")
                    
                    # 3 Buttons Layout
                    col1, col2, col3 = st.columns(3)
                    
                    # BUTTON 1: SOLVED
                    with col1:
                        if st.button("✅ Solved", key=f"sol_{c['id']}"):
                            update_complaint_data(c["id"], {"status": "Resolved"})
                            st.rerun()
                    
                    # BUTTON 2: EXTEND TIME
                    with col2:
                        with st.popover("⏳ Extend Time"):
                            st.write("Agar company ne aur time manga hai:")
                            extra_days = st.number_input("Kitne din (Days)?", min_value=1, value=3, key=f"num_{c['id']}")
                            if st.button("Update Time", key=f"ext_{c['id']}"):
                                extra_hours = extra_days * 24
                                update_complaint_data(c["id"], {
                                    "sla_hours": c.get("sla_hours", 48) + extra_hours, 
                                    "status": "Pending" 
                                })
                                st.rerun()
                    
                    # BUTTON 3: ESCALATE LEVEL 2
                    with col3:
                        if st.button("❌ Escalate", key=f"esc_{c['id']}"):
                            with st.spinner("🧠 AI fetching Nodal Officer & Drafting Legal Warning..."):
                                nodal_email = get_official_email(c['location'], level=2)
                                l2_sys_instruct = "You are drafting a legal escalation warning. Do NOT invent data. Use EXACTLY the provided Ticket ID and details."
                                l2_prompt = f"""
                                Draft a strict Level 2 Escalation Email to the Grievance/Nodal Officer of {c['location']}.
                                
                                YOU MUST INCLUDE THIS HISTORY:
                                - Previous Ticket ID: {c['id']}
                                - Date of 1st Complaint: {c['date']}
                                - Name: {c['name']}
                                - Core Issue: {c.get('description', 'Defective product/service')}
                                
                                Tone: Highly formal, mention SLA breach, state that Level 1 was unresponsive, and threaten escalation to Consumer Court / NCH if not resolved in 24 hours. Output ONLY the email body starting with 'Subject:'.
                                """
                                l2_draft = ask_gemini(l2_prompt, system_instruction=l2_sys_instruct)
                                clean_l2_draft = clean_llm_response(l2_draft)
                                
                                update_complaint_data(c["id"], {"status": "Escalated Level 2", "level": 2, "sla_hours": c.get("sla_hours", 48) + 48})
                                
                                mail_subject = urllib.parse.quote(f"URGENT ESCALATION: SLA Breached for Ticket {c['id']}")
                                mail_body = urllib.parse.quote(clean_l2_draft + "\n\n--- PLEASE ATTACH PREVIOUS SCREENSHOTS / BILLS HERE ---")
                                st.link_button("✉️ Open Mail & Send Level 2 Warning", f"mailto:{nodal_email}?subject={mail_subject}&body={mail_body}", type="primary")
                                st.rerun()
                
                elif "Pending" in c["status"]:
                    st.info(f"⏳ SLA is active. Options will appear after {allowed_hours} hours.")