# Os Achadinhos da Isanlly: generador de posts

Genera posts listos para el grupo de WhatsApp: **foto de marca + video corto + texto con
el enlace de afiliada**. Isanlly abre el panel en el celular y comparte con un toque.

- **Panel (app instalable):** https://malfservicios.github.io/achadinhos-isanlly/
  En Android: Chrome → menú ⋮ → *Agregar a pantalla de inicio*.
- **Automático:** todos los días a las 10h y 17h (hora de Brasilia) busca los más vendidos
  con descuento en Mercado Livre y genera hasta 6 posts.
- **Manual:** pestaña *Actions → Gerar achadinhos → Run workflow*, pegar uno o más enlaces
  (`meli.la/...` o de producto). Precio opcional: `https://meli.la/xxxx | 79,90 | 119,90`.
  Desde el panel: botón **＋ Post de um link**.

## Cómo funciona

| Parte | Dónde |
|---|---|
| Búsqueda de ofertas (API oficial de Mercado Libre) | `gerador/mercadolivre.py` |
| Texto (Claude escribe la parte creativa; el precio y el enlace los pone el código) | `gerador/textos.py` |
| Imagen 1080×1350 con la identidad del grupo | `gerador/arte.py` |
| Video ~9 s (FFmpeg) | `gerador/video.py` |
| Panel web (PWA) | `docs/` |
| Ejecución programada | `.github/workflows/gerar.yml` |

El enlace de afiliada se arma con `matt_word` y `matt_tool` (en `config.json`), los mismos
parámetros que trae el enlace `meli.la` de Isanlly. Conviene confirmar en el panel de
afiliados de Mercado Livre que los clics de esos enlaces se registran.

Lo generado (posts, fotos, videos, historial y token cifrado) vive en la rama `dados`, que se
reescribe con un solo commit en cada ejecución, así que el repositorio no crece.
Se guardan los últimos 10 días.

## Configuración (una sola vez)

En GitHub: *Settings → Secrets and variables → Actions → New repository secret*.

| Secret | Para qué | Estado |
|---|---|---|
| `TOKEN_KEY` | cifrar el token de Mercado Libre | ya configurado |
| `ML_CLIENT_ID` / `ML_CLIENT_SECRET` | API de Mercado Libre | **pendiente** |
| `ANTHROPIC_API_KEY` | textos escritos por Claude (sin él se usan frases fijas) | **opcional** |

### 1. Crear la app en Mercado Libre
1. Entrar a https://developers.mercadolivre.com.br → *Minhas aplicações* → *Criar aplicação*.
2. **URI de redirect:** `https://malfservicios.github.io/achadinhos-isanlly/`
3. Permisos: lectura (*read*) y *offline_access*. No hacen falta permisos de escritura.
4. Copiar el **Client ID** y el **Client Secret** a los secrets `ML_CLIENT_ID` y `ML_CLIENT_SECRET`.

### 2. Conectar (autorizar)
1. Abrir (cambiando `CLIENT_ID`):
   `https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=CLIENT_ID&redirect_uri=https://malfservicios.github.io/achadinhos-isanlly/`
2. Aceptar. Vuelve al panel, que muestra un **código**. Copiarlo (vale pocos minutos).
3. *Actions → Conectar Mercado Livre → Run workflow* → pegar el código.
   Al terminar, lanza solo la primera búsqueda de ofertas.

### 3. (Opcional) Textos con Claude
Crear una clave en https://console.anthropic.com y guardarla en `ANTHROPIC_API_KEY`.
El modelo y el esfuerzo están en `config.json` (`texto`).

## Ajustes en `config.json`
- `busca.posts_por_execucao`: cuántos posts por ejecución.
- `busca.desconto_minimo`: % mínimo de descuento.
- `busca.categorias`: categorías del Mercado Libre donde buscar.
- `video.ativo`: `false` para no generar video.
- Horarios: `cron` en `.github/workflows/gerar.yml` (en UTC; Brasil = UTC−3).

## Probar en la PC
```
pip install -r requirements.txt
python -m gerador.main links "https://meli.la/1ffx3hM | 79,90 | 119,90"
```
Hace falta `ffmpeg` en el PATH (o la variable `FFMPEG`). El resultado queda en `dados/`.

## App de Android (APK)
`android/` es una *Trusted Web Activity*: abre el panel a pantalla completa, con el ícono del grupo.
GitHub la compila sola cuando cambia algo en `android/` (**Actions → APK de Android**) y la publica en
**Releases**. Enlace fijo a la última versión:
https://github.com/Malfservicios/achadinhos-isanlly/releases/latest/download/achadinhos.apk

- La llave de firma está en `android/firma-local/` (fuera de git) y en los secrets
  `SIGNING_KEY_BASE64` / `SIGNING_PASSWORD`. **Guarda una copia**: sin ella no se pueden instalar
  actualizaciones encima de la app.
- El repositorio `Malfservicios/malfservicios.github.io` guarda `.well-known/assetlinks.json` con la huella
  de esa llave; así Android oculta la barra del navegador.
