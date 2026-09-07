import fcntl
from pathlib import Path
from typing import Any, Dict

import runpod

from actions.composite import run_composite
from actions.download_models import run_download_models
from settings import get_settings


def _error(message: str, status: str = "error") -> Dict[str, Any]:
    return {"status": status, "message": message}


def _ensure_models() -> None:
    settings = get_settings()
    sentinel = Path(settings.model_cache_dir).parent / ".download_complete"
    if sentinel.is_file():
        return
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    with (sentinel.parent / ".download.lock").open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if not sentinel.is_file():
            print("Initializing model cache", flush=True)
            run_download_models(settings)


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    payload = job.get("input", {})
    action = payload.get("action")
    print("Received action=%s job_id=%s" % (action, payload.get("job_id")), flush=True)

    # Important: let init job failures bubble up so RunPod marks the job FAILED.
    # `/api/ready` relies on RunPod job status for readiness.
    if action == "download_models":
        result = run_download_models(get_settings())
        return {"status": "success", **result}

    try:
        if action == "composite":
            _ensure_models()
            result = run_composite(payload, get_settings())
            print("Composite finished status=%s" % result.get("status"), flush=True)
            return result

        return _error("Unsupported action. Use 'download_models' or 'composite'.")
    except Exception as error:
        print("Handler error: %s: %s" % (error.__class__.__name__, error), flush=True)
        return _error(str(error))


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
