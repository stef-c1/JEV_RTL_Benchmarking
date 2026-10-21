"""Count the input tokens of question records exactly as the Kev server counts them.

    cd /volume1/users/scuycken/kev && HF_HUB_OFFLINE=1 .venv/bin/python \
        /users/micas/scuycken/workspace/JEV_RTL/probes/kev_token_count.py QUESTIONS.jsonl [...]

It prints one JSON object: {question_id: [input tokens, state tokens]}. The script uses Kev's own
request rendering (kev.api.to_record) and encoder (kev.model.encode), with the tokenizer of the base
model. The four Kev models of the study count the same tokens: on 2026-10-15 all 348 requests of
dataset_v1 had the same input_tokens in the four answer files. On 2026-10-16 the script gave the
input_tokens of the Kev-4B run for the first 40 records of dataset_v1 (40 of 40 equal).
"""
import json
import sys

from kev.api import SystemOneRequest, to_record
from kev.model import SERVE_MAX_BRANCH, SERVE_MAX_STATE, encode
from transformers import AutoTokenizer

TOKENIZER = ("/volume1/users/scuycken/hf_cache/hub/models--Qwen--Qwen3.5-4B-Base/snapshots/"
             "1001bb4d826a52d1f399e183466143f4da7b741b")


def count(tok, rec):
    """-> (input tokens, state tokens) of one question record, the special tokens included."""
    req = SystemOneRequest(state=rec["state"], model="kev-latest", questions=rec["questions"])
    enc = encode(tok, to_record(req)[0], max_state=SERVE_MAX_STATE, max_branch=SERVE_MAX_BRANCH, strict=True)
    return len(enc["ids"]), enc["state_tokens"]


def main():
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    out = {}
    for path in sys.argv[1:]:
        for line in open(path):
            rec = json.loads(line)
            out[rec["question_id"]] = count(tok, rec)
    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
