"""Source-agnostic skills pipeline: fetch candidates (per provider) → upsert into
the generic `skills` table → LLM classify (cached, re-runs on prompt change) →
translate descriptions to Chinese. The request-time block reads `skills` rows."""
