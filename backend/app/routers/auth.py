from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..schemas.auth import LoginRequest, TokenResponse, VerifyResponse
from ..auth import create_token, verify_token
from ..config import get_settings, Settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    if request.password != settings.app_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )
    token = create_token(settings)
    return TokenResponse(token=token)


@router.get("/verify", response_model=VerifyResponse)
async def verify(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> VerifyResponse:
    if not credentials or not verify_token(credentials.credentials, settings):
        return VerifyResponse(valid=False)
    return VerifyResponse(valid=True)
