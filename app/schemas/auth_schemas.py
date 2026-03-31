from pydantic import BaseModel,EmailStr,Field

class Login(BaseModel):
    username :str
    password :str

class Signup(BaseModel):
    username:str
    email:EmailStr
    password: str = Field(..., min_length=6, max_length=72)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id:int
    user_name:str