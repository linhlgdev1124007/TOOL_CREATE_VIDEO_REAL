"""Pinned Flowkit host with a durable six-submit guard at the provider boundary."""
import argparse
import os
from pathlib import Path
import sys

import pipeline as p
from flowkit_adapter import Budget, PIN


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()
    job = Path(args.job).resolve()
    if not job.is_relative_to(p.ROOT/"output"):
        parser.error("Job must be inside output")
    vendor = p.ROOT/"integrations/flowkit"
    if p.run(["git", "rev-parse", "HEAD"], cwd=vendor).stdout.strip() != PIN:
        raise RuntimeError("Flowkit commit differs from verified adapter pin")
    os.environ.update(FLOW_PROJECT_ID=args.project_id, API_HOST="127.0.0.1", WS_HOST="127.0.0.1",
                      FLOW_MAX_CONCURRENT="1", FLOW_GENERATION_MAX_CONCURRENT="1",
                      MAX_RETRIES="0", FLOW_ALLOW_DEGRADED="0")
    sys.path.insert(0, str(vendor))
    from agent.services.flow_client import get_flow_client
    from agent.services import flow_batch as fb
    from agent.main import app
    import uvicorn
    client = get_flow_client()
    original = client.batch_rpc
    candidates = client._extension_candidates
    # No automatic cross-profile resubmission after a timeout/disconnect.
    client._extension_candidates = lambda *a, **k: candidates(*a, **k)[:1]
    budget_path = job/"flow/budget.json"
    budget = Budget(budget_path)

    async def guarded(rpcid, freq, captcha_action=None, **kwargs):
        if captcha_action:
            if rpcid != fb.RPC_GEN_VIDEO_TEXT:
                return {"status": 400, "error": "This Reel permits text-to-video atmosphere cutaways only"}
            try:
                budget.reserve({"rpc": rpcid, "project_id": args.project_id})
            except (ValueError, FileExistsError) as exc:
                return {"status": 429, "error": str(exc)}
        return await original(rpcid, freq, captcha_action, **kwargs)
    client.batch_rpc = guarded

    @app.get("/wrydeco/guard")
    async def guard_status():
        used = len(p.read(budget_path)["attempts"]) if budget_path.exists() else 0
        return {"pin": PIN, "job": str(job), "project_id": args.project_id, "limit": 6, "used": used,
                "allowed_mode": "omni_text_4s", "automatic_resubmission": False}

    uvicorn.run(app, host="127.0.0.1", port=8100)


if __name__ == "__main__":
    main()
