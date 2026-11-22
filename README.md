# Gaming Content Factory

Infraestructura cloud para producir contenido gaming en formato vertical.

## Estado actual

- Existe una prueba manual de renderizado FFmpeg de 12 segundos (gráficos originales; no es el Short).
- Existe el paquete de preproducción del Short 01 de GTA VI: plan de cinco escenas, subtítulos provisionales, guía de derechos y script FFmpeg 1080x1920/30 fps.
- **El Short final todavía no existe.** Faltan los cinco archivos de vídeo aprobados y la narración final.
- Los tiempos de subtítulos son provisionales y deben ajustarse escuchando la voz definitiva.

## Seguridad y costes

- El repositorio es público por decisión temporal del propietario: todo el código y texto editorial aquí subido puede ser visto por cualquiera.
- No guardar claves API, tokens, contraseñas, claves de Supabase, datos personales ni archivos multimedia privados.
- No hay publicación automática ni tareas programadas.
- No se ha conectado ningún servicio externo nuevo para esta etapa.
- No incluir gameplay, tráileres, música ni material promocional de GTA VI sin revisar y documentar los permisos correspondientes.
- Los clips ambientales de terceros nunca deben presentarse como gameplay ni como material oficial de Rockstar.
- La publicación requiere aprobación humana independiente del render.

## Prueba de render

1. Abrir **Actions**.
2. Elegir **Render preview (manual)**.
3. Pulsar **Run workflow**.
4. La prueba instala FFmpeg en un runner Ubuntu, genera 12 segundos a 720x1280/30 fps y valida el archivo.

## Short 01 — paquete de producción

Consulta `production/short-01/scene-plan.json` para el guion visual y el desglose de escenas. Los subtítulos provisionales están en `production/short-01/captions.srt`. La carpeta `production/short-01/media/` describe los archivos de entrada requeridos y el control de derechos.

Cuando los cinco clips y la narración aprobados estén disponibles en esa carpeta, el script `render/render_short_01.sh` puede generar un MP4 vertical de 51 segundos:

```bash
bash render/render_short_01.sh production/short-01 short-01-preview.mp4
```

El script requiere FFmpeg y ffprobe. No inventa ni descarga recursos, y se detiene si faltan los archivos obligatorios. La música es opcional; si se usa, debe ser original o estar licenciada para el uso previsto.

## Siguiente etapa

Preparar una entrada privada de medios en la infraestructura cloud existente, verificar el acceso y los límites gratuitos, y conectar el render de GitHub Actions a esos archivos sin exponerlos en este repositorio público. Después: render, control de calidad y revisión humana. La publicación seguirá siendo una acción separada y requerirá autorización explícita.
