from langchain_core.callbacks import AsyncCallbackHandler
from app.utils.status_notifier import update_status

class BatchProgressCallbackHandler(AsyncCallbackHandler):
    """
    Callback handler para actualizar el progreso durante el procesamiento en batch,
    contando la finalización de cada llamada al LLM.
    """
    def __init__(self, collection, docfile_id, user_id, total_items):
        self.collection = collection
        self.docfile_id = docfile_id
        self.user_id = user_id
        self.total_items = total_items
        self.completed_count = 0
        self.lock = None # Podría ser necesario un lock en escenarios muy concurrentes/distribuidos

    async def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
         """
         Se dispara al finalizar una llamada a un Large Language Model (LLM).
         Cada llamada a model.ainvoke() dentro de recognize_page dispara esto una vez.
         """
         self.completed_count += 1

         progress = int((self.completed_count / self.total_items) * 100)
         # Asegurarse de que el progreso no supere el 99% antes del paso final de actualización en BD
         progress = min(progress, 99)

        #  print(f"Completed item {self.completed_count}/{self.total_items}. Progress: {progress}%")

         # Llama a tu función de actualización de estado
         await update_status(
             self.collection,
             self.docfile_id,
             "Reconociendo",
             self.user_id,
             progress=progress,
             update_db=False,
             send_progress_ws=True 
         )

    async def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
         """
         Se dispara si ocurre un error en la llamada al LLM.
         Podrías manejar aquí errores de páginas individuales si es necesario.
         """