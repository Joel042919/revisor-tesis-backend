import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

REPORTES_DIR = "./reportes_pdf"
os.makedirs(REPORTES_DIR, exist_ok=True)

def sanitizar_valor(valor) -> str:
    if isinstance(valor, dict):
        return "\n".join([f"- {k}: {v}" for k, v in valor.items()])
    elif isinstance(valor, list):
        return ", ".join([str(x) for x in valor])
    return str(valor)

def crear_tabla_errores(diccionario_errores: dict, estilo_celda):
    """Convierte un diccionario de errores en una tabla de ReportLab"""
    # Cabecera de la tabla
    datos_tabla = [["Regla Infringida", "Detalle de la Observación y Corrección"]]
    
    # Llenado de filas
    for llave, descripcion in diccionario_errores.items():
        titulo_limpio = Paragraph(str(llave).replace("_", " ").title(), estilo_celda)
        desc_limpia = Paragraph(sanitizar_valor(descripcion), estilo_celda)
        datos_tabla.append([titulo_limpio, desc_limpia])

    # Creación y estilo de la tabla
    # Columna 1: 30% del ancho, Columna 2: 70% del ancho
    tabla = Table(datos_tabla, colWidths=[130, 350]) 
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0C342C")), # Fondo verde oscuro cabecera
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), # Texto blanco cabecera
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F8FAFC")), # Fondo gris muy claro para el cuerpo
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), # Alinear texto arriba
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#135245")), # Bordes de la tabla
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    return tabla

def generar_pdf_reporte(datos: dict, job_id: str) -> str:
    nombre_base = datos['nombre_archivo'].replace(".docx", "").replace(".pdf", "").replace(" ", "_")
    nombre_archivo_pdf = f"Reporte_{nombre_base}_{job_id[:8]}.pdf"
    ruta_fisica = os.path.join(REPORTES_DIR, nombre_archivo_pdf)

    doc = SimpleDocTemplate(ruta_fisica, pagesize=letter)
    styles = getSampleStyleSheet()
    
    estilo_titulo = styles['Heading1']
    estilo_titulo.alignment = 1
    estilo_subtitulo = styles['Heading2']
    estilo_subtitulo.textColor = colors.HexColor("#065F46")
    estilo_normal = styles['Normal']
    estilo_celda = ParagraphStyle("EstiloCelda", parent=styles['Normal'], fontSize=9, leading=12)

    story = []

    # --- ENCABEZADO Y METADATOS ---
    story.append(Paragraph("Reporte Detallado de Revisión de Tesis", estilo_titulo))
    story.append(Spacer(1, 15))
    
    story.append(Paragraph(f"<b>Documento Analizado:</b> {datos['nombre_archivo']}", estilo_normal))
    titulo_limpio = sanitizar_valor(datos['titulo_trabajo'])
    story.append(Paragraph(f"<b>Título Identificado:</b> {titulo_limpio}", estilo_normal))
    
    autores_str = sanitizar_valor(datos['nombre_alumnos'])
    story.append(Paragraph(f"<b>Autor(es):</b> {autores_str}", estilo_normal))
    
    color_nota = "green" if datos['nota'] >= 14 else "red"
    story.append(Paragraph(f"<b>Calificación Asignada:</b> <font color={color_nota}>{datos['nota']}/20 ({datos['estado']})</font>", estilo_normal))
    
    bases_str = sanitizar_valor(datos['bases_de_datos']) if datos['bases_de_datos'] else 'Ninguna'
    story.append(Paragraph(f"<b>Bases de Datos Detectadas:</b> {bases_str}", estilo_normal))
    story.append(Spacer(1, 25))

    # --- TABLA: OBSERVACIONES DE FORMA ---
    story.append(Paragraph("1. Observaciones de Forma (Formato y Estructura)", estilo_subtitulo))
    story.append(Spacer(1, 10))
    if datos['errores_forma']:
        tabla_forma = crear_tabla_errores(datos['errores_forma'], estilo_celda)
        story.append(tabla_forma)
    else:
        story.append(Paragraph("✓ El documento cumple con todas las reglas de forma establecidas.", estilo_normal))
    
    story.append(Spacer(1, 20))

    # --- TABLA: OBSERVACIONES DE FONDO ---
    story.append(Paragraph("2. Observaciones de Fondo (Contenido y Metodología)", estilo_subtitulo))
    story.append(Spacer(1, 10))
    if datos['errores_fondo']:
        tabla_fondo = crear_tabla_errores(datos['errores_fondo'], estilo_celda)
        story.append(tabla_fondo)
    else:
        story.append(Paragraph("✓ El documento cumple con todos los criterios de fondo evaluados.", estilo_normal))

    doc.build(story)
    return nombre_archivo_pdf