from fastapi import APIRouter, HTTPException, status
from app.models.auth import UserSignUpRequest, UserLoginRequest

# This creates a router we can plug into the main application
router = APIRouter()

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def sign_up(user_data: UserSignUpRequest):
    """Register a new user."""
    # TODO: Add database connection to save the user securely
    return {
        "message": f"User {user_data.full_name} successfully created!", 
        "email": user_data.email
    }

@router.post("/login")
async def login(credentials: UserLoginRequest):
    """Authenticate a user and return a token."""
    # TODO: Add database check to verify password and generate a real token
    
    # Fake check just so if we  can test the connection
    if credentials.password == "password123":
        return {"access_token": "fake-jwt-token-for-now", "token_type": "bearer"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password"
    )