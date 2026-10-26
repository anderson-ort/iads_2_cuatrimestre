# SearXNG: nuestro propio buscador web

**En una frase:** SearXNG es un buscador que instalamos nosotros en Docker y que consulta a Google, Bing, DuckDuckGo, Wikipedia y otros al mismo tiempo. En Ortelana le da al agente ReAct acceso a información de internet sin API keys, sin costo y sin cuota.

---

## 1. ¿Qué es?

SearXNG es un **metabuscador** open source: no tiene su propio índice de internet, sino que reenvía tu búsqueda a varios buscadores, junta los resultados y te los devuelve en una sola lista.

Piensalo como un comparador de precios: no vende nada, pero le pregunta a muchas tiendas y te muestra todo junto.

| Característica | Qué significa para nosotros |
|----------------|-----------------------------|
| Self-hosted | Corre en nuestra máquina (Docker). No dependemos de un servicio pago |
| Sin API keys | No hay que registrarse ni cuidar una clave |
| Privado | Los buscadores no ven quién hizo la búsqueda |
| API JSON | Además de la página web, devuelve resultados en JSON, fáciles de procesar en Python |

## 2. ¿Cómo funciona?

```text
GET http://localhost:8888/search?q=tela+polar&format=json
        │
        ▼
   SearXNG ──> Google, Bing, DuckDuckGo, Wikipedia...
        │
        ▼
{"results": [{"title": "...", "url": "...", "content": "..."}, ...]}
```

Por defecto SearXNG solo responde HTML. Para que devuelva JSON hay que habilitarlo en su configuración. Lo hacemos en `ortelana_app/searxng/settings.yml`:

```yaml
use_default_settings: true   # todo lo demás queda como viene
server:
  limiter: false             # sin límite de pedidos: es de uso interno
search:
  formats:
    - html
    - json                   # ← lo que usa nuestro código
```

## 3. ¿Cómo lo usamos en Ortelana?

### Infraestructura

En `ortelana_app/docker-compose.yaml`:

| Configuración | Valor | Por qué |
|---------------|-------|---------|
| Puerto | `8888:8080` | SearXNG escucha en 8080 dentro del contenedor; lo exponemos en 8888 |
| `SEARXNG_SECRET` | desde `.env` | Clave interna obligatoria (firma de cookies). Es un texto aleatorio |
| `settings.yml` | montado en solo lectura | Habilita el formato JSON |

La URL que usa la app está en `config.toml` → `[web] searxng_url = "http://localhost:8888"`.

### Código

Está en `ortelana_app/src/web.py`, clase `WebSearch`:

```text
search(consulta)
   ├─ 1. SearXNG (JSON)            → toma los primeros 5 resultados
   │      falla (caído, timeout, error HTTP)
   ├─ 2. DuckDuckGo (librería ddgs) → plan B
   │      también falla
   └─ 3. devuelve "Web search unavailable: ..." (el agente sigue funcionando)
```

### ¿Quién lo usa?

Solo el **agente ReAct**, a través de la tool `search_web` (`src/tools.py`). El router manda al agente las consultas que necesitan información externa o actual, por ejemplo "¿qué tela conviene para camperas de nieve?". El prompt del agente le indica **no** usar la web para datos de Ortelana (precios, stock, promociones): esos salen siempre del RAG interno.

## 4. ¿Por qué es relevante para nosotros?

| Necesidad | Cómo la cubre SearXNG |
|-----------|-----------------------|
| Información que no está en nuestros documentos | Busca en internet en tiempo real |
| Capa gratuita / bajo costo | No consume cuota ni requiere API key |
| Resiliencia | Si un buscador falla, los demás responden. Si SearXNG cae, entra DuckDuckGo |
| Control | Elegimos qué buscadores usar y cómo se configura |

Comparado con usar solo DuckDuckGo (clases 09 y 10): DuckDuckGo directo suele bloquear por *rate limit* cuando se le pide mucho. SearXNG reparte las búsquedas entre varios buscadores, y DuckDuckGo queda como respaldo.

## 5. Limitaciones a tener en cuenta

- **Los buscadores pueden bloquear tu IP** (CAPTCHA o rate limit) si se hacen muchas búsquedas seguidas. SearXNG marca esos motores como "unresponsive" y sigue con los demás.
- **Los resultados varían** de un día a otro: no sirve para tests deterministas. Por eso los tests usan respuestas simuladas.
- **Versión de la imagen:** hoy `docker-compose.yaml` usa `searxng/searxng:latest`. Es cómodo, pero cada `docker compose pull` puede traer una versión distinta. Para resultados reproducibles conviene fijar una etiqueta concreta, como la que estaba comentada (`2026.10.23-629368e40`).
- **No es información verificada:** el agente puede recibir resultados incorrectos de internet. Por eso no se usa para datos propios de Ortelana.

## Para probarlo

```bash
cd 11_clase/ortelana_app
docker compose up -d searxng
curl "http://localhost:8888/search?q=tela+polar&format=json"   # debería devolver JSON
uv run pytest tests/test_web.py -v                              # sin red
```
