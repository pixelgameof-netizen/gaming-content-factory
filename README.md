# Gaming Content Factory

Infraestructura cloud para producir contenido gaming en formato vertical.

## Estado actual

El repositorio contiene una primera prueba manual de renderizado con FFmpeg. **No contiene todavía el Short final de GTA VI ni material de terceros.**

## Seguridad y costes

- El repositorio es público por decisión temporal del propietario: todo el código que se suba aquí puede ser visto por cualquiera.
- No guardar claves API, tokens, contraseñas, claves de Supabase, datos personales ni archivos multimedia privados.
- No hay publicación automática ni tareas programadas.
- El render se inicia manualmente desde GitHub Actions.
- La prueba usa gráficos originales generados por FFmpeg; no utiliza gameplay ni clips de GTA VI.
- El artefacto de prueba se conserva durante un día.
- El flujo no necesita credenciales de Supabase ni conecta servicios externos.

## Ejecutar la prueba de render

1. Abrir la pestaña **Actions** del repositorio.
2. Elegir **Render preview (manual)**.
3. Pulsar **Run workflow** y confirmar.
4. Cuando termine, abrir la ejecución y descargar el artefacto `gaming-content-factory-preview`.

El flujo instala FFmpeg temporalmente en un runner Ubuntu, genera un MP4 de 12 segundos en 720x1280 a 30 fps y comprueba sus dimensiones con ffprobe.

## Próximas etapas

1. Verificar el MP4 de prueba.
2. Incorporar medios con licencia y revisados individualmente.
3. Añadir narración aprobada, subtítulos sincronizados y diseño sonoro.
4. Renderizar el Short editorial de GTA VI y revisar calidad visual y de audio.
5. Guardar el resultado final en el almacenamiento aprobado.
6. Presentar el vídeo para aprobación humana. Publicar será una acción separada y requerirá autorización explícita.
