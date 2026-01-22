import mysql.connector
from langchain_groq import ChatGroq

# --- 1. SETUP YOUR CREDENTIALS HERE ---
API_KEY = "gsk_..."  # <--- PASTE YOUR ACTUAL GROQ API KEY HERE
DB_PASS = "root"     # <--- PASTE YOUR MYSQL PASSWORD HERE

print("------------------------------------------------")
print("🔍 DIAGNOSTIC TEST STARTED")
print("------------------------------------------------")

# --- TEST 1: DATABASE CONNECTION ---
print("\n1. Testing MySQL Database Connection...")
try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password=DB_PASS,
        database="hcp_crm"
    )
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM hcp_directory")
    count = cursor.fetchone()[0]
    print(f"   ✅ SUCCESS! Database connected. Found {count} doctors.")
    db.close()
except Exception as e:
    print(f"   ❌ FAILED! Database Error: {e}")
    print("   👉 ACTION: Check your MySQL password or if 'hcp_crm' database exists.")

# --- TEST 2: AI MODEL CONNECTION ---
print("\n2. Testing Groq AI Connection...")
try:
    llm = ChatGroq(model="llama-3.1-8b-instant", groq_api_key=API_KEY)
    response = llm.invoke("Say 'Hello' if you can hear me.")
    print(f"   ✅ SUCCESS! AI Responded: {response.content}")
except Exception as e:
    print(f"   ❌ FAILED! API Error: {e}")
    print("   👉 ACTION: Check your Groq API Key.")

print("\n------------------------------------------------")
print("🏁 TEST COMPLETE")
print("------------------------------------------------")