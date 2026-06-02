import re
import httpx
from app.core.cache import ttl_cache

_headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html",
}


@ttl_cache(600)
def fetch_leaderboard(_config: dict, limit: int) -> list[dict]:
    """Parse AI model leaderboard from datalearner.com HTML table."""
    try:
        resp = httpx.get(
            "https://www.datalearner.com/leaderboards",
            headers=_headers,
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()
        html = resp.text

        # Extract the single table
        table_m = re.search(r"<table[^>]*>(.*?)</table>", html, re.DOTALL)
        if not table_m:
            return []

        table_html = table_m.group(1)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)

        # Parse header to get benchmark names
        header_cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rows[0], re.DOTALL)
        headers = [re.sub(r"<[^>]+>", "", c).strip() for c in header_cells]
        # headers: ['', '排名', '模型', 'HLE', 'ARC-AGI-2', 'FrontierMathTier 4', 'SWE-benchVerified', 'τ²-Bench', '开源情况', '']
        # Benchmark columns start at index 3
        benchmark_names = [h for h in headers[3:-2] if h]  # Skip empty, 排名, 模型, 开源情况, last

        result = []
        rank = 0
        for row in rows[1:]:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            values = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            values = [re.sub(r"\s+", " ", v).strip() for v in values]
            # values: ['', rank, 'ModelNameCompany', 'HLE', 'ARC', 'FM', 'SWE', 'τ²', 'license', 'detail']

            if len(values) < 5 or not values[2]:
                continue

            rank_str = values[1] if len(values) > 1 else ""
            if rank_str and rank_str.isdigit():
                rank = int(rank_str)
            elif not rank_str:
                rank += 1

            model_company = values[2]

            # Model name and company are concatenated without separator
            # Known companies to split on
            companies = [
                "Anthropic", "OpenAI", "Google Deep Mind", "Facebook AI研究实验室",
                "Moonshot AI", "阿里巴巴", "智谱AI", "DeepSeek-AI", "xAI",
                "Meta", "Microsoft", "Mistral AI", "Cohere", "AI21 Labs",
                "01.AI", "百川智能", "字节跳动", "腾讯", "百度",
                "Apple", "Amazon", "NVIDIA", "Intel", "AMD",
            ]
            company = ""
            model_name = model_company
            for c in companies:
                if model_company.endswith(c):
                    model_name = model_company[: -len(c)]
                    company = c
                    break

            # Scores
            scores = {}
            for i, bname in enumerate(benchmark_names):
                idx = 3 + i
                if idx < len(values):
                    val = values[idx].replace("—", "").strip()
                    scores[bname] = val

            # Build summary from available scores
            score_parts = []
            for bname in benchmark_names:
                v = scores.get(bname, "")
                if v:
                    score_parts.append(f"{bname}: {v}")
            summary = " · ".join(score_parts[:4])

            hle_score = scores.get("HLE", "")
            try:
                score_num = int(float(hle_score) * 100) if hle_score else 0
            except ValueError:
                score_num = 0

            result.append({
                "id": f"dl_{rank}_{model_name}",
                "title": model_name,
                "summary": summary,
                "url": f"https://www.datalearner.com/leaderboards",
                "rank": rank,
                "model": model_name,
                "company": company,
                "license": values[8] if len(values) > 8 else "",
                "scores": scores,
                "HLE": scores.get("HLE", ""),
                "ARC-AGI-2": scores.get("ARC-AGI-2", ""),
                "FrontierMath": scores.get("FrontierMathTier 4", scores.get("FrontierMath Tier 4", "")),
                "SWE-bench": scores.get("SWE-benchVerified", scores.get("SWE-bench Verified", "")),
                "τ²-Bench": scores.get("τ²-Bench", ""),
                "benchmarks": benchmark_names,
                "score": score_num,
                "source_type": "datalearner_leaderboard",
            })

        return result[:limit]

    except Exception:
        return []


@ttl_cache(600)
def fetch_aa_index(_config: dict, limit: int) -> list[dict]:
    """Parse AA Intelligence Index leaderboard from datalearner.com."""
    try:
        resp = httpx.get(
            "https://www.datalearner.com/leaderboards/external/aa-quality-index",
            headers=_headers,
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()
        html = resp.text

        table_m = re.search(r"<table[^>]*>(.*?)</table>", html, re.DOTALL)
        if not table_m:
            return []

        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_m.group(1), re.DOTALL)

        # Known companies for splitting (English names from AA index)
        _companies = [
            "Google Deep Mind", "Moonshot AI", "Meta AI", "Facebook AI研究实验室",
            "DeepSeek-AI", "xAI", "Alibaba", "Anthropic", "OpenAI",
            "Google", "Microsoft", "Mistral AI", "Cohere", "AI21 Labs",
            "01.AI", "智谱AI", "百川智能", "字节跳动", "腾讯", "百度",
            "Apple", "Amazon", "NVIDIA", "Intel", "AMD", "IBM",
            "Swiss AI", "Liquid AI", "Xiaomi", "Hugging Face",
        ]

        result = []
        next_rank = 1
        for row in rows[1:]:  # Skip header
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            # Keep all cells including empty ones (top 3 have SVG icons, no text)
            vals = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            vals = [re.sub(r"\s+", " ", v).strip() for v in vals]
            # vals: ['', 'ModelName (reasoning)Company', 'score', 'company']
            #  or: ['4', 'ModelName (reasoning)Company', 'score', 'company']

            if len(vals) < 4:
                continue

            rank_str = vals[0]
            model_str = vals[1]
            score_str = vals[2]

            try:
                rank = int(rank_str)
            except ValueError:
                rank = next_rank  # Top rows without number (medal icon) — assign sequential

            next_rank = rank + 1

            # Extract reasoning level: " (max)", " (xhigh)", etc.
            reasoning = ""
            reasoning_m = re.search(r"\s*\(([^)]+)\)", model_str)
            if reasoning_m:
                reasoning = reasoning_m.group(1)
                model_str = model_str[:reasoning_m.start()] + model_str[reasoning_m.end():]

            # Split company from model name using the 4th company column
            company = vals[3] if len(vals) > 3 else ""
            model_name = model_str.strip()
            if company and model_name.endswith(company):
                model_name = model_name[:-len(company)].strip()
            else:
                # Fallback: try known companies
                for c in sorted(_companies, key=len, reverse=True):
                    if model_name.endswith(c):
                        company = c
                        model_name = model_name[:-len(c)].strip()
                        break

            title = model_name
            if reasoning:
                title = f"{model_name} ({reasoning})"

            try:
                score_num = int(score_str)
            except ValueError:
                score_num = 0

            result.append({
                "id": f"aa_{rank}_{model_name}",
                "title": title,
                "summary": f"智能指数 {score_str} · {company}" if company else f"智能指数 {score_str}",
                "url": "https://www.datalearner.com/leaderboards/external/aa-quality-index",
                "rank": rank,
                "model": model_name,
                "reasoning": reasoning,
                "aa_score": score_str,
                "company": company,
                "score": score_num,
                "source_type": "datalearner_aa_index",
            })

        return result[:limit]

    except Exception:
        return []
