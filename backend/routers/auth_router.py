"""Auth router – login and seed admin user."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import verify_password, hash_password, create_access_token
from database import get_db
from models import User
from schemas import TokenRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: TokenRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(data={"sub": user.username})
    return TokenResponse(access_token=token)


@router.post("/seed", status_code=201)
async def seed_admin(db: Session = Depends(get_db)):
    """Create a default admin user (only if none exists). Call once on first run."""
    existing = db.query(User).first()
    if existing:
        raise HTTPException(status_code=409, detail="Admin user already exists")
    user = User(
        username="admin",
        hashed_password=hash_password("admin123"),
        role="admin",
    )
    db.add(user)
    db.commit()
    return {"message": "Admin user created", "username": "admin", "password": "admin123"}
