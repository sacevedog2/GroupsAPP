import grpc
import logging
from app.grpc.proto import auth_pb2, auth_pb2_grpc
from app.core.config import settings

logger = logging.getLogger(__name__)

def validate_token_via_grpc(token: str) -> str:
    """
    Calls the auth-service via gRPC to validate a JWT token.
    Returns the user_id if valid, raises exception if invalid.
    """
    try:
        # We use insecure channel for internal microservices communication
        with grpc.insecure_channel(settings.AUTH_GRPC_URL) as channel:
            stub = auth_pb2_grpc.AuthInternalStub(channel)
            request = auth_pb2.TokenValidationRequest(access_token=token)
            response = stub.ValidateToken(request, timeout=2.0)
            
            if not response.valid:
                logger.warning(f"Invalid token: {response.reason}")
                raise ValueError(response.reason)
                
            return response.user_id
    except grpc.RpcError as e:
        logger.error(f"gRPC call to Auth service failed: {e}")
        raise ValueError("Auth service unavailable")
