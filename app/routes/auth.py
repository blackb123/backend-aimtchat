# app/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.model import User
from app.schemas.auth_schemas import Signup, Login, Token

router = APIRouter()

# GET ALL USERS (for chat sidebar)
@router.get("/users")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "status": "online" if user.is_online else "offline"
        }
        for user in users
    ]

# REGISTER
@router.post("/register")
def register_user(data: Signup, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    existing_username = db.query(User).filter(User.username == data.username).first()
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already taken")


    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
   
    new_user = User(
        username=data.username,
        email=data.email,
        password=hash_password(data.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully"}



# LOGIN
@router.post("/login", response_model=Token)
def login(data: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Incorrect password")

    token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id" : user.id,
        "user_name" : user.username

    }
