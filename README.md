# AI Regression Guard

Developer-first AI regression & failure detection system for production LLM applications.

## What is this?

A system that automatically detects when your AI app's behavior gets worse (regresses) after changes to prompts, models, or agent logic - and can fail CI before bad AI reaches users.

Think of it as **tests + monitoring for AI behavior**.

## 5-Minute Quickstart

### 1. Install

```bash
pip install ai-regression-guard
```

### 2. Create test suite

Create `suite.json` with test cases:

```json
{
  "run_id": "support_ticket_classifier",
  "prompt_template": "Classify this support ticket: {text}\n\nRespond with JSON: {\"category\": \"billing|technical\", \"summary\": \"...\"}",
  "schema": {
    "category": {"type": "string", "enum": ["billing", "technical"]},
    "summary": {"type": "string"}
  },
  "scorer_weights": {
    "refusal": 0.2,
    "schema": 0.3,
    "contains": 0.3,
    "not_contains": 0.1,
    "judge": 0.1
  },
  "cases": [
    {
      "id": "billing_refund",
      "input": {"text": "I was charged twice, need refund"},
      "expected_contains": ["billing", "refund"],
      "rubric": "Must classify as billing issue"
    },
    {
      "id": "password_reset",
      "input": {"text": "Password reset not working"},
      "expected_contains": ["technical", "password"]
    }
  ]
}
```

### 3. Generate baseline

```bash
export OPENAI_API_KEY="your-key"

ai-regression-guard baseline \
  --suite suite.json \
  --provider openai \
  --model gpt-4
```

This creates `.baselines/support_ticket_classifier.json` with per-case scores.

### 4. Check for regressions

```bash
ai-regression-guard check \
  --suite suite.json \
  --provider openai \
  --model gpt-4 \
  --threshold 0.05
```

**Exit codes:**
- `0` = No regression (CI passes ✅)
- `1` = Regression detected (CI fails ❌)

**On regression, you'll see:**
```
[X] REGRESSION DETECTED

TOP 3 WORST CASES:
1. billing_refund
   Baseline: 0.92 | New: 0.65 | Delta: -0.27
   Failing scorers: contains, llm_judge
   Judge: Missing billing terminology

FULL PER-CASE REPORT:
Case ID           Baseline   New     Delta  Failing Scorers    Judge Reason
--------------------------------------------------------------------------------
billing_refund    0.92       0.65    -0.27  contains, judge    Missing billing...
password_reset    0.88       0.87    -0.01  -                  Minor wording...
```

### 5. Set up CI/CD

See `examples/demo_repo/` for a complete working example with GitHub Actions.

```bash
# Clone the demo
cd examples/demo_repo

# Try it yourself
ai-regression-guard check \
  --suite suite_semantic.json \
  --provider openai \
  --model gpt-4
```

## How It Works

1. **Define test inputs** - Create a suite file with test cases
2. **Generate baseline** - Run LLM on inputs, score outputs, store baseline
3. **Check in CI** - Regenerate outputs, compare scores, fail if regressed
4. **Block bad changes** - PR fails if AI quality degrades

## Architecture

- **core/** - Pure logic (scoring, regression detection, baselines)
- **providers/** - LLM integrations (OpenAI, Anthropic, Fake)
- **cli/** - Command-line interface for CI/CD
- **ci/github_action/** - GitHub Action for automated checks

## Current Status

**v0.5** - Adoption + Distribution Pack:
- ✅ **Per-case reporting** - Detailed score breakdown for every test case
- ✅ **Failing scorer analysis** - Identify which specific scorers degraded
- ✅ **Top 3 worst cases** - Highlighted on regression for fast debugging
- ✅ **Judge reason tracking** - LLM explanations stored and displayed
- ✅ **Detailed baseline storage** - Per-case scores with scorer breakdown
- ✅ **Complete demo repository** - Working example with GitHub Actions
- ✅ Refusal detection scorer
- ✅ JSON schema validation scorer
- ✅ ContainsScorer - Check for expected phrases (partial credit)
- ✅ NotContainsScorer - Detect forbidden phrases (refusals, hallucinations)
- ✅ LLMJudgeScorer - Use LLM to judge quality based on rubric
- ✅ Judge caching - Avoid redundant API calls, control costs
- ✅ Composite scorer with weights
- ✅ Regression detection logic
- ✅ File-based baseline storage
- ✅ OpenAI provider (GPT-4, GPT-3.5, etc.)
- ✅ Anthropic provider (Claude models)
- ✅ Fake provider for testing without API costs
- ✅ FakeJudgeProvider - Deterministic judge for testing
- ✅ Baseline command - Generate baselines from LLM outputs
- ✅ Check command - Verify no regressions in CI
- ✅ GitHub Action with provider support
- ✅ Complete test coverage

## CLI Usage

### Generate Baseline

```bash
ai-regression-guard baseline \
  --suite examples/suite.json \
  --provider openai \
  --model gpt-4 \
  --baseline .baselines
```

### Check for Regression

```bash
ai-regression-guard check \
  --suite examples/suite.json \
  --provider openai \
  --model gpt-4 \
  --baseline .baselines \
  --threshold 0.05
```

### Providers

- `openai` - Requires `OPENAI_API_KEY` environment variable
- `anthropic` - Requires `ANTHROPIC_API_KEY` environment variable
- `fake` - No API key needed, deterministic responses for testing

### Optional Flags

- `--no-cache` - Disable judge result caching (debugging only, not recommended in CI)

## Suite File Format

### Basic Suite

```json
{
  "run_id": "your_test_name",
  "schema": {
    "field": {"type": "string", "enum": ["a", "b"]}
  },
  "scorer_weights": {
    "refusal": 0.3,
    "schema": 0.7
  },
  "prompt_template": "Your prompt: {field}",
  "cases": [
    {
      "id": "test_case_1",
      "input": {"field": "value"}
    }
  ]
}
```

### Semantic Evaluation Suite

For catching semantic regressions (wrong answers that still match schema):

```json
{
  "run_id": "support_ticket_classifier_semantic",
  "schema": {
    "category": {"type": "string", "enum": ["billing", "technical", "account"]},
    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
    "summary": {"type": "string"}
  },
  "scorer_weights": {
    "refusal": 0.2,
    "schema": 0.3,
    "contains": 0.2,
    "not_contains": 0.1,
    "judge": 0.2
  },
  "prompt_template": "Classify this ticket: {text}",
  "default_rubric": "Score 0-1. Must classify correctly, include brief summary, avoid hallucinations.",
  "cases": [
    {
      "id": "billing_payment_issue",
      "input": {"text": "Customer can't process payment"},
      "expected_contains": ["billing", "payment"],
      "expected_not_contains": ["cannot help", "as an ai"],
      "rubric": "Must classify as billing with high priority"
    }
  ]
}
```

**Semantic Scoring Features:**

- **expected_contains** - List of phrases that should appear (case-insensitive, partial credit)
- **expected_not_contains** - Forbidden phrases (refusals, hallucinations) - fails if any present
- **rubric** - Per-case rubric for LLM judge (overrides default_rubric, can be null to skip judge)
- **default_rubric** - Default rubric applied to all cases without explicit rubric

##  LLM-as-a-Judge

**IMPORTANT: Judge scoring incurs additional API costs and is cached to minimize expenses.**

The LLMJudgeScorer uses an LLM to evaluate output quality based on a rubric:

### How It Works

1. For each test case with a rubric, the judge LLM receives:
   - Input (the original test input)
   - Output (the generated response to evaluate)
   - Rubric (scoring criteria)

2. Judge returns strict JSON:
   ```json
   {"score": 0.85, "reason": "correctly classified with good summary"}
   ```

3. Result is cached in `.judge_cache/` to avoid redundant API calls

### Judge Caching

**Caching is enabled by default** to control costs and ensure deterministic CI:

- Cache key includes: run_id, case_id, output hash, rubric, judge provider/model
- Second run with same inputs/outputs uses cached score (no API call)
- Cache is stored in `.judge_cache/` directory
- **For debugging only**: Use `--no-cache` flag to bypass cache (not recommended in CI)

### Safety Guarantees

- Judge always uses temperature=0 (deterministic)
- Parse errors fall back to score=0.0 with reason="judge_parse_error"
- API errors fall back to score=0.0 with reason="judge_api_error"
- Never crashes CI, even on judge failures

### Cost Warning

**Using LLM judge increases API costs.**  Each unique output evaluation costs one API call. Cache hits are free. Monitor your `.judge_cache/` directory size to track evaluation coverage.

## GitHub Actions Setup

### 1. Add API key to secrets

Go to your repo → Settings → Secrets → New repository secret

- Name: `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`)
- Value: Your API key

### 2. Create workflow file

`.github/workflows/ai-quality-gate.yml`:

```yaml
name: AI Quality Gate

on:
  pull_request:
  push:
    branches: [main]

jobs:
  ai-regression-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install ai-regression-guard
        run: pip install ai-regression-guard

      - name: Run AI Regression Check
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          ai-regression-guard check \
            --suite suite.json \
            --provider openai \
            --model gpt-4 \
            --threshold 0.05
```

### 3. Commit baseline

Generate and commit your baseline:

```bash
ai-regression-guard baseline \
  --suite suite.json \
  --provider openai \
  --model gpt-4

git add .baselines/
git commit -m "Add AI regression baseline"
git push
```

Now every PR will check for AI quality regressions!

**See `examples/demo_repo/` for a complete working example.**

## Running Tests

```bash
python tests/test_evals.py
python tests/test_regressions.py
python tests/test_cli.py
python tests/test_providers.py
```

## Target User

AI startup engineers running LLMs in production.

## Principles

- Correctness, simplicity, and testability
- No overengineering
- Framework-agnostic core
- CI/CD first-class feature
