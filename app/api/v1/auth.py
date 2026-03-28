import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status

from app.models.auth import UserSignUpRequest, UserLoginRequest
from app.models.internal import UserInternal
from app.core.security import hash_password, verify_password

router = APIRouter()

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def sign_up(user_data: UserSignUpRequest):
    """
    Register a new user by converting the Request to a secured Internal Model.
    """
    try:
        # 1. Create a secure hash of the password
        secure_password = hash_password(user_data.password)
        
        # 2. Map the request data to our Internal Model
        new_user = UserInternal(
            id=str(uuid.uuid4()),
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=secure_password,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        # 3. Return the success response
        return {
            "message": "User registered successfully",
            "user_id": new_user.id,
            "email": new_user.email,
            "created_at": new_user.created_at
        }
    except Exception as e:
        # If it crashes, this tells us WHY in the browser
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System Error: {str(e)}"
        )

@router.post("/login")
async def login(credentials: UserLoginRequest):
    """
    Simulate login by verifying a password.
    """
    # For testing: assume the 'stored' password is "password123"
    stored_hash = hash_password("password123")
    
    if verify_password(credentials.password, stored_hash):
        return {"access_token": "fake-jwt-token", "token_type": "bearer"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password"
    )