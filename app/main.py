# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.csrf import CSRFMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from app.core.limiter import limiter

# Importar routers de la carpeta de endpoints
from app.api.endpoints import auth, processing, crud, websocket, user_registration, user_management, export

# Importar el inicializador del worker de la cola de tareas
from app.services.task_queue import start_graph_worker_loop

# Importar el tracker avanzado de memoria
from app.utils.advanced_memory_tracker import advanced_memory_tracker, cleanup_advanced_memory_tracker
from app.utils.log_filters import setup_logging_filters
import logging
import atexit

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar filtros de logging personalizados
setup_logging_filters()

app = FastAPI(
    title="API Integrity AI Caución",
    description="API para el proyecto Integrity - AI Caución",
    version="1.0.0"
)

# Configuración de CORS
origins = [
    "http://localhost:3000",
    "https://integrity-frontend-lime.vercel.app",
    "https://risco-frontend.vercel.app"
    "https://integrity-staging.genovasolutions.com",
    "https://integrity.genovasolutions.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSRF (se ejecuta *después* de CORS, porque se añade antes)
# —esto garantiza que la cookie y los encabezados ya estén disponibles.
app.add_middleware(CSRFMiddleware)

# Middleware de logging personalizado
app.add_middleware(LoggingMiddleware)

# Configuración de SlowAPI
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Intenta nuevamente en unos segundos."},
    )

# Incluir los routers de los endpoints
app.include_router(auth.router, tags=["auth"])
app.include_router(user_registration.router, prefix="/user-registration", tags=["user-registration"])
app.include_router(user_management.router, prefix="/admin", tags=["user-management"])
app.include_router(processing.router, tags=["processing"])
app.include_router(crud.router, tags=["CRUD"])
app.include_router(websocket.router, tags=["Websocket"])
app.include_router(export.router, tags=["export"])

# Inicializar el worker al iniciar la aplicación
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Iniciando aplicación Integrity AI...")
    
    # Inicializar el advanced memory tracker
    if advanced_memory_tracker.enabled:
        logger.info("🔍 Advanced Memory Tracker habilitado")
    else:
        logger.info("🔍 Advanced Memory Tracker deshabilitado")
    
    # Inicializar worker de procesamiento LangGraph
    start_graph_worker_loop()     # Worker LangGraph unificado
    
    logger.info("✅ Aplicación iniciada correctamente")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Deteniendo aplicación...")
    
    # Limpiar el tracker de memoria
    cleanup_advanced_memory_tracker()
    
    logger.info("✅ Aplicación detenida correctamente")

# Registrar limpieza al salir del proceso
atexit.register(cleanup_advanced_memory_tracker)

if __name__ == "__main__":
    import uvicorn
    # Deshabilitar access log de uvicorn ya que usamos nuestro middleware personalizado
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True, 
        access_log=False  # Deshabilitamos el access log automático
    )
