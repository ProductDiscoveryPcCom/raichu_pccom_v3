# 🚀 PcComponentes Content Generator

**Versión 5.1.0** | Generador de contenido SEO optimizado con IA

Aplicación Streamlit que genera contenido de alta calidad para PcComponentes usando Claude AI, con análisis competitivo, validación CMS y flujo de 3 etapas para máxima calidad.

---

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Requisitos Previos](#-requisitos-previos)
- [Instalación](#-instalación)
- [Configuración](#️-configuración)
- [Uso](#-uso)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Modos de Generación](#-modos-de-generación)
- [Arquitectura](#️-arquitectura)
- [Desarrollo](#-desarrollo)
- [Troubleshooting](#-troubleshooting)
- [Changelog](#-changelog)
- [Contribuir](#-contribuir)
- [Licencia](#-licencia)

---

## ✨ Características

### 🎯 Generación de Contenido

- **18 Arquetipos predefinidos**: Reviews, guías, comparativas, noticias, etc.
- **Flujo de 3 etapas**: Borrador → Análisis Crítico → Versión Final
- **Validación CMS v4.1.1**: Estructura HTML compatible con el CMS de PcComponentes
- **Control de longitud preciso**: ±5% del objetivo
- **Tono de marca**: Aspiracional, positivo, experto pero cercano

### 🔄 Modo Reescritura Competitiva

- **Análisis automático** de top 5 competidores en Google
- **Identificación de gaps** de contenido
- **Generación mejorada** que supera a la competencia
- **Validación competitiva** en análisis crítico

### 🔍 Validaciones Automáticas

- Estructura HTML CMS-compatible (3 articles)
- Word count y precisión
- Enlaces internos y externos
- Elementos clave (callouts, FAQs, verdict)
- CSS y clases correctas

### 📊 Análisis y Métricas

- Análisis de estructura HTML
- Conteo preciso de palabras
- Validación de enlaces
- Detección de problemas críticos
- Sugerencias de mejora

---

## 🔧 Requisitos Previos

- **Python 3.9+** (recomendado 3.11)
- **API Key de Anthropic** (Claude)
- **Conexión a internet** (para scraping y API calls)
- **(Opcional) Google Search Console API** para verificación de keywords

---

## 📥 Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/content-generator.git
cd content-generator
```

### 2. Crear entorno virtual
```bash
# Linux/Mac
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Copia el archivo de ejemplo y edita con tus credenciales:
```bash
cp .env.example .env
# Editar .env con tu API key de Claude
```

---

## ⚙️ Configuración

### Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:
```bash
# API Keys
ANTHROPIC_API_KEY=tu-api-key-aqui

# Configuración de Claude
CLAUDE_MODEL=claude-sonnet-4-20250514
MAX_TOKENS=8000
TEMPERATURE=0.7

# Configuración de la App
DEBUG_MODE=False
```

### Secrets para Streamlit Cloud

Crear `.streamlit/secrets.toml`:
```toml
[api]
claude_key = "tu-api-key-aqui"

[settings]
debug_mode = false
```

### Configuración de Streamlit

Crear `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#FF6000"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[server]
maxUploadSize = 200
enableXsrfProtection = true
enableCORS = false
```

---

## 🚀 Uso

### Ejecución Local
```bash
streamlit run app.py
```

La aplicación se abrirá en `http://localhost:8501`

### Despliegue en Streamlit Cloud

1. Push del código a GitHub
2. Conectar repositorio en [share.streamlit.io](https://share.streamlit.io)
3. Configurar secrets en Settings > Secrets
4. Deploy automático

---

## 📁 Estructura del Proyecto
```
content-generator-mvp/
├── app.py                          # Aplicación principal
├── requirements.txt                # Dependencias Python
├── .env.example                    # Ejemplo de variables de entorno
├── .gitignore                      # Archivos a ignorar en Git
├── README.md                       # Este archivo
│
├── config/                         # Configuración
│   ├── __init__.py
│   ├── settings.py                 # Configuración general
│   ├── archetipos.py               # 18 arquetipos de contenido
│   ├── brand.py                    # Tono de marca y CSS
│   └── cms_compatible.css          # CSS del CMS
│
├── core/                           # Lógica principal
│   ├── __init__.py
│   ├── generator.py                # ContentGenerator class
│   └── scraper.py                  # Scraping de datos
│
├── prompts/                        # Prompts de IA
│   ├── __init__.py
│   ├── new_content.py              # Prompts para contenido nuevo
│   └── rewrite.py                  # Prompts para reescritura
│
├── ui/                             # Componentes de interfaz
│   ├── __init__.py
│   ├── sidebar.py                  # Sidebar con configuración
│   ├── inputs.py                   # Inputs de contenido
│   ├── results.py                  # Visualización de resultados
│   └── rewrite.py                  # Interfaz de reescritura
│
├── utils/                          # Utilidades
│   ├── __init__.py
│   ├── html_utils.py               # Procesamiento HTML
│   └── state_manager.py            # Gestión de estado
│
├── .streamlit/                     # Config de Streamlit
│   ├── config.toml                 # Tema y configuración
│   └── secrets.toml.example        # Ejemplo de secrets
│
└── tests/                          # Tests (opcional)
    ├── __init__.py
    └── test_modular.py
```

---

## 🎨 Modos de Generación

### 📝 Modo: Crear Nuevo

Genera contenido desde cero basándose en arquetipos predefinidos.

**Flujo:**
1. Seleccionar arquetipo (18 opciones)
2. Configurar parámetros (producto, keywords, longitud)
3. Generar en 3 etapas
4. Validar y exportar

**Ideal para:**
- Artículos nuevos
- Reviews de productos
- Guías y tutoriales
- Comparativas
- Contenido original

### 🔄 Modo: Reescritura

Analiza competidores y genera contenido superior.

**Flujo:**
1. Introducir keyword objetivo
2. Scraping automático de top 5 URLs
3. Análisis competitivo (gaps, fortalezas, debilidades)
4. Generación mejorada en 3 etapas
5. Validación competitiva

**Ideal para:**
- Mejorar contenido existente
- Competir por keywords específicas
- Superar a competidores
- Contenido diferenciado

---

## 🏗️ Arquitectura

### Flujo de Generación (3 Etapas)
```
┌─────────────────────────────────────────────┐
│         ETAPA 1: BORRADOR INICIAL           │
│  - Claude genera primera versión            │
│  - Basado en inputs del usuario             │
│  - ~1-2 minutos                             │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│      ETAPA 2: ANÁLISIS CRÍTICO              │
│  - Claude analiza el borrador               │
│  - Identifica 3-5 problemas                 │
│  - Propone correcciones específicas         │
│  - JSON estructurado                        │
│  - ~1 minuto                                │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│       ETAPA 3: VERSIÓN FINAL                │
│  - Claude aplica correcciones               │
│  - Versión lista para publicar              │
│  - Validación CMS automática                │
│  - ~1-2 minutos                             │
└─────────────────────────────────────────────┘
```

### Stack Tecnológico

- **Frontend**: Streamlit 1.28+
- **IA**: Claude Sonnet 4 (Anthropic API)
- **Backend**: Python 3.11
- **Scraping**: BeautifulSoup4, Requests
- **Deployment**: Streamlit Cloud

---

## 👨‍💻 Desarrollo

### Instalación de dependencias de desarrollo
```bash
pip install -r requirements-dev.txt
```

### Running tests
```bash
pytest tests/
```

### Code formatting
```bash
black .
isort .
```

### Linting
```bash
flake8 .
mypy .
```

---

## 🐛 Troubleshooting

### Error: "API key not found"

**Solución**: Verifica que `.env` o `secrets.toml` contenga tu API key de Claude.

### Error: "Module not found"

**Solución**: 
```bash
pip install -r requirements.txt --upgrade
```

### El contenido no cumple validación CMS

**Solución**: Revisa la sección de errores en la UI. Los errores críticos deben corregirse antes de publicar.

### Scraping de competidores falla

**Solución**: 
- Verifica conexión a internet
- Algunos sitios bloquean scraping (normal)
- Usa VPN si es necesario
- En producción, implementar sistema robusto con Zenrows

---

## 📝 Changelog

Ver [CHANGELOG.md](CHANGELOG.md) para historial completo de versiones.

### v4.1.1 (2025-01-XX)

- ✅ Refactorización completa a arquitectura modular
- ✅ Nuevo sistema de validación CMS v4.1.1
- ✅ Modo reescritura con análisis competitivo
- ✅ 18 arquetipos predefinidos
- ✅ Flujo de 3 etapas optimizado

---

## 🤝 Contribuir

1. Fork del repositorio
2. Crear branch para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit de cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

### Guidelines

- Código en inglés, comentarios en español
- Seguir estructura modular existente
- Añadir tests para nuevas features
- Actualizar documentación

---

## 📄 Licencia

Uso interno de PcComponentes. Todos los derechos reservados.

---

## 👥 Equipo

**Product Discovery & Content**  
PcComponentes

---

## 📞 Soporte

Para bugs o sugerencias, abrir un issue en GitHub.

---

**Hecho con ❤️ por el equipo de Product Discovery & Content de PcComponentes**
