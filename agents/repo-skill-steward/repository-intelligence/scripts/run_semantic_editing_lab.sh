#!/usr/bin/env bash
set -euo pipefail

: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"

export CODEGRAPH_TELEMETRY=off
export HOME="$RUNNER_TEMP/serena-home"
export PIP_DISABLE_PIP_VERSION_CHECK=1

fixture="$RUNNER_TEMP/semantic-edit-fixture"
rm -rf "$fixture" "$HOME"
mkdir -p "$fixture/core" "$fixture/service" "$fixture/api" "$HOME"
touch "$fixture/core/__init__.py" "$fixture/service/__init__.py" "$fixture/api/__init__.py"

cat > "$fixture/core/money.py" <<'PY'
def normalize_amount(value):
    """Normalize a monetary value to two decimals."""
    return round(float(value), 2)

def obsolete_helper(value):
    """Unused helper used to verify safe semantic deletion."""
    return value
PY

cat > "$fixture/service/orders.py" <<'PY'
from core.money import normalize_amount

def calculate_total(items):
    """Calculate checkout total from line-item amounts."""
    subtotal = sum(items)
    return normalize_amount(subtotal)
PY

cat > "$fixture/api/checkout.py" <<'PY'
from service.orders import calculate_total

def handle_checkout(items):
    """HTTP-style checkout entry point."""
    return calculate_total(items)
PY

python3 - <<'PY'
import os
from pathlib import Path
root = Path(os.environ["RUNNER_TEMP"]) / "semantic-edit-fixture"
path = root / "service" / "orders.py"
path.write_text(path.read_text() + "\n# semantic-edit-fixture\n" * 80)
PY

git init -q "$fixture"
git -C "$fixture" config user.email "ci@example.invalid"
git -C "$fixture" config user.name "Sazan CI"
git -C "$fixture" add .
git -C "$fixture" commit -qm "fixture"

codegraph_bin="$RUNNER_TEMP/codegraph-server"
curl -fsSL --retry 3 -o "$codegraph_bin"   https://github.com/codegraph-ai/CodeGraph/releases/download/v0.20.1/codegraph-server-linux-x64
echo "32b26422fa5ffe0a130955b7f7df771f722b2d427d67f53f104d9907bdfb24a6  $codegraph_bin" | sha256sum -c -
chmod +x "$codegraph_bin"

uri="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().as_uri())' "$fixture/core/money.py")"
args="$(python3 -c 'import json,sys; print(json.dumps({"uri":sys.argv[1],"line":1,"changeType":"modify"}))' "$uri")"
(
  cd "$fixture"
  "$codegraph_bin" --graph-only     --run-tool codegraph_analyze_impact     --tool-args "$args"     > "$RUNNER_TEMP/pre-impact.txt"
)
grep -q "normalize_amount" "$RUNNER_TEMP/pre-impact.txt"
grep -q "calculate_total" "$RUNNER_TEMP/pre-impact.txt"

uv_archive="$RUNNER_TEMP/uv-x86_64-unknown-linux-gnu.tar.gz"
curl -fsSL --retry 3 -o "$uv_archive" \
  https://github.com/astral-sh/uv/releases/download/0.12.21/uv-x86_64-unknown-linux-gnu.tar.gz
echo "23f02075b652bb1df64178cfae41b5caf160822e720e2663568f3f5d63bc52c0  $uv_archive" | sha256sum -c -
mkdir -p "$RUNNER_TEMP/uv-bin"
tar -xzf "$uv_archive" -C "$RUNNER_TEMP/uv-bin" --strip-components=1
export PATH="$RUNNER_TEMP/uv-bin:$PATH"
uv --version

venv="$RUNNER_TEMP/serena-venv"
python3 -m venv "$venv"
"$venv/bin/python" -m pip install --quiet   "git+https://github.com/oraios/serena.git@949a27ef1e5fda1a6e7b561e777bcece345c6ffd"
"$venv/bin/serena" --version | tee "$RUNNER_TEMP/serena-version.txt"
grep -q "1.7.0" "$RUNNER_TEMP/serena-version.txt"

"$venv/bin/python" - <<'PY'
from importlib.metadata import metadata
m = metadata("serena-agent")
assert m["Version"] == "1.7.0"
assert "MIT" in (m.get("License") or "")
PY

"$venv/bin/serena" init -b LSP
(
  cd "$fixture"
  "$venv/bin/serena" project create --index
  "$venv/bin/serena" project health-check
)

FIXTURE="$fixture" "$venv/bin/python" - <<'PY'
import json
import os
from pathlib import Path

from serena.agent import SerenaAgent
from serena.config.serena_config import LanguageBackend, SerenaConfig
from serena.tools import FindReferencingSymbolsTool, RenameSymbolTool, SafeDeleteSymbol

root = Path(os.environ["FIXTURE"]).resolve()
config = SerenaConfig.from_config_file().with_headless_mode_overrides()
config.language_backend = LanguageBackend.LSP
agent = SerenaAgent(project=str(root), serena_config=config)

refs_tool = agent.get_tool(FindReferencingSymbolsTool)
refs = agent.execute_task(
    lambda: refs_tool.apply(
        name_path="normalize_amount",
        relative_path="core/money.py",
    )
)
assert "calculate_total" in refs, refs

rename_tool = agent.get_tool(RenameSymbolTool)
rename_result = agent.execute_task(
    lambda: rename_tool.apply(
        name_path="normalize_amount",
        relative_path="core/money.py",
        new_name="normalize_money",
    )
)
assert rename_result, rename_result

delete_tool = agent.get_tool(SafeDeleteSymbol)
delete_result = agent.execute_task(
    lambda: delete_tool.apply(
        name_path_pattern="obsolete_helper",
        relative_path="core/money.py",
    )
)
assert "Cannot delete" not in delete_result, delete_result

agent.shutdown()

money = (root / "core" / "money.py").read_text()
orders = (root / "service" / "orders.py").read_text()
assert "normalize_money" in money
assert "normalize_money" in orders
assert "normalize_amount" not in money
assert "normalize_amount" not in orders
assert "obsolete_helper" not in money
print(json.dumps({
    "references_verified": True,
    "cross_file_rename": True,
    "safe_delete": True,
}, sort_keys=True))
PY

python3 -m compileall -q "$fixture"
PYTHONPATH="$fixture" python3 - <<'PY'
from api.checkout import handle_checkout
assert handle_checkout([1.111, 2.225]) == 3.34
PY

(
  cd "$fixture"
  "$codegraph_bin" --graph-only     --run-tool codegraph_symbol_search     --tool-args '{"query":"normalize_money","limit":5,"compact":true}'     > "$RUNNER_TEMP/post-symbol.txt"
)
grep -q "normalize_money" "$RUNNER_TEMP/post-symbol.txt"

uri="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().as_uri())' "$fixture/core/money.py")"
args="$(python3 -c 'import json,sys; print(json.dumps({"uri":sys.argv[1],"line":1,"changeType":"modify"}))' "$uri")"
(
  cd "$fixture"
  "$codegraph_bin" --graph-only     --run-tool codegraph_analyze_impact     --tool-args "$args"     > "$RUNNER_TEMP/post-impact.txt"
)
grep -q "normalize_money" "$RUNNER_TEMP/post-impact.txt"
grep -q "calculate_total" "$RUNNER_TEMP/post-impact.txt"

echo "semantic-editing-lab=success"
