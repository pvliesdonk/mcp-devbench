# Smoke: ensure default container

After running the server:

```bash
uv run app/main.py
```

Use an MCP client to call the `ensure_default` tool, or import the function:

```bash
uv run -q - <<'PY'
from app.runtime_docker import ensure_default_container
print(ensure_default_container())
PY
```
