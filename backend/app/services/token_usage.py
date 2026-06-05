def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def extract_token_usage(response: dict, prompt_text: str, completion_text: str) -> dict:
    usage = response.get("usage") or {}
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if isinstance(prompt, int) and isinstance(completion, int) and isinstance(total, int):
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "estimated": False,
        }
    prompt_estimate = estimate_tokens(prompt_text)
    completion_estimate = estimate_tokens(completion_text)
    return {
        "prompt_tokens": prompt_estimate,
        "completion_tokens": completion_estimate,
        "total_tokens": prompt_estimate + completion_estimate,
        "estimated": True,
    }
