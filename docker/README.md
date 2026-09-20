# DivaBot en Docker 💅

La One no entra en un container… pero La Two sí, y bien perfumada. Este docker
empaqueta el bot (Discord + WhatsApp) y opcionalmente el LLM local (llama.cpp)
y el bridge de Baileys, todo orquestado con docker-compose.

## Arquitectura

```
┌───────────── docker compose (red interna) ─────────────┐
│                                                         │
│  discord (python) ──┐                                   │
│  whatsapp (python) ─┼─ ask_llm() ─> deepseek API       │
│                     │              (LLM_PROVIDER=deepseek) │
│                     └─> http://llama:8080/v1           │
│                         (LLM_PROVIDER=local)           │
│  llama (llama.cpp)  <─ volumen ~/models (GGUF, ro)     │
│  bridge (node:22)   <─ whatsapp_bridge + sesión        │
└─────────────────────────────────────────────────────────┘
```

## Quick start

```bash
# 1. Generar .env con tus tokens (desde ~/.hermes/.env o ./env-source)
./scripts/setup_docker_env.sh

# 2. Levantar SOLO Discord + DeepSeek API (sin GPU, recomendado)
docker compose up -d discord

# 3. O con el LLM local (llama.cpp, CPU por defecto)
docker compose --profile local up -d

# 4. O todo: Discord + llama.cpp + WhatsApp
docker compose --profile local --profile whatsapp up -d

# Logs
docker compose logs -f discord
```

Si no tenés `~/.hermes/.env`, creá `.env` a mano copiando
`.env.example` y completando `DISCORD_TOKEN` y (`DEEPSEEK_API_KEY` o
`LLM_PROVIDER=local`).

## Perfiles

| Perfil     | Servicios                | Cuándo                                    |
|------------|--------------------------|-------------------------------------------|
| (ninguno)  | discord                  | DeepSeek API, cero infra local            |
| `local`    | + llama                  | Querés el modelo en tu máquina            |
| `whatsapp` | + whatsapp, bridge       | Bot de WhatsApp (self-chat)               |

Los perfiles se combinan: `--profile local --profile whatsapp`.

## Variables clave

| Variable               | Default                          | Notas                              |
|------------------------|----------------------------------|------------------------------------|
| `LLM_PROVIDER`         | `deepseek`                       | `local` para llama.cpp             |
| `LLAMA_IMAGE`          | `ghcr.io/ggml-org/llama.cpp:server` | `:server-cuda`, `:server-rocm`, `:server-vulkan` |
| `MODEL_FILE`           | `Hermes-3-Llama-3.1-8B.Q8_0.gguf`| Nombre del GGUF dentro de `MODELS_DIR` |
| `MODELS_DIR`           | `~/models`                       | Montado read-only en `/models`     |
| `LLAMA_THREADS`        | `8`                              | Hilos de CPU del servidor llama    |

## GPU (llama.cpp)

Por defecto llama.cpp corre en CPU. Para usar tu GPU:

- **NVIDIA**: `LLAMA_IMAGE=ghcr.io/ggml-org/llama.cpp:server-cuda` y descomentar
  el bloque `deploy.resources.reservations.devices` del servicio `llama` en
  `docker-compose.yml`. Necesitás el runtime nvidia (nvidia-container-toolkit).
- **AMD ROCm**: `LLAMA_IMAGE=ghcr.io/ggml-org/llama.cpp:server-rocm` y agregar
  al servicio `llama`:
  ```yaml
  devices:
    - /dev/kfd
    - /dev/dri
  ```
- **Vulkan**: `LLAMA_IMAGE=ghcr.io/ggml-org/llama.cpp:server-vulkan` y
  `devices: ["/dev/dri"]`.

## WhatsApp (bridge)

El bridge de Baileys necesita parear una vez escaneando un QR:

```bash
docker compose --profile whatsapp logs -f bridge   # muestra el QR la primera vez
```

Después de parear, la sesión persiste en `./whatsapp_session` (montada como
volumen). Ojo: esa carpeta contiene `creds.json` (tu sesión viva) — está en
`.gitignore`, no la commitees.

## Comandos útiles

```bash
docker compose ps                      # estado
docker compose --profile local down    # bajar todo
docker run --rm divabot python -c "import llm_client; print(llm_client.PROVIDER)"
docker exec -it $(docker compose ps -q discord) python scripts/llm_cli.py "hola diva"
```

## Troubleshooting

- **`discord` se reinicia en loop**: revisá `docker compose logs discord` —
  si dice 4014, el Message Content Intent está desactivado en el portal de
  Discord (el watchdog del bot te da el link exacto).
- **`llama` no levanta**: ¿existe `${MODELS_DIR}/${MODEL_FILE}`? Probá
  `ls ~/models` y ajustá `MODEL_FILE` en `docker compose` (o `export`).
- **`bridge` unhealthy**: `docker compose logs bridge` — si no está pareado,
  escaneá el QR.
- **Puerto 3001 ocupado**: el bridge publica `3001:3001`; si ya tenés algo en
  ese puerto, cambiá el mapeo (ej. `3002:3001`).
