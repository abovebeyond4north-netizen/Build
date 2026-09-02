# Audit Teachable Model

This directory teaches a tiny model from the `self_audit_improve.py` tool's issue taxonomy.

It does **not** train a large language model. It trains a small, transparent, pure-Python multinomial Naive Bayes classifier that learns to classify short Python snippets into the same audit categories used by the tool.

## Files

- `train_audit_model.py` — dependency-free trainer that generates labeled teaching examples.
- `predict_audit_issue.py` — inference script for classifying a snippet after training.
- `training_metrics.json` — result from the first local training run.
- `MODEL_CARD_AUDIT_MODEL.md` — safety, purpose, and limitation notes.

## Current local training result

- Accuracy: `1.000`
- Correct: `111/111`
- Training rows: `393`
- Test rows: `111`

The score is high because the first dataset is synthetic and rule-shaped. Treat it as a teaching scaffold, not proof of real-world generalization.

## Run

```bash
cd audit_teachable_model
python train_audit_model.py
echo "try:\n    run()\nexcept:\n    pass" | python predict_audit_issue.py
```

## What this teaches

The model learns labels like:

- `syntax_error`
- `bare_except`
- `broad_exception`
- `high_complexity`
- `todo_marker`
- `magic_number`
- `long_line`
- `missing_docstring`
- `print_usage`

## Best next upgrade

Use `self_audit_improve.py` as the ground-truth teacher, generate thousands of labeled examples from real open-source snippets, then train a stronger model to predict:

1. issue type,
2. severity,
3. suggested fix,
4. confidence,
5. whether the issue is a false positive for CLI code.
