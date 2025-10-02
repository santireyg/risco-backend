# path: app/middleware/csrf.py

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException, status
from app.core.config import ENVIRONMENT


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Middleware “double-submit cookie”.
    • Métodos ‘safe’ (GET, HEAD, OPTIONS) ⇢ se omite.
    • Para POST/PUT/PATCH/DELETE:
        – Si la cookie 'csrf_token' AÚN NO EXISTE  → dejamos pasar (ej. /login, /register).
        – Si existe, debe coincidir con el header 'X-CSRF-Token'; si no, 403.
    """
    def __init__(
        self,
        app,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
    ):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):
        # Permitir todo en entorno de desarrollo
        if ENVIRONMENT == "dev":
            return await call_next(request)

        # 1️⃣  Métodos que no modifican estado → sin verificación
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)

        # 2️⃣  Leer cookie; si aún no existe, dejamos pasar (primer login / register)
        cookie_token = request.cookies.get(self.cookie_name)
        if cookie_token is None:
            return await call_next(request)

        # 3️⃣  Comparar con el header
        header_token = request.headers.get(self.header_name)
        if not header_token or cookie_token != header_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token mismatch",
            )

        # 4️⃣  Todo OK → continuar
        return await call_next(request)
