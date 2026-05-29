"""鉴权中间件（简易 JWT 实现）"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.config import Settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def create_access_token(settings: Settings, username: str = "admin") -> str:
    """创建 JWT token"""
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode = {"sub": username, "exp": expire}
    return jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> bool:
    """验证 JWT token（可选鉴权，通过配置控制）"""
    settings = request.app.state.settings

    # 开发环境跳过鉴权
    if settings.environment == "development":
        return True

    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证信息")

    try:
        jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return True
    except JWTError:
        raise HTTPException(status_code=401, detail="认证信息无效或已过期")
