# app/utils/memory_cleanup.py

import ctypes
import gc
import logging
import platform
import os

logger = logging.getLogger(__name__)

# 🎯 Switch maestro - Solo logs si está habilitado el tracking
MEMORY_TRACKING_ENABLED = os.getenv("ADVANCED_MEMORY_TRACKING_ENABLED", "false").lower() == "true"

def try_malloc_trim():
    """
    Intenta liberar memoria con malloc_trim() si está disponible.
    
    Returns:
        bool: True si malloc_trim() se ejecutó exitosamente, False si no está disponible
    """
    try:
        system = platform.system()
        
        if system == "Linux":
            # Linux con glibc
            libc = ctypes.CDLL("libc.so.6")
            result = libc.malloc_trim(0)
            if MEMORY_TRACKING_ENABLED:
                logger.debug(f"malloc_trim() resultado: {result}")
            return True
            
        elif system == "Darwin":  # macOS
            # macOS no tiene malloc_trim, solo GC extra
            if MEMORY_TRACKING_ENABLED:
                logger.debug("macOS: usando solo gc.collect() adicional")
            gc.collect()
            return False
            
        else:
            # Windows u otros
            if MEMORY_TRACKING_ENABLED:
                logger.debug(f"Sistema {system}: malloc_trim no disponible")
            return False
            
    except Exception as e:
        if MEMORY_TRACKING_ENABLED:
            logger.debug(f"Error en malloc_trim: {e}")
        return False

def aggressive_memory_cleanup(stage_name: str = "unknown"):
    """
    Limpieza agresiva de memoria combinando GC múltiple + malloc_trim.
    Solo loggea si el tracking está habilitado.
    
    Args:
        stage_name: Nombre de la etapa para logging
    """
    # Múltiples rondas de garbage collection
    total_collected = 0
    for i in range(3):
        collected = gc.collect()
        total_collected += collected
        if MEMORY_TRACKING_ENABLED and collected > 0:
            logger.debug(f"GC ronda {i+1} en {stage_name}: {collected} objetos liberados")
    
    # Intentar malloc_trim
    trim_success = try_malloc_trim()
    
    # Solo loggear si tracking está habilitado
    if MEMORY_TRACKING_ENABLED:
        logger.info(f"Limpieza agresiva en {stage_name}: {total_collected} objetos GC, malloc_trim: {trim_success}")
    
    return trim_success
