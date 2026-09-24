"""Build the report: pass % per topic x language for each model + MCP set.

    python report.py   -> reports/report.html, reports/report.xlsx, reports/topic_language_long.csv
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from common import load_config, load_jsonl


def heatmap_html(pct, n, min_n):
    mask = n.reindex_like(pct).fillna(0).to_numpy() < min_n
    sty = (pct.style
           .background_gradient(cmap="RdYlGn", vmin=0, vmax=100, axis=None)
           .format("{:.0f}", na_rep="")
           .apply(lambda _: np.where(mask, "opacity:0.3", ""), axis=None))
    return sty.to_html()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args()
    cfg = load_config(a.config)
    min_n = cfg.get("min_n_per_cell", 5)
    topics = {int(k): f"{int(k):02d} {v}" for k, v in cfg["topics"].items()}
    langs = cfg["languages"]

    df = pd.DataFrame(load_jsonl(cfg["graded"]))
    df = df[df["passed"].notna()].copy()
    if df.empty:
        raise SystemExit("No gradable results yet (fill in reference answers and run grade.py).")
    df["passed"] = df["passed"].astype(float) * 100
    df["combo"] = df["model_id"] + " + " + df["mcp_set"]
    df["topic_label"] = df["topic"].map(topics)
    out = Path(cfg["report_dir"])
    out.mkdir(parents=True, exist_ok=True)

    summary = (df.groupby("combo")
               .agg(pass_pct=("passed", "mean"), n=("passed", "size"),
                    same_language_pct=("same_language", lambda s: 100 * s.fillna(False).astype(float).mean()),
                    avg_tool_calls=("n_tool_calls", "mean"), avg_latency_s=("latency_s", "mean"),
                    total_cost_usd=("cost_usd", "sum"))
               .sort_values("pass_pct", ascending=False).round(1))

    def pivot(col):
        return df.pivot_table(index="combo", columns=col, values="passed", aggfunc="mean").round(0)

    by_lang = pivot("language").reindex(columns=[l for l in langs if l in df["language"].unique()])
    by_topic = pivot("topic_label")
    by_level = pivot("level")
    by_behaviour = pivot("expected_behaviour")

    long = (df.groupby(["combo", "topic_label", "language"])["passed"]
            .agg(pass_pct="mean", n="size").round(1).reset_index())
    long.to_csv(out / "topic_language_long.csv", index=False)

    with pd.ExcelWriter(out / "report.xlsx") as xw:
        summary.to_excel(xw, sheet_name="summary")
        by_lang.to_excel(xw, sheet_name="by_language")
        by_topic.to_excel(xw, sheet_name="by_topic")
        by_level.to_excel(xw, sheet_name="by_level")
        by_behaviour.to_excel(xw, sheet_name="by_behaviour")
        (df.pivot_table(index=["combo", "topic_label"], columns="language", values="passed", aggfunc="mean")
           .round(0).to_excel(xw, sheet_name="topic_x_language"))
        df.drop(columns=["tool_calls"]).to_excel(xw, sheet_name="raw", index=False)

    parts = [
        "<html><head><meta charset='utf-8'><style>body{font-family:sans-serif;margin:2rem}"
        "table{border-collapse:collapse;margin-bottom:1.5rem}td,th{padding:4px 8px;border:1px solid #ddd;"
        "text-align:center}</style></head><body><h1>Swiss Grounding MCP evaluation</h1>",
        f"<p>Pass % (0-100). Faded cells have fewer than {min_n} questions: do not read them as results.</p>",
        "<h2>Summary</h2>", summary.to_html(),
        "<h2>By language</h2>", by_lang.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100, axis=None)
                                      .format("{:.0f}", na_rep="").to_html(),
        "<h2>By expected behaviour</h2>", by_behaviour.to_html(),
        "<h2>By level</h2>", by_level.to_html(),
    ]
    for combo, g in df.groupby("combo"):
        pct = g.pivot_table(index="topic_label", columns="language", values="passed", aggfunc="mean")
        n = g.pivot_table(index="topic_label", columns="language", values="passed", aggfunc="size")
        cols = [l for l in langs if l in pct.columns]
        parts += [f"<h2>{combo}: topic x language</h2>", heatmap_html(pct[cols], n[cols], min_n)]
    parts.append("</body></html>")
    (out / "report.html").write_text("\n".join(parts), encoding="utf-8")
    print(summary.to_string())
    print(f"\nReport written to {out}/")


if __name__ == "__main__":
    main()
