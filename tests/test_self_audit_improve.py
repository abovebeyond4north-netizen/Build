import ast
import unittest

from self_audit_improve import AuditIssue, PythonCodeAnalyzer, SelfAuditImproveTool


class PythonCodeAnalyzerTests(unittest.TestCase):
    def test_syntax_error_short_circuits_deeper_analysis(self) -> None:
        issues = PythonCodeAnalyzer("def broken(:\n    pass\n").analyze()

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, "syntax")
        self.assertEqual(issues[0].severity, 10)

    def test_bare_except_is_high_severity_reliability_issue(self) -> None:
        source = """
def example():
    try:
        return 1
    except:
        return 0
"""
        issues = PythonCodeAnalyzer(source).analyze()

        reliability = [issue for issue in issues if issue.category == "reliability"]
        self.assertTrue(reliability)
        self.assertEqual(reliability[0].severity, 9)

    def test_todo_marker_inside_string_is_not_reported(self) -> None:
        source = 'message = "TODO is part of user-visible text"\n'
        issues = PythonCodeAnalyzer(source).analyze()

        markers = [
            issue
            for issue in issues
            if issue.category == "maintainability" and "marker" in issue.problem.lower()
        ]
        self.assertEqual(markers, [])

    def test_todo_marker_in_comment_is_reported_at_comment_line(self) -> None:
        source = 'message = "safe"\n# FIXME replace fallback\nvalue = 1\n'
        issues = PythonCodeAnalyzer(source).analyze()

        markers = [
            issue
            for issue in issues
            if issue.category == "maintainability" and "marker" in issue.problem.lower()
        ]
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].line, 2)

    def test_broad_exception_inside_tuple_is_reported(self) -> None:
        source = """
def example():
    try:
        return 1
    except (ValueError, Exception):
        return 0
"""
        issues = PythonCodeAnalyzer(source).analyze()

        reliability = [issue for issue in issues if issue.category == "reliability"]
        self.assertEqual(len(reliability), 1)
        self.assertEqual(reliability[0].severity, 6)
        self.assertIn("Exception", reliability[0].problem)

    def test_qualified_broad_exception_is_reported(self) -> None:
        source = """
import builtins

def example():
    try:
        return 1
    except builtins.BaseException:
        return 0
"""
        issues = PythonCodeAnalyzer(source).analyze()

        reliability = [issue for issue in issues if issue.category == "reliability"]
        self.assertEqual(len(reliability), 1)
        self.assertIn("BaseException", reliability[0].problem)

    def test_complexity_does_not_leak_from_nested_function(self) -> None:
        source = """
def outer(value):
    def inner(item):
        if item > 0:
            item -= 1
        if item > 1:
            item -= 1
        if item > 2:
            item -= 1
        if item > 3:
            item -= 1
        if item > 4:
            item -= 1
        if item > 5:
            item -= 1
        return item
    return inner(value)
"""
        tree = ast.parse(source)
        outer = tree.body[0]
        self.assertIsInstance(outer, ast.FunctionDef)

        complexity = PythonCodeAnalyzer._estimate_complexity(outer)
        self.assertEqual(complexity, 0)

    def test_complexity_counts_control_flow_in_current_scope(self) -> None:
        source = """
def evaluate(value):
    if value > 0 and value < 10:
        return 1
    for _ in range(2):
        value += 1
    return value
"""
        function = ast.parse(source).body[0]
        self.assertEqual(PythonCodeAnalyzer._estimate_complexity(function), 3)


class SelfAuditImproveToolTests(unittest.TestCase):
    def test_quality_score_is_clamped_at_zero(self) -> None:
        issues = [
            AuditIssue(
                line=index + 1,
                severity=10,
                category="syntax",
                problem="problem",
                recommendation="fix",
            )
            for index in range(11)
        ]

        self.assertEqual(SelfAuditImproveTool._calculate_quality_score(issues), 0)


if __name__ == "__main__":
    unittest.main()
