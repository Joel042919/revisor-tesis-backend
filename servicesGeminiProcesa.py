import asyncio
import random
import json
from models import ResultadoTesis
import google.generativeai as genai
import os
import time
from utilsPdf import generar_pdf_reporte
from models import ResultadoTesis
from dotenv import load_dotenv
import docx

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


def extraer_texto_docx(ruta_archivo:str) -> str:
    """Extraer todo el texto en un archivo .word"""
    try:
        doc = docx.Document(ruta_archivo)
        return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    except Exception as e:
        print(f"Error extrayendo texto del documento: {e}")
        return ""


async def extraer_reglas_gemini(ruta_rubrica:str) -> dict:
    """
    Sube el archivo físicamente a la API de Gemini para que lo lea nativamente 
    y construya un JSON estricto con las reglas de evaluación.
    """
    
    diccionario_reglas = {"forma":{},"fondo":{}}
    archivo_gemini = None
    
    try:
        archivo_gemini = genai.upload_file(path=ruta_rubrica)
    
        prompt_sistema=f"""
        Actúa como un experto en extracción de datos y estructuración de documentos académicos. Tu tarea es analizar el documento que te envio que es una una guía normativa y convertirlo en un objeto JSON siguiendo estrictamente una jerarquía de "Forma" y "Fondo" por sección.
        INSTRUCCIONES DE SALIDA:
        Formato: Devuelve UNICAMENTE el código JSON dentro de un bloque de código.
        Estructura Raíz: El JSON debe tener dos ramas principales: "forma" y "fondo".
        Rama "forma": Incluye todas las reglas generales de presentación (Ejm: márgenes, fuentes, interlineado, normas de citación, medios de entrega, etc.).
        Rama "fondo": Desglosa cada sección del documento (Ejm: Carátula, Jurado, Introducción, Referencias, Anexos, etc.) detallando los requisitos de contenido obligatorios para cada una.
        Restricción Crítica: NO incluyas ninguna etiqueta de citación, números de referencia, ni explicaciones adicionales fuera del JSON.
        Idioma: Todo el contenido del JSON debe estar en español.
        """
        
        modelo = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=prompt_sistema,
            generation_config={"temperature":0.3}
        )
        
        respuesta = await modelo.generate_content_async([
            archivo_gemini,
            "Analiza el documento adjunto y extrae las reglas en formato JSON."
        ])
        
        contenido_crudo = respuesta.text.strip()
        
        #Limpieza de comillas
        if contenido_crudo.startswith("```json"):
            contenido_crudo = contenido_crudo[7:]
        elif contenido_crudo.startswith("```"):
            contenido_crudo = contenido_crudo[3:]
            
        if contenido_crudo.endswith("```"):
            contenido_crudo = contenido_crudo[:-3]
            
        diccionario_reglas = json.loads(contenido_crudo.strip())
        
    except json.JSONDecodeError as e:
        print(f"Error al decodificar el JSON devuelto por Gemini: {e}")
    except Exception as e:
        print(f"Error general en la llamada a Gemini: {e}")
    finally:
        if archivo_gemini:
            try:
                genai.delete_file(archivo_gemini.name)
            except Exception as e:
                print(f"No se pudo eliminar el archivo temporal de Gemini: {e}")

    return diccionario_reglas


async def procesar_documento_gemini(info: dict, prompt: str, reglas:dict, manager, job_id: str, sem: asyncio.Semaphore) -> ResultadoTesis:
    async with sem:
        tiempo_inicio = time.time()
        archivo_gemini = None
        
        # Variables por defecto en caso de que la IA falle al procesar
        titulo_trabajo = f"Documento: {info['nombre']}"
        nombre_alumnos = ["No detectado"]
        nota = 0.0
        errores_forma_detectados = {}
        errores_fondo_detectados = {}
        bases_de_datos = []
        
        try:
            # 1. Subir la tesis del alumno a los servidores de Gemini
            archivo_gemini = genai.upload_file(path=info['ruta'])
            
            # 2. Construir el prompt estricto integrando el diccionario de reglas
            prompt_sistema = f"""
            Eres un tribunal académico evaluando una tesis de grado. 
            Evalúa el documento adjunto utilizando ESTRICTAMENTE las siguientes reglas extraídas de la rúbrica oficial. 
            Aquí está el contrato de evaluación (JSON):
            {json.dumps(reglas, ensure_ascii=False, indent=3)}
            
            Instrucciones adicionales del evaluador principal (usuario): {prompt}
            
            INSTRUCCIONES DE SALIDA:
            Debes devolver UNICAMENTE un objeto JSON válido con la siguiente estructura exacta:
            {{
                "titulo_trabajo": "Título de la tesis encontrado en la carátula o inicio",
                "nombre_alumnos": ["Nombre del alumno 1", "Nombre del alumno 2"],
                "nota": [Calificación numérica de 0 a 20 basada en la cantidad y gravedad de los errores],
                "errores_forma": {{
                    // REGLA DE ORO: Solo puedes usar las llaves exactas del diccionario de reglas 'forma' provisto arriba.
                    // Si el documento NO cumple la regla, usa esa llave. 
                    // El valor debe ser tu explicación de por qué el documento falló esa regla.
                    // Si el documento sí cumple la regla, NO incluyas la llave en este objeto.
                }},
                "errores_fondo": {{
                    // Igual que arriba. Solo usa las llaves del diccionario de reglas 'fondo'.
                    // El valor es el hallazgo o justificación de la penalización.
                }},
                "bases_de_datos": ["Scopus", "IEEE", "PubMed", "Science Direct"] // Extrae las bases de datos bibliográficas detectadas en el documento.
            }}
            No incluyas markdown (```json). No inventes llaves nuevas para los errores.
            """

            modelo = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=prompt_sistema,
                generation_config={"temperature": 0.2} # Temperatura baja para que sea estricto y no alucine
            )

            # 3. Llamada a la IA
            respuesta = await modelo.generate_content_async([
                archivo_gemini, 
                "Evalúa la tesis adjunta detalladamente y devuelve el JSON solicitado."
            ])
            
            contenido_crudo = respuesta.text.strip()
            
            # 4. Limpieza de etiquetas Markdown
            if contenido_crudo.startswith("```json"):
                contenido_crudo = contenido_crudo[7:]
            elif contenido_crudo.startswith("```"):
                contenido_crudo = contenido_crudo[3:]
            if contenido_crudo.endswith("```"):
                contenido_crudo = contenido_crudo[:-3]
                
            # 5. Convertir a diccionario de Python
            datos_extraidos = json.loads(contenido_crudo.strip())
            
            # 6. Asignar de forma segura usando .get()
            titulo_trabajo = datos_extraidos.get("titulo_trabajo", titulo_trabajo)
            nombre_alumnos = datos_extraidos.get("nombre_alumnos", nombre_alumnos)
            nota = float(datos_extraidos.get("nota", 0.0))
            errores_forma_detectados = datos_extraidos.get("errores_forma", {})
            errores_fondo_detectados = datos_extraidos.get("errores_fondo", {})
            bases_de_datos = datos_extraidos.get("bases_de_datos", [])

        except json.JSONDecodeError as e:
            print(f"Error decodificando el JSON de la evaluación de {info['nombre']}: {e}")
            errores_forma_detectados = {"error_sistema": "El modelo no devolvió un formato válido."}
        except Exception as e:
            print(f"Error general evaluando {info['nombre']} con Gemini: {e}")
            errores_forma_detectados = {"error_procesamiento": str(e)}
        finally:
            # 7. IMPORTANTE: Borrar el archivo de la nube de Gemini
            if archivo_gemini:
                try:
                    genai.delete_file(archivo_gemini.name)
                except Exception as e:
                    print(f"No se pudo eliminar la tesis de la nube de Gemini: {e}")
        
        tiempo_fin = time.time()
        
        
        #Procesar PDF
        datos_para_pdf = {
            "nombre_archivo": info['nombre'],
            "titulo_trabajo": titulo_trabajo,
            "nombre_alumnos": nombre_alumnos,
            "nota": nota,
            "estado":"Aprobado" if nota >= 14 else "Desaprobado",
            "errores_forma": errores_forma_detectados,
            "errores_fondo": errores_fondo_detectados,
            "bases_de_datos": bases_de_datos
        }
        
        nombre_pdf = generar_pdf_reporte(datos_para_pdf, job_id)
        
        url_pdf = f"http://127.0.0.1:8000/reportes/{nombre_pdf}"
        
        # 8. Retornar la estructura Pydantic que espera el orquestador y el dashboard
        return ResultadoTesis(
            nombre_archivo=info['nombre'],
            titulo_trabajo=titulo_trabajo,
            nombre_alumnos=nombre_alumnos,
            nota=nota,
            errores_forma=errores_forma_detectados,
            errores_fondo=errores_fondo_detectados,
            bases_de_datos=bases_de_datos,
            tiempo_procesamiento_segundos=round(tiempo_fin - tiempo_inicio, 2),
            link_pdf_review=url_pdf
        )