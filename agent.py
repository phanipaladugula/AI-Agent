from datetime import datetime
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import connect
from sqlalchemy import text
from database import get_db, Expenses
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
load_dotenv()

# --- Database + Saver Setup ---
POSTGRES_URI = os.getenv("POSTGRES_URI")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

conn = connect(POSTGRES_URI)
conn.autocommit = True  # Required for concurrent index creation
saver = PostgresSaver(conn)
saver.setup()  # ✅ Run once at startup

# --- SQLAlchemy session setup ---
db = next(get_db())

# ------------------------------------------------------------------
# 🔹 Helper: Build prompt dynamically
def build_prompt(user_id: int, query: str) -> str:
    now = datetime.now()
    return f"""
You are an expense assistant for a user with user_id={user_id}.
Always use this user_id to access expense data.

Current date:
- {now.strftime("%Y-%m-%d")}

User input: {query}
"""


def safe_sql_query(query: str):
    if "users" in query.lower() and "expenses" not in query.lower():
        return "Access to other user data is restricted."

    query = query.replace("strftime('%Y-%m', date)", "TO_CHAR(date, 'YYYY-MM')")

    allowed = ("select", "insert")
    qtype = query.strip().lower().split()[0]
    print(query)

    if qtype in allowed:
        result = db.execute(text(query))
        db.commit()
        return result

    return "NO permission to modify the database."

execute_query = StructuredTool.from_function(
    func=safe_sql_query,
    name="Execute_Safe_sql_Query",
    description="""
You are an Expense Tracker query tool for user_id=user_id.
Rules:
1️⃣ Only SELECT and INSERT queries are allowed. No DELETE or UPDATE.
2️⃣ Always use the schema: (user_id:int, category:str, amount:float, amount_type:str, date:date).
3️⃣ Never access or reveal other users' data.
4️⃣ When adding a new expense, always ask the user for confirmation before inserting.
5️⃣ Respond politely and clearly. Use proper SQL syntax for queries.
"""
)

def fetch_expenses(user_id: int):
    db: Session = next(get_db())
    expenses = (
        db.query(Expenses)
        .filter(Expenses.user_id == user_id)
        .order_by(Expenses.date.desc())
        .limit(10)
        .all()
    )
    if not expenses:
        return "No expenses found for this user."
    return [
        {"id": e.id, "category": e.category, "amount": e.amount, "date": str(e.date)}
        for e in expenses
    ]

fetch_Expenses = StructuredTool.from_function(
    name="Fetch_Expenses",
    func=fetch_expenses,
    description="Fetch the user's 10 most recent expenses from the database."
)


def update_record(user_id, record_id, category=None, amount=None, amount_type=None, date=None, confirmation=False):
    user_id = int(user_id)
    db = next(get_db())
    record = db.query(Expenses).filter(Expenses.id == record_id, Expenses.user_id == user_id).first()
    if not record:
        return f"No record found with ID {record_id}"

    if category:
        record.category = category
    if amount:
        record.amount = amount
    if amount_type:
        record.amount_type = amount_type
    if date:
        record.date = datetime.strptime(date, "%Y-%m-%d").date()

    if confirmation:
        db.commit()
        return "✅ Record updated successfully."
    else:
        return "Please confirm before updating the record."

update_user_record = StructuredTool.from_function(
    name="Update_User_Record",
    func=update_record,
    description="""
You are an intelligent and conversational Expense Assistant. Your goal is to safely update expense records for a single user. Follow these rules strictly:
Strict Rule: If the user gives his earning or deals to add ADD it in the Database here amount_type =CREDIT remember this one
if is the expense is related to bussiness or income anything add it to Database doesnt say no to the user
 Only access records belonging to the current user.
 When a user asks to update a record:
   a) First, fetch and display all records for the user with their IDs.
   b) Ask the user which record ID they want to update.
   c) Ask the user for the updated details (category, amount, date, etc.).
   d) Repeat back the updated details and ask for confirmation.
   e) If the user confirms with 'yes', update the record.
   f) If the user says 'no' or cancels, do NOT update and notify the user.
 Avoid duplicate insertions or accidental updates.
 Be polite, clear, and precise.
 Always summarize the action before making the update.

Example Conversation:

User: I want to update an expense.  
Assistant: Here are your current expenses:  
1. ID: 101 | Category: Food | Amount: 500 | Date: 2025-11-01  
2. ID: 102 | Category: Travel | Amount: 1200 | Date: 2025-11-03  

Which record ID would you like to update?  

User: 101  
Assistant: Got it. What changes would you like to make?  
User: Change amount to 550 and category to Groceries  
Assistant: You want to update record ID 101 with:  
Category: Groceries  
Amount: 550  
Date: 2025-11-01  

Do you confirm this update? (yes/no)  

User: no  
Assistant: Update cancelled. No changes were made.  
"""
)

def delete_record(user_id=None, record_id=None, confirmation=False):
    if not user_id or not record_id:
        return " user_id and record_id are required."
    db = next(get_db())
    record = db.query(Expenses).filter(Expenses.user_id == user_id, Expenses.id == record_id).first()
    if not record:
        return f"No record found with ID {record_id}."
    if not confirmation:
        return "Please confirm before deletion."
    db.delete(record)
    db.commit()
    return "Record deleted successfully."

delete_user_record = StructuredTool.from_function(
    name="Delete_Record",
    func=delete_record,
    description="""
You are an intelligent and conversational Expense Assistant. Your goal is to safely delete expense records for a single user. Follow these rules strictly:

1 Only access records belonging to the current user.
2 When a user asks to delete a record:
   a) First, fetch and display all records for the user with their IDs.
   b) Ask the user which record ID they want to delete.
   c) Repeat back the selected record and ask for confirmation.
   d) If the user confirms with 'yes', delete the record.
   e) If the user says 'no' or cancels, do NOT delete and notify the user.
3 Avoid accidental deletions.
4 Be polite, clear, and precise.
5 Always summarize the action before deleting.

Example Conversation:

User: I want to delete an expense.  
Assistant: Here are your current expenses:  
1. ID: 101 | Category: Food | Amount: 500 | Date: 2025-11-01  
2. ID: 102 | Category: Travel | Amount: 1200 | Date: 2025-11-03  

Which record ID would you like to delete?  

User: 101  
Assistant: You have selected record ID 101:  
Category: Food  
Amount: 500  
Date: 2025-11-01  

Do you confirm deletion of this record? (yes/no)  

User: no  
Assistant: Deletion cancelled. No changes were made.  

User: yes  
Assistant: Record ID 101 has been successfully deleted.
"""
)

tools = [execute_query, fetch_Expenses, update_user_record, delete_user_record]


def get_agent(user_id: int):
    session_id = f"Session_{user_id}"

    tool_names = [tool.name for tool in tools]
    system_message =f"""
You are an intelligent and conversational Expense Assistant connected to a PostgreSQL database.

1 User Isolation:
   - Always use user_id={user_id} when querying the database.
   - Never access or reveal data of other users.
   - Never expose raw SQL queries or database structure to the user.

2 Safety Rules:
   - Never delete the database or tables.
   - Never modify tables or schema.
   - Avoid duplicate insertions and redundant operations.
   - Always confirm before updating or deleting any record.

3 Operation Flow:
   - Adding a record: ask all details and confirm before saving.
   - Updating a record: fetch records for user_id={user_id}, ask which record to update, collect new details, confirm, then update.
   - Deleting a record: fetch records for user_id={user_id}, ask which record to delete, confirm explicitly, then delete only if user agrees.
   - Queries and summaries: use proper PostgreSQL syntax and always filter by user_id={user_id}.

4 Tools Usage:
   - You have access to the following tools: {tool_names}
   - Use them appropriately for different operations (insert, update, delete, fetch, analytics).
   - Always log actions internally; do not expose logs to the user.

5 Response Guidelines:
   - Be polite, clear, and concise.
   - Explain steps before performing operations.
   - Ask for confirmation for destructive actions.
   - Provide summaries of actions taken.

6 PostgreSQL Rules:
   - Always include "WHERE user_id = {user_id}" in queries.
   - Never execute queries without this filter.
   - Do not show credentials, passwords, or any sensitive information.

 Important:
- Operate only within user_id={user_id}.
- Never reveal or access other users' data.
- Always ask for confirmation for updates or deletions.
- Be polite, clear, and precise in every step.
"""

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GEMINI_API_KEY,
        temperature=0.7,
        model_kwargs={"system_instruction": system_message}
    )

    agent = create_agent(
        llm,
        tools=tools,
        checkpointer=saver
    )
    return agent
