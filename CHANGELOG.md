# Changelog

All notable changes to ai-regression-guard will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2024-03-02

### Added
- **Cloud Upload Mode**: Upload run reports to hosted API with shareable URLs
- `--cloud` flag for `check` command to enable cloud upload
- `--cloud-url` flag to configure cloud API endpoint (default: https://api.ai-regression-guard.com)
- `--cloud-project` flag to specify project identifier
- `--cloud-api-key` flag for API authentication (or use `AIRG_API_KEY` env var)
- New `cloud/` module with upload client using stdlib urllib
- Automatic retry logic for cloud uploads (1 retry with 10s timeout)
- Comprehensive cloud upload tests with mocked HTTP requests

### Changed
- Cloud upload failures print warnings but don't affect CI exit codes
- API keys are never logged or printed in output
- Cloud reports include tool version, timestamps, and per-case breakdowns

### Security
- API keys sanitized from error messages
- Cloud upload is opt-in only (disabled by default)

## [0.5.0] - 2024-01-XX

### Added
- **Per-case reporting**: Detailed score breakdown for each test case
- **Failing scorer analysis**: Identify which specific scorers degraded per case
- **Top 3 worst cases**: Highlighted in regression reports for quick diagnosis
- **Judge reason tracking**: LLM judge explanations stored and displayed
- **Detailed baseline storage**: Per-case scores with scorer breakdown
- **Demo repository**: Complete working example with GitHub Actions workflow

### Changed
- `baseline` command now stores detailed per-case scores
- `check` command displays comprehensive per-case delta table on regression
- Baseline format upgraded to `DetailedBaselineData` (backwards compatible)
- Default scorer weights now include all 5 scorers

### Fixed
- Weight normalization when scorer weights don't sum to 1.0
- Missing scorer handling in delta computation

## [0.4.0] - 2024-01-XX

### Added
- **Semantic assertions**: `ContainsScorer` and `NotContainsScorer` for content validation
- **LLM-as-a-Judge**: `LLMJudgeScorer` with custom rubrics per test case
- **Judge caching**: SHA256-based deterministic cache for CI/CD stability
- **Composite scorer detailed breakdown**: `score_detailed()` method for per-scorer analysis
- Example suite with semantic assertions (`examples/suite_semantic.json`)
- Comprehensive semantic scoring tests

### Changed
- Judge scoring is now **always cached** by default
- Judge responses use strict JSON-only format
- All judge calls use `temperature=0` for determinism
- Error handling: judge failures return score=0.0 instead of crashing

### Security
- Judge cache uses SHA256 hashing to prevent cache poisoning
- Strict JSON parsing with safe fallbacks

## [0.3.0] - 2024-01-XX

### Added
- **Real LLM integration**: Provider abstraction for OpenAI, Anthropic
- `baseline` command: Generate baselines by running LLM on test suites
- `check` command: Compare new runs against baselines
- `FakeProvider`: Deterministic testing without real API calls
- Suite format with `prompt_template` and input variables

### Changed
- Suite format now uses `input` fields instead of `expected_output`
- CLI now supports `--provider` and `--model` flags

## [0.2.0] - 2024-01-XX

### Added
- **CLI interface**: `ai-regression-guard run` command
- **GitHub Action**: Composite action for CI/CD integration
- Baseline storage and retrieval system
- Exit codes for CI/CD (0 = pass, 1 = fail)
- CLI tests

### Changed
- Moved core logic to `core/` module
- Added `cli/` module for command-line interface

## [0.1.0] - 2024-01-XX

### Added
- Initial release
- Core scoring system: `BaseScorer`, `RefusalScorer`, `JsonSchemaScorer`, `CompositeScorer`
- Regression detection logic with configurable thresholds
- File-based baseline storage
- Basic test suite and examples

---

## Release Strategy

- **0.1.x**: Core scoring engine
- **0.2.x**: CLI and CI/CD integration
- **0.3.x**: Real LLM providers
- **0.4.x**: Semantic assertions and LLM judge
- **0.5.x**: Adoption and distribution (per-case reporting, demos)
- **1.0.0**: Stable API (planned)
