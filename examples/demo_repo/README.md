# AI Regression Guard - Demo Repository

This is a complete working example demonstrating how to use **ai-regression-guard** to prevent AI quality regressions in CI/CD.

## What's Included

- `suite_semantic.json` - Test suite with 3 customer support cases
- `.baselines/` - Pre-generated baseline scores (committed to git)
- `.github/workflows/ai-quality-gate.yml` - GitHub Actions workflow

## 3-Minute Quickstart

### 1. Install

```bash
pip install ai-regression-guard
```

### 2. Set API Key

```bash
export OPENAI_API_KEY="your-key-here"
```

### 3. Run Regression Check

```bash
ai-regression-guard check \
  --suite suite_semantic.json \
  --provider openai \
  --model gpt-4 \
  --threshold 0.05
```

**Expected output:**
```
======================================================================
AI REGRESSION GUARD - CHECK REGRESSION
======================================================================

RUN ID: customer-support-agent-v1
PROVIDER: openai
MODEL: gpt-4
TEST CASES: 3
THRESHOLD: 0.05

BASELINE SCORE: 0.87

Generating outputs...
  billing_simple: Generating... Done
    Score: 0.92
  technical_password: Generating... Done
    Score: 0.85
  billing_cancellation: Generating... Done
    Score: 0.84

NEW AVERAGE SCORE: 0.87

----------------------------------------------------------------------
Metric                                Value
----------------------------------------------------------------------
Baseline Average                       0.87
New Average                            0.87
Delta                                 +0.00
Threshold                             -0.05
----------------------------------------------------------------------

[OK] NO REGRESSION

Quality maintained or improved - PASSING CI
```

## What This Detects

The guard checks for multiple types of quality degradation:

1. **Refusals** - "I cannot help with that"
2. **Schema violations** - Invalid JSON or missing required fields
3. **Semantic regressions** - Missing expected content (e.g., "billing", "refund")
4. **Forbidden content** - Unexpected phrases appearing in output
5. **LLM Judge** - Overall quality assessment by a judge model

## If Regression Detected

When quality drops below baseline, you'll see:

```
[X] REGRESSION DETECTED

TOP 3 WORST CASES:
1. billing_simple
   Baseline: 0.92 | New: 0.72 | Delta: -0.20
   Failing scorers: contains, llm_judge
   Judge: Missing key billing terminology

FULL PER-CASE REPORT:
Case ID              Baseline        New      Delta Failing Scorers            Judge Reason
--------------------------------------------------------------------------------------------------------------------
billing_simple           0.92       0.72      -0.20 contains, llm_judge        Missing key billing terminology
...

Quality degraded beyond threshold - FAILING CI
```

Exit code: **1** (fails CI)

## Updating Your Baseline

When you intentionally improve the prompt:

```bash
# Generate new baseline
ai-regression-guard baseline \
  --suite suite_semantic.json \
  --provider openai \
  --model gpt-4

# Commit the updated baseline
git add .baselines/
git commit -m "Update baseline after prompt improvements"
```

## Using in GitHub Actions

The included `.github/workflows/ai-quality-gate.yml` automatically runs on every PR.

**Requirements:**
- Add `OPENAI_API_KEY` to GitHub Secrets
- Commit `.baselines/` directory to git
- That's it!

Every PR will be blocked if AI quality regresses.

## Next Steps

1. **Customize the test suite** - Add your own cases in `suite_semantic.json`
2. **Adjust scorer weights** - Tune what matters most for your use case
3. **Add judge rubrics** - Get LLM-based quality assessment per case
4. **Set appropriate thresholds** - Balance sensitivity vs noise

---

**Full docs:** https://github.com/yourusername/ai-regression-guard
