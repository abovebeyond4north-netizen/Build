# Model Card — Audit Teachable Model

## Purpose

This model teaches a lightweight classifier to recognize Python code-quality issue patterns from `self_audit_improve.py`.

## Model type

Pure-Python multinomial Naive Bayes text classifier.

## Training data

Synthetic labeled Python snippets generated from the tool's issue taxonomy.

## Labels

- `syntax_error`
- `bare_except`
- `broad_exception`
- `high_complexity`
- `todo_marker`
- `magic_number`
- `long_line`
- `missing_docstring`
- `print_usage`

## Metrics

```json
{
  "accuracy": 1.0,
  "correct": 111,
  "total": 111,
  "training_rows": 393,
  "test_rows": 111
}
```

## Limitations

- It classifies short snippets, not whole repositories.
- It is not a replacement for AST-based static analysis.
- It can miss subtle semantic issues.
- It can overfit synthetic examples.
- It should be used as a teaching assistant or triage model, not as a security authority.

## Safety

The model is defensive. It identifies code quality risks and recommends safer implementation paths.

## Recommended next step

Pair this classifier with `self_audit_improve.py`: use the AST tool for ground-truth labels, then use the classifier to pre-triage likely issue categories before deeper static analysis.
