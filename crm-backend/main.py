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

# --- LangGraph Tools [cite: 60, 62] ---

@tool
def log_interaction(
    hcp_name: str, 
    type: str, 
    date: str, 
    topics: Optional[str] = "None", 
    materials: Optional[str] = "None",    # <--- Correct Position
    sentiment: Optional[str] = "None", 
    outcomes: Optional[str] = "None",
    follow_up: Optional[str] = "None"     # <--- Correct Position
):
    """
    Log a NEW interaction. 
    - materials: brochures, pamphlets, studies.
    - follow_up: reminders, next steps, emails.
    """
    try:
        db = get_db()
        cursor = db.cursor()
        
        # SQL with columns in your exact requested sequence
        sql = """INSERT INTO interactions 
                 (hcp_name, interaction_type, interaction_date, topics_discussed, 
                  materials_shared, sentiment, outcomes, follow_up_action) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                 
        val = (hcp_name, type, date, topics, materials, sentiment, outcomes, follow_up)
        cursor.execute(sql, val)
        db.commit()
        return "✅ Interaction logged with full details."
    except Exception as e:
        return f"❌ Error logging: {str(e)}"

@tool
def search_hcp(name_query: str):
    """Search for an HCP in the directory by name to verify they exist."""
    db = get_db()
    cursor = db.cursor()
    # Simple search query
    cursor.execute(f"SELECT name, specialty, hospital FROM hcp_directory WHERE name LIKE '%{name_query}%'")
    result = cursor.fetchall()
    return str(result) if result else "No HCP found."

@tool
def edit_interaction(
    hcp_name: Optional[str] = None, 
    type: Optional[str] = None, 
    date: Optional[str] = None, 
    topics: Optional[str] = None, 
    materials: Optional[str] = None,   # <--- Correct Position
    sentiment: Optional[str] = None, 
    outcomes: Optional[str] = None,
    follow_up: Optional[str] = None    # <--- Correct Position
):
    """
    EDIT the LAST logged interaction.
    """
    try:
        db = get_db()
        cursor = db.cursor()
        
        updates = []
        values = []
        
        # Build the dynamic query
        if hcp_name and hcp_name != "None":
            updates.append("hcp_name = %s"); values.append(hcp_name)
        if type and type != "None":
            updates.append("interaction_type = %s"); values.append(type)
        if date and date != "None":
            updates.append("interaction_date = %s"); values.append(date)
        if topics and topics != "None":
            updates.append("topics_discussed = %s"); values.append(topics)
        if materials and materials != "None":
            updates.append("materials_shared = %s"); values.append(materials)
        if sentiment and sentiment != "None":
            updates.append("sentiment = %s"); values.append(sentiment)
        if outcomes and outcomes != "None":
            updates.append("outcomes = %s"); values.append(outcomes)
        if follow_up and follow_up != "None":
            updates.append("follow_up_action = %s"); values.append(follow_up)
            
        if not updates:
            return "No changes requested."

        sql = f"UPDATE interactions SET {', '.join(updates)} ORDER BY id DESC LIMIT 1"
        cursor.execute(sql, tuple(values))
        db.commit()
        
        return "✅ Interaction updated in database."
    except Exception as e:
        return f"❌ Error updating: {str(e)}"

@tool
def check_compliance(text: str):
    """
    UNIQUE TOOL: Scans interaction notes for risky/off-label keywords. 
    Use this before logging if the user discusses drug efficacy.
    """
    risky_keywords = ["guarantee", "cure", "miracle", "off-label"]
    flagged = [word for word in risky_keywords if word in text.lower()]
    if flagged:
        return f"⚠️ COMPLIANCE WARNING: Found restricted terms: {flagged}. Please rephrase."
    return "✅ Compliance Check Passed."

# --- Agent Setup ---
# Using llama-3.3-70b-versatile model as required [cite: 16]
llm = ChatGroq(model="llama-3.3-70b-versatile", groq_api_key="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") 

# List of tools the agent can use
tools = [log_interaction, search_hcp, edit_interaction, check_compliance]


agent_executor = create_react_agent(llm, tools)

today_str = datetime.date.today().strftime("%Y-%m-%d")

# --- Define System Prompt String ---
SYSTEM_PROMPT = (
    f"You are a precise data entry assistant. Today's date is {today_str}.\n"
    "Follow these rules STRICTLY:\n"
    "1. KILL SWITCH - NO DUPLICATES:\n"
    "   - After you successfully call `log_interaction` or `edit_interaction`, you MUST STOP.\n"
    "   - DO NOT call the tool again. DO NOT ask 'Is there anything else?'.\n"
    "   - Just output a final confirmation message like: 'Done. Interaction logged.'\n"
    "2. TOOL USAGE:\n"
    "   - Use `log_interaction` for NEW meetings.\n"
    "   - Use `edit_interaction` for CHANGES.\n"
    "3. DATA MAPPING:\n"
    "   - Materials: brochures, pamphlets, studies.\n"
    "   - Follow Up: reminders, next steps.\n"
    "4. MISSING DATA: Pass the string 'None' (not null) for any missing field."
)
# --- API Endpoint ---
class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    # FIX 2: Inject the System Prompt manually into the messages list
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        ("user", req.message)
    ]
    
 # ... inside chat_endpoint ...
    result = agent_executor.invoke({"messages": messages})
    last_message = result["messages"][-1].content
    
    # --- DEBUG PRINT ---
    print("DEBUG - Full Result:", result["messages"]) 
    
    # Extract Tool Data (to update UI)
    extracted_data = None
    
    # Loop through messages
    for msg in result["messages"]:
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tool in msg.tool_calls:
                if tool['name'] in ['log_interaction', 'edit_interaction']:
                    extracted_data = tool['args']
                    # BREAK 1: Found a tool? Stop looking at other tools in this message.
                    break 
        
        # BREAK 2: Found data? Stop looking at future messages (Ignore hallucinations).
        if extracted_data:
            break

    return {
        "response": last_message, 
        "form_data": extracted_data 
    }
# Run with: uvicorn main:app --reload