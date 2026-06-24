#!/usr/bin/env python3
"""Dry-run the LLM skill filter on candidate repos and print a keep/drop table.

Reads the JSON exported by github_skills_preview.py (one or more files), merges
and de-dupes them, then classifies each repo with the model configured in your
AIModelConfig (default model unless --model-id/--model-name is given). Prints
what survives (label=skill) vs what gets dropped and why, so you can judge the
filter quality before building the full pipeline.

Run from the backend dir, with your project Python env (3.10+) and a populated
.env (DATABASE_URL + APP_SECRET_KEY are read from it via app.core.config):

    python3 scripts/github_skills_preview.py --query "topic:claude-skill" --top 40 --json > c.json
    python3 scripts/github_skills_preview.py --query "topic:codex-skill"  --top 40 --json > x.json
    python3 scripts/skill_classify_test.py c.json x.json
    python3 scripts/skill_classify_test.py c.json x.json --model-name "gpt-4o-mini" --batch 18
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if TYPE_CHECKING:  # only for type hints; real imports are lazy inside build_client
    from app.services.ai_client import AIClient

# 核心标签分类配置：区分 skill 项目、合集、工具/通用框架、以及完全无关的仓库
LABELS = ["skill", "collection", "tool_or_app", "unrelated"]

# 标签的中文显示名称对照表。根据最新要求，专属的 skills 开发/运行框架也归类为 skill 标签并予以保留。
LABEL_CN = {
    "skill": "保留 · 真 skill / 专属框架",
    "collection": "剔除 · 合集/清单/市场",
    "tool_or_app": "剔除 · 普通app/通用框架/CLI",
    "unrelated": "剔除 · 无关蹭 topic",
    "unknown": "未判定 (模型没返回)",
}

# 核心系统提示词配置：供大模型进行分类识别的依据，定义了详细的角色、分类准则、标签定义以及判定规则
SYSTEM_PROMPT = """\
# 角色
你在为一个「真·单个 AI agent skill 及专属框架」排行榜做仓库筛选。把 GitHub 仓库分类，
只保留「单个可安装的 skill」和「用于开发/集成/运行 agent skills 的专属框架/SDK/运行沙箱」，
剔除普通应用、多 skill 合集仓库和无关仓库。

# 什么是 agent skill
一个 agent skill（Claude Code / Codex / Agent Skill）是自包含、可安装的单一能力，
通常是一个 SKILL.md + 可选脚本/资源，让 AI 编码 agent完成一件聚焦的事
（例：生成幻灯片、给 Logo 做动画、八字排盘）。它由 agent 调用。
此外，专门用于编写、集成、管理或执行这些 agent skills 的专属开发框架、SDK 或执行环境（如 skills framework）
同样也属于我们需要保留的 skill 范畴。
不是给人运行的普通 app，不是与 agent 无关的普通通用框架/SDK，
不是「很多 skill 的合集/清单/市场」，也不是通用的 IDE/平台。

# 标签（每个仓库恰好一个）
- skill        ：单个可安装的 agent skill（一件聚焦能力），或开发/运行 agent skills 的专属框架与SDK。【保留】
- collection   ：打包/索引了多个 skill —— 多 skill 合集（"300+ skills"）、
                awesome 清单、marketplace/registry、官方多 skill 仓库。【剔除】
- tool_or_app  ：普通应用/CLI/桌面端/IDE/平台，或与 agent skill 无关的普通开发框架/SDK。【剔除】
- unrelated    ：领域无关、纯蹭 topic（如 K8s 平台、向量库、教程/示例仓）。【剔除】

# 判定规则
1. 仓库打包「一件能力」供 agent 调用，或是专门支持 agent skills 的专属开发框架与 SDK → skill。
2. 含/链接「多个 skill」，或名字 awesome-*，或是 marketplace/registry → collection
   （即便每个都是 skill，整仓也算 collection）。
3. 由人当普通 app/CLI/桌面/服务运行，或是与 agent skills 开发无关的通用框架/SDK/IDE → tool_or_app。
4. 主题与 agent skill 无关 → unrelated。
5. skill 与 collection 难分时：描述出现「N 个 skills / skill 套件 / 合集 / marketplace」
   → collection；描述是「单一工作流/能力」→ skill。
6. 只依据 name + description + topics 判断。description 为空时按 name+topics 判，降低 confidence。
7. 从严：只有符合定义的 skill 或 skills 框架能留下。拿不准时，选剔除标签并标低 confidence。

# 示例
anthropics/skills「Public repository for Agent Skills」                  → collection
ComposioHQ/awesome-claude-skills「A curated list of awesome Claude…」     → collection
alirezarezvani/claude-skills「337 Claude Code skills & plugins」          → collection
CherryHQ/cherry-studio「AI productivity studio…」                         → tool_or_app
browser-act/skills「Browser automation CLI built for AI agents」          → skill (注：虽然是 CLI 框架，但专门用于开发运行 AI agent skills)
kubesphere/kubesphere「The container platform tailored for Kubernetes」   → unrelated
nolangz/pixel2motion「AI logo animation skill: turn raster logos…」       → skill
zarazhangrui/frontend-slides「Create beautiful slides on the web…」       → skill

# 输入
用户消息是一个 JSON 数组，每项：{ "full_name", "description", "topics": [] }

# 输出
只输出一个 JSON 对象，无任何多余文字、不要 markdown 代码块：
{ "results": [ { "full_name": "...", "label": "skill|collection|tool_or_app|unrelated",
                 "confidence": 0.0, "reason": "≤15字" } ] }
results 必须与输入等长、同序，full_name 原样回填。
"""


def load_repos(paths: list[str]) -> list[dict]:
    """Load + merge + de-dupe candidate repos by full_name (topics overlap)."""
    merged: dict[str, dict] = {}
    for p in paths:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        for r in data:
            fn = r.get("full_name")
            if not fn:
                continue
            if fn in merged:
                prev = merged[fn]
                prev["stars"] = max(prev.get("stars", 0), r.get("stars", 0))
                prev["topics"] = sorted(set(prev.get("topics", [])) | set(r.get("topics", [])))
            else:
                merged[fn] = dict(r)
    return sorted(merged.values(), key=lambda r: r.get("stars", 0), reverse=True)


def build_client(model_id: int | None, model_name: str | None) -> "AIClient":
    from sqlalchemy import select

    from app.core.config import settings
    from app.core.crypto import CryptoService
    from app.core.database import SessionLocal
    from app.models.entities import AIModelConfig
    from app.services.ai_client import AIClient
    from app.services.ai_models import get_default_ai_model

    session = SessionLocal()
    try:
        if model_id is not None:
            cfg = session.get(AIModelConfig, model_id)
        elif model_name:
            cfg = session.scalar(select(AIModelConfig).where(AIModelConfig.name == model_name))
        else:
            cfg = get_default_ai_model(session) or session.scalar(
                select(AIModelConfig).where(AIModelConfig.enabled.is_(True)).order_by(AIModelConfig.id)
            )
        if cfg is None:
            sys.exit("找不到可用的 AIModelConfig（检查 --model-name / 默认模型 / 数据库）。")
        api_key = CryptoService(settings.app_secret_key).decrypt(cfg.api_key_encrypted)
        print(f"模型: {cfg.name}  ({cfg.model})  @ {cfg.base_url}")
        return AIClient(
            base_url=cfg.base_url, api_key=api_key, model=cfg.model,
            model_name=cfg.name, task_name="skill 分类",
        )
    finally:
        session.close()


async def classify(client: AIClient, repos: list[dict], batch_size: int) -> tuple[dict, dict]:
    verdicts: dict[str, dict] = {}
    usage = {"prompt": 0, "completion": 0, "total": 0}
    batches = [repos[i:i + batch_size] for i in range(0, len(repos), batch_size)]
    print(f"输入: {len(repos)} 个候选 (去重后) | 批大小 {batch_size} | 批数 {len(batches)}\n")
    for bi, batch in enumerate(batches, 1):
        payload = [
            {"full_name": r["full_name"], "description": r.get("description", ""), "topics": r.get("topics", [])}
            for r in batch
        ]
        try:
            res = await client.complete_json_with_usage(SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001 — test tool: report and continue
            print(f"  ! 批 {bi}/{len(batches)} 失败: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        for item in res.content.get("results", []):
            fn = item.get("full_name")
            if fn:
                verdicts[fn] = item
        usage["prompt"] += res.usage["prompt_tokens"]
        usage["completion"] += res.usage["completion_tokens"]
        usage["total"] += res.usage["total_tokens"]
        print(f"  ✓ 批 {bi}/{len(batches)}  ({len(batch)} 个)")
    return verdicts, usage


def report(repos: list[dict], verdicts: dict, usage: dict) -> None:
    for r in repos:
        v = verdicts.get(r["full_name"], {})
        r["label"] = v.get("label") if v.get("label") in LABELS else "unknown"
        r["confidence"] = v.get("confidence", 0.0)
        r["reason"] = (v.get("reason") or "").strip()

    counts = {k: sum(1 for r in repos if r["label"] == k) for k in [*LABELS, "unknown"]}
    kept = counts["skill"]
    dropped = sum(counts[k] for k in ["collection", "tool_or_app", "unrelated"])

    print("\n" + "=" * 100)
    print("分类结果")
    for k in [*LABELS, "unknown"]:
        if counts[k]:
            print(f"  {k:<12} {counts[k]:>3}   {LABEL_CN[k]}")
    print(f"  ── 保留 {kept} / 剔除 {dropped}" + (f" / 未判定 {counts['unknown']}" if counts["unknown"] else ""))
    print(f"  tokens: prompt {usage['prompt']:,} + completion {usage['completion']:,} = {usage['total']:,}")

    def rows(label: str) -> None:
        group = [r for r in repos if r["label"] == label]
        if not group:
            return
        print(f"\n■ {label}  ({LABEL_CN[label]})  —  {len(group)}")
        for r in sorted(group, key=lambda x: x.get("stars", 0), reverse=True):
            conf = f"{r['confidence']:.2f}" if isinstance(r["confidence"], (int, float)) else "  ? "
            desc = (r.get("description") or "")[:42]
            print(f"  {r.get('stars', 0):>7} {conf:>5}  {r['full_name']:<40} {r['reason'][:18]:<18} ⟨{desc}⟩")

    print("\n" + "─" * 100)
    rows("skill")
    for label in ["collection", "tool_or_app", "unrelated", "unknown"]:
        rows(label)


def main() -> None:
    ap = argparse.ArgumentParser(description="Dry-run the LLM skill filter on candidate repos.")
    ap.add_argument("files", nargs="+", help="JSON files from github_skills_preview.py --json")
    ap.add_argument("--batch", type=int, default=18, help="repos per model call (default 18)")
    ap.add_argument("--model-id", type=int, default=None, help="AIModelConfig id (else default model)")
    ap.add_argument("--model-name", default=None, help="AIModelConfig name (else default model)")
    args = ap.parse_args()

    repos = load_repos(args.files)
    if not repos:
        sys.exit("没有读到候选仓库。")
    client = build_client(args.model_id, args.model_name)
    verdicts, usage = asyncio.run(classify(client, repos, args.batch))
    report(repos, verdicts, usage)


if __name__ == "__main__":
    main()
