# MinerU setup guide (for autopaper)

autopaper converts PDFs to Markdown through MinerU. This guide covers installing MinerU and getting either a **local command** or a **local service** running, then pointing autopaper at it. It reflects MinerU 3.4.4; for the exhaustive parameter reference see the upstream docs (<https://opendatalab.github.io/MinerU/>) and the [GitHub repo](https://github.com/opendatalab/MinerU).

## 1. Pick a mode

autopaper selects a backend from files in the data root (`<root>/`, default `./reference-works/`). If several are present the higher-priority one wins:

| Priority | Config in `<root>/` | What it needs | Use when |
| --- | --- | --- | --- |
| 1 | `.mineru_url` | a running `mineru-api` service | one service shared by many runs/clients |
| 2 | `.mineru_command` | a local `mineru` CLI | no long-running service; simplest |
| 3 | `.mineru_token` | online MinerU cloud account | no local install |

## 2. Install MinerU

```bash
uv tool install "mineru[all]"     # recommended; installs all executables
# or: pip install "mineru[all]"
mineru --version                  # expect 3.x
```

`mineru[all]` provides eight executables; the ones relevant here:

| Command | Purpose |
| --- | --- |
| `mineru` | CLI document parsing (used by `.mineru_command`) |
| `mineru-api` | FastAPI parsing service (used by `.mineru_url`) |
| `mineru-gradio` | browser UI (starts its own internal API) |
| `mineru-models-download` | download pipeline / VLM models |
| `mineru-openai-server` | OpenAI-compatible VLM inference server |
| `mineru-vllm-server`, `mineru-lmdeploy-server` | VLM inference backends |
| `mineru-router` | multi-GPU / multi-service load balancing |

## 3. Download models

Models are not bundled; the first parse downloads them (can be several GB). To pre-download:

```bash
mineru-models-download -s modelscope -m all        # or -s huggingface
mineru-models-download -s modelscope -m pipeline   # CPU-only setups, smaller
```

`mineru-models-download -s auto -m all` auto-selects a source. Model locations are recorded in `~/.mineru.json`.

## 4. Mode A — local command

```bash
mineru -p document.pdf -o output/
mineru -p document.pdf -o output/ -b pipeline        # CPU-friendly, no hallucination
mineru -p document.pdf -o output/ -b vlm-engine      # highest accuracy, needs GPU
```

Output layout (autopaper locates the `.md` and `images/` automatically):

```
output/<doc-name>/<method>/<doc-name>.md   # method: auto | txt | ocr (pipeline)
output/<doc-name>/hybrid_auto/<doc-name>.md
output/<doc-name>/vlm/<doc-name>.md
output/<doc-name>/<method>/images/
```

Point autopaper at it:

```bash
touch <root>/.mineru_command                       # empty file => the `mineru` command
echo 'mineru -b pipeline -l en' > <root>/.mineru_command   # or pin flags in the file
```

autopaper runs `<command> -p <paper>.pdf -o <tmp>` and collects the result.

## 5. Mode B — local service

Start the REST service:

```bash
mineru-api                                   # 127.0.0.1:8000, local machine only
mineru-api --host 0.0.0.0 --port 8080        # reachable from the LAN
mineru-api --enable-vlm-preload True         # preload VLM model to cut first-request latency
```

Self-hosted `mineru-api` has **no authentication**. Do not expose it publicly without a reverse proxy; use `--host 0.0.0.0` only on a trusted network.

Endpoints:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/file_parse` | POST | synchronous parse, returns a result ZIP |
| `/tasks` | POST | submit an async task |
| `/tasks/{task_id}` | GET | task status |
| `/tasks/{task_id}/result` | GET | task result |
| `/health` | GET | health check |
| `/docs` | GET | Swagger API docs |

Smoke test:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/file_parse \
  -F "files=@document.pdf" -F "backend=pipeline" -F "lang_list=ch" \
  -o result.zip
```

Point autopaper at it:

```bash
echo http://127.0.0.1:8000 > <root>/.mineru_url
```

In service mode autopaper posts to `/file_parse` with `backend=hybrid-engine` and `lang_list=ch` by default; override with `MINERU_BACKEND` / `MINERU_LANG` (set both for autopaper and, if needed, for a CPU-only service use `MINERU_BACKEND=pipeline`).

## 6. Backends

| Backend | Accuracy | Speed | Needs | Notes |
| --- | --- | --- | --- | --- |
| `pipeline` | medium | fast | CPU, ~4 GB RAM | no hallucination; safest on CPU |
| `hybrid-engine` (default) | high | medium | GPU, ≥8 GB VRAM | `--effort high` adds image/chart analysis; `medium` disables it |
| `vlm-engine` | highest | slow | GPU, ≥8 GB VRAM | Chinese/English only |

VLM and Hybrid backends read pages as images, so scanned PDFs need no special handling. With `pipeline`, `-m auto` (default) detects scanned pages and switches to OCR; force it with `-m ocr`.

## 7. Mode C — online MinerU cloud

Register at <https://mineru.net>, read the API docs at <https://mineru.net/apiManage/docs>, then:

```bash
printf '%s' "$YOUR_TOKEN" > <root>/.mineru_token && chmod 600 <root>/.mineru_token
# or: export MINERU_TOKEN=...
```

The online API applies page limits (≤200 pages per file) and a daily priority-page quota; local installs are bounded only by your hardware.

## 8. Environment variables

| Variable | For | Meaning |
| --- | --- | --- |
| `MINERU_MODEL_SOURCE` | MinerU | `modelscope` / `huggingface` / `local` |
| `MINERU_DEVICE_MODE` | MinerU | force `cuda` / `cpu` / `npu` / `mps` |
| `MINERU_LOG_LEVEL` | MinerU | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `MINERU_API_OUTPUT_ROOT` | mineru-api | service output dir (default `./output`) |
| `MINERU_API_MAX_CONCURRENT_REQUESTS` | mineru-api | request concurrency (default 3) |
| `MINERU_URL` | autopaper | overrides `<root>/.mineru_url` |
| `MINERU_COMMAND` | autopaper | overrides `<root>/.mineru_command` |
| `MINERU_BACKEND`, `MINERU_LANG` | autopaper | service-mode backend / OCR language |
| `MINERU_TOKEN` | autopaper | overrides `<root>/.mineru_token` |
| `MINERU_MODEL_VERSION` | autopaper | online API model (default `vlm`) |

## 9. Troubleshooting

- **First run is slow** — models are downloading; pre-download with `mineru-models-download`, or set `MINERU_MODEL_SOURCE`.
- **GPU out of memory** — switch to `-b pipeline`, or use `hybrid-engine --effort medium` (image analysis off).
- **Service unreachable from another machine** — start it with `--host 0.0.0.0` and open the port; `127.0.0.1` is local-only.
- **Scanned PDF parses poorly** — use `-m ocr` with the right `-l`, or a VLM/Hybrid backend.
- **HTTP 401/403 from the online API** — token missing/expired; check `<root>/.mineru_token`.
- **Chinese formulas** — set `MINERU_FORMULA_CH_SUPPORT=true`.

## 10. How autopaper uses these modes

- `.mineru_url`: `POST <url>/file_parse` (multipart) with `response_format_zip=true`, then extracts `<doc>.md` and `images/` from the returned ZIP.
- `.mineru_command`: runs `<command> -p <paper>.pdf -o <tmp>` and copies the Markdown plus `images/` into the work directory.
- `.mineru_token`: submits the PDF to the online MinerU batch API and polls until the result ZIP is ready.

The precedence is service > command > online; see the README section "Prerequisite: a MinerU conversion backend".
