from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_,or_
from langchain_core.messages import HumanMessage
from jose import JWTError,jwt
from database import get_db, User, Expenses, UserCreate,chat, AddExpense, ExpenseOut, Base, engine,update_expenses,Messages,Delete_Multiple,RegisterStep1,RegisterStep2
from authorization import hash_password, verify_password, create_access_token,secret_key,algorithm,generate_otp,send_otp_email,verify_otp
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
import os
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()
orging=["*"]

Base.metadata.create_all(bind=engine)

oauth_scheme = OAuth2PasswordBearer(tokenUrl="token")
app = FastAPI(title="Expense Tracker")


app.add_middleware(
    CORSMiddleware,
    allow_origins=orging,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user(token: str = Depends(oauth_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        user_id: int = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
    except JWTError:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return user.id

@app.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form.username   
    password = form.password

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/register")
def register_send_otp(data: RegisterStep1, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    otp = generate_otp(data.email)
    send_otp_email(data.email, otp)
    return {"message": f"OTP sent to {data.email}. It expires in 5 minutes."}


@app.post("/register/verify")
def verify_and_register(data: RegisterStep2, db: Session = Depends(get_db)):
    if not verify_otp(data.email, data.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
 
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already registered")
    
    new_user = User(email=data.email, password=hash_password(data.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "Registration complete!", "email": new_user.email}


@app.post("/addexpense", response_model=AddExpense)
def add_expense(expense: AddExpense, db: Session = Depends(get_db), userid: int = Depends(get_current_user)):
    record = Expenses(
        user_id=userid,
        category=expense.category,
        amount=expense.amount,
        amount_type=expense.amount_type,
        date=expense.date
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/getexpense", response_model=list[ExpenseOut])
def retriew_expense(userid: int = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Expenses).filter(Expenses.user_id == userid).all()

@app.post("/update_expense/{expense_id}",response_model=update_expenses)
def update_expense(data:update_expenses,expense_id:int,user_id:int=Depends(get_current_user),db:Session=Depends(get_db)):
    record=db.query(Expenses).filter(and_(Expenses.user_id==user_id,Expenses.id==expense_id)).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    update_data=data.dict(exclude_unset=True)
    for key,value in update_data.items():
        setattr(record,key,value)
    db.commit()
    db.refresh(record)
    return record
@app.delete("/delete_expense/{expense_id}")
def delete_expense(expense_id:int,user_id:int=Depends(get_current_user),db:Session=Depends(get_db)):
    record=db.query(Expenses).filter(and_(Expenses.user_id==user_id,Expenses.id==expense_id)).first()
    if not record:
        raise HTTPException(status_code=404,detail="Expense not found")
    db.delete(record)
    db.commit()
    return {"Message":"Expense Deleted "}

@app.delete("/multiple_items")
def delete_multiple_items(data:Delete_Multiple,user_id:int=Depends(get_current_user),db:Session=Depends(get_db)):
    deleted=db.query(Expenses).filter(Expenses.user_id==user_id,Expenses.id.in_(data.items)).delete(synchronize_session=False)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Record with Ids not found")
    db.commit()
    return "Successfully delete the Records"

    
@app.post("/chat")
async def Aichat(req: chat, user_id: int = Depends(get_current_user)):
    from agent import get_agent, build_prompt

    prompt = build_prompt(user_id, req.query)
    agent = get_agent(user_id)
    result = agent.invoke(
        {"messages": [HumanMessage(content=prompt)]},
        config={"configurable": {"thread_id": user_id}} # <--- thread_id GOES HERE
    )
    if isinstance(result, dict) and 'messages' in result:
    
        final_message = result['messages'][-1]
        if hasattr(final_message, 'content') and isinstance(final_message.content, str):
            return {"response": final_message.content}
        elif hasattr(final_message, 'content') and isinstance(final_message.content, list):
         
            if final_message.content and isinstance(final_message.content[0], dict) and 'text' in final_message.content[0]:
                return {"response": final_message.content[0]['text']}
        else:
            return {"response": str(final_message)}

    elif isinstance(result, dict) and "output" in result:
        return {"response": result["output"]}
        
    return {"response": f"An unknown error occurred. Raw output structure mismatch."}