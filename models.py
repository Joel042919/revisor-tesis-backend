from pydantic import BaseModel
from typing import List, Dict

class ResultadoTesis(BaseModel):
    nombre_archivo: str
    titulo_trabajo: str
    nombre_alumnos: List[str]
    nota: float
    errores_forma: Dict[str, str]  # Ahora son diccionarios clave: descripción
    errores_fondo: Dict[str, str]
    bases_de_datos: List[str]
    tiempo_procesamiento_segundos: float
    link_pdf_review: str