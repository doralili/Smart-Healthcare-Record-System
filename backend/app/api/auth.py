from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.core.timezone import now_beijing
from app.db.session import get_db
from app.models.patient import Patient
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.audit_service import request_audit_context, write_audit_log


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    username = payload.username.strip()
    full_name = payload.full_name.strip()

    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is required",
        )

    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name is required",
        )

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    user = User(
        username=username,
        password_hash=password_hash,
        role="PATIENT",
        status="ACTIVE",
        created_at=now_beijing(),
    )

    try:
        db.add(user)
        db.flush()

        patient = Patient(
            user_id=user.id,
            synthea_patient_id=f"SELF-{uuid4().hex}",
            full_name=full_name,
            gender=payload.gender,
            birth_date=payload.birth_date,
            phone=payload.phone,
            address=payload.address,
            created_at=now_beijing(),
        )
        db.add(patient)
        db.flush()

        write_audit_log(
            db,
            action="PATIENT_REGISTER",
            actor=user,
            target_type="user",
            target_id=user.id,
            patient_id=patient.id,
            outcome="SUCCESS",
            detail="Patient self-registration with profile creation",
            **request_audit_context(request),
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or patient profile already exists",
        ) from exc

    db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        status=user.status,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    db.execute(
        text(
            "UPDATE users "
            "SET last_login_at = CURRENT_TIMESTAMP "
            "WHERE id = :user_id"
        ),
        {"user_id": user.id},
    )
    write_audit_log(
        db,
        action="LOGIN",
        actor=user,
        target_type="user",
        target_id=user.id,
        outcome="SUCCESS",
        detail="User signed in",
        **request_audit_context(request),
    )
    db.commit()

    access_token = create_access_token(subject=str(user.id), role=user.role)

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            status=user.status,
        ),
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status=current_user.status,
    )
