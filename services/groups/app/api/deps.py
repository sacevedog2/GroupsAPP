from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.grpc.client import validate_token_via_grpc
import logging

logger = logging.getLogger(__name__)

# Reusable security scheme for Swagger UI
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Dependency that validates the Bearer token using Auth Service via gRPC
    and returns the user_id.
    """
    token = credentials.credentials
    try:
        user_id = validate_token_via_grpc(token)
        return user_id
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
