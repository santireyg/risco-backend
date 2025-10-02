# app/utils/log_filters.py

import logging
import re
from typing import List, Pattern


class ExcludeLoggerFilter(logging.Filter):
    """Filtro para excluir logs de loggers específicos"""
    
    def __init__(self, excluded_loggers: List[str]):
        super().__init__()
        self.excluded_loggers = excluded_loggers
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Retorna False para excluir el log
        return record.name not in self.excluded_loggers


class ExcludePatternFilter(logging.Filter):
    """Filtro para excluir logs que coincidan con patrones específicos"""
    
    def __init__(self, excluded_patterns: List[str]):
        super().__init__()
        self.excluded_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in excluded_patterns]
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Retorna False para excluir el log
        message = record.getMessage()
        for pattern in self.excluded_patterns:
            if pattern.search(message):
                return False
        return True


class HTTPLoggingFilter(logging.Filter):
    """Filtro específico para logs HTTP de uvicorn"""
    
    def __init__(self):
        super().__init__()
        # Patrones de URLs que queremos excluir
        self.excluded_paths = [
            r'/me\b',
            r'/documents\?',  # GET /documents con query params
            r'/documents$',   # GET /documents sin query params
            r'/ws/',          # WebSocket paths
            r'/websocket',    # WebSocket paths
        ]
        self.excluded_patterns = [re.compile(pattern) for pattern in self.excluded_paths]
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Solo filtrar logs de uvicorn.access
        if record.name != "uvicorn.access":
            return True
            
        message = record.getMessage()
        
        # Excluir peticiones específicas
        for pattern in self.excluded_patterns:
            if pattern.search(message):
                return False
                
        return True


def setup_logging_filters():
    """Configura todos los filtros de logging necesarios"""
    
    # Obtener el logger raíz
    root_logger = logging.getLogger()
    
    # Filtro para excluir loggers específicos
    logger_filter = ExcludeLoggerFilter([
        "httpx",  # Logs de requests HTTP externos (OpenAI, etc.)
        "openai", 
        "urllib3",
    ])
    
    # Filtro para excluir patrones específicos en mensajes
    pattern_filter = ExcludePatternFilter([
        r"HTTP Request: POST https://api\.openai\.com",
        r"Procesando lote de páginas \d+-\d+ para docfile",
        r"INFO:httpx:",
        r"INFO:openai:",
    ])
    
    # Filtro específico para logs HTTP
    http_filter = HTTPLoggingFilter()
    
    # Aplicar filtros a todos los handlers del logger raíz
    for handler in root_logger.handlers:
        handler.addFilter(logger_filter)
        handler.addFilter(pattern_filter)
        handler.addFilter(http_filter)
    
    # También aplicar a uvicorn.access específicamente
    uvicorn_logger = logging.getLogger("uvicorn.access")
    for handler in uvicorn_logger.handlers:
        handler.addFilter(http_filter)
