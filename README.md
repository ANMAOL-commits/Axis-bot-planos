# Bot de planos – de un boceto a mano alzada a un plano arquitectónico

Subís una **foto de un boceto** (o escribís los ambientes y medidas) y el bot genera un **plano de planta** como el de la imagen de referencia:
muros, puertas y ventanas, mobiliario, jardín, cochera con autos, **cotas**, cuadro lateral (superficies, ambientes, notas, norte, escala gráfica) y logo.

**Salidas:** PNG · PDF · SVG · **DXF (se abre en AutoCAD)** · JSON editable. Opcional: render "fotográfico" con IA (experimental).

## Cómo funciona
1. **Gemini lee el boceto** y arma un modelo geométrico de la vivienda (cada ambiente = rectángulo con medidas en metros).
2. El programa **dibuja el plano con medidas exactas** (no es una imagen inventada por IA: lo que ves es el modelo, y lo podés corregir).
3. Si algo no coincide con tu boceto, **editás el JSON o pedís el cambio por escrito** y se vuelve a dibujar.

## Instalación (Windows + Python 3.14 64 bits + Visual Studio Code)
1. Descomprimí el zip (por ejemplo en `C:\Bot_planos`) y abrí esa carpeta en VS Code.
2. Abrí la terminal (`Terminal > Nueva terminal`) y escribí, línea por línea:
       python -m venv .venv
       .venv\Scripts\Activate.ps1
       pip install -r requirements.txt
   (Si PowerShell bloquea la activación: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, respondé `S` y repetí.)
3. Copiá `.env.example` como `.env` y pegá tu clave de Gemini (https://aistudio.google.com/api-keys):
       GEMINI_API_KEY=AQ.tu_clave_completa
   Sin comillas ni espacios. Sirven las claves nuevas (`AQ.`) y las viejas (`AIza`).
4. Probá la clave: `python probar_clave.py` (debe terminar en "✔ Todo funciona").
5. Ejecutá `python app.py` y abrí http://127.0.0.1:5000 (o doble clic en `iniciar_bot.bat`).

Sin clave podés probar igual con la casilla **"Probar con la vivienda de ejemplo"**.

## Cómo sacar buenas fotos del boceto
- Dibujá con **lápiz negro o fibra** sobre hoja blanca; paredes con línea firme; las puertas como un pequeño arco o una interrupción en la pared.
- **Escribí las medidas** de cada ambiente (ej. `3,5 x 3,5`) y el **nombre** de cada uno. Es lo que más mejora el resultado.
- Fotografiá de frente, con buena luz y sin sombras. Podés subir varias fotos.
- Si no hay medidas, completá "ancho total de la casa" para calibrar la escala.
- Indicá en el texto lo que no se ve en el dibujo (cantidad de baños, cochera para 2 autos, galería, etc.).

## Después de generar
- **Pedir cambios con IA:** escribí, por ejemplo, "agregá un dormitorio de 3 x 3 m al lado del pasillo". Se vuelve a dibujar.
- **Corregir a mano (JSON):** cada ambiente tiene `x, y, w, h` (esquina superior izquierda, ancho y alto, en metros). Los ambientes contiguos deben compartir el valor del borde. Tocá "Redibujar" (no usa IA).
- **DXF:** capas `MUROS`, `PUERTAS`, `VENTANAS`, `COTAS`, `AMBIENTES`, `EXTERIORES`, `TERRENO`, en metros. Para AutoCAD: `ABRIR` > archivo `.dxf`.
- **Render con IA (experimental):** usa un modelo de imágenes de Gemini; puede alterar textos y medidas. Servirá como imagen ilustrativa; el plano técnico es el dibujo vectorial.

## Personalizar
- **Logo:** reemplazá `static/logo.png` (idealmente PNG con fondo transparente).
- **Nombre de la empresa:** variable `EMPRESA` del archivo `.env`.
- **Ejemplo:** `ejemplos/ejemplo_vivienda.json` muestra el formato del modelo (y es lo que usa la IA como guía). `ejemplos/ejemplo_resultado.png` es el plano que genera.

## Alcance y cuidados
- Los ambientes son **rectángulos** (las formas en L se arman con varios rectángulos). Una sola planta por plano; no dibuja escaleras, techos ni instalaciones.
- La IA **interpreta** el boceto: revisá siempre medidas, puertas y ventanas antes de usar el plano. Los avisos aparecen debajo del plano (por ejemplo, ambientes superpuestos o aberturas colocadas automáticamente).
- Las superficies son aproximadas (ambientes + espesor de muros). No reemplaza un proyecto firmado por un profesional.
- En el nivel gratuito de Gemini el contenido enviado puede usarse para mejorar los productos de Google (verificá los términos vigentes); no subas material confidencial de clientes sin revisarlo. No compartas el archivo `.env`.

## Errores frecuentes
| Mensaje | Qué hacer |
|---|---|
| Google rechazó la clave | Copiá la clave completa de AI Studio en `.env`, sin comillas, y reiniciá `app.py` |
| Límite de uso de Gemini | Esperá un minuto y reintentá |
| "El plano no tiene ambientes" | Escribí los ambientes y medidas en el cuadro de detalles o mejorá la foto |
| Ambientes superpuestos (aviso) | Corregí `x, y, w, h` en el JSON y tocá "Redibujar" |
| `pip` o `python` no se reconocen | Verificá que aparezca `(.venv)` en la terminal y que estés en la carpeta del bot |

## Estructura
    app.py              servidor y página web
    plano/interpretar.py   lectura del boceto con Gemini
    plano/modelo.py     validación, alineación de bordes, aberturas automáticas, superficies
    plano/dibujo.py     dibujo del plano (PNG / PDF / SVG)
    plano/dxf.py        exportación a AutoCAD
    plano/imagen_ia.py  render opcional con IA
    gemini_rest.py      llamadas a la API de Gemini (sin SDK)
    templates/ static/  página web y logo
    ejemplos/           vivienda de ejemplo y resultado
    salida/             planos generados (una carpeta por plano)
