# Imagen base oficial y ligera de Python
FROM python:3.11-slim

# Evitar generación de bytecode (.pyc) y forzar salida inmediata de logs (sin buffering)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8085

# Directorio de trabajo
WORKDIR /app

# Instalar curl para Healthcheck y limpiar caché de apt
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario y grupo del sistema sin privilegios de root (Seguridad: Non-root user)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -d /app appuser

# Copiar requirements primero para aprovechar la caché de capas de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente y recursos estáticos
COPY . .

# Asegurar propiedad de los archivos para el usuario no privilegiado
RUN chown -R appuser:appgroup /app

# Ejecutar como usuario no root
USER appuser

# Exponer el puerto interno
EXPOSE 8085

# Verificación de salud del contenedor
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8085/health || exit 1

# Ejecutar FastAPI mediante Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8085", "--proxy-headers", "--forwarded-allow-ips=*"]
