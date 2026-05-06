from typing import List, Dict, Any
from models import ResultadoTesis

def generar_datos_dashboard(datos: List[ResultadoTesis]) -> Dict[str, Any]:
    total_archivos = len(datos)
    if total_archivos == 0:
        return {}

    aprobados = sum(1 for t in datos if t.nota >= 14)
    avg_global = sum(t.nota for t in datos) / total_archivos
    avg_procesamiento = sum(t.tiempo_procesamiento_segundos for t in datos) / total_archivos

    # 1. Agrupar y contar errores frecuentes (tanto de forma como de fondo)
    conteo_errores = {}
    for t in datos:
        for error_key in t.errores_forma.keys():
            conteo_errores[error_key] = conteo_errores.get(error_key, 0) + 1
        for error_key in t.errores_fondo.keys():
            conteo_errores[error_key] = conteo_errores.get(error_key, 0) + 1
    
    # Formatear errores ordenados de mayor a menor frecuencia
    error_frecuente = [
        {"name": k.replace("_", " ").capitalize(), "value": v} 
        for k, v in sorted(conteo_errores.items(), key=lambda item: item[1], reverse=True)
    ]

    # 2. Agrupar y contar bases de datos
    conteo_bases = {}
    for t in datos:
        for base in t.bases_de_datos:
            conteo_bases[base] = conteo_bases.get(base, 0) + 1
            
    base_frecuente = [
        {"name": k, "amount": v} 
        for k, v in sorted(conteo_bases.items(), key=lambda item: item[1], reverse=True)
    ]

    # 3. Calcular histograma de notas
    hist = {"0-10": 0, "11-13": 0, "14-16": 0, "17-20": 0}
    for t in datos:
        n = t.nota
        if n <= 10: hist["0-10"] += 1
        elif n <= 13: hist["11-13"] += 1
        elif n <= 16: hist["14-16"] += 1
        else: hist["17-20"] += 1
        
    notas_histograma = [{"rango": k, "cantidad": v} for k, v in hist.items()]

    # 4. Mapear lista de estudiantes
    estudiante_trabajo = [
        {
            "tituloTrabajo": t.titulo_trabajo,
            "autor": t.nombre_alumnos,
            "nota": round(t.nota, 2),
            "linkPdfReview": t.link_pdf_review
        } for t in datos
    ]

    return {
        "totalAprobados": aprobados,
        "avgGlobal": round(avg_global, 1),
        "avgProcesamiento": round(avg_procesamiento, 1),
        "errorFrecuente": error_frecuente[:5], # Tomamos el Top 5 de errores
        "baseFrecuente": base_frecuente,
        "notasHistograma": notas_histograma,
        "estudianteTrabajo": estudiante_trabajo
    }