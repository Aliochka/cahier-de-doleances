# ruff: noqa: E402
"""Campagne séquentielle hors ligne, backend existant, reprise par empreinte et arrêt GPU propre."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import bootstrap  # noqa: F401  # isort: skip
import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass

from cahier_rag.judges.contracts import InferenceConfig
from cahier_rag.judges.models import MODELS

from constrained import BoundaryJudge
from prompt import SYSTEM, VERSION, messages, parse
from qcommon import HERE, ROOT, read, rows, save, sha


@dataclass
class Input:
    window: dict
    method: str

    def messages(self, _version):
        return messages(self.window, self.method)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("split", choices=["development", "validation"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--preflight-only", action="store_true")
    args = ap.parse_args()
    if args.split == "validation":
        freeze = read(HERE / "data/freeze.json")
        for name, digest in freeze["files"].items():
            assert frozen_match(HERE / name, digest), ("freeze changed", name)
        assert (HERE / "data/reference-validation.jsonl").exists(), (
            "Reference must be frozen before model validation runs"
        )
    config = InferenceConfig(batch_size=1, max_input_tokens=24576, max_new_tokens=512, seed=42)
    judge = BoundaryJudge(
        MODELS["qwen3-14b"], ROOT / "rag/models/judges", config, prompt_version=VERSION
    )
    judge.load_tokenizer()
    windows = [w for w in rows(HERE / "data/windows.jsonl") if w["split"] == args.split]
    if args.limit:
        windows = windows[: args.limit]
    inputs = [Input(w, method) for w in windows for method in ["B", "C"]]
    counts = judge.token_counts(inputs)
    recipe = dict(
        model=judge.spec.to_dict(),
        snapshot_hash=judge.snapshot_hash,
        inference=config.to_dict(),
        prompt_version=VERSION,
        prompt_sha256=sha(SYSTEM),
        chat_template_sha256=sha(judge.tokenizer.chat_template),
        process_memory_fraction=0.72,
        decoder="lm-format-enforcer-0.11.3-visible-block-enums-v1",
        safe_token_filter="existing safe_token_ids; output only",
    )
    save(
        HERE / f"data/{args.split}-token-counts.json",
        [
            dict(
                id=i.window["id"],
                method=i.method,
                input_tokens=n,
                within_budget=n <= config.max_input_tokens,
            )
            for i, n in zip(inputs, counts)
        ],
    )
    save(HERE / f"data/{args.split}-recipe.json", recipe)
    print("Tokenizer checked", len(inputs), "inputs, max", max(counts), flush=True)
    if args.preflight_only:
        return
    path = HERE / f"data/{args.split}-outputs.jsonl"
    done = rows(path) if path.exists() else []
    keys = {(r["window_id"], r["method"], r["input_sha256"], r["recipe_sha256"]) for r in done}
    recipe_hash = sha(json.dumps(recipe, sort_keys=True))
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable, no fallback")
    if subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], text=True
    ).strip():
        raise RuntimeError("Other GPU compute process present")
    torch.cuda.set_per_process_memory_fraction(0.72)
    load_at = time.perf_counter()
    judge.load()
    load_total = time.perf_counter() - load_at
    print("Model loaded", round(judge.load_seconds, 2), "s", flush=True)
    try:
        for item, n in zip(inputs, counts):
            ih = sha(json.dumps(item.messages(VERSION), ensure_ascii=False))
            key = (item.window["id"], item.method, ih, recipe_hash)
            if key in keys:
                continue
            other = [
                p.strip()
                for p in subprocess.check_output(
                    ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], text=True
                ).splitlines()
                if p.strip() and p.strip() != str(os.getpid())
            ]
            if other:
                print("Stopping: another compute process appeared", other, flush=True)
                break
            result = dict(
                window_id=item.window["id"],
                persee_id=item.window["persee_id"],
                method=item.method,
                input_sha256=ih,
                recipe_sha256=recipe_hash,
                input_tokens=n,
                raw=None,
                parsed=None,
                error=None,
            )
            start = time.perf_counter()
            torch.cuda.reset_peak_memory_stats()
            if n > config.max_input_tokens:
                result["error"] = "input_context_overflow_no_truncation"
            else:
                try:
                    raw = judge.generate([item])[0]
                    torch.cuda.synchronize()
                    result["raw"] = raw
                    result["output_tokens"] = judge.last_output_tokens
                    try:
                        result["parsed"] = parse(raw, item.window)
                    except (ValueError, TypeError, KeyError) as e:
                        result["error"] = "invalid_output:" + str(e)
                except (ValueError, RuntimeError) as e:
                    result["error"] = "inference_error:" + str(e)
            result.update(
                seconds=time.perf_counter() - start,
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                gpu_memory_free_bytes=torch.cuda.mem_get_info()[0],
            )
            with path.open("a") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()
            print(
                result["window_id"],
                item.method,
                "tokens",
                n,
                "time",
                round(result["seconds"], 2),
                "error",
                result["error"],
                "decision",
                (result["parsed"] or {}).get("decision"),
                flush=True,
            )
            if result["error"] and "inference_error" in result["error"]:
                break
    finally:
        save(
            HERE / f"data/{args.split}-runtime.json",
            dict(
                load_seconds=judge.load_seconds,
                load_and_setup_seconds=load_total,
                completed_before=len(done),
                process_id=os.getpid(),
                recipe=recipe,
            ),
        )
        judge.close()


if __name__ == "__main__":
    main()
