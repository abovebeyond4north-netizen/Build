# Teacher-Student Bridge

This upgrade connects the deterministic `self_audit_improve.py` tool to the lightweight model.

## What changed

The bridge turns the audit tool into a rule-based teacher:

1. Generate or collect small Python snippets.
2. Run `self_audit_improve.py` on each snippet.
3. Map detected issues into model labels.
4. Balance the labeled rows so one class does not dominate.
5. Train the tiny student model.
6. Use deterministic guards for sharp cases such as syntax errors, bare `except:`, broad exception handlers, TODO markers, long lines, and print usage.

## Run

From the repository root:

```bash
python audit_teachable_model/teacher_student_bridge.py run
```

Predict from stdin after training:

```bash
printf 'try:\n    run()\nexcept:\n    pass\n' | python audit_teachable_model/teacher_student_bridge.py predict
```

## Outputs

The bridge writes:

- `audit_teachable_model/teacher_labeled_examples.jsonl`
- `audit_teachable_model/teacher_audit_model.json`
- `audit_teachable_model/teacher_training_metrics.json`

The GitHub Actions workflow uploads those as artifacts.

## Current local smoke result

```text
teacher_rows=252
balanced_training_rows=405
fit_accuracy=0.837
labels=bare_except,broad_exception,high_complexity,long_line,magic_number,missing_docstring,print_usage,syntax_error,todo_marker
smoke=passed
```

## Important limitation

This is a bridge and smoke-test pipeline, not a real-world benchmark yet. The next serious upgrade is to feed it real open-source snippets and compare teacher labels against human-reviewed labels.
