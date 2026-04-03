#!/bin/bash

# Script para ejecutar TriadLLM
# Este script verifica los prerequisitos y ejecuta la aplicación

echo "🚀 Iniciando TriadLLM..."

# Función para auto-reparar problemas comunes
auto_fix() {
    echo "🔧 Intentando auto-reparar problemas comunes..."
    
    # Verificar si uv está instalado
    if ! command -v uv &> /dev/null; then
        echo "❌ Error: uv no está instalado. Por favor instala uv primero."
        echo "Puedes instalarlo desde: https://docs.astral.sh/uv/getting-started/installation/"
        return 1
    fi
    
    # Verificar si uv está actualizado
    echo "🔄 Verificando versión de uv..."
    uv --version
    
    # Verificar si el entorno virtual está configurado
    if [ ! -d ".venv" ]; then
        echo "📦 Configurando entorno virtual con uv..."
        uv sync || { echo "❌ Error al configurar el entorno"; return 1; }
    fi
    
    # Verificar versión de Python
    echo "🐍 Verificando versión de Python..."
    if [ -d ".venv" ]; then
        PYTHON_VERSION=$(".venv/bin/python" --version 2>&1 | awk '{print $2}')
    else
        PYTHON_VERSION=$(uv python --version 2>&1 | awk '{print $2}')
    fi
    
    if [[ -z "$PYTHON_VERSION" ]]; then
        echo "❌ No se pudo detectar la versión de Python"
        return 1
    fi
    
    echo "📋 Versión de Python detectada: $PYTHON_VERSION"
    
    if [[ ! $PYTHON_VERSION =~ ^3\.13\. ]]; then
        echo "⚠️  Advertencia: Se recomienda Python 3.13. Versión actual: $PYTHON_VERSION"
        read -p "¿Deseas continuar de todos modos? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi
    
    return 0
}

# Función para verificar configuración
check_config() {
    CONFIG_DIR=""
    if [ "$OSTYPE" == "linux-gnu"* ]; then
        CONFIG_DIR="$HOME/.config/TriadLLM"
    elif [ "$OSTYPE" == "darwin"* ]; then
        CONFIG_DIR="$HOME/Library/Application Support/TriadLLM"
    elif [ "$OSTYPE" == "cygwin" ] || [ "$OSTYPE" == "msys" ] || [ "$OSTYPE" == "win32" ]; then
        CONFIG_DIR="$APPDATA\TriadLLM"
    else
        CONFIG_DIR="$HOME/.config/TriadLLM"
    fi
    
    if [ ! -f "$CONFIG_DIR/profiles.yaml" ]; then
        echo "📝 Configurando archivo de configuración..."
        mkdir -p "$CONFIG_DIR"
        cp src/triadllm/examples/profiles.yaml "$CONFIG_DIR/" || {
            echo "❌ Error al copiar el archivo de configuración"
            return 1
        }
    fi
    
    return 0
}

# Función para verificar variables de entorno
check_env() {
    if [ -z "$OPENAI_API_KEY" ] && [ -z "$MISTRAL_API_KEY" ]; then
        echo "🔑 No se encontraron variables de entorno para API keys"
        echo "📌 Puedes configurar OPENAI_API_KEY y/o MISTRAL_API_KEY para usar los proveedores correspondientes"
        read -p "¿Deseas continuar de todos modos? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi
    
    return 0
}

# Ejecutar preflight checks
echo "✈️  Ejecutando verificaciones previas..."

if ! auto_fix; then
    echo "❌ No se pudieron resolver los problemas automáticamente"
    exit 1
fi

if ! check_config; then
    echo "❌ Error en la configuración"
    exit 1
fi

if ! check_env; then
    echo "❌ Verificación de entorno fallida"
    exit 1
fi

echo "✅ Todos los prerequisitos verificados. Iniciando TriadLLM..."
echo ""

# Verificar si el entorno está configurado
if [ ! -f "uv.lock" ]; then
    echo "⚠️  Advertencia: No se encontró uv.lock. ¿Has ejecutado 'uv sync'?"
    read -p "¿Deseas ejecutar 'uv sync' ahora? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        uv sync || { echo "❌ Error al ejecutar uv sync"; exit 1; }
    fi
fi

# Verificar si hay un archivo de configuración
CONFIG_DIR=""
if [ "$OSTYPE" == "linux-gnu"* ]; then
    CONFIG_DIR="$HOME/.config/TriadLLM"
elif [ "$OSTYPE" == "darwin"* ]; then
    CONFIG_DIR="$HOME/Library/Application Support/TriadLLM"
elif [ "$OSTYPE" == "cygwin" ] || [ "$OSTYPE" == "msys" ] || [ "$OSTYPE" == "win32" ]; then
    CONFIG_DIR="$APPDATA\TriadLLM"
else
    CONFIG_DIR="$HOME/.config/TriadLLM"
fi

if [ ! -f "$CONFIG_DIR/profiles.yaml" ]; then
    echo "⚠️  Advertencia: No se encontró el archivo de configuración profiles.yaml"
    echo "Copiando archivo de ejemplo..."
    mkdir -p "$CONFIG_DIR"
    cp src/triadllm/examples/profiles.yaml "$CONFIG_DIR/" || {
        echo "❌ Error al copiar el archivo de configuración"
        exit 1
    }
fi

# Verificar variables de entorno para API keys
if [ -z "$OPENAI_API_KEY" ] && [ -z "$MISTRAL_API_KEY" ]; then
    echo "⚠️  Advertencia: No se encontraron variables de entorno para API keys"
    echo "Puedes configurar OPENAI_API_KEY y/o MISTRAL_API_KEY para usar los proveedores correspondientes"
    read -p "¿Deseas continuar de todos modos? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✅ Todos los prerequisitos verificados. Iniciando TriadLLM..."
echo ""

# Ejecutar la aplicación
if [ -d ".venv" ]; then
    source .venv/bin/activate
    python -m triadllm
else
    uv run triad
fi