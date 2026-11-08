# -*- coding: utf-8 -*-
"""M6: WebArena 头部链 invalid-action (none:err) 发现率定量分析.

输入:  results/webarena_mining.json, webarena_chains.jsonl, webarena_signatures.jsonl
输出:  results/webarena_headrate.json  (幂等覆盖)

核心指标: 按 c' (contrast) 排序的头部链中, 含 none:err / 任意 err 符号的比例,
用于把手稿 6.5 节的定性表述 ("头部链几乎全含 none:err") 升级为定量表述.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 05_experiments/
RES = os.path.join(BASE, "results")


def load_jsonl(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    meta = json.load(open(os.path.join(RES, "webarena_mining.json"), encoding="utf-8"))
    chains = load_jsonl("webarena_chains.jsonl")
    sigs = load_jsonl("webarena_signatures.jsonl")

    chains.sort(key=lambda r: -r["contrast_sm"])

    def has_err(seq):
        return any(":err" in s for s in seq)

    def has_none_err(seq):
        return any(s == "none:err" for s in seq)

    head = {}
    for k in (5, 10, 20, 50, 100):
        top = chains[:k]
        head[f"top{k}"] = {
            "n": len(top),
            "n_with_none_err": sum(has_none_err(c["chain"]) for c in top),
            "frac_with_none_err": round(sum(has_none_err(c["chain"]) for c in top) / len(top), 4),
            "n_with_any_err": sum(has_err(c["chain"]) for c in top),
            "frac_with_any_err": round(sum(has_err(c["chain"]) for c in top) / len(top), 4),
        }

    overall_chains = {
        "n": len(chains),
        "n_with_none_err": sum(has_none_err(c["chain"]) for c in chains),
        "frac_with_none_err": round(sum(has_none_err(c["chain"]) for c in chains) / len(chains), 4),
        "n_with_any_err": sum(has_err(c["chain"]) for c in chains),
        "frac_with_any_err": round(sum(has_err(c["chain"]) for c in chains) / len(chains), 4),
        "n_perfect_with_none_err": sum(has_none_err(c["chain"]) and c.get("perfect") for c in chains),
        "n_perfect": sum(bool(c.get("perfect")) for c in chains),
    }

    def sig_has_err(items):
        return any(it.startswith("err:") for it in items)

    overall_sigs = {
        "n": len(sigs),
        "n_with_err_item": sum(sig_has_err(s["items"]) for s in sigs),
        "frac_with_err_item": round(sum(sig_has_err(s["items"]) for s in sigs) / len(sigs), 4),
    }

    out = {
        "source": {
            "corpus": meta["corpus"],
            "signatures": meta["signatures"]["n"],
            "chains": meta["chains"]["n"],
        },
        "head_chain_err_rate": head,
        "all_chains": overall_chains,
        "all_signatures": overall_sigs,
    }

    dst = os.path.join(RES, "webarena_headrate.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("written:", dst)


if __name__ == "__main__":
    main()
