# Results

30 Wikipedia articles · judge: `gemini-3.1-flash-lite` · 95% Wilson intervals in brackets

## How faithful are the summaries?

| Summarizer | Summaries | Sentences | Flagged | Contradicted | Not in article | Supported, but quote not found |
|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | 29 | 164 | 7.3% (4–12) | 0.6% (0–3) | 0.0% (0–2) | 6.7% (4–12) |
| `gemini-3.5-flash` | 29 | 169 | 5.9% (3–11) | 0.0% (0–2) | 0.0% (0–2) | 5.9% (3–11) |

## Does the judge catch planted errors?

| Planted error | Cases | Caught | Untouched sentences judged the same as before |
|---|---|---|---|
| negation | 25 | 100.0% (87–100) | 94.8% (89–98) |
| entity | 23 | 100.0% (86–100) | 98.1% (93–99) |
| addition | 29 | 100.0% (88–100) | 91.9% (86–95) |
| number | 20 | 95.0% (76–99) | 95.7% (89–98) |

## Refused by the safety filter

2 requests were refused and are left out of the tables above: Edison Chen (`gemini-3.5-flash-lite`, summarizing); Edison Chen (`gemini-3.5-flash`, summarizing).

## Does the judge agree with a human?

| Check | Result |
|---|---|
| Judge's flags the human agrees with (precision) | 31.8% (16–53) of 22 |
| Sentences the judge passed that the human found unfaithful (misses) | 40.9% (23–61) of 22 |
| Missed entity swaps that are, by chance, still true | 0 of 0 |
