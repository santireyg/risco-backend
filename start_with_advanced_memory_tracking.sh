#!/bin/bash
# start_with_advanced_memory_tracking.sh

echo "🔍 Iniciando aplicación con tracking avanzado de memoria..."

# Verificar dependencias
echo "📋 Verificando dependencias..."

# Verificar si psutil está instalado
python3 -c "import psutil" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Error: psutil no está instalado"
    echo "💡 Instalar con: pip install psutil"
    exit 1
fi

echo "✅ psutil: OK"

#!/bin/bash

# Script para iniciar la aplicación CON tracking avanzado de memoria
# ⚠️  SOLO PARA DESARROLLO Y DEBUGGING - NO USAR EN PRODUCCIÓN

echo "🔍 Iniciando aplicación con tracking avanzado de memoria..."

# 🎯 ACTIVAR EL SWITCH MAESTRO
export ADVANCED_MEMORY_TRACKING_ENABLED=true

# Verificar dependencias
echo "📋 Verificando dependencias..."
python3 -c "import psutil; print('✅ psutil: OK')" || { echo "❌ psutil no encontrado. Instala con: pip install psutil"; exit 1; }

# Configurar tracking avanzado
export MEMORY_SNAPSHOT_INTERVAL=15                    # Snapshots cada 15 segundos
export ZOMBIE_MEMORY_THRESHOLD_MB=5                   # Detectar memoria zombie > 5MB
export LEAK_DETECTION_THRESHOLD_MB=20                 # Detectar leaks > 20MB
export TOP_MEMORY_ALLOCATIONS=25                      # Trackear top 25 allocations

# Configurar variables adicionales para debugging
export PYTHONMALLOC=malloc                        # Usar malloc estándar para mejor tracking
export PYTHONFAULTHANDLER=1                       # Habilitar fault handler
export PYTHONUNBUFFERED=1                         # Output sin buffer

# Configurar variables adicionales para debugging
export PYTHONMALLOC=malloc                        # Usar malloc estándar para mejor tracking
export PYTHONFAULTHANDLER=1                       # Habilitar fault handler
export PYTHONUNBUFFERED=1                         # Output sin buffer

echo "⚙️  Configuración aplicada:"
echo "   📊 Advanced Memory Tracking: ENABLED"
echo "   ⏱️  Snapshot Interval: ${MEMORY_SNAPSHOT_INTERVAL}s"
echo "   🧟 Zombie Memory Threshold: ${ZOMBIE_MEMORY_THRESHOLD_MB}MB"
echo "   🚨 Leak Detection Threshold: ${LEAK_DETECTION_THRESHOLD_MB}MB"
echo "   📈 Top Allocations Tracked: ${TOP_MEMORY_ALLOCATIONS}"
echo ""

# Mostrar información del sistema
echo "💻 Información del sistema:"
python3 -c "
import psutil
import sys
memory = psutil.virtual_memory()
print(f'   🧠 Memoria total: {memory.total / (1024**3):.1f}GB')
print(f'   📊 Memoria disponible: {memory.available / (1024**3):.1f}GB')
print(f'   🔄 Memoria en uso: {memory.percent:.1f}%')
print(f'   🐍 Python: {sys.version.split()[0]}')
"
echo ""

echo "🚀 Iniciando servidor FastAPI con tracking avanzado..."
echo "📝 Los logs detallados se mostrarán en tiempo real"
echo ""
echo "🛑 Para detener: Ctrl+C"
echo "═════════════════════════════════════════════════════════════════"

# Iniciar el servidor
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
