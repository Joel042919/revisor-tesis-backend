from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import asyncio
import json

# ==========================================
# 1. Configuración de la App y CORS
# ==========================================
app = FastAPI(title="Revisor de Tesis IA")

# Fundamental para permitir peticiones desde tu frontend en Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Ajusta esto al puerto de tu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 2. Gestor de WebSockets (Para el Frontend)
# ==========================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

manager = ConnectionManager()

# ==========================================
# 3. Esquemas Pydantic (La estructura estricta)
# ==========================================
class ResultadoTesis(BaseModel):
    nombre_archivo: str
    nombre_alumnos: list[str]
    nota: float
    estado: str
    errores_forma: list[str]
    errores_fondo: list[str]
    bases_de_datos: list[str]
    tiempo_procesamiento_segundos: float

# ==========================================
# 4. Lógica de Procesamiento (El Core Multihilo)
# ==========================================
# Variables globales en memoria para almacenar los resultados listos para el dashboard
resultados_globales: List[ResultadoTesis] = []

async def simular_revision_gemini(archivo: str, prompt: str, client_id: str, sem: asyncio.Semaphore):
    """
    Esta función simula la llamada a LangChain/Gemini. 
    El semáforo garantiza que solo 3 de estas funciones corran al mismo tiempo.
    """
    async with sem:
        await manager.send_personal_message(json.dumps({"tipo": "estado", "mensaje": f"Iniciando revisión de: {archivo}..."}), client_id)
        
        # Aquí iría tu lógica real de LangChain procesando el Word
        await asyncio.sleep(4) # Simulamos que toma 4 segundos procesar
        
        await manager.send_personal_message(json.dumps({"tipo": "estado", "mensaje": f"Estructurando reporte de: {archivo}..."}), client_id)
        
        # Simulamos el objeto Pydantic que te devolvería Gemini
        resultado = ResultadoTesis(
            nombre_archivo=archivo,
            nombre_alumnos=["Juan Perez"],
            nota=15.5,
            estado="Aprobado",
            errores_forma=["Márgenes incorrectos", "Falta interlineado 1.5"],
            errores_fondo=["Falta justificación práctica"],
            bases_de_datos=["Scopus", "Zenodo"],
            tiempo_procesamiento_segundos=4.0
        )
        resultados_globales.append(resultado)
        
        await manager.send_personal_message(json.dumps({"tipo": "completado", "archivo": archivo}), client_id)

async def orquestador_multihilo(archivos_nombres: List[str], prompt: str, client_id: str):
    """
    Lanza todas las tareas, pero el semáforo interno limita a 3 a la vez.
    """
    resultados_globales.clear() # Limpiamos resultados anteriores
    sem = asyncio.Semaphore(3) # Límite estricto de concurrencia
    
    tareas = [ simular_revision_gemini(archivo, prompt, client_id, sem) for archivo in archivos_nombres ]
    await asyncio.gather(*tareas)
    
    # Avisamos al frontend que TODO el lote terminó para que pida el dashboard
    await manager.send_personal_message(json.dumps({"tipo": "finalizado_total", "mensaje": "Todas las tesis han sido procesadas."}), client_id)

# ==========================================
# 5. Rutas (Endpoints)
# ==========================================

@app.post("/api/subir-tesis")
async def subir_tesis(
    background_tasks: BackgroundTasks,
    client_id: str = Form(...),
    prompt: str = Form(...),
    archivos: List[UploadFile] = File(...)
):
    """
    Ruta inicial que recibe los archivos y el prompt desde el Dropzone.
    Nota: Si envías los archivos desde el frontend en chunks de 30MB, 
    aquí debes implementar la lógica para ensamblar los chunks en un archivo temporal.
    """
    nombres_archivos = []
    
    for archivo in archivos:
        # Aquí guardarías el archivo físicamente o en memoria
        # contenido = await archivo.read()
        nombres_archivos.append(archivo.filename)
        
    # Lanzamos el procesamiento en segundo plano para no bloquear esta petición
    background_tasks.add_task(orquestador_multihilo, nombres_archivos, prompt, client_id)
    
    return {"mensaje": "Archivos recibidos correctamente, iniciando procesamiento...", "archivos": nombres_archivos}


@app.get("/api/dashboard-stats")
async def obtener_metricas_dashboard():
    """
    Next.js llama a esta ruta cuando el WebSocket avisa que terminó el proceso.
    Aquí haces los cálculos nativos con Python sobre 'resultados_globales'.
    """
    total_tesis = len(resultados_globales)
    if total_tesis == 0:
        return {"error": "No hay datos procesados."}

    aprobados = sum(1 for t in resultados_globales if t.estado == "Aprobado")
    promedio_general = sum(t.nota for t in resultados_globales) / total_tesis
    
    # Puedes usar collections.Counter aquí para los top errores y bases de datos

    return {
        "total_analizados": total_tesis,
        "aprobados": aprobados,
        "desaprobados": total_tesis - aprobados,
        "promedio_global": round(promedio_general, 2),
        "resultados_detallados": [t.dict() for t in resultados_globales]
    }


@app.websocket("/ws/progreso/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    Ruta para la conexión en tiempo real. 
    Next.js se conecta aquí apenas el usuario entra a la página.
    """
    await manager.connect(websocket, client_id)
    try:
        while True:
            # Mantenemos la conexión viva esperando mensajes del cliente (si fueran necesarios)
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)