import time
import threading
import logging
from uuid import UUID
from typing import Any, Dict, List, Optional, Union, cast
from bson import ObjectId

from langchain_core.callbacks.base import BaseCallbackHandler
from app.core.database import docs_collection
from app.models.docs_processing_time import ProcessingTime

logger = logging.getLogger(__name__)

class TimingCallbackHandler(BaseCallbackHandler):
    def __init__(self, stage_name: str) -> None:
        """
        Inicializa el TimingCallbackHandler.
        
        Args:
            stage_name: Nombre de la etapa ('upload_convert', 'recognize', 'extract', 'validation')
        """
        super().__init__()
        self.stage_name = stage_name
        self.run_times: Dict[UUID, float] = {}
        self.run_names: Dict[UUID, str] = {}
        self.docfile_ids: Dict[UUID, str] = {}
        self.user_ids: Dict[UUID, str] = {}
        self.target_run_id: Optional[UUID] = None

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Se ejecuta cuando un runnable (chain) comienza."""
        # Si el target_run_id no está definido, este es el PRIMER run que queremos monitorear
        # (independientemente de si tiene parent o no)
        if self.target_run_id is None:
            self.target_run_id = run_id
            
            # El 'run_name' de RunnableConfig(run_name="...") suele estar en kwargs['name']
            name_to_log = kwargs.get("name")
            if not name_to_log: # Fallback al nombre en el objeto serializado
                name_to_log = serialized.get("name")
            if not name_to_log and serialized.get("id"): # Fallback al path de la clase
                name_to_log = ".".join(cast(List[str], serialized.get("id", ["Unknown"])[-2:]))
            if not name_to_log:
                name_to_log = f"Unnamed Runnable ({run_id})"

            # Extraer docfile_id de los inputs
            docfile_id = "N/A"
            if isinstance(inputs, dict) and "docfile_id" in inputs:
                docfile_id = inputs["docfile_id"]

            # Extraer user_id de los inputs
            user_id = "N/A"
            if isinstance(inputs, dict) and "current_user" in inputs:
                current_user = inputs["current_user"]
                if isinstance(current_user, dict) and "id" in current_user:
                    user_id = current_user["id"]

            self.run_times[run_id] = time.perf_counter()
            self.run_names[run_id] = name_to_log
            self.docfile_ids[run_id] = docfile_id
            self.user_ids[run_id] = user_id

    def on_chain_end(
        self,
        outputs: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Se ejecuta cuando un runnable (chain) finaliza exitosamente."""
        # Solo procesar el run objetivo
        if run_id == self.target_run_id and run_id in self.run_times:
            end_time = time.perf_counter()
            start_time = self.run_times.pop(run_id)
            duration = end_time - start_time
            name_to_log = self.run_names.pop(run_id, f"Runnable {run_id}")
            docfile_id = self.docfile_ids.pop(run_id, "N/A")
            user_id = self.user_ids.pop(run_id, "N/A")
            
            # Guardar el tiempo en la base de datos y enviar notificación WebSocket
            if docfile_id != "N/A":
                self._schedule_update_processing_time_sync(docfile_id, duration, user_id)
            
            # Resetear el target_run_id para futuras ejecuciones
            self.target_run_id = None

    def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Se ejecuta cuando un runnable (chain) falla."""
        # Solo procesar el run objetivo
        if run_id == self.target_run_id:
            if run_id in self.run_times:
                end_time = time.perf_counter()
                start_time = self.run_times.pop(run_id)
                duration = end_time - start_time
                name_to_log = self.run_names.pop(run_id, f"Runnable {run_id}")
                docfile_id = self.docfile_ids.pop(run_id, "N/A")
                user_id = self.user_ids.pop(run_id, "N/A")
                logger.error(f"Error en: '{name_to_log}' | Documento: {docfile_id} | User: {user_id} | Tiempo: {duration:.4f}s | Error: {error}")
                
                # Aunque haya error, guardamos el tiempo parcial
                if docfile_id != "N/A":
                    self._schedule_update_processing_time_sync(docfile_id, duration, user_id)
            else:
                name_to_log = self.run_names.pop(run_id, f"Runnable {run_id}")
                docfile_id = self.docfile_ids.pop(run_id, "N/A")
                user_id = self.user_ids.pop(run_id, "N/A")
                logger.error(f"Error en: '{name_to_log}' | Documento: {docfile_id} | User: {user_id} | Error: {error} (Sin tiempo registrado)")
            
            # Resetear el target_run_id para futuras ejecuciones
            self.target_run_id = None

    async def _update_processing_time(self, docfile_id: str, duration: float, user_id: str = "N/A") -> None:
        """Actualiza el tiempo de procesamiento en la base de datos y envía notificación WebSocket."""
        client = None
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            from app.core.config import MONGO_URI, MONGO_DB
            from app.utils.status_notifier import update_status
            
            # Crear una nueva conexión para este event loop
            client = AsyncIOMotorClient(MONGO_URI)
            db = client[MONGO_DB]
            collection = db.documents
            
            object_id = ObjectId(docfile_id)
            
            # Obtener el documento actual
            document = await collection.find_one({"_id": object_id})
            if not document:
                logger.error(f"Documento {docfile_id} no encontrado para actualizar timing")
                return
            
            # Obtener o crear processing_time
            processing_time_data = document.get("processing_time", {})
            processing_time = ProcessingTime(**processing_time_data) if processing_time_data else ProcessingTime()
            
            # Actualizar el tiempo de la etapa específica
            setattr(processing_time, self.stage_name, duration)
            
            # Calcular y actualizar el tiempo total
            processing_time.update_total()
            
            # Actualizar en la base de datos
            result = await collection.update_one(
                {"_id": object_id},
                {"$set": {"processing_time": processing_time.model_dump()}}
            )
            
            if result.modified_count > 0:
                # Enviar notificación WebSocket con la información de processing_time actualizada
                if user_id != "N/A":
                    try:
                        await update_status(
                            collection=collection,
                            docfile_id=docfile_id,
                            new_status=document.get("status", "Procesando"),  # Mantener el estado actual
                            user_id=user_id,
                            processing_time=processing_time.model_dump(),
                            update_db=False  # Ya actualizamos la BD arriba, no necesitamos hacerlo de nuevo
                        )
                    except Exception as ws_error:
                        logger.error(f"Error enviando notificación WebSocket: {ws_error}")
            else:
                logger.error(f"No se pudo actualizar el tiempo para {self.stage_name}")
            
        except Exception as e:
            logger.error(f"Error actualizando tiempo de procesamiento: {e}")
        finally:
            # Cerrar la conexión de forma segura en el bloque finally
            if client is not None:
                try:
                    client.close()  # Usar close() síncrono en lugar de await client.close()
                except Exception as close_error:
                    logger.error(f"Error cerrando conexión MongoDB: {close_error}")

    def _schedule_update_processing_time_sync(self, docfile_id: str, duration: float, user_id: str = "N/A") -> None:
        """Programa la actualización del tiempo de procesamiento de forma síncrona y segura."""
        import asyncio
        import threading
        
        def run_update():
            try:
                # Crear un nuevo event loop para este thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._update_processing_time(docfile_id, duration, user_id))
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error en thread de actualización de timing: {e}")
        
        # Ejecutar en un thread separado para evitar problemas con el event loop
        thread = threading.Thread(target=run_update, daemon=True)
        thread.start()