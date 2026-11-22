"""Run a model on the test set with the exact suggest_files prompt from SlothContributor.

Usage (Colab, GPU):
  python generate.py --model google/gemma-2-2b-it       --data data/test.jsonl --out gens/gemma2-2b.jsonl
  python generate.py --model Qwen/Qwen2.5-1.5B-Instruct --data data/test.jsonl --out gens/qwen2.5-1.5b.jsonl
  python generate.py --model google/gemma-2-2b-it --adapter ckpt/gemma-lora --data data/test.jsonl --out gens/gemma2-2b-lora.jsonl

Greedy decoding (the app itself uses Ollama's default sampling, so numbers are for the model,
not an exact replay of one app run). Resumable: ids already in --out are skipped.
"""
import argparse
import json
import os

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from common import build_prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", default=None, help="optional LoRA adapter dir")
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=300, help="max test examples")
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--max-new-tokens", type=int, default=200)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.data, encoding="utf-8")][: args.n]
    done = set()
    if os.path.exists(args.out):
        done = {json.loads(l)["id"] for l in open(args.out, encoding="utf-8")}
    rows = [r for r in rows if r["id"] not in done]
    print(f"{len(rows)} examples to run ({len(done)} already done)")
    if not rows:
        return
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    use_bf16 = torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 8
    kwargs = dict(torch_dtype=torch.bfloat16 if use_bf16 else torch.float16, device_map="auto")
    if "gemma" in args.model.lower():
        kwargs["attn_implementation"] = "eager"
    tok = AutoTokenizer.from_pretrained(args.model)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model, **kwargs)
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    def render(r):
        msgs = [{"role": "user", "content": build_prompt(r["title"], r["body"])}]
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)

    prompts = [(r["id"], render(r)) for r in rows]
    prompts.sort(key=lambda x: len(x[1]))  # similar lengths per batch, less padding
    with open(args.out, "a", encoding="utf-8") as f:
        for i in range(0, len(prompts), args.batch_size):
            chunk = prompts[i : i + args.batch_size]
            enc = tok([p for _, p in chunk], return_tensors="pt", padding=True,
                      add_special_tokens=False).to(model.device)  # template already has BOS
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=args.max_new_tokens,
                                     do_sample=False, pad_token_id=tok.pad_token_id)
            new = out[:, enc["input_ids"].shape[1]:]
            for (id_, _), ids in zip(chunk, new):
                f.write(json.dumps({"id": id_, "response": tok.decode(ids, skip_special_tokens=True)},
                                   ensure_ascii=False) + "\n")
            f.flush()
            print(f"{min(i + args.batch_size, len(prompts))}/{len(prompts)}")


if __name__ == "__main__":
    main()