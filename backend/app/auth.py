import hashlib
import hmac
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import get_settings, Settings


bearer_scheme = HTTPBearer()


def create_token(settings: Settings) -> str:
    """Create a simple HMAC-signed token based on the password."""
    message = f"cut-the-fat:{settings.app_password}"
    return hmac.new(
        settings.secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_token(token: str, settings: Settings) -> bool:
    expected = create_token(settings)
    return hmac.compare_digest(token, expected)


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    if not verify_token(credentials.credentials, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
