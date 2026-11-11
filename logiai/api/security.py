from fastapi import Header, HTTPException, Depends
from logiai import config
import secrets


def _egal(a, b):
    return secrets.compare_digest(a, b)


def verify_api_key(x_api_key: str | None = Header(default=None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key missing")

    if config.ADMIN_KEY and _egal(x_api_key, config.ADMIN_KEY):
        return "admin"

    if config.API_KEY and _egal(x_api_key, config.API_KEY):
        return "user"

    raise HTTPException(status_code=401, detail="Invalid API key")


def require_admin(role: str = Depends(verify_api_key)):
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return role