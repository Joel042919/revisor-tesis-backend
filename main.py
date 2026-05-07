from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import os
import uuid
from models import ResultadoTesis
from utilsDashboard import generar_datos_dashboard
#from servicesGeminiProcesa import procesar_documento_gemini, extraer_reglas_gemini
from servicesOpenAIProcesa import procesar_documento_openai, extraer_reglas_openai

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

# Montar la carpeta de reportes para hacerla accesible vía HTTP
app.mount("/reportes", StaticFiles(directory="./reportes_pdf"), name="reportes")

TEMP_DIR = "./temp_trabajos"
os.makedirs(TEMP_DIR,exist_ok=True)

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
# 3. Lógica de Procesamiento
# ==========================================

resultados_globales: Dict[str,List[ResultadoTesis]] = {}

async def orquestador_multihilo(ruta_reglas:str,archivos_info: List[Dict[str,str]], prompt:str,job_id:str):
    resultados_globales[job_id] = []
    total_archivos = len(archivos_info)
    
    #PROCESAR EL WORD DE REVISION A JSON
    await manager.send_personal_message(json.dumps({
        "estado":"PROCESANDO",
        "procesados":0,
        "total":total_archivos,
        "mensaje":"Leyendo archivo de reglas de revisión y construyendo rúbrica..."
    }),job_id)
    
    ######GEMINI
    #diccionario_reglas = await extraer_reglas_gemini(ruta_reglas)
    ######OPENAI
    diccionario_reglas = await extraer_reglas_openai(ruta_reglas)
    
    if os.path.exists(ruta_reglas):
        os.remove(ruta_reglas)
        
    
    #PROCESAR LAS TESIS CON EL DICCIONARIO DE REVISION
    procesados = 0
    sem = asyncio.Semaphore(3)
    
    async def worker(info: Dict[str,str]):
        nonlocal procesados
        async with sem:
            await manager.send_personal_message(json.dumps({
                "estado":"PROCESANDO",
                "procesados":procesados,
                "total":total_archivos,
                "mensaje":f"Analizando profundidad lógica y formato de: {info['nombre']}..."
            }),job_id)
        
        #####GEMINI
        #resultado = await procesar_documento_gemini(info,prompt,diccionario_reglas,manager,job_id,sem)
        #####OPENAI
        resultado = await procesar_documento_openai(info,prompt,diccionario_reglas,manager,job_id,sem)
        resultados_globales[job_id].append(resultado)
        
        procesados+=1
        
        await manager.send_personal_message(json.dumps({
            "estado":"PROCESANDO",
            "procesados":procesados,
            "total":total_archivos,
            "mensaje":f"Evaluación de {info['nombre']} completada."
        }),job_id)
        
        if os.path.exists(info['ruta']):
            os.remove(info['ruta'])
    
    tareas = [worker(info) for info in archivos_info]
    await asyncio.gather(*tareas)
    
    #Preparamos la data del dashboard
    datos_dashboard = generar_datos_dashboard(resultados_globales[job_id])
    
    await manager.send_personal_message(json.dumps({
        "estado": "COMPLETADO",
        "total": total_archivos,
        "mensaje": "Revisión finalizada con éxito.",
        "data_dashboard": datos_dashboard
    }), job_id)

# ==========================================
# 4. Rutas (Endpoints)
# ==========================================

@app.post("/api/subir-tesis")
async def subir_tesis(
    background_tasks: BackgroundTasks,
    prompt: str = Form(""),
    archivo_reglas:UploadFile=File(...),
    archivos: List[UploadFile] = File(...)
):
    job_id = str(uuid.uuid4())
    
    #Guardar el archivo de reglas
    ruta_reglas = os.path.join(TEMP_DIR,f"{job_id}_REGLAS_{archivo_reglas.filename}")
    with open(ruta_reglas,"wb") as buffer:
        import shutil
        shutil.copyfileobj(archivo_reglas.file,buffer)
    
    #Guardar los archivos a evaluar
    archivos_info = []
    for archivo in archivos:
        ruta_temporal = os.path.join(TEMP_DIR,f"{job_id}_{archivo.filename}")
        with open(ruta_temporal,"wb") as buffer:
            import shutil
            shutil.copyfileobj(archivo.file,buffer)
            
        archivos_info.append({"ruta":ruta_temporal,"nombre":archivo.filename})
        
    # Lanzamos el orquestador pasando la ruta de las reglas
    background_tasks.add_task(orquestador_multihilo, ruta_reglas,archivos_info, prompt, job_id)
    
    return {"job_id": job_id}

@app.websocket("/ws/progreso/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(websocket, job_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(job_id)
