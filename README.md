# Gaming Content Factory

Plataforma cloud para descubrir material de videojuegos, revisar derechos y producir videos cortos con narración, subtítulos y montaje automatizado.

## Estado real — 24 de noviembre de 2026

La infraestructura base y los flujos automatizados están implementados, pero **la primera producción real todavía no ha completado el ciclo de renderizado y aprobación**.

### Ya implementado

- Aplicación de gestión en Floot, conectada a Supabase.
- Buckets privados para medios de origen y videos finales.
- Catálogo de candidatos de gameplay y revisión explícita de derechos.
- GitHub Actions para descubrir candidatos en Wikimedia Commons.
- Filtros de descubrimiento para CC0, CC BY 3.0 y CC BY 4.0; la detección no equivale a autorización de uso.
- Cola de trabajos y worker de renderizado con GitHub OIDC.
- Conversión de fuentes WebM a MP4, generación de narración española con Kokoro ONNX, subtítulos SRT y render FFmpeg.
- Control de calidad técnico y registro privado del resultado.
- La publicación automática permanece desactivada.

### Validaciones que ya pasaron

- Gameplay Hunter: ejecución correcta con cinco clips Minecraft preparados para revisión privada.
- Inspección técnica: SHA-256, streams de video/audio y fotogramas de revisión.
- Generación de voz y subtítulos en español: prueba de GitHub Actions aprobada.
- Renderizador genérico: prueba sintética de GitHub Actions aprobada.

Estas pruebas validan componentes individuales. **No significan que ya exista un MP4 final de la primera producción.**

### Pendiente para la primera entrega

1. Crear el trabajo real desde la sesión autenticada del propietario en la aplicación.
2. Ejecutar el worker con ese trabajo en cola.
3. Verificar el MP4 generado, su narración, subtítulos, imagen, sonido y duración.
4. Confirmar que el archivo queda privado y se puede revisar desde móvil y PC.
5. Completar la aprobación del archivo exacto mediante su SHA-256.

## Automatizaciones actuales

- `.github/workflows/gameplay-hunter.yml`: búsqueda diaria programada y ejecución manual. Acepta hasta seis consultas de juegos y guarda candidatos; el paso de staging e inspección actual prepara un conjunto curado de Minecraft.
- `.github/workflows/render-job.yml`: worker programado cada diez minutos y ejecución manual. Si no hay trabajos en cola, termina sin renderizar.
- `.github/workflows/test-tts.yml`: prueba de voz y subtítulos.
- `.github/workflows/test-render-generic.yml`: prueba sintética del renderizador.

## Límites y seguridad

- Un candidato encontrado en Commons no está automáticamente autorizado. Deben revisarse licencia, atribución, políticas del editor del juego y elementos de terceros.
- No se deben incorporar clips, música o tráileres solo por estar disponibles en Internet.
- Los medios y resultados de producción deben permanecer en almacenamiento privado.
- No guardar claves, tokens ni secretos en este repositorio.
- El repositorio es actualmente **público**: el código y la documentación aquí alojados son visibles públicamente. No contiene archivos multimedia privados ni debe contener credenciales.
- No publicar automáticamente. La aprobación del propietario debe referirse a la versión exacta del MP4 y su SHA-256; cualquier cambio invalida esa aprobación.

## Operación

Consulta [docs/operations-runbook.md](docs/operations-runbook.md) para el flujo operativo, las pruebas existentes y los criterios de cierre.
