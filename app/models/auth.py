from pydantic import BaseModel, EmailStr, Field

class UserSignUpRequest(BaseModel):
    """What Sharan's Sign-up form must send to the API"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str

class UserLoginRequest(BaseModel):
    """What Sharan's Login form must send to the API"""
    email: EmailStr
    password: str