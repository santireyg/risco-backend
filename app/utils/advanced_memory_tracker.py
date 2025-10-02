# app/utils/advanced_memory_tracker.py

import tracemalloc
import gc
import os
import sys
import asyncio
import functools
import threading
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import psutil
import weakref

# 🎯 SWITCH MAESTRO - Solo activo si la variable existe y es true
ADVANCED_MEMORY_TRACKING_ENABLED = os.getenv("ADVANCED_MEMORY_TRACKING_ENABLED", "false").lower() == "true"

# Configuración (solo si está habilitado)
MEMORY_SNAPSHOT_INTERVAL = int(os.getenv("MEMORY_SNAPSHOT_INTERVAL", "30")) if ADVANCED_MEMORY_TRACKING_ENABLED else 0
ZOMBIE_MEMORY_THRESHOLD_MB = int(os.getenv("ZOMBIE_MEMORY_THRESHOLD_MB", "10")) if ADVANCED_MEMORY_TRACKING_ENABLED else 0
LEAK_DETECTION_THRESHOLD_MB = int(os.getenv("LEAK_DETECTION_THRESHOLD_MB", "50")) if ADVANCED_MEMORY_TRACKING_ENABLED else 0
TOP_MEMORY_ALLOCATIONS = int(os.getenv("TOP_MEMORY_ALLOCATIONS", "20")) if ADVANCED_MEMORY_TRACKING_ENABLED else 0

logger = logging.getLogger(__name__)

@dataclass
class MemorySnapshot:
    """Instantánea de memoria en un punto específico del tiempo"""
    timestamp: datetime
    stage: str
    docfile_id: Optional[str]
    filename: Optional[str]
    tracemalloc_snapshot: Any  # tracemalloc.Snapshot
    rss_memory_mb: float
    heap_memory_mb: float
    gc_stats: Dict[int, int]
    top_allocations: List[Tuple[str, float]]  # (traceback, size_mb)

@dataclass
class ProcessMemoryReport:
    """Reporte completo de memoria para un proceso de documento"""
    docfile_id: str
    filename: str
    start_time: datetime
    end_time: Optional[datetime] = None
    snapshots: List[MemorySnapshot] = field(default_factory=list)
    memory_leaks: List[Dict[str, Any]] = field(default_factory=list)
    zombie_memory: List[Dict[str, Any]] = field(default_factory=list)
    peak_memory_mb: float = 0.0
    total_memory_growth_mb: float = 0.0
    
class AdvancedMemoryTracker:
    """
    Tracker avanzado de memoria que utiliza tracemalloc para detectar:
    - Memory leaks detallados con stack traces
    - Memoria zombie que permanece después del procesamiento
    - Análisis de patrones de asignación de memoria
    - Reportes comprensivos por documento procesado
    """
    
    def __init__(self):
        self.enabled = ADVANCED_MEMORY_TRACKING_ENABLED
        self.active_processes: Dict[str, ProcessMemoryReport] = {}
        self.completed_processes: List[ProcessMemoryReport] = []
        self.baseline_snapshot: Optional[MemorySnapshot] = None
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        self._lock = threading.Lock()
        
        if self.enabled:
            self._initialize_tracemalloc()
            self._start_background_monitoring()
    
    def _initialize_tracemalloc(self):
        """Inicializa tracemalloc si no está ya iniciado"""
        if not self.enabled:
            return
            
        if not tracemalloc.is_tracing():
            # Configurar tracemalloc para capturar hasta 25 frames en el stack trace
            tracemalloc.start(25)
            logger.info("[ADVANCED_MEMORY] Tracemalloc iniciado")
            
            # Tomar snapshot baseline después de la inicialización
            self.baseline_snapshot = self._take_memory_snapshot("baseline", None, None)
    
    def _start_background_monitoring(self):
        """Inicia el monitoreo en background"""
        if not self.enabled:
            return
            
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(
                target=self._background_monitor, 
                daemon=True,
                name="AdvancedMemoryMonitor"
            )
            self.monitoring_thread.start()
            logger.info("[ADVANCED_MEMORY] Monitoreo en background iniciado")
    
    def _background_monitor(self):
        """Función que se ejecuta en background para monitorear memoria"""
        if not self.enabled:
            return
            
        while not self.stop_monitoring.wait(MEMORY_SNAPSHOT_INTERVAL):
            try:
                with self._lock:
                    # Detectar memoria zombie global
                    self._detect_zombie_memory()
                    
                    # Tomar snapshots de procesos activos
                    for process_id, report in self.active_processes.items():
                        snapshot = self._take_memory_snapshot(
                            f"background_{process_id}", 
                            report.docfile_id, 
                            report.filename
                        )
                        report.snapshots.append(snapshot)
                        
                        # Actualizar memoria pico
                        if snapshot.rss_memory_mb > report.peak_memory_mb:
                            report.peak_memory_mb = snapshot.rss_memory_mb
                            
            except Exception as e:
                logger.error(f"[ADVANCED_MEMORY] Error en monitoreo background: {e}")
    
    def _take_memory_snapshot(self, stage: str, docfile_id: Optional[str], filename: Optional[str]) -> MemorySnapshot:
        """Toma una instantánea completa de memoria"""
        if not self.enabled:
            return None
            
        try:
            # Forzar garbage collection para datos más precisos
            gc.collect()
            
            # Obtener snapshot de tracemalloc
            tm_snapshot = tracemalloc.take_snapshot()
            
            # Obtener memoria RSS del proceso
            process = psutil.Process()
            rss_memory_mb = process.memory_info().rss / (1024 * 1024)
            
            # Obtener estadísticas de heap (suma de todas las asignaciones rastreadas)
            heap_memory_mb = sum(stat.size for stat in tm_snapshot.statistics('filename')) / (1024 * 1024)
            
            # Obtener estadísticas de garbage collector
            gc_stats = {i: len(gc.get_objects(i)) for i in range(3)}
            
            # Obtener top allocations
            top_stats = tm_snapshot.statistics('traceback')[:TOP_MEMORY_ALLOCATIONS]
            top_allocations = []
            
            for stat in top_stats:
                size_mb = stat.size / (1024 * 1024)
                # Formatear el traceback para logging
                traceback_str = '\n'.join(stat.traceback.format())
                top_allocations.append((traceback_str, size_mb))
            
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                stage=stage,
                docfile_id=docfile_id,
                filename=filename,
                tracemalloc_snapshot=tm_snapshot,
                rss_memory_mb=rss_memory_mb,
                heap_memory_mb=heap_memory_mb,
                gc_stats=gc_stats,
                top_allocations=top_allocations
            )
            
            logger.info(f"[ADVANCED_MEMORY] Snapshot tomado - Stage: {stage} - "
                       f"RSS: {rss_memory_mb:.2f}MB - Heap: {heap_memory_mb:.2f}MB - "
                       f"DocID: {docfile_id or 'N/A'} - File: {filename or 'N/A'}")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"[ADVANCED_MEMORY] Error tomando snapshot: {e}")
            # Retornar snapshot básico en caso de error
            return MemorySnapshot(
                timestamp=datetime.now(),
                stage=stage,
                docfile_id=docfile_id,
                filename=filename,
                tracemalloc_snapshot=None,
                rss_memory_mb=0.0,
                heap_memory_mb=0.0,
                gc_stats={},
                top_allocations=[]
            )
    
    def _detect_zombie_memory(self):
        """Detecta memoria zombie comparando con baseline"""
        if not self.baseline_snapshot or not self.baseline_snapshot.tracemalloc_snapshot:
            return
        
        try:
            current_snapshot = tracemalloc.take_snapshot()
            
            # Comparar con baseline para encontrar memoria persistente
            top_stats = current_snapshot.compare_to(
                self.baseline_snapshot.tracemalloc_snapshot, 
                'traceback'
            )
            
            zombie_allocations = []
            for stat in top_stats[:10]:  # Top 10 diferencias
                if stat.size_diff > ZOMBIE_MEMORY_THRESHOLD_MB * 1024 * 1024:  # Convertir a bytes
                    zombie_info = {
                        'size_diff_mb': stat.size_diff / (1024 * 1024),
                        'count_diff': stat.count_diff,
                        'traceback': '\n'.join(stat.traceback.format()),
                        'detected_at': datetime.now()
                    }
                    zombie_allocations.append(zombie_info)
            
            if zombie_allocations:
                logger.warning(f"[ADVANCED_MEMORY] MEMORIA ZOMBIE DETECTADA - {len(zombie_allocations)} allocations persistentes")
                for zombie in zombie_allocations:
                    logger.warning(f"[ZOMBIE] {zombie['size_diff_mb']:.2f}MB - Count: {zombie['count_diff']}")
                    logger.debug(f"[ZOMBIE] Traceback:\n{zombie['traceback']}")
                    
        except Exception as e:
            logger.error(f"[ADVANCED_MEMORY] Error detectando memoria zombie: {e}")
    
    def start_process_tracking(self, docfile_id: str, filename: str, stage: str) -> str:
        """Inicia el tracking de un proceso específico"""
        if not self.enabled:
            return ""
        
        process_id = f"{docfile_id}_{int(time.time())}"
        
        with self._lock:
            # Crear reporte para este proceso
            report = ProcessMemoryReport(
                docfile_id=docfile_id,
                filename=filename,
                start_time=datetime.now()
            )
            
            # Tomar snapshot inicial
            initial_snapshot = self._take_memory_snapshot(f"start_{stage}", docfile_id, filename)
            report.snapshots.append(initial_snapshot)
            
            self.active_processes[process_id] = report
        
        logger.info(f"[ADVANCED_MEMORY] Iniciando tracking - ProcessID: {process_id} - "
                   f"DocID: {docfile_id} - File: {filename} - Stage: {stage}")
        
        return process_id
    
    def add_stage_snapshot(self, process_id: str, stage: str):
        """Añade un snapshot para una etapa específica"""
        if not self.enabled or not process_id:
            return
        
        with self._lock:
            if process_id in self.active_processes:
                report = self.active_processes[process_id]
                snapshot = self._take_memory_snapshot(stage, report.docfile_id, report.filename)
                report.snapshots.append(snapshot)
    
    def end_process_tracking(self, process_id: str, stage: str = "end") -> Optional[ProcessMemoryReport]:
        """Finaliza el tracking y genera reporte"""
        if not self.enabled or not process_id:
            return None
        
        with self._lock:
            if process_id not in self.active_processes:
                return None
            
            report = self.active_processes[process_id]
            report.end_time = datetime.now()
            
            # Tomar snapshot final
            final_snapshot = self._take_memory_snapshot(f"end_{stage}", report.docfile_id, report.filename)
            report.snapshots.append(final_snapshot)
            
            # Calcular crecimiento total de memoria
            if report.snapshots:
                initial_memory = report.snapshots[0].rss_memory_mb
                final_memory = final_snapshot.rss_memory_mb
                report.total_memory_growth_mb = final_memory - initial_memory
            
            # Detectar leaks en este proceso
            self._analyze_process_leaks(report)
            
            # Mover a procesos completados
            del self.active_processes[process_id]
            self.completed_processes.append(report)
            
            # Mantener solo los últimos 50 reportes para evitar acumulación
            if len(self.completed_processes) > 50:
                self.completed_processes = self.completed_processes[-50:]
        
        self._log_process_summary(report)
        return report
    
    def _analyze_process_leaks(self, report: ProcessMemoryReport):
        """Analiza leaks específicos del proceso"""
        if len(report.snapshots) < 2:
            return
        
        initial_snapshot = report.snapshots[0]
        final_snapshot = report.snapshots[-1]
        
        # Leak por crecimiento total
        if report.total_memory_growth_mb > LEAK_DETECTION_THRESHOLD_MB:
            leak_info = {
                'type': 'total_growth',
                'growth_mb': report.total_memory_growth_mb,
                'initial_memory_mb': initial_snapshot.rss_memory_mb,
                'final_memory_mb': final_snapshot.rss_memory_mb,
                'detected_at': datetime.now()
            }
            report.memory_leaks.append(leak_info)
        
        # Análisis detallado con tracemalloc si está disponible
        if (initial_snapshot.tracemalloc_snapshot and 
            final_snapshot.tracemalloc_snapshot):
            
            try:
                top_stats = final_snapshot.tracemalloc_snapshot.compare_to(
                    initial_snapshot.tracemalloc_snapshot, 
                    'traceback'
                )
                
                for stat in top_stats[:5]:  # Top 5 diferencias
                    size_diff_mb = stat.size_diff / (1024 * 1024)
                    if size_diff_mb > 10:  # Más de 10MB de diferencia
                        leak_info = {
                            'type': 'tracemalloc_diff',
                            'size_diff_mb': size_diff_mb,
                            'count_diff': stat.count_diff,
                            'traceback': '\n'.join(stat.traceback.format()),
                            'detected_at': datetime.now()
                        }
                        report.memory_leaks.append(leak_info)
                        
            except Exception as e:
                logger.error(f"[ADVANCED_MEMORY] Error analizando leaks con tracemalloc: {e}")
    
    def _log_process_summary(self, report: ProcessMemoryReport):
        """Registra un resumen del proceso completado"""
        duration = (report.end_time - report.start_time).total_seconds()
        
        logger.info(f"[ADVANCED_MEMORY] RESUMEN PROCESO COMPLETADO")
        logger.info(f"  DocID: {report.docfile_id}")
        logger.info(f"  Archivo: {report.filename}")
        logger.info(f"  Duración: {duration:.2f}s")
        logger.info(f"  Snapshots tomados: {len(report.snapshots)}")
        logger.info(f"  Memoria pico: {report.peak_memory_mb:.2f}MB")
        logger.info(f"  Crecimiento total: {report.total_memory_growth_mb:+.2f}MB")
        
        if report.memory_leaks:
            logger.warning(f"  LEAKS DETECTADOS: {len(report.memory_leaks)}")
            for i, leak in enumerate(report.memory_leaks):
                logger.warning(f"    Leak {i+1}: {leak['type']} - "
                             f"{leak.get('growth_mb', leak.get('size_diff_mb', 0)):.2f}MB")
        
        if report.zombie_memory:
            logger.warning(f"  MEMORIA ZOMBIE: {len(report.zombie_memory)} instancias")
    
    def get_memory_report(self) -> Dict[str, Any]:
        """Obtiene un reporte completo del estado de memoria"""
        if not self.enabled:
            return {"enabled": False}
        
        with self._lock:
            # Estadísticas generales
            current_process = psutil.Process()
            current_memory = current_process.memory_info().rss / (1024 * 1024)
            
            # Estadísticas de tracemalloc
            tm_current, tm_peak = tracemalloc.get_traced_memory()
            tm_current_mb = tm_current / (1024 * 1024)
            tm_peak_mb = tm_peak / (1024 * 1024)
            
            report = {
                "enabled": True,
                "current_memory_mb": current_memory,
                "tracemalloc_current_mb": tm_current_mb,
                "tracemalloc_peak_mb": tm_peak_mb,
                "active_processes": len(self.active_processes),
                "completed_processes": len(self.completed_processes),
                "total_leaks_detected": sum(len(p.memory_leaks) for p in self.completed_processes),
                "baseline_memory_mb": self.baseline_snapshot.rss_memory_mb if self.baseline_snapshot else 0,
                "processes": []
            }
            
            # Añadir información de procesos recientes
            for process_report in self.completed_processes[-10:]:  # Últimos 10
                process_info = {
                    "docfile_id": process_report.docfile_id,
                    "filename": process_report.filename,
                    "duration_seconds": (process_report.end_time - process_report.start_time).total_seconds(),
                    "peak_memory_mb": process_report.peak_memory_mb,
                    "memory_growth_mb": process_report.total_memory_growth_mb,
                    "leaks_count": len(process_report.memory_leaks),
                    "snapshots_count": len(process_report.snapshots)
                }
                report["processes"].append(process_info)
            
            return report
    
    def cleanup(self):
        """Limpia recursos y detiene el tracking"""
        if not self.enabled:
            return
            
        logger.info("[ADVANCED_MEMORY] Limpiando tracker avanzado...")
        
        # Detener monitoreo background
        self.stop_monitoring.set()
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        # Detener tracemalloc
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        
        # Limpiar estructuras de datos
        with self._lock:
            self.active_processes.clear()
            self.completed_processes.clear()
            self.baseline_snapshot = None
        
        logger.info("[ADVANCED_MEMORY] Tracker limpiado y detenido")

# Instancia global del tracker
advanced_memory_tracker = AdvancedMemoryTracker()

def advanced_memory_monitor(stage_name: str):
    """
    Decorador avanzado para monitorear memoria con tracemalloc.
    Reemplaza al decorador memory_monitor existente.
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not advanced_memory_tracker.enabled:
                return await func(*args, **kwargs)
            
            # Extraer contexto
            docfile_id = None
            filename = None
            
            # Buscar docfile_id
            if args:
                for arg in args:
                    if isinstance(arg, str) and len(arg) == 24:
                        docfile_id = arg
                        break
            if 'docfile_id' in kwargs:
                docfile_id = kwargs['docfile_id']
            
            # Buscar filename
            if 'filename' in kwargs:
                filename = kwargs['filename']
            elif len(args) >= 2 and isinstance(args[1], str) and '.' in args[1]:
                filename = args[1]
            
            # Iniciar tracking
            process_id = advanced_memory_tracker.start_process_tracking(
                docfile_id or "unknown", 
                filename or "unknown", 
                stage_name
            )
            
            try:
                # Snapshot antes de ejecutar
                advanced_memory_tracker.add_stage_snapshot(process_id, f"before_{stage_name}")
                
                # Ejecutar función
                result = await func(*args, **kwargs)
                
                # Snapshot después de ejecutar
                advanced_memory_tracker.add_stage_snapshot(process_id, f"after_{stage_name}")
                
                return result
                
            except Exception as e:
                # Snapshot en caso de error
                advanced_memory_tracker.add_stage_snapshot(process_id, f"error_{stage_name}")
                raise
            finally:
                # Finalizar tracking
                advanced_memory_tracker.end_process_tracking(process_id, stage_name)
                
                # Forzar limpieza de memoria
                gc.collect()
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not advanced_memory_tracker.enabled:
                return func(*args, **kwargs)
            
            # Extraer contexto (similar al async)
            docfile_id = None
            filename = None
            
            if args:
                for arg in args:
                    if isinstance(arg, str) and len(arg) == 24:
                        docfile_id = arg
                        break
            if 'docfile_id' in kwargs:
                docfile_id = kwargs['docfile_id']
            
            if 'filename' in kwargs:
                filename = kwargs['filename']
            elif len(args) >= 2 and isinstance(args[1], str) and '.' in args[1]:
                filename = args[1]
            
            process_id = advanced_memory_tracker.start_process_tracking(
                docfile_id or "unknown", 
                filename or "unknown", 
                stage_name
            )
            
            try:
                advanced_memory_tracker.add_stage_snapshot(process_id, f"before_{stage_name}")
                result = func(*args, **kwargs)
                advanced_memory_tracker.add_stage_snapshot(process_id, f"after_{stage_name}")
                return result
            except Exception as e:
                advanced_memory_tracker.add_stage_snapshot(process_id, f"error_{stage_name}")
                raise
            finally:
                advanced_memory_tracker.end_process_tracking(process_id, stage_name)
                gc.collect()
        
        # Detectar si es función async
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def get_advanced_memory_report() -> Dict[str, Any]:
    """Función utilitaria para obtener reporte de memoria"""
    return advanced_memory_tracker.get_memory_report()

def cleanup_advanced_memory_tracker():
    """Función para limpiar el tracker al finalizar la aplicación"""
    advanced_memory_tracker.cleanup()
