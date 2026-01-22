from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from typing import Optional
from langchain_core.messages import SystemMessage
import datetime



app = FastAPI()

# Enable CORS so React can talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Connection ---
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root", # <--- UPDATE THIS
        database="hcp_crm"
    )

# ==========================================
#        THE 5 ESSENTIAL TOOLS
# ==========================================

# TOOL 1: Log Interaction (The Core Logger)
@tool
def log_interaction(
    hcp_name: str, 
    type: str, 
    date: str, 
    topics: Optional[str] = "None", 
    materials: Optional[str] = "None",    
    sentiment: Optional[str] = "None", 
    outcomes: Optional[str] = "None",
    follow_up: Optional[str] = "None"     
):
    """
    Log a NEW interaction. 
    - materials: brochures, pamphlets, studies.
    - follow_up: reminders, next steps, emails.
    NEVER use this tool for questions like "Who is?" or "Do I have?".
    Log a NEW interaction. Use this when the user says 'Log', 'Record', or 'I met'.
    """
    # """Log a meeting. details: topics, materials, sentiment, outcomes, follow_up."""
    try:
        db = get_db()
        cursor = db.cursor()
        sql = """INSERT INTO interactions 
                 (hcp_name, interaction_type, interaction_date, topics_discussed, 
                  materials_shared, sentiment, outcomes, follow_up_action) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        val = (hcp_name, type, date, topics, materials, sentiment, outcomes, follow_up)
        cursor.execute(sql, val)
        db.commit()
        return "✅ Interaction logged successfully."
    except Exception as e:
        return f"❌ Error logging: {str(e)}"

# TOOL 2: Edit Interaction (The Fixer)
@tool
def edit_interaction(
    hcp_name: Optional[str] = None, 
    type: Optional[str] = None, 
    date: Optional[str] = None, 
    topics: Optional[str] = None, 
    materials: Optional[str] = None,   
    sentiment: Optional[str] = None, 
    outcomes: Optional[str] = None,
    follow_up: Optional[str] = None    
):
    """
    EDIT the LAST logged interaction.
    Use when user says 'change', 'update', 'correct', 'add' or 'fix'.
    """
    # """Get last 3 logs for HCP."""
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        updates = []
        values = []
        
        if hcp_name and hcp_name != "None": updates.append("hcp_name = %s"); values.append(hcp_name)
        if type and type != "None": updates.append("interaction_type = %s"); values.append(type)
        if date and date != "None": updates.append("interaction_date = %s"); values.append(date)
        if topics and topics != "None": updates.append("topics_discussed = %s"); values.append(topics)
        if materials and materials != "None": updates.append("materials_shared = %s"); values.append(materials)
        if sentiment and sentiment != "None": updates.append("sentiment = %s"); values.append(sentiment)
        if outcomes and outcomes != "None": updates.append("outcomes = %s"); values.append(outcomes)
        if follow_up and follow_up != "None": updates.append("follow_up_action = %s"); values.append(follow_up)
            
        if not updates:
            return "No changes requested."

        sql = f"UPDATE interactions SET {', '.join(updates)} ORDER BY id DESC LIMIT 1"
        cursor.execute(sql, tuple(values))
        db.commit()
        return "✅ Interaction updated in database."
    except Exception as e:
        return f"❌ Error updating: {str(e)}"

# TOOL 3: Interaction History (Memory)
@tool
def get_interaction_history(hcp_name: str):
    """
    Retrieves the last 3 interactions to help the user prepare.
    Use when user asks: "What did we discuss last time?", "History with Dr. Smith?"
    """
    # """Get last 3 logs for HCP."""
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        sql = "SELECT interaction_date, topics_discussed, outcomes FROM interactions WHERE hcp_name LIKE %s ORDER BY id DESC LIMIT 3"
        cursor.execute(sql, (f"%{hcp_name}%",))
        results = cursor.fetchall()
        
        if not results: return "No history found."
            
        history = "\n".join([f"- {r['interaction_date']}: {r['topics_discussed']} (Outcome: {r['outcomes']})" for r in results])
        return f"📜 History for {hcp_name}:\n{history}"
    except Exception as e:
        return f"Error: {str(e)}"

# TOOL 4: HCP Profile (Context)
@tool
def get_hcp_profile(hcp_name: str):
    """
    Get the doctor's bio and best visiting time.
    Use when user asks: "Who is he?", "When should I visit?", "Profile?"
    """
    
    # """Get bio and visit time."""
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT name, specialty, hospital, best_time_to_visit FROM hcp_directory WHERE name LIKE %s", (f"%{hcp_name}%",))
        r = cursor.fetchone()
        if r:
            return f"👤 PROFILE: {r['name']} ({r['specialty']} at {r['hospital']}). 🕒 Best Time: {r['best_time_to_visit']}."
        return "HCP not found."
    except Exception as e:
        return f"Error: {str(e)}"

# TOOL 5: Check Stock (Inventory - The "Expert" Tool)
@tool
def check_sample_stock(product_name: str):
    """
    Checks inventory count for a product.
    Use when user asks: "Do I have samples?", "Stock check", "How many boxes?"
    """
    # """Check inventory count."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT stock_count FROM inventory WHERE product_name LIKE %s", (f"%{product_name}%",))
        r = cursor.fetchone()
        if r:
            return f"📦 Stock Check: You have {r[0]} boxes of {product_name}."
        return "❌ Product not found in inventory."
    except Exception as e:
        return f"Error: {str(e)}"



# --- Agent Setup ---
# Using llama-3.3-70b-versatile model as required [cite: 16]
llm = ChatGroq(model="llama-3.3-70b-versatile", groq_api_key="YOUR_GROQ_API_KEY") 

# List of tools the agent can use
tools = [log_interaction, edit_interaction, get_interaction_history, get_hcp_profile, check_sample_stock]

agent_executor = create_react_agent(llm, tools)

today_str = datetime.date.today().strftime("%Y-%m-%d")
# --- Updated System Prompt ---
SYSTEM_PROMPT = (
    f"You are a smart CRM assistant. Today is {today_str}.\n"
    "GUIDELINES:\n"
    "1. DECIDE THE TOOL FIRST:\n"
    "   - IF USER ASKS 'WHO IS...' or 'PROFILE': Call `get_hcp_profile`. Then SPEAK the Name, Specialty, Hospital, and Visit Time to the user. DO NOT SAVE/LOG ANYTHING.\n"
    "   - IF user asks about STOCK/SAMPLES -> Use `check_sample_stock`.\n"
    "   - IF user asks about HISTORY/PAST -> Use `get_interaction_history`.\n"
    "2. EXECUTE & SPEAK: Call the tool, get the result, and then SUMMARIZE the answer for the user.\n"
    "3. DO NOT STOP: You must explain the result to the user.\n"
    "4. LOGGING: If user provides meeting details, use `log_interaction`.\n"
    "CRITICAL: Never fill the form (log_interaction) just because you found an answer. Only fill it when the user *tells* you to log a meeting."
)

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        ("user", req.message)
    ]
    
    # Run Agent
    result = agent_executor.invoke({"messages": messages})
    
    # Extract Logic (First-Match-Only to prevent hallucinations)
    extracted_data = None
    for msg in result["messages"]:
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tool in msg.tool_calls:
                if tool['name'] in ['log_interaction', 'edit_interaction']:
                    extracted_data = tool['args']
                    break # Stop at the first valid tool call
        if extracted_data:
            break

    # Get final text response
    last_message = result["messages"][-1].content

    return {
        "response": last_message, 
        "form_data": extracted_data 
    }
# Run with: uvicorn main:app --reload