# -*- coding: utf-8 -*-
"""
Arquetipos de Contenido - PcComponentes Content Generator

Define los 34 arquetipos de contenido SEO disponibles para la generación.
Cada arquetipo incluye: estructura, tono, keywords, preguntas guía,
rangos de longitud y campos específicos.

Autor: PcComponentes - Product Discovery & Content
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES DE LONGITUD
# ============================================================================

DEFAULT_MIN_LENGTH = 800
DEFAULT_MAX_LENGTH = 2500
DEFAULT_CONTENT_LENGTH = 1500


# ============================================================================
# PREGUNTAS UNIVERSALES
# Estas preguntas aplican a TODOS los arquetipos y proporcionan contexto base
# ============================================================================

PREGUNTAS_UNIVERSALES = [
    "¿A qué público va dirigido? (principiante que nunca ha comprado / usuario con conocimientos básicos / experto técnico)",
    "¿Cuál es la intención de búsqueda principal? (aprender sobre el tema / comparar opciones / comprar ya)",
    "¿Hay productos específicos de PcComponentes que DEBEN incluirse? (pega URLs o nombres — solo si no los has añadido en los campos de producto del formulario)",
    "¿Existe contenido de la competencia a superar? ¿Qué hacen bien o mal?",
    "¿Es contenido evergreen o tiene fecha de caducidad? (si caduca, ¿cuándo?)",
    "¿Qué ángulo o valor diferencial puede aportar PcComponentes? (dato interno, experiencia del equipo, insight exclusivo, test propio, precio competitivo)",
]


# ============================================================================
# DEFINICIÓN DE ARQUETIPOS
# ============================================================================

ARQUETIPOS: Dict[str, Dict[str, Any]] = {
    
    # -------------------------------------------------------------------------
    # ARQ-1 a ARQ-5: Arquetipos Fundamentales
    # -------------------------------------------------------------------------
    
    "ARQ-1": {
        "code": "ARQ-1",
        "name": "Artículos SEO con Enlaces Internos",
        "description": "Artículo optimizado para SEO con estructura de enlaces internos estratégicos hacia categorías y productos relevantes.",
        "tone": "Informativo, profesional y orientado a la conversión",
        "keywords": ["seo", "enlaces internos", "categorías", "productos"],
        "structure": [
            "Introducción con keyword principal",
            "Desarrollo con H2/H3 estructurados",
            "Secciones con enlaces internos contextuales",
            "Tabla comparativa (opcional)",
            "FAQs con schema markup",
            "Veredicto final con CTA"
        ],
        "guiding_questions": [
            "¿Qué problema o necesidad resuelve este artículo para el lector?",
            "¿A qué categorías de PcComponentes debe enlazar? (pega URLs)",
            "¿Qué 3-5 productos específicos deben destacarse con enlace? (pega URLs)",
            "¿Hay ofertas o promociones ACTIVAS que mencionar? (con fechas)",
            "¿Qué preguntas frecuentes busca la gente sobre este tema?",
            "¿Cuál es la acción que queremos que haga el lector al terminar?"
        ],
        "default_length": 1500,
        "min_length": 1000,
        "max_length": 2500,
        "visual_elements": ["toc", "table", "callout", "verdict"],
        "campos_especificos": ["categoria_principal", "productos_destacados", "cta_principal"]
    },
    
    "ARQ-2": {
        "code": "ARQ-2",
        "name": "Guía Paso a Paso",
        "description": "Tutorial detallado que guía al usuario a través de un proceso con pasos numerados y claros.",
        "tone": "Didáctico, claro y accesible",
        "keywords": ["guía", "tutorial", "paso a paso", "cómo"],
        "structure": [
            "Introducción: qué aprenderá el lector",
            "Requisitos previos (si aplica)",
            "Pasos numerados con instrucciones detalladas",
            "Tips y advertencias en callouts",
            "Resumen de pasos",
            "FAQs sobre el proceso",
            "Conclusión con siguientes pasos"
        ],
        "guiding_questions": [
            "¿Qué nivel de experiencia tiene el usuario objetivo? (nunca lo ha hecho / lo ha intentado / quiere mejorar)",
            "¿Cuántos pasos principales tiene el proceso? (enuméralos brevemente)",
            "¿Qué herramientas, materiales o productos se necesitan? (con enlaces a PcC si aplica)",
            "¿Cuáles son los 3 errores más comunes que comete la gente?",
            "¿Cuánto tiempo lleva completar el proceso?",
            "¿Hay variantes del proceso según el caso? (ej: en Windows vs Mac)",
            "¿Qué debe hacer el usuario si algo sale mal?"
        ],
        "default_length": 1800,
        "min_length": 1200,
        "max_length": 3000,
        "visual_elements": ["toc", "callout", "check_list"],
        "campos_especificos": ["nivel_dificultad", "tiempo_estimado", "herramientas", "errores_comunes"]
    },
    
    "ARQ-3": {
        "code": "ARQ-3",
        "name": "Explicación / Educativo",
        "description": "Contenido educativo que explica conceptos, tecnologías o temas complejos de forma accesible.",
        "tone": "Educativo, claro y profundo",
        "keywords": ["qué es", "explicación", "guía", "entender"],
        "structure": [
            "Definición clara del concepto",
            "Contexto histórico o técnico",
            "Cómo funciona (explicación detallada)",
            "Ejemplos prácticos",
            "Ventajas y desventajas",
            "Casos de uso",
            "FAQs",
            "Conclusión y recursos adicionales"
        ],
        "guiding_questions": [
            "¿Qué concepto o tecnología se va a explicar exactamente?",
            "¿El lector es totalmente nuevo en el tema o ya tiene base?",
            "¿Hay una analogía cotidiana que ayude a entenderlo? (ej: 'la RAM es como el escritorio donde trabajas')",
            "¿Qué conceptos PREVIOS debe conocer el lector?",
            "¿Qué conceptos RELACIONADOS debemos mencionar (y quizás enlazar a otros artículos)?",
            "¿Hay mitos o malentendidos comunes sobre este tema que debamos aclarar?",
            "¿Cómo afecta este concepto a la decisión de compra del usuario?"
        ],
        "default_length": 1600,
        "min_length": 1000,
        "max_length": 2500,
        "visual_elements": ["toc", "callout", "table"],
        "campos_especificos": ["concepto_principal", "nivel_tecnico", "conceptos_previos", "mitos_comunes"]
    },
    
    "ARQ-4": {
        "code": "ARQ-4",
        "name": "Review / Análisis de Producto",
        "description": "Análisis detallado de un producto con especificaciones, pruebas, pros/contras y veredicto.",
        "tone": "Experto, objetivo y detallado",
        "keywords": ["review", "análisis", "opinión", "prueba"],
        "structure": [
            "Introducción y primeras impresiones",
            "Especificaciones técnicas (tabla)",
            "Diseño y construcción",
            "Rendimiento en pruebas",
            "Características destacadas",
            "Puntos fuertes y débiles",
            "Comparación con alternativas",
            "FAQs del producto",
            "Veredicto final con puntuación"
        ],
        "guiding_questions": [
            "¿Qué producto específico se analiza? (URL de PcComponentes)",
            "¿Fuente de datos principal: prueba propia, reviews de usuarios, especificaciones del fabricante, benchmarks de terceros, o combinación?",
            "¿Cuáles son las 3-5 especificaciones MÁS importantes para el comprador?",
            "¿Cuáles son los 3 puntos FUERTES principales? (indica fuente: prueba propia, reviews usuarios, análisis de specs)",
            "¿Cuáles son los 2-3 puntos DÉBILES o 'peros'? (ser honestos — indica fuente)",
            "¿Contra qué 2-3 productos compite directamente? (URLs de PcC si no los has añadido como productos)",
            "¿Para qué TIPO de usuario es ideal y para cuál NO lo es?",
            "¿Hay datos de benchmarks, tests o pruebas de rendimiento? (enlaza fuentes si es posible)",
            "¿Cuál es el VEREDICTO: lo recomendamos o no? ¿Por qué?"
        ],
        "default_length": 2000,
        "min_length": 1500,
        "max_length": 3500,
        "visual_elements": ["toc", "table", "verdict", "callout"],
        "campos_especificos": ["producto_url", "precio", "competidores", "puntuacion", "veredicto"]
    },
    
    "ARQ-5": {
        "code": "ARQ-5",
        "name": "Comparativa A vs B",
        "description": "Comparación directa entre dos productos o tecnologías, analizando diferencias y ayudando en la decisión.",
        "tone": "Objetivo, analítico y útil para la decisión",
        "keywords": ["vs", "comparativa", "diferencias", "cuál elegir"],
        "structure": [
            "Introducción a ambas opciones",
            "Tabla comparativa de especificaciones",
            "Comparación por categorías (rendimiento, precio, etc.)",
            "¿Cuándo elegir la opción A?",
            "¿Cuándo elegir la opción B?",
            "FAQs sobre la comparativa",
            "Veredicto: cuál recomendamos y por qué"
        ],
        "guiding_questions": [
            "¿Qué dos productos/tecnologías se comparan? (URLs de ambos)",
            "¿Por qué el usuario duda entre estos dos específicamente?",
            "¿Cuáles son las 5 diferencias CLAVE que importan al comprador?",
            "¿En qué escenarios gana claramente la opción A?",
            "¿En qué escenarios gana claramente la opción B?",
            "¿Hay diferencia de precio significativa? ¿Merece la pena?",
            "¿Cuál es tu evaluación general: ganador claro, depende del perfil, o empate técnico?",
            "¿Existe una tercera alternativa que deberíamos mencionar?"
        ],
        "default_length": 1800,
        "min_length": 1200,
        "max_length": 2800,
        "visual_elements": ["toc", "comparison_table", "verdict"],
        "campos_especificos": ["producto_a_url", "producto_b_url", "criterios_comparacion", "ganador"]
    },
    
    # -------------------------------------------------------------------------
    # ARQ-6 a ARQ-10: Arquetipos de Listas y Selección
    # -------------------------------------------------------------------------
    
    "ARQ-6": {
        "code": "ARQ-6",
        "name": "Guía de Compra",
        "description": "Guía completa para ayudar al usuario a elegir el producto adecuado según sus necesidades.",
        "tone": "Consultivo, experto y orientado a la ayuda",
        "keywords": ["guía de compra", "cómo elegir", "qué buscar"],
        "structure": [
            "Por qué necesitas una guía de compra",
            "Factores clave a considerar",
            "Tipos de productos disponibles",
            "Rangos de precio y qué esperar",
            "Errores comunes al comprar",
            "Nuestra selección recomendada",
            "FAQs de compra",
            "Conclusión y recomendación final"
        ],
        "guiding_questions": [
            "¿Qué categoría de producto cubre la guía exactamente?",
            "¿Cuáles son los 5 factores de decisión MÁS importantes? (ordénalos)",
            "¿Qué rangos de precio existen? (ej: económico <100€, gama media 100-300€, premium >300€)",
            "¿Qué producto recomiendas en CADA rango de precio? (URLs)",
            "¿Cuáles son los 3 errores típicos que comete el comprador novato?",
            "¿Hay marcas especialmente recomendadas o a evitar? ¿Por qué?",
            "¿Qué especificación es la que más confunde al comprador?",
            "¿Hay productos exclusivos de PcC o marcas propias a destacar?"
        ],
        "default_length": 2000,
        "min_length": 1500,
        "max_length": 3000,
        "visual_elements": ["toc", "table", "callout", "verdict"],
        "campos_especificos": ["categoria", "rangos_precio", "productos_recomendados", "marcas_recomendadas"]
    },
    
    "ARQ-7": {
        "code": "ARQ-7",
        "name": "Roundup / Mejores X",
        "description": "Lista curada de los mejores productos en una categoría, con análisis individual y comparativa.",
        "tone": "Experto, curador y orientado a la selección",
        "keywords": ["mejores", "top", "ranking", "selección"],
        "structure": [
            "Introducción y criterios de selección",
            "Tabla resumen de productos",
            "Análisis individual de cada producto",
            "Comparativa general",
            "¿Cuál elegir según tu caso?",
            "FAQs sobre la categoría",
            "Veredicto y mejor opción global"
        ],
        "guiding_questions": [
            "¿Qué categoría de productos se cubre exactamente? (ej: 'auriculares gaming inalámbricos')",
            "¿Cuántos productos incluir? Lista cada uno con su URL de PcComponentes:",
            "¿Cuál es el criterio principal de 'mejor'? (rendimiento / calidad-precio / popularidad)",
            "¿Hay un producto 'Mejor en general' o 'Elección del editor'? ¿Cuál y por qué?",
            "¿Hay un producto 'Mejor calidad-precio'? ¿Cuál?",
            "¿Cuál es el rango de precios de la selección? (mínimo - máximo)",
            "¿Hay productos exclusivos de PcC, marcas propias o con oferta especial?",
            "¿Hay productos populares que quedan fuera de la selección? ¿Por qué? (stock, calidad, mejor alternativa)"
        ],
        "default_length": 2200,
        "min_length": 1500,
        "max_length": 4000,
        "visual_elements": ["toc", "grid", "badges", "verdict"],
        "campos_especificos": ["categoria", "productos_lista", "criterio_ranking", "mejor_global", "mejor_calidad_precio"]
    },
    
    "ARQ-8": {
        "code": "ARQ-8",
        "name": "Lista de Recomendaciones",
        "description": "Lista de productos o recursos recomendados para un propósito específico.",
        "tone": "Amigable, útil y directo",
        "keywords": ["recomendaciones", "lista", "sugerencias", "opciones"],
        "structure": [
            "Introducción al tema",
            "Criterios de selección",
            "Lista de recomendaciones con descripción",
            "Tips para elegir",
            "FAQs",
            "Conclusión"
        ],
        "guiding_questions": [
            "¿Para qué propósito ESPECÍFICO son las recomendaciones? (ej: 'portátiles para estudiantes de ingeniería')",
            "¿Cuántos productos incluir? Lista cada uno con URL:",
            "¿Qué tienen en común todos los productos recomendados?",
            "¿Hay diferentes perfiles de usuario dentro del propósito? (ej: presupuesto ajustado vs sin límite)",
            "¿Por qué estos productos y no otros de la misma categoría?",
            "¿Hay algún producto 'sorpresa' que la gente no conoce pero es muy bueno?"
        ],
        "default_length": 1400,
        "min_length": 800,
        "max_length": 2200,
        "visual_elements": ["toc", "callout", "grid"],
        "campos_especificos": ["proposito", "productos_lista", "perfil_usuario"]
    },
    
    "ARQ-9": {
        "code": "ARQ-9",
        "name": "Mejores Productos por Precio",
        "description": "Selección de los mejores productos organizados por rangos de precio.",
        "tone": "Práctico, orientado al presupuesto",
        "keywords": ["mejor calidad precio", "por menos de", "económico", "presupuesto"],
        "structure": [
            "Introducción y rangos de precio",
            "Mejor opción económica",
            "Mejor opción gama media",
            "Mejor opción premium",
            "Tabla comparativa por precio",
            "¿Cuánto invertir según tu uso?",
            "FAQs sobre precios",
            "Conclusión"
        ],
        "guiding_questions": [
            "¿Qué categoría de producto? (ej: 'ratones gaming')",
            "Define los rangos de precio EXACTOS (ej: <30€, 30-60€, 60-100€, >100€)",
            "¿Cuál es el MEJOR producto en cada rango? (URLs):",
            "¿Hay ofertas o descuentos ACTIVOS en alguno de estos productos?",
            "¿En qué rango está el 'sweet spot' o mejor equilibrio calidad-precio?",
            "¿Merece la pena pagar el premium o con gama media es suficiente?",
            "¿Hay productos que parecen baratos pero son mala compra? ¿Cuáles evitar?"
        ],
        "default_length": 1600,
        "min_length": 1000,
        "max_length": 2500,
        "visual_elements": ["toc", "table", "callout"],
        "campos_especificos": ["categoria", "rangos_precio", "productos_por_rango", "sweet_spot"]
    },
    
    "ARQ-10": {
        "code": "ARQ-10",
        "name": "Productos para Perfil Específico",
        "description": "Selección de productos ideales para un perfil de usuario concreto (gamers, profesionales, etc.).",
        "tone": "Personalizado, empático y especializado",
        "keywords": ["para gamers", "para profesionales", "para estudiantes", "ideal para"],
        "structure": [
            "Introducción al perfil de usuario",
            "Necesidades específicas del perfil",
            "Productos recomendados",
            "Setup o configuración ideal",
            "Errores a evitar",
            "FAQs del perfil",
            "Conclusión y kit recomendado"
        ],
        "guiding_questions": [
            "¿Qué perfil de usuario es el objetivo? (descríbelo: edad, ocupación, necesidades)",
            "¿Cuáles son las 3-5 necesidades PRINCIPALES de este perfil?",
            "¿Qué presupuesto típico tiene este perfil? (rango realista)",
            "¿Qué productos son IMPRESCINDIBLES para este perfil? (URLs)",
            "¿Qué productos son opcionales pero recomendados?",
            "¿Qué errores comete este perfil al comprar? (ej: 'los estudiantes compran portátiles gaming pesados cuando necesitan ultrabooks')",
            "¿Hay un 'kit completo' o setup ideal que podamos recomendar?",
            "¿Este perfil tiene necesidades especiales? (ej: portabilidad, silencio, estética)"
        ],
        "default_length": 1700,
        "min_length": 1200,
        "max_length": 2600,
        "visual_elements": ["toc", "callout", "grid"],
        "campos_especificos": ["perfil_usuario", "necesidades", "presupuesto_tipico", "kit_recomendado"]
    },
    
    # -------------------------------------------------------------------------
    # ARQ-11 a ARQ-15: Arquetipos Técnicos y de Problema/Solución
    # -------------------------------------------------------------------------
    
    "ARQ-11": {
        "code": "ARQ-11",
        "name": "Solución de Problemas / Troubleshooting",
        "description": "Guía para diagnosticar y resolver problemas técnicos comunes.",
        "tone": "Técnico, metódico y orientado a soluciones",
        "keywords": ["problema", "solución", "error", "no funciona", "cómo arreglar"],
        "structure": [
            "Descripción del problema",
            "Causas comunes",
            "Diagnóstico paso a paso",
            "Soluciones ordenadas por probabilidad",
            "Cuándo buscar ayuda profesional",
            "FAQs relacionadas",
            "Prevención futura"
        ],
        "guiding_questions": [
            "¿Qué problema ESPECÍFICO se aborda? (describe el síntoma exacto)",
            "¿Cuáles son las 3-5 causas más frecuentes de este problema? (ordénalas por probabilidad)",
            "¿Qué nivel técnico necesita el usuario para aplicar las soluciones? (cualquiera puede / necesita conocimientos básicos / requiere experiencia)",
            "¿Hay riesgos al intentar solucionarlo? (pérdida de datos, dañar hardware, etc.)",
            "¿Cuándo debe el usuario PARAR y buscar ayuda profesional?",
            "¿Hay productos que ayuden a prevenir o solucionar el problema? (URLs)",
            "¿Cómo puede el usuario PREVENIR este problema en el futuro?"
        ],
        "default_length": 1500,
        "min_length": 1000,
        "max_length": 2200,
        "visual_elements": ["toc", "callout"],
        "campos_especificos": ["problema", "causas", "nivel_tecnico", "riesgos", "productos_solucion"]
    },
    
    "ARQ-12": {
        "code": "ARQ-12",
        "name": "Especificaciones Técnicas Explicadas",
        "description": "Explicación de especificaciones técnicas de forma accesible para el usuario.",
        "tone": "Técnico pero accesible, educativo",
        "keywords": ["especificaciones", "qué significa", "explicación técnica"],
        "structure": [
            "Introducción a las especificaciones",
            "Glosario de términos",
            "Explicación de cada especificación",
            "Cómo afecta al rendimiento",
            "Valores recomendados según uso",
            "FAQs técnicas",
            "Conclusión"
        ],
        "guiding_questions": [
            "¿Qué tipo de producto o tecnología se explica? (ej: 'especificaciones de monitores')",
            "¿Cuáles son las 5-8 especificaciones MÁS confusas para el usuario?",
            "Para cada especificación: ¿qué valores son malos / aceptables / buenos / excelentes?",
            "¿Hay mitos o malentendidos comunes? (ej: 'más Hz siempre es mejor')",
            "¿Qué especificación es la MÁS importante según el uso? (gaming vs trabajo vs casual)",
            "¿Hay especificaciones 'marketing' que no importan realmente?",
            "¿Puedes dar ejemplos de productos con buenas/malas specs? (URLs)"
        ],
        "default_length": 1600,
        "min_length": 1000,
        "max_length": 2500,
        "visual_elements": ["toc", "table", "callout"],
        "campos_especificos": ["tipo_producto", "specs_principales", "mitos_comunes", "spec_mas_importante"]
    },
    
    "ARQ-13": {
        "code": "ARQ-13",
        "name": "Configuración y Setup",
        "description": "Guía de configuración inicial o setup de un producto o sistema.",
        "tone": "Práctico, detallado y paso a paso",
        "keywords": ["configurar", "setup", "instalación", "primeros pasos"],
        "structure": [
            "Qué necesitas antes de empezar",
            "Unboxing y contenido",
            "Instalación física/software",
            "Configuración inicial",
            "Configuración avanzada (opcional)",
            "Prueba de funcionamiento",
            "Solución de problemas comunes",
            "FAQs de configuración"
        ],
        "guiding_questions": [
            "¿Qué producto o sistema se configura? (URL si aplica)",
            "¿Qué conocimientos previos necesita el usuario? (ninguno / básicos de PC / avanzados)",
            "¿Qué materiales o herramientas adicionales necesita? (cables, adaptadores, etc.)",
            "¿Cuánto tiempo lleva la configuración completa? (aproximado)",
            "¿Cuáles son los 3 errores más comunes durante la configuración?",
            "¿Hay pasos donde el usuario suele atascarse? ¿Cómo lo solucionamos?",
            "¿Hay configuraciones 'ocultas' o avanzadas que mejoran la experiencia?",
            "¿Qué debe hacer el usuario para verificar que todo funciona correctamente?"
        ],
        "default_length": 1800,
        "min_length": 1200,
        "max_length": 2800,
        "visual_elements": ["toc", "check_list", "callout"],
        "campos_especificos": ["producto", "tiempo_setup", "requisitos", "errores_comunes"]
    },
    
    "ARQ-14": {
        "code": "ARQ-14",
        "name": "Optimización y Mejora",
        "description": "Guía para optimizar el rendimiento o mejorar un producto/sistema existente.",
        "tone": "Experto, orientado a resultados",
        "keywords": ["optimizar", "mejorar", "rendimiento", "tips"],
        "structure": [
            "Estado actual vs potencial",
            "Diagnóstico de rendimiento",
            "Optimizaciones rápidas",
            "Mejoras intermedias",
            "Mejoras avanzadas",
            "Medición de resultados",
            "FAQs de optimización",
            "Conclusión y mantenimiento"
        ],
        "guiding_questions": [
            "¿Qué se quiere optimizar exactamente? (ej: 'rendimiento en juegos del PC')",
            "¿Cuál es el problema o limitación actual que experimenta el usuario?",
            "¿Qué mejora REALISTA puede esperar el usuario? (ej: '+20% FPS', 'arranque 50% más rápido')",
            "¿Hay optimizaciones GRATUITAS (solo configuración) que pueda hacer?",
            "¿Hay optimizaciones que requieren COMPRAR algo? (URLs de productos)",
            "¿Qué optimizaciones son 'mitos' que no funcionan realmente?",
            "¿Cómo puede el usuario MEDIR si la optimización funcionó?",
            "¿Hay riesgos en alguna de las optimizaciones? (ej: overclocking)"
        ],
        "default_length": 1700,
        "min_length": 1200,
        "max_length": 2600,
        "visual_elements": ["toc", "callout", "table"],
        "campos_especificos": ["objetivo_optimizacion", "mejora_esperada", "productos_upgrade", "metricas"]
    },
    
    "ARQ-15": {
        "code": "ARQ-15",
        "name": "Mantenimiento y Cuidados",
        "description": "Guía de mantenimiento preventivo y cuidados para alargar la vida útil de productos.",
        "tone": "Práctico, preventivo y cuidadoso",
        "keywords": ["mantenimiento", "cuidados", "limpieza", "vida útil"],
        "structure": [
            "Importancia del mantenimiento",
            "Mantenimiento diario/semanal",
            "Mantenimiento mensual",
            "Mantenimiento anual",
            "Señales de problemas",
            "Productos de limpieza recomendados",
            "FAQs de mantenimiento",
            "Calendario de mantenimiento"
        ],
        "guiding_questions": [
            "¿Qué producto o tipo de producto requiere mantenimiento?",
            "¿Con qué frecuencia debe hacerse cada tipo de mantenimiento?",
            "¿Qué herramientas o productos de limpieza se necesitan? (URLs de PcC)",
            "¿Qué señales indican que el producto necesita mantenimiento URGENTE?",
            "¿Qué errores de mantenimiento pueden DAÑAR el producto?",
            "¿Cuánto puede alargar la vida útil un buen mantenimiento? (estimación)",
            "¿Hay mantenimientos que requieren ayuda profesional?"
        ],
        "default_length": 1400,
        "min_length": 900,
        "max_length": 2000,
        "visual_elements": ["toc", "callout", "table"],
        "campos_especificos": ["producto", "frecuencia_mantenimiento", "productos_limpieza"]
    },
    
    # -------------------------------------------------------------------------
    # ARQ-16 a ARQ-20: Arquetipos de Tendencias y Actualidad
    # -------------------------------------------------------------------------
    
    "ARQ-16": {
        "code": "ARQ-16",
        "name": "Novedades y Lanzamientos",
        "description": "Cobertura de nuevos productos, lanzamientos o actualizaciones importantes.",
        "tone": "Entusiasta, informativo y actualizado",
        "keywords": ["nuevo", "lanzamiento", "2025", "última versión"],
        "structure": [
            "Anuncio del lanzamiento",
            "Características principales",
            "Comparación con versión anterior",
            "Precio y disponibilidad",
            "Primeras impresiones",
            "¿Merece la pena actualizar?",
            "FAQs del lanzamiento",
            "Conclusión"
        ],
        "guiding_questions": [
            "¿Qué producto se ha lanzado exactamente? (nombre completo y URL si ya está en PcC)",
            "¿Cuáles son las 3-5 novedades PRINCIPALES vs la versión anterior?",
            "¿Cuál es el precio de lanzamiento? ¿Es competitivo?",
            "¿Cuándo estará disponible en PcC? (fecha exacta si se sabe)",
            "¿Merece la pena actualizar desde la versión anterior? ¿Para quién sí/no?",
            "¿Hay alternativas de la competencia a considerar?",
            "¿Hay preventa o lista de espera en PcC?",
            "¿Qué dicen las primeras reviews o impresiones?"
        ],
        "default_length": 1500,
        "min_length": 1000,
        "max_length": 2200,
        "visual_elements": ["toc"],
        "campos_especificos": ["producto_nuevo", "fecha_lanzamiento", "precio", "mejoras_clave"]
    },
    
    "ARQ-17": {
        "code": "ARQ-17",
        "name": "Tendencias del Sector",
        "description": "Análisis de tendencias actuales y futuras en el sector tecnológico.",
        "tone": "Analítico, visionario e informado",
        "keywords": ["tendencias", "futuro", "2025", "hacia dónde va"],
        "structure": [
            "Estado actual del sector",
            "Tendencias emergentes",
            "Tecnologías a vigilar",
            "Impacto en el consumidor",
            "Predicciones a corto/medio plazo",
            "Cómo prepararse",
            "FAQs sobre tendencias",
            "Conclusión"
        ],
        "guiding_questions": [
            "¿Qué sector o tecnología se analiza? (ej: 'IA en gaming', 'almacenamiento SSD')",
            "¿Cuáles son las 3-5 tendencias más relevantes AHORA?",
            "¿Qué impacto tendrán estas tendencias en el usuario medio?",
            "¿Hay productos ACTUALES en PcC que ya incorporan estas tendencias? (URLs)",
            "¿Qué productos quedarán obsoletos por estas tendencias?",
            "¿Cuándo se espera que estas tendencias sean mainstream?",
            "¿Cuál es el consejo de timing de compra según perfil? (necesidad urgente / puede esperar / debería esperar)"
        ],
        "default_length": 1600,
        "min_length": 1000,
        "max_length": 2400,
        "visual_elements": ["toc", "callout"],
        "campos_especificos": ["sector", "tendencias_principales", "productos_tendencia"]
    },
    
    "ARQ-18": {
        "code": "ARQ-18",
        "name": "Eventos y Ferias Tech",
        "description": "Cobertura de eventos tecnológicos, ferias y presentaciones importantes.",
        "tone": "Periodístico, informativo y emocionante",
        "keywords": ["CES", "MWC", "evento", "feria", "presentación"],
        "structure": [
            "Qué es el evento",
            "Novedades más destacadas",
            "Análisis por categoría",
            "Sorpresas y decepciones",
            "Impacto para el consumidor",
            "Cuándo llegarán los productos",
            "FAQs del evento",
            "Resumen final"
        ],
        "guiding_questions": [
            "¿Qué evento se cubre? (nombre, fechas, ubicación)",
            "¿Cuáles fueron los 5-10 anuncios más importantes?",
            "¿Qué productos llegarán a PcComponentes? (estimación de fechas)",
            "¿Hubo sorpresas inesperadas o decepciones?",
            "¿Qué marcas presentes en PcC tuvieron anuncios relevantes?",
            "¿Hay productos que se pueden reservar ya en PcC?",
            "¿Qué tendencias del evento afectarán al mercado español?"
        ],
        "default_length": 1800,
        "min_length": 1200,
        "max_length": 3000,
        "visual_elements": ["toc", "grid", "callout"],
        "campos_especificos": ["evento", "fecha", "marcas_destacadas", "productos_destacados"]
    },
    
    "ARQ-19": {
        "code": "ARQ-19",
        "name": "Ofertas y Promociones",
        "description": "Contenido sobre ofertas, descuentos y promociones especiales.",
        "tone": "Urgente, atractivo y orientado a la acción",
        "keywords": ["oferta", "descuento", "promoción", "Black Friday", "rebajas"],
        "structure": [
            "Resumen de la promoción",
            "Mejores ofertas destacadas",
            "Ofertas por categoría",
            "Cómo aprovechar al máximo",
            "Productos que merece la pena comprar",
            "Fechas y condiciones",
            "FAQs de la promoción",
            "Conclusión y llamada a la acción"
        ],
        "guiding_questions": [
            "¿Qué promoción o evento de ofertas es? (nombre exacto)",
            "¿Fechas EXACTAS de inicio y fin?",
            "¿Cuáles son las 5-10 mejores ofertas? (URLs con precio antes/después)",
            "¿Hay códigos de descuento adicionales? ¿Cuáles?",
            "¿Hay límite de stock en alguna oferta?",
            "¿Hay ofertas flash con horarios específicos?",
            "¿Envío gratis? ¿A partir de qué importe?",
            "¿Qué productos NO están en oferta pero la gente cree que sí?",
            "¿Se puede financiar? ¿Condiciones?"
        ],
        "default_length": 1500,
        "min_length": 1000,
        "max_length": 2500,
        "visual_elements": ["toc", "callout_promo", "grid", "badges"],
        "campos_especificos": ["tipo_promocion", "fechas_exactas", "mejores_ofertas", "codigos_descuento"]
    },
    
    "ARQ-20": {
        "code": "ARQ-20",
        "name": "Black Friday / Cyber Monday",
        "description": "Contenido especializado para las campañas de Black Friday y Cyber Monday.",
        "tone": "Urgente, emocionante y orientado a ofertas",
        "keywords": ["Black Friday", "Cyber Monday", "ofertas", "descuentos"],
        "structure": [
            "Fechas y horarios importantes",
            "Cómo prepararse",
            "Top ofertas destacadas",
            "Mejores ofertas por categoría",
            "Ofertas flash y exclusivas",
            "Consejos para comprar",
            "FAQs Black Friday",
            "Actualización en tiempo real"
        ],
        "guiding_questions": [
            "¿Fechas EXACTAS del Black Friday en PcComponentes? (inicio, fin, Cyber Monday)",
            "¿Cuáles son las ofertas ESTRELLA? (los 10 productos con mejor descuento - URLs)",
            "¿Hay ofertas EXCLUSIVAS de PcComponentes?",
            "¿Hay ofertas flash programadas? (horarios si se saben)",
            "¿Qué categorías tienen mejores descuentos este año?",
            "¿Hay límites de stock? ¿Productos que se agotarán rápido?",
            "¿Se pueden combinar ofertas con códigos de descuento?",
            "¿Hay financiación especial para Black Friday?",
            "¿Política de devoluciones especial?",
            "¿Consejos para no perderse las mejores ofertas?"
        ],
        "default_length": 2000,
        "min_length": 1500,
        "max_length": 4000,
        "visual_elements": ["toc", "callout_promo", "grid", "verdict"],
        "campos_especificos": ["fechas_bf", "ofertas_estrella", "ofertas_flash", "categorias_destacadas"]
    },
    
    # -------------------------------------------------------------------------
    # ARQ-21 a ARQ-25: Arquetipos de Gaming y Entretenimiento
    # -------------------------------------------------------------------------
    
    "ARQ-21": {
        "code": "ARQ-21",
        "name": "Setup Gaming Completo",
        "description": "Guía para montar un setup gaming completo con todos los componentes necesarios.",
        "tone": "Gamer, entusiasta y detallado",
        "keywords": ["setup gaming", "PC gaming", "configuración gamer"],
        "structure": [
            "Objetivos del setup",
            "Presupuesto y prioridades",
            "Componentes esenciales",
            "Periféricos recomendados",
            "Setup de escritorio y ergonomía",
            "Configuración de software",
            "Upgrades futuros",
            "FAQs de setup gaming",
            "Setup final recomendado"
        ],
        "guiding_questions": [
            "¿Cuál es el presupuesto TOTAL disponible? (rango)",
            "¿Qué juegos ESPECÍFICOS quiere jugar? (nombra 3-5 títulos)",
            "¿Qué resolución y FPS objetivo? (1080p/60fps, 1440p/144fps, 4K/60fps, etc.)",
            "¿El usuario ya tiene algún componente que reutilizar? (monitor, teclado, etc.)",
            "¿Prefiere AMD o NVIDIA/Intel? ¿O le da igual?",
            "¿Tiene requisitos especiales? (poco ruido, tamaño compacto, RGB, estética)",
            "¿Necesita WiFi o tiene conexión Ethernet?",
            "¿Va a hacer streaming o solo jugar?",
            "Lista los componentes ESPECÍFICOS recomendados (URLs de PcC):"
        ],
        "default_length": 2200,
        "min_length": 1500,
        "max_length": 3500,
        "visual_elements": ["toc", "table", "grid", "callout"],
        "campos_especificos": ["presupuesto", "juegos_objetivo", "resolucion_fps", "componentes_recomendados"]
    },
    
    "ARQ-22": {
        "code": "ARQ-22",
        "name": "Requisitos de Videojuegos",
        "description": "Análisis de requisitos de hardware para videojuegos específicos.",
        "tone": "Técnico, práctico y gamer",
        "keywords": ["requisitos", "specs mínimas", "recomendados", "fps"],
        "structure": [
            "Sobre el juego",
            "Requisitos mínimos oficiales",
            "Requisitos recomendados",
            "Requisitos para 4K/Ultra",
            "Configuraciones de hardware probadas",
            "Optimización de ajustes gráficos",
            "FAQs de rendimiento",
            "Hardware recomendado"
        ],
        "guiding_questions": [
            "¿Qué juego ESPECÍFICO se analiza?",
            "¿Cuáles son los requisitos OFICIALES? (mínimos y recomendados)",
            "¿Qué hardware REAL consigue 60fps estables en cada calidad? (fuentes: benchmarks propios, TechPowerUp, Hardware Unboxed, Digital Foundry, etc.)",
            "¿El juego tiene problemas de optimización conocidos?",
            "¿Qué ajustes gráficos tienen más impacto en rendimiento?",
            "¿Hay configuraciones 'trampa' que mejoran FPS sin perder calidad visual?",
            "¿Qué GPUs/CPUs recomendamos de PcC para este juego? (URLs por rango de precio)"
        ],
        "default_length": 1400,
        "min_length": 900,
        "max_length": 2000,
        "visual_elements": ["toc", "table", "callout"],
        "campos_especificos": ["juego", "requisitos_minimos", "requisitos_recomendados", "hardware_recomendado"]
    },
    
    "ARQ-23": {
        "code": "ARQ-23",
        "name": "Streaming y Creación de Contenido",
        "description": "Guía para equipamiento de streaming y creación de contenido digital.",
        "tone": "Creativo, técnico y práctico",
        "keywords": ["streaming", "YouTube", "Twitch", "creador de contenido"],
        "structure": [
            "Tipos de creación de contenido",
            "Equipamiento esencial",
            "Software recomendado",
            "Configuración de OBS/streaming",
            "Iluminación y sonido",
            "Upgrades según crecimiento",
            "FAQs para streamers",
            "Kit recomendado por nivel"
        ],
        "guiding_questions": [
            "¿Qué tipo de contenido va a crear? (gaming, vlogs, tutoriales, podcasts, etc.)",
            "¿En qué plataforma principalmente? (Twitch, YouTube, TikTok, etc.)",
            "¿Cuál es el presupuesto inicial?",
            "¿Es principiante total o ya tiene algo de experiencia/equipo?",
            "¿Necesita cámara? ¿Facecam o solo pantalla?",
            "¿Qué calidad de audio necesita? (micrófono básico vs profesional)",
            "¿Necesita iluminación? ¿Tiene luz natural?",
            "Lista el kit ESPECÍFICO recomendado por nivel (URLs de PcC):"
        ],
        "default_length": 1800,
        "min_length": 1200,
        "max_length": 2800,
        "visual_elements": ["toc", "callout", "grid"],
        "campos_especificos": ["tipo_contenido", "plataforma", "presupuesto", "kit_recomendado"]
    },
    
    "ARQ-24": {
        "code": "ARQ-24",
        "name": "Periféricos Gaming",
        "description": "Guía especializada en periféricos gaming: teclados, ratones, auriculares, etc.",
        "tone": "Gamer experto, detallado",
        "keywords": ["teclado gaming", "ratón gaming", "auriculares gaming", "periféricos"],
        "structure": [
            "Importancia de los periféricos",
            "Tipos de periféricos",
            "Características clave por periférico",
            "Mejores opciones por presupuesto",
            "Combinaciones recomendadas",
            "FAQs de periféricos",
            "Setup recomendado"
        ],
        "guiding_questions": [
            "¿Qué periférico específico se cubre? (ratón / teclado / auriculares / alfombrilla / todos)",
            "¿Para qué tipo de juegos? (FPS competitivo, MMO, casual, etc.)",
            "¿Cuáles son las 3-5 características CLAVE que debe tener?",
            "¿Hay tecnologías específicas importantes? (switches, sensores, drivers, etc.)",
            "¿Cable o inalámbrico? ¿Pros y contras?",
            "¿Cuál es la mejor opción en cada rango de precio? (URLs)",
            "¿Hay marcas especialmente recomendadas para gaming?",
            "¿Qué combinación de periféricos recomiendas como setup completo?"
        ],
        "default_length": 1600,
        "min_length": 1000,
        "max_length": 2400,
        "visual_elements": ["toc", "table", "callout"],
        "campos_especificos": ["tipo_periferico", "caracteristicas_clave", "productos_recomendados"]
    },
    
    "ARQ-25": {
        "code": "ARQ-25",
        "name": "Consolas y Gaming Portátil",
        "description": "Contenido sobre consolas de videojuegos y gaming portátil.",
        "tone": "Gamer, comparativo y actualizado",
        "keywords": ["PS5", "Xbox", "Nintendo Switch", "Steam Deck", "consola"],
        "structure": [
            "Panorama actual de consolas",
            "Comparativa de consolas",
            "Juegos exclusivos",
            "Accesorios recomendados",
            "Gaming portátil",
            "¿Qué consola elegir?",
            "FAQs de consolas",
            "Recomendación final"
        ],
        "guiding_questions": [
            "¿Qué consolas o dispositivos se comparan/analizan?",
            "¿Cuáles son los juegos EXCLUSIVOS más relevantes de cada una?",
            "¿Qué accesorios son imprescindibles? (URLs de PcC)",
            "¿Para qué tipo de jugador es cada opción? (casual, hardcore, familiar, etc.)",
            "¿Hay bundles o packs especiales disponibles en PcC?",
            "¿Cuál tiene mejor relación calidad-precio actualmente?",
            "¿Hay modelo nuevo próximo que recomiende esperar?"
        ],
        "default_length": 1700,
        "min_length": 1100,
        "max_length": 2600,
        "visual_elements": ["toc", "comparison_table", "verdict"],
        "campos_especificos": ["consolas", "juegos_exclusivos", "accesorios_recomendados"]
    },
    
    # -------------------------------------------------------------------------
    # ARQ-26 a ARQ-30: Arquetipos Profesionales y de Productividad
    # -------------------------------------------------------------------------
    
    "ARQ-26": {
        "code": "ARQ-26",
        "name": "Workstation Profesional",
        "description": "Guía para configurar estaciones de trabajo profesionales.",
        "tone": "Profesional, técnico y orientado a productividad",
        "keywords": ["workstation", "profesional", "edición", "renderizado", "CAD"],
        "structure": [
            "Tipos de trabajo profesional",
            "Requisitos por disciplina",
            "Componentes clave",
            "Configuraciones recomendadas",
            "Software y optimización",
            "Ergonomía y espacio de trabajo",
            "FAQs profesionales",
            "Setup recomendado por disciplina"
        ],
        "guiding_questions": [
            "¿Qué tipo de trabajo profesional se realizará? (edición vídeo, 3D, CAD, desarrollo, etc.)",
            "¿Qué software ESPECÍFICO se utilizará? (Premiere, DaVinci, Blender, AutoCAD, etc.)",
            "¿Cuál es el presupuesto disponible?",
            "¿Hay requisitos específicos del sector? (certificaciones, drivers especiales, etc.)",
            "¿Necesita GPU profesional (Quadro/ProArt) o vale gaming?",
            "¿Cuánta RAM y almacenamiento necesita según su flujo de trabajo?",
            "¿Trabaja con archivos muy grandes? (vídeo 4K/8K, proyectos 3D complejos)",
            "Lista la configuración ESPECÍFICA recomendada (URLs de PcC):"
        ],
        "default_length": 2000,
        "min_length": 1400,
        "max_length": 3000,
        "visual_elements": ["toc", "table", "callout"],
        "campos_especificos": ["disciplina", "software_principal", "presupuesto", "configuracion_recomendada"]
    },
    
    "ARQ-27": {
        "code": "ARQ-27",
        "name": "Teletrabajo y Home Office",
        "description": "Guía para equipar un espacio de teletrabajo productivo.",
        "tone": "Práctico, ergonómico y orientado al bienestar",
        "keywords": ["teletrabajo", "home office", "trabajo desde casa", "oficina en casa"],
        "structure": [
            "Importancia de un buen setup",
            "Espacio y mobiliario",
            "Tecnología esencial",
            "Conectividad y red",
            "Ergonomía y salud",
            "Productividad y organización",
            "FAQs de home office",
            "Kit recomendado por presupuesto"
        ],
        "guiding_questions": [
            "¿Cuántas horas al día trabaja desde casa?",
            "¿Qué tipo de trabajo realiza? (videollamadas, programación, diseño, administrativo, etc.)",
            "¿Cuál es el espacio disponible? (habitación dedicada, rincón del salón, etc.)",
            "¿Necesita hacer muchas videoconferencias? ¿Con qué calidad?",
            "¿Tiene problemas de espalda o ergonómicos actuales?",
            "¿Necesita monitor extra, dock station, etc.?",
            "¿Tiene buena conexión a internet o necesita mejorarla?",
            "¿Cuál es el presupuesto? Lista kit recomendado (URLs):"
        ],
        "default_length": 1600,
        "min_length": 1000,
        "max_length": 2400,
        "visual_elements": ["toc", "callout", "grid"],
        "campos_especificos": ["tipo_trabajo", "espacio_disponible", "kit_recomendado"]
    },
    
    "ARQ-28": {
        "code": "ARQ-28",
        "name": "Productividad y Software",
        "description": "Guías de software y herramientas para mejorar la productividad.",
        "tone": "Práctico, orientado a resultados",
        "keywords": ["productividad", "software", "herramientas", "aplicaciones"],
        "structure": [
            "Objetivos de productividad",
            "Categorías de herramientas",
            "Software recomendado por categoría",
            "Integraciones útiles",
            "Tips de productividad",
            "FAQs de software",
            "Stack recomendado"
        ],
        "guiding_questions": [
            "¿Qué área de productividad se cubre? (gestión de tareas, notas, automatización, etc.)",
            "¿Qué herramientas se comparan o recomiendan?",
            "¿Hay opciones gratuitas y de pago? ¿Cuáles son las diferencias?",
            "¿Qué integraciones son importantes? (con otras apps, sistemas)",
            "¿Para uso individual o equipo?",
            "¿Hay hardware que mejore la productividad con este software? (URLs)"
        ],
        "default_length": 1500,
        "min_length": 900,
        "max_length": 2200,
        "visual_elements": ["toc", "table", "callout"],
        "campos_especificos": ["area_productividad", "herramientas", "hardware_complementario"]
    },
    
    "ARQ-29": {
        "code": "ARQ-29",
        "name": "Seguridad y Privacidad",
        "description": "Guías sobre seguridad informática, privacidad y protección de datos.",
        "tone": "Serio, informativo y orientado a la protección",
        "keywords": ["seguridad", "privacidad", "antivirus", "protección", "backup"],
        "structure": [
            "Importancia de la seguridad",
            "Amenazas actuales",
            "Medidas básicas de protección",
            "Herramientas de seguridad",
            "Configuración de privacidad",
            "Backup y recuperación",
            "FAQs de seguridad",
            "Checklist de seguridad"
        ],
        "guiding_questions": [
            "¿Qué aspecto de seguridad se aborda? (antivirus, backup, VPN, contraseñas, etc.)",
            "¿Es para usuario doméstico o empresa/profesional?",
            "¿Cuáles son las amenazas más relevantes ACTUALMENTE?",
            "¿Qué productos o software de seguridad recomiendas? (URLs si aplica)",
            "¿Hay medidas GRATUITAS efectivas que pueda tomar?",
            "¿Qué errores comunes de seguridad comete la gente?",
            "¿Cómo puede verificar el usuario que está protegido?"
        ],
        "default_length": 1600,
        "min_length": 1000,
        "max_length": 2400,
        "visual_elements": ["toc", "callout", "table"],
        "campos_especificos": ["aspecto_seguridad", "nivel_usuario", "productos_recomendados"]
    },
    
    "ARQ-30": {
        "code": "ARQ-30",
        "name": "Redes y Conectividad",
        "description": "Guías sobre redes domésticas, WiFi, NAS y conectividad.",
        "tone": "Técnico accesible, práctico",
        "keywords": ["WiFi", "router", "red", "NAS", "conectividad"],
        "structure": [
            "Fundamentos de redes domésticas",
            "Tipos de conexión",
            "Equipamiento necesario",
            "Configuración paso a paso",
            "Optimización de la red",
            "Solución de problemas comunes",
            "FAQs de redes",
            "Setup recomendado"
        ],
        "guiding_questions": [
            "¿Qué aspecto de redes se cubre? (WiFi, router, mesh, NAS, PLC, etc.)",
            "¿Tamaño del hogar/oficina? (m² aproximados)",
            "¿Cuántos dispositivos se conectarán simultáneamente?",
            "¿Hay requisitos especiales? (gaming sin lag, streaming 4K, trabajo remoto, etc.)",
            "¿Tiene zonas con mala cobertura WiFi actualmente?",
            "¿Qué velocidad de internet tiene contratada?",
            "Lista los productos ESPECÍFICOS recomendados (URLs de PcC):"
        ],
        "default_length": 1700,
        "min_length": 1100,
        "max_length": 2600,
        "visual_elements": ["toc", "callout", "table"],
        "campos_especificos": ["tipo_red", "tamano_espacio", "num_dispositivos", "productos_recomendados"]
    },
    
    # -------------------------------------------------------------------------
    # ARQ-31 a ARQ-34: Arquetipos Especiales y de Nicho
    # -------------------------------------------------------------------------
    
    "ARQ-31": {
        "code": "ARQ-31",
        "name": "Hogar Inteligente / Smart Home",
        "description": "Guías sobre domótica, dispositivos inteligentes y automatización del hogar.",
        "tone": "Moderno, práctico y orientado al futuro",
        "keywords": ["smart home", "domótica", "hogar inteligente", "automatización"],
        "structure": [
            "Qué es un hogar inteligente",
            "Ecosistemas disponibles",
            "Dispositivos esenciales",
            "Configuración e integración",
            "Automatizaciones útiles",
            "Seguridad del smart home",
            "FAQs de domótica",
            "Kit de inicio recomendado"
        ],
        "guiding_questions": [
            "¿Qué ecosistema usa o prefiere el usuario? (Alexa, Google Home, HomeKit, Zigbee, etc.)",
            "¿Qué aspectos del hogar quiere automatizar? (iluminación, clima, seguridad, etc.)",
            "¿Cuál es el presupuesto inicial?",
            "¿Vive en piso propio o alquiler? (afecta a instalaciones permanentes)",
            "¿Tiene hub central o empieza desde cero?",
            "¿Qué automatizaciones le serían más útiles en su día a día?",
            "¿Hay requisitos de compatibilidad con dispositivos que ya tiene?",
            "Lista el kit de inicio ESPECÍFICO (URLs de PcC):"
        ],
        "default_length": 1800,
        "min_length": 1200,
        "max_length": 2800,
        "visual_elements": ["toc", "callout", "grid"],
        "campos_especificos": ["ecosistema", "areas_automatizar", "presupuesto", "kit_inicio"]
    },
    
    "ARQ-32": {
        "code": "ARQ-32",
        "name": "Fotografía y Vídeo",
        "description": "Guías sobre equipamiento fotográfico, cámaras y producción de vídeo.",
        "tone": "Creativo, técnico y visual",
        "keywords": ["cámara", "fotografía", "vídeo", "objetivos", "accesorios foto"],
        "structure": [
            "Tipos de fotografía/vídeo",
            "Equipamiento por nivel",
            "Cámaras recomendadas",
            "Objetivos y accesorios",
            "Iluminación y sonido",
            "Post-producción",
            "FAQs de foto/vídeo",
            "Kit recomendado"
        ],
        "guiding_questions": [
            "¿Fotografía, vídeo o ambos?",
            "¿Qué nivel tiene? (principiante, aficionado avanzado, profesional)",
            "¿Qué tipo de contenido creará? (retratos, paisajes, productos, eventos, etc.)",
            "¿Presupuesto disponible?",
            "¿Ya tiene equipo previo? ¿Qué sistema/montura?",
            "¿Necesita equipo de iluminación o audio?",
            "¿Portabilidad importante o puede cargar equipo pesado?",
            "Lista el kit ESPECÍFICO recomendado (URLs de PcC):"
        ],
        "default_length": 1800,
        "min_length": 1200,
        "max_length": 2800,
        "visual_elements": ["toc", "table", "callout"],
        "campos_especificos": ["tipo_contenido", "nivel", "presupuesto", "kit_recomendado"]
    },
    
    "ARQ-33": {
        "code": "ARQ-33",
        "name": "Movilidad y Gadgets",
        "description": "Guías sobre smartphones, tablets, wearables y gadgets tecnológicos.",
        "tone": "Moderno, práctico y orientado a tendencias",
        "keywords": ["smartphone", "tablet", "smartwatch", "gadgets", "wearables"],
        "structure": [
            "Panorama actual del mercado",
            "Tipos de dispositivos",
            "Características clave",
            "Comparativa de opciones",
            "Accesorios recomendados",
            "Integración con otros dispositivos",
            "FAQs de movilidad",
            "Recomendaciones finales"
        ],
        "guiding_questions": [
            "¿Qué tipo de dispositivo móvil? (smartphone, tablet, smartwatch, auriculares TWS, etc.)",
            "¿Ecosistema preferido? (iOS/Apple, Android/Samsung, Android/Xiaomi, etc.)",
            "¿Uso principal del dispositivo? (trabajo, entretenimiento, deporte, etc.)",
            "¿Rango de precio?",
            "¿Hay características imprescindibles? (cámara, batería, pantalla, etc.)",
            "¿Compatibilidad necesaria con otros dispositivos?",
            "Lista productos ESPECÍFICOS recomendados (URLs de PcC):"
        ],
        "default_length": 1600,
        "min_length": 1000,
        "max_length": 2400,
        "visual_elements": ["toc", "table", "verdict"],
        "campos_especificos": ["tipo_dispositivo", "ecosistema", "uso_principal", "productos_recomendados"]
    },
    
    "ARQ-34": {
        "code": "ARQ-34",
        "name": "Sostenibilidad y Eficiencia Energética",
        "description": "Contenido sobre tecnología sostenible, eficiencia energética y eco-friendly.",
        "tone": "Consciente, informativo y orientado al impacto positivo",
        "keywords": ["sostenible", "eficiencia energética", "eco-friendly", "consumo"],
        "structure": [
            "Importancia de la sostenibilidad tech",
            "Consumo energético de dispositivos",
            "Productos eficientes recomendados",
            "Tips para reducir consumo",
            "Reciclaje y segunda vida",
            "Certificaciones a buscar",
            "FAQs de sostenibilidad",
            "Conclusión y compromiso"
        ],
        "guiding_questions": [
            "¿Qué aspecto de sostenibilidad se aborda? (eficiencia energética, reciclaje, durabilidad, etc.)",
            "¿Qué categoría de productos?",
            "¿Hay datos concretos de consumo energético a incluir?",
            "¿Qué productos de PcC son especialmente eficientes? (URLs)",
            "¿Qué certificaciones de eficiencia existen? (Energy Star, 80 Plus, etc.)",
            "¿Cómo puede el usuario medir su consumo/impacto?",
            "¿PcC tiene programa de reciclaje o trade-in?"
        ],
        "default_length": 1500,
        "min_length": 1000,
        "max_length": 2200,
        "visual_elements": ["toc", "callout", "table"],
        "campos_especificos": ["aspecto_sostenibilidad", "categoria_productos", "productos_eficientes"]
    },

    # ========================================================================
    # ARQ-35 a ARQ-37: Contenido Externo y Comunicación
    # ========================================================================

    "ARQ-35": {
        "code": "ARQ-35",
        "name": "Nota de Prensa",
        "description": (
            "Comunicado oficial de PcComponentes para medios de comunicación. "
            "Cubre lanzamientos de producto, acuerdos comerciales, hitos corporativos, "
            "campañas especiales y datos de mercado. Formato periodístico estándar con "
            "pirámide invertida: lo más importante primero."
        ),
        "tone": "Institucional, profesional y periodístico. Tercera persona. Sin adjetivos promocionales.",
        "keywords": [
            "nota de prensa", "comunicado", "lanzamiento", "PcComponentes",
            "comunicación corporativa"
        ],
        "structure": [
            "Titular informativo (qué + quién + cuándo)",
            "Subtítulo / bajada con dato clave",
            "Lead: quién, qué, cuándo, dónde, por qué (1 párrafo)",
            "Cuerpo: contexto, cifras, declaraciones entrecomilladas",
            "Datos complementarios / background del mercado",
            "Boilerplate corporativo de PcComponentes",
            "Datos de contacto de prensa",
        ],
        "guiding_questions": [
            "¿Qué tipo de comunicado es? (lanzamiento de producto / acuerdo comercial / hito corporativo / campaña / datos de mercado)",
            "¿Cuál es la noticia principal en una frase?",
            "¿Hay cifras o datos concretos para incluir? (ventas, %, fechas, usuarios)",
            "¿Quién debe aparecer como portavoz? (nombre y cargo para citas entrecomilladas)",
            "¿Qué declaración o quote debe incluirse del portavoz?",
            "¿Hay fecha de embargo o de lanzamiento específica?",
            "¿A qué medios va dirigida? (generalistas, tech, económicos)",
            "¿Hay productos específicos que mencionar? (URLs de PcComponentes)",
            "¿Se debe incluir enlace a sala de prensa o recursos multimedia?",
        ],
        "default_length": 800,
        "min_length": 500,
        "max_length": 1200,
        "visual_elements": [],
        "campos_especificos": [
            "tipo_comunicado",
            "noticia_principal",
            "portavoz_nombre",
            "portavoz_cargo",
            "quote_portavoz",
            "fecha_embargo",
            "contacto_prensa",
        ]
    },

    "ARQ-36": {
        "code": "ARQ-36",
        "name": "Contenido para Web de Afiliados",
        "description": (
            "Artículo optimizado para conversión en webs de afiliación que enlazan a "
            "PcComponentes. Contenido configurable: puede llevar marca PcComponentes "
            "visible o ser white-label. Estructura orientada a resolver la duda del "
            "usuario y guiar hacia la compra con enlaces de afiliado."
        ),
        "tone": (
            "Persuasivo pero honesto. Experto independiente que recomienda con criterio. "
            "Evitar hipérboles. Justificar cada recomendación con datos o experiencia. "
            "Orientado a conversión sin parecer publicitario."
        ),
        "keywords": [
            "mejor", "recomendación", "análisis", "precio",
            "dónde comprar", "merece la pena", "opinión"
        ],
        "structure": [
            "Hook: pregunta o situación con la que el lector se identifique",
            "Tabla resumen rápida (producto + nota + precio + enlace)",
            "Problema o necesidad del lector",
            "Criterios de selección explicados",
            "Análisis de cada producto recomendado (specs + pros/contras + CTA)",
            "Tabla comparativa detallada",
            "¿Cuál elegir? Recomendación por perfil de usuario",
            "FAQs de compra",
            "Veredicto final con CTA principal",
        ],
        "guiding_questions": [
            "¿El contenido lleva marca PcComponentes o es white-label (sin mención)?",
            "¿Qué keyword principal debe posicionar el artículo?",
            "¿Cuántos productos incluir y cuáles? (URLs de PcComponentes)",
            "¿Cuál es el producto 'estrella' que más interesa promover?",
            "¿Hay un rango de precios específico para la audiencia? (budget / gama media / premium)",
            "¿La web de afiliados tiene un nicho concreto? (gaming, hogar, oficina, etc.)",
            "¿Qué formato de enlace de afiliado usar? (texto, botón, tabla)",
            "¿Se deben incluir comparativas con productos de otros retailers?",
            "¿Hay algún cupón o promoción activa para mencionar?",
        ],
        "default_length": 2000,
        "min_length": 1500,
        "max_length": 3500,
        "visual_elements": ["toc", "table", "verdict"],
        "campos_especificos": [
            "modo_marca",
            "keyword_principal",
            "producto_estrella",
            "rango_precios",
            "nicho_web",
            "formato_enlaces",
            "cupon_activo",
        ]
    },

    "ARQ-37": {
        "code": "ARQ-37",
        "name": "Guest Posting",
        "description": (
            "Artículo para publicar en blogs o medios externos con el objetivo de obtener "
            "un backlink hacia PcComponentes. El contenido debe aportar valor real al medio "
            "que lo publica, con mención sutil y contextual de PcComponentes. "
            "Máximo 2-3 menciones naturales + 1 enlace contextual."
        ),
        "tone": (
            "Experto divulgativo. Tono neutral de autor invitado que comparte conocimiento. "
            "Sin lenguaje comercial ni CTAs directos. La mención a PcComponentes debe ser "
            "natural e integrada, como quien cita una fuente autorizada."
        ),
        "keywords": [
            "guía", "cómo", "consejos", "tendencias",
            "tecnología", "explicación"
        ],
        "structure": [
            "Titular atractivo para la audiencia del medio (sin marca)",
            "Introducción: contexto del tema + por qué importa ahora",
            "Desarrollo: contenido de valor puro (datos, consejos, análisis)",
            "Sección donde PcComponentes aporta dato/recurso/ejemplo (mención contextual)",
            "Conclusión con takeaway práctico para el lector",
            "Bio del autor (mención PcComponentes + enlace)",
        ],
        "guiding_questions": [
            "¿En qué medio/blog se va a publicar? (nombre y URL si es posible)",
            "¿Cuál es la temática/audiencia del medio? (generalista tech, nicho gaming, negocio, lifestyle)",
            "¿Qué tema concreto va a tratar el artículo?",
            "¿Qué URL de PcComponentes debe llevar el backlink? (home, categoría, artículo del blog)",
            "¿Cuántas menciones de PcComponentes permite el medio? (1 enlace / 2-3 menciones / solo bio)",
            "¿Hay directrices editoriales del medio a respetar? (longitud, formato, tono)",
            "¿Se publica con autoría de PcComponentes o con un nombre de autor específico?",
            "¿Hay algún dato, estudio o recurso de PcComponentes que se pueda citar como fuente?",
        ],
        "default_length": 1200,
        "min_length": 800,
        "max_length": 2000,
        "visual_elements": [],
        "campos_especificos": [
            "medio_destino",
            "url_medio",
            "tematica_medio",
            "url_backlink",
            "nivel_mencion",
            "nombre_autor",
            "directrices_medio",
        ]
    },
}


# ============================================================================
# FUNCIONES DE ACCESO
# ============================================================================

def get_arquetipo(code: str) -> Optional[Dict[str, Any]]:
    """Obtiene los datos completos de un arquetipo por su código."""
    return ARQUETIPOS.get(code)


def get_arquetipo_names() -> Dict[str, str]:
    """Obtiene un diccionario de código -> nombre para todos los arquetipos."""
    return {code: data["name"] for code, data in ARQUETIPOS.items()}


def get_arquetipo_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Busca un arquetipo por su nombre (búsqueda parcial)."""
    name_lower = name.lower()
    for code, data in ARQUETIPOS.items():
        if name_lower in data["name"].lower():
            return data
    return None


def get_guiding_questions(code: str, include_universal: bool = True) -> List[str]:
    """
    Obtiene las preguntas guía de un arquetipo.
    
    Args:
        code: Código del arquetipo
        include_universal: Si True, incluye las preguntas universales primero
    """
    arquetipo = ARQUETIPOS.get(code)
    if not arquetipo:
        return []
    
    questions = []
    if include_universal:
        questions.extend(PREGUNTAS_UNIVERSALES)
    questions.extend(arquetipo.get("guiding_questions", []))
    
    return questions


def get_universal_questions() -> List[str]:
    """Obtiene las preguntas universales que aplican a todos los arquetipos."""
    return PREGUNTAS_UNIVERSALES.copy()


def get_structure(code: str) -> List[str]:
    """Obtiene la estructura recomendada para un arquetipo."""
    arquetipo = ARQUETIPOS.get(code)
    return arquetipo.get("structure", []) if arquetipo else []


def get_default_length(code: str) -> int:
    """Obtiene la longitud por defecto recomendada para un arquetipo."""
    arquetipo = ARQUETIPOS.get(code)
    return arquetipo.get("default_length", DEFAULT_CONTENT_LENGTH) if arquetipo else DEFAULT_CONTENT_LENGTH


def get_length_range(code: str) -> Tuple[int, int]:
    """Obtiene el rango de longitud permitido para un arquetipo."""
    arquetipo = ARQUETIPOS.get(code)
    if arquetipo:
        return (arquetipo.get("min_length", DEFAULT_MIN_LENGTH), 
                arquetipo.get("max_length", DEFAULT_MAX_LENGTH))
    return (DEFAULT_MIN_LENGTH, DEFAULT_MAX_LENGTH)


def get_visual_elements(code: str) -> List[str]:
    """Obtiene los elementos visuales recomendados para un arquetipo."""
    arquetipo = ARQUETIPOS.get(code)
    return arquetipo.get("visual_elements", []) if arquetipo else []


def get_campos_especificos(code: str) -> List[str]:
    """Obtiene los campos específicos requeridos por un arquetipo."""
    arquetipo = ARQUETIPOS.get(code)
    return arquetipo.get("campos_especificos", []) if arquetipo else []


def get_tone(code: str) -> str:
    """Obtiene el tono recomendado para un arquetipo."""
    arquetipo = ARQUETIPOS.get(code)
    return arquetipo.get("tone", "") if arquetipo else ""


def get_keywords(code: str) -> List[str]:
    """Obtiene las keywords asociadas a un arquetipo."""
    arquetipo = ARQUETIPOS.get(code)
    return arquetipo.get("keywords", []) if arquetipo else []


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def get_all_arquetipo_codes() -> List[str]:
    """Obtiene lista de todos los códigos de arquetipos."""
    return sorted(ARQUETIPOS.keys())


def get_arquetipos_by_category(category_keywords: List[str]) -> List[Dict[str, Any]]:
    """Filtra arquetipos que contengan ciertas keywords."""
    results = []
    category_lower = [kw.lower() for kw in category_keywords]
    
    for code, data in ARQUETIPOS.items():
        arquetipos_keywords = [kw.lower() for kw in data.get("keywords", [])]
        name_lower = data.get("name", "").lower()
        
        if any(cat_kw in name_lower or cat_kw in arquetipos_keywords 
               for cat_kw in category_lower):
            results.append(data)
    
    return results


def format_arquetipo_for_prompt(code: str, include_questions: bool = True) -> str:
    """Formatea la información de un arquetipo para incluir en prompts."""
    arquetipo = ARQUETIPOS.get(code)
    if not arquetipo:
        return f"Arquetipo {code} no encontrado."
    
    lines = [
        f"**Arquetipo**: {arquetipo['name']} ({code})",
        f"**Descripción**: {arquetipo.get('description', '')}",
        f"**Tono**: {arquetipo.get('tone', '')}",
        f"**Longitud objetivo**: {arquetipo.get('default_length', DEFAULT_CONTENT_LENGTH)} palabras",
        "",
        "**Estructura recomendada**:"
    ]
    
    for i, section in enumerate(arquetipo.get("structure", []), 1):
        lines.append(f"  {i}. {section}")
    
    if arquetipo.get("visual_elements"):
        lines.append("")
        lines.append(f"**Elementos visuales**: {', '.join(arquetipo['visual_elements'])}")
    
    return "\n".join(lines)


def validate_arquetipo_code(code: str) -> bool:
    """Valida que un código de arquetipo sea válido."""
    return code in ARQUETIPOS


def get_arquetipo_summary(code: str) -> Dict[str, Any]:
    """Obtiene un resumen compacto de un arquetipo."""
    arquetipo = ARQUETIPOS.get(code)
    if not arquetipo:
        return {"error": f"Arquetipo {code} no encontrado"}
    
    return {
        "code": code,
        "name": arquetipo["name"],
        "description": arquetipo.get("description", ""),
        "tone": arquetipo.get("tone", ""),
        "default_length": arquetipo.get("default_length", DEFAULT_CONTENT_LENGTH),
        "min_length": arquetipo.get("min_length", DEFAULT_MIN_LENGTH),
        "max_length": arquetipo.get("max_length", DEFAULT_MAX_LENGTH),
        "num_sections": len(arquetipo.get("structure", [])),
        "num_questions": len(arquetipo.get("guiding_questions", [])),
        "num_questions_with_universal": len(arquetipo.get("guiding_questions", [])) + len(PREGUNTAS_UNIVERSALES),
        "visual_elements": arquetipo.get("visual_elements", []),
        "campos_especificos": arquetipo.get("campos_especificos", []),
    }


def get_question_stats() -> Dict[str, Any]:
    """Obtiene estadísticas sobre las preguntas guía de todos los arquetipos."""
    total_questions = 0
    min_questions = float('inf')
    max_questions = 0
    
    for code, data in ARQUETIPOS.items():
        num_q = len(data.get("guiding_questions", []))
        total_questions += num_q
        min_questions = min(min_questions, num_q)
        max_questions = max(max_questions, num_q)
    
    num_arquetipos = len(ARQUETIPOS)
    
    return {
        "num_arquetipos": num_arquetipos,
        "num_universal_questions": len(PREGUNTAS_UNIVERSALES),
        "total_specific_questions": total_questions,
        "avg_specific_questions": round(total_questions / num_arquetipos, 1),
        "min_specific_questions": min_questions,
        "max_specific_questions": max_questions,
        "avg_total_questions": round((total_questions / num_arquetipos) + len(PREGUNTAS_UNIVERSALES), 1),
    }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    'DEFAULT_MIN_LENGTH',
    'DEFAULT_MAX_LENGTH', 
    'DEFAULT_CONTENT_LENGTH',
    'PREGUNTAS_UNIVERSALES',
    'ARQUETIPOS',
    'get_arquetipo',
    'get_arquetipo_names',
    'get_arquetipo_by_name',
    'get_guiding_questions',
    'get_universal_questions',
    'get_structure',
    'get_default_length',
    'get_length_range',
    'get_visual_elements',
    'get_campos_especificos',
    'get_tone',
    'get_keywords',
    'get_all_arquetipo_codes',
    'get_arquetipos_by_category',
    'format_arquetipo_for_prompt',
    'validate_arquetipo_code',
    'get_arquetipo_summary',
    'get_question_stats',
]
