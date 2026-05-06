import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Carpeta temporal para los reportes (se creará si no existe)
REPORTES_DIR = "./reportes_pdf"
os.makedirs(REPORTES_DIR, exist_ok=True)

def generar_pdf_reporte(datos: dict, job_id: str) -> str:
    """
    Genera un PDF con los resultados de la revisión y devuelve la ruta relativa 
    para que FastAPI la pueda servir.
    """
    # Crear un nombre de archivo seguro
    nombre_base = datos['nombre_archivo'].replace(".docx", "").replace(".pdf", "").replace(" ", "_")
    nombre_archivo_pdf = f"Reporte_{nombre_base}_{job_id[:8]}.pdf"
    ruta_fisica = os.path.join(REPORTES_DIR, nombre_archivo_pdf)

    # Configuración del documento
    doc = SimpleDocTemplate(ruta_fisica, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    estilo_titulo = styles['Heading1']
    estilo_titulo.alignment = 1 # Centrado
    estilo_subtitulo = styles['Heading2']
    estilo_subtitulo.textColor = colors.HexColor("#065F46") # Un verde esmeralda para que combine con tu UI
    estilo_normal = styles['Normal']
    estilo_llave = ParagraphStyle(
        "EstiloLlave",
        parent=styles['Normal'],
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#B91C1C") # Rojo suave para los errores
    )

    story = []

    # --- ENCABEZADO ---
    story.append(Paragraph("Reporte de Revisión Académica IA", estilo_titulo))
    story.append(Spacer(1, 15))

    # --- METADATOS ---
    story.append(Paragraph(f"<b>Documento Analizado:</b> {datos['nombre_archivo']}", estilo_normal))
    story.append(Paragraph(f"<b>Título Identificado:</b> {datos['titulo_trabajo']}", estilo_normal))
    story.append(Paragraph(f"<b>Autor(es):</b> {', '.join(datos['nombre_alumnos'])}", estilo_normal))
    
    # Color de nota dinámico
    color_nota = "green" if datos['nota'] >= 14 else "red"
    story.append(Paragraph(f"<b>Calificación Asignada:</b> <font color={color_nota}>{datos['nota']}/20 ({datos['estado']})</font>", estilo_normal))
    
    story.append(Paragraph(f"<b>Bases de Datos Detectadas:</b> {', '.join(datos['bases_de_datos']) if datos['bases_de_datos'] else 'Ninguna'}", estilo_normal))
    story.append(Spacer(1, 20))

    # --- OBSERVACIONES DE FORMA ---
    story.append(Paragraph("1. Observaciones de Forma", estilo_subtitulo))
    story.append(Spacer(1, 5))
    if datos['errores_forma']:
        for llave, descripcion in datos['errores_forma'].items():
            titulo_error = llave.replace("_", " ").capitalize()
            story.append(Paragraph(f"{titulo_error}:", estilo_llave))
            story.append(Paragraph(descripcion, estilo_normal))
            story.append(Spacer(1, 10))
    else:
        story.append(Paragraph("✓ No se encontraron errores de forma.", estilo_normal))
    
    story.append(Spacer(1, 15))

    # --- OBSERVACIONES DE FONDO ---
    story.append(Paragraph("2. Observaciones de Fondo", estilo_subtitulo))
    story.append(Spacer(1, 5))
    if datos['errores_fondo']:
        for llave, descripcion in datos['errores_fondo'].items():
            titulo_error = llave.replace("_", " ").capitalize()
            story.append(Paragraph(f"{titulo_error}:", estilo_llave))
            story.append(Paragraph(descripcion, estilo_normal))
            story.append(Spacer(1, 10))
    else:
        story.append(Paragraph("✓ No se encontraron errores de fondo.", estilo_normal))

    # Construir PDF
    doc.build(story)
    
    # Retornamos solo el nombre del archivo, para armar la URL en FastAPI
    return nombre_archivo_pdf