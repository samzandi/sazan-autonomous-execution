#!/usr/bin/env bash
set -euo pipefail

: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"

export CODEGRAPH_TELEMETRY=off

python3 -m py_compile "$GITHUB_WORKSPACE/agents/repo-skill-steward/repository-intelligence/scripts/diff_impact_normalizer.py"
python3 -m unittest tests/test_repository_intelligence_diff_impact.py

fixture="$RUNNER_TEMP/api-diff-fixture"
rm -rf "$fixture"
mkdir -p "$fixture/api" "$fixture/tests"
touch "$fixture/api/__init__.py"

cat > "$fixture/api/service.py" <<'PY'
def publish_order_created(order):
    return {"event": "order.created", "order": order}

def handle_checkout(order):
    return publish_order_created(order)
PY

cat > "$fixture/tests/test_service.py" <<'PY'
from api.service import handle_checkout

def test_checkout_publishes():
    assert handle_checkout({"id": 1})["event"] == "order.created"
PY

git init -q -b main "$fixture"
git -C "$fixture" config user.email "ci@example.invalid"
git -C "$fixture" config user.name "Sazan CI"
git -C "$fixture" add .
git -C "$fixture" commit -qm "base"
git -C "$fixture" checkout -qb feature/change-checkout

cat > "$fixture/api/service.py" <<'PY'
def publish_order_created(order):
    return {"event": "order.created", "order": order}

def handle_checkout(order, currency="EUR"):
    return {"event": publish_order_created(order)["event"], "currency": currency}
PY

git -C "$fixture" add api/service.py
git -C "$fixture" commit -qm "change checkout handler signature"

codegraph="$RUNNER_TEMP/codegraph-server"
curl -fsSL --retry 3 -o "$codegraph"   https://github.com/codegraph-ai/CodeGraph/releases/download/v0.20.1/codegraph-server-linux-x64
echo "32b26422fa5ffe0a130955b7f7df771f722b2d427d67f53f104d9907bdfb24a6  $codegraph" | sha256sum -c -
chmod +x "$codegraph"

(
  cd "$fixture"
  "$codegraph" --graph-only     --run-tool codegraph_pr_context     --tool-args '{"baseBranch":"main","compact":false}'     > "$RUNNER_TEMP/codegraph-pr-context.txt"
)

test -s "$RUNNER_TEMP/codegraph-pr-context.txt"
grep -q "handle_checkout" "$RUNNER_TEMP/codegraph-pr-context.txt"
grep -q "test_checkout" "$RUNNER_TEMP/codegraph-pr-context.txt"
grep -Eq '"risk_level"[[:space:]]*:[[:space:]]*"(low|medium|high)"|Risk:.*(low|medium|high)' "$RUNNER_TEMP/codegraph-pr-context.txt"

cat > "$RUNNER_TEMP/workspace.json" <<'JSON'
{
  "schema_version": 1,
  "workspace_id": "c002-diff-impact-fixture",
  "repositories": [
    {
      "repository_id": "web",
      "visibility": "local-fixture",
      "source": "fixture/web",
      "revision": "web-001",
      "requires": [{
        "key": "http.checkout.v1",
        "kind": "http-api",
        "version": "1.0.0",
        "provider_hint": "api",
        "state": "observed",
        "evidence": ["web:http-client"]
      }]
    },
    {
      "repository_id": "api",
      "visibility": "local-fixture",
      "source": "fixture/api",
      "revision": "api-002",
      "provides": [
        {
          "key": "http.checkout.v1",
          "kind": "http-api",
          "version": "1.0.0",
          "state": "observed",
          "evidence": ["api:http-route"]
        },
        {
          "key": "event.order.created",
          "kind": "event",
          "version": "1.0.0",
          "state": "observed",
          "evidence": ["api:event-publisher"]
        }
      ]
    },
    {
      "repository_id": "repo_worker_01",
      "visibility": "private",
      "source": "secret-owner/private-worker",
      "revision": "worker-001",
      "requires": [{
        "key": "event.order.created",
        "kind": "event",
        "version": "1.0.0",
        "provider_hint": "api",
        "state": "observed",
        "evidence": ["worker:event-consumer"]
      }]
    }
  ]
}
JSON

python3 "$GITHUB_WORKSPACE/agents/repo-skill-steward/repository-intelligence/scripts/multi_repo_registry.py"   "$RUNNER_TEMP/workspace.json"   --registry "$RUNNER_TEMP/registry.json"   --contracts "$RUNNER_TEMP/contracts.json"   --require-no-blockers

python3 - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ["RUNNER_TEMP"])
contracts = json.loads((p / "contracts.json").read_text())
http_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "http-api")
event_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "event")
obs = {
  "schema_version":1,
  "workspace_id":"c002-diff-impact-fixture",
  "steps":[
    {"step_id":"web.submit","repository_id":"web","label":"Web submit","symbol":"submitCheckout","kind":"entry","entry":True,"state":"observed","evidence":["web:submit"]},
    {"step_id":"web.http","repository_id":"web","label":"HTTP client","symbol":"postCheckout","kind":"http-client","state":"observed","evidence":["web:http"]},
    {"step_id":"api.handle","repository_id":"api","label":"API checkout","symbol":"handle_checkout","kind":"http-handler","state":"observed","evidence":["api:handler"]},
    {"step_id":"api.publish","repository_id":"api","label":"Publish event","symbol":"publish_order_created","kind":"event-publisher","state":"observed","evidence":["api:publish"]},
    {"step_id":"worker.consume","repository_id":"repo_worker_01","label":"Consume event","symbol":"consume_order_created","kind":"event-consumer","state":"observed","evidence":["worker:consume"]},
    {"step_id":"worker.store","repository_id":"repo_worker_01","label":"Store order","symbol":"persist_order","kind":"storage-write","terminal":True,"state":"observed","evidence":["worker:store"]}
  ],
  "edges":[
    {"from":"web.submit","to":"web.http","relation":"calls","state":"observed","evidence":["web:call"]},
    {"from":"api.handle","to":"api.publish","relation":"publishes","state":"observed","evidence":["api:call"]},
    {"from":"worker.consume","to":"worker.store","relation":"writes","state":"observed","evidence":["worker:call"]}
  ],
  "bindings":[
    {"contract_id":http_id,"provider_step":"api.handle","consumer_step":"web.http","flow_direction":"consumer-to-provider","state":"observed","evidence":["binding:http"]},
    {"contract_id":event_id,"provider_step":"api.publish","consumer_step":"worker.consume","flow_direction":"provider-to-consumer","state":"observed","evidence":["binding:event"]}
  ]
}
(p / "observations.json").write_text(json.dumps(obs))
PY

python3 "$GITHUB_WORKSPACE/agents/repo-skill-steward/repository-intelligence/scripts/process_flow_synthesis.py"   "$RUNNER_TEMP/registry.json"   "$RUNNER_TEMP/contracts.json"   "$RUNNER_TEMP/observations.json"   --json "$RUNNER_TEMP/flows.json"   --markdown "$RUNNER_TEMP/FLOWS.md"   --require-flow

python3 - <<'PY'
import json, os, re
from pathlib import Path
p = Path(os.environ["RUNNER_TEMP"])
raw = (p / "codegraph-pr-context.txt").read_text()
contracts = json.loads((p / "contracts.json").read_text())
http_id = next(c["contract_id"] for c in contracts["contracts"] if c["kind"] == "http-api")
match = re.search(r'"risk_level"s*:s*"(low|medium|high)"', raw)
if not match:
    match = re.search(r'Risk:.*?(low|medium|high)', raw, re.I)
assert match, raw
changes = {
  "schema_version":1,
  "workspace_id":"c002-diff-impact-fixture",
  "changes":[{
    "change_id":"api-handler-change",
    "repository_id":"api",
    "change_type":"modify",
    "surface_kind":"symbol",
    "identifier":"handle_checkout",
    "path":"api/service.py",
    "symbol":"handle_checkout",
    "state":"observed",
    "evidence":["git-diff:main...HEAD","codegraph:pr_context"],
    "local_impact":{
      "risk_level":match.group(1).lower(),
      "symbols":["handle_checkout"],
      "files":["api/service.py"],
      "tests":["tests/test_service.py"],
      "direct_callers":["test_checkout_publishes"],
      "steps":["api.handle"],
      "evidence":["codegraph:pr_context"]
    },
    "contract_touches":[{
      "contract_id":http_id,
      "side":"provider",
      "state":"observed",
      "evidence":["api:http-contract"]
    }]
  }]
}
(p / "changes.json").write_text(json.dumps(changes))
PY

python3 "$GITHUB_WORKSPACE/agents/repo-skill-steward/repository-intelligence/scripts/diff_impact_normalizer.py"   "$RUNNER_TEMP/registry.json"   "$RUNNER_TEMP/contracts.json"   "$RUNNER_TEMP/flows.json"   "$RUNNER_TEMP/changes.json"   --json "$RUNNER_TEMP/impact.json"   --markdown "$RUNNER_TEMP/IMPACT.md"   --require-complete

python3 - <<'PY'
import json, os, re
from pathlib import Path
p = Path(os.environ["RUNNER_TEMP"])
raw = (p / "codegraph-pr-context.txt").read_text()
out = json.loads((p / "impact.json").read_text())
match = re.search(r'"risk_level"s*:s*"(low|medium|high)"', raw)
if not match:
    match = re.search(r'Risk:.*?(low|medium|high)', raw, re.I)
assert out["status"] == "verified"
assert out["blast_radius"]["repositories"] == ["api", "repo_worker_01", "web"]
assert out["summary"]["impacted_contracts"] == 1
assert out["summary"]["impacted_flows"] == 1
assert out["changes"][0]["local_impact"]["risk_level"] == match.group(1).lower()
assert "tests/test_service.py" in out["blast_radius"]["related_tests"]
assert "risk_level" not in out
assert "secret-owner" not in json.dumps(out)
PY

cat > "$RUNNER_TEMP/partial.json" <<'JSON'
{
  "schema_version":1,
  "workspace_id":"c002-diff-impact-fixture",
  "changes":[{
    "change_id":"file-only",
    "repository_id":"api",
    "change_type":"modify",
    "surface_kind":"file",
    "identifier":"api/service.py",
    "state":"observed",
    "evidence":["git-diff:api/service.py"]
  }]
}
JSON

set +e
python3 "$GITHUB_WORKSPACE/agents/repo-skill-steward/repository-intelligence/scripts/diff_impact_normalizer.py"   "$RUNNER_TEMP/registry.json"   "$RUNNER_TEMP/contracts.json"   "$RUNNER_TEMP/flows.json"   "$RUNNER_TEMP/partial.json"   --json "$RUNNER_TEMP/partial-impact.json"   --markdown "$RUNNER_TEMP/PARTIAL.md"   --require-complete
code=$?
set -e
test "$code" -eq 7
grep -q '"status": "partial-evidence"' "$RUNNER_TEMP/partial-impact.json"

echo "diff-impact-revalidation=success"
