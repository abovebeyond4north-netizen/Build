from __future__ import annotations

import ast
import base64
import hashlib
import json
import math
import os
import random
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = 2
AUTHORITY_VERSION = "1.0.0"
HIDDEN_CASE_COUNT = 32
METAMORPHIC_PAIR_COUNT = 8
SUPPORTED_CAPABILITIES = frozenset(
    {
        "normalize_text",
        "sequence_span",
        "clamp_value",
        "python_error_diagnosis",
    }
)
SAFE_CALL_NAMES = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
}
BLOCKED_NAMES = {
    "__builtins__",
    "__import__",
    "breakpoint",
    "classmethod",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "memoryview",
    "object",
    "open",
    "property",
    "setattr",
    "staticmethod",
    "super",
    "type",
    "vars",
}
MAX_SOURCE_BYTES = 16_384
MAX_AST_NODES = 512
RUN_TIMEOUT_SECONDS = 2.0


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_digest(source: str) -> str:
    return sha256_bytes(source.encode("utf-8"))


def authority_digest() -> str:
    return sha256_bytes(Path(__file__).read_bytes())


def manifest_path() -> Path:
    return Path(__file__).with_name("manifest.json")


def load_manifest() -> dict[str, Any]:
    try:
        data = json.loads(manifest_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid authority manifest: {exc}") from exc
    expected = {
        "schema_version": 1,
        "authority_version": AUTHORITY_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "hidden_case_count": HIDDEN_CASE_COUNT,
        "metamorphic_pair_count": METAMORPHIC_PAIR_COUNT,
        "supported_capabilities": sorted(SUPPORTED_CAPABILITIES),
    }
    if data != expected:
        raise RuntimeError(
            "authority manifest does not match executable constants"
        )
    return data


def manifest_digest() -> str:
    return sha256_bytes(canonical_json(load_manifest()))


def state_root() -> Path:
    configured = os.environ.get("DGM_VERIFIER_AUTHORITY_STATE")
    root = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".dgm-verifier-authority"
    )
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


def openssl_bin() -> str:
    value = os.environ.get("DGM_OPENSSL_BIN", "openssl")
    resolved = shutil.which(value)
    if resolved is None:
        raise RuntimeError(
            "OpenSSL is required for verifier-authority signatures"
        )
    return resolved


def ensure_keypair() -> tuple[Path, Path]:
    root = state_root()
    private_key = root / "authority-private.pem"
    public_key = root / "authority-public.pem"
    if private_key.exists() != public_key.exists():
        raise RuntimeError("authority keypair is incomplete")
    if not private_key.exists():
        completed = subprocess.run(
            [
                openssl_bin(),
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
                str(private_key),
            ],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "unable to generate authority private key: "
                + completed.stderr.decode(
                    "utf-8",
                    errors="replace",
                )[-500:]
            )
        completed = subprocess.run(
            [
                openssl_bin(),
                "pkey",
                "-in",
                str(private_key),
                "-pubout",
                "-out",
                str(public_key),
            ],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "unable to derive authority public key: "
                + completed.stderr.decode(
                    "utf-8",
                    errors="replace",
                )[-500:]
            )
    try:
        private_key.chmod(0o600)
        public_key.chmod(0o644)
    except OSError:
        pass
    return private_key, public_key


def public_key_pem() -> str:
    _, public_key = ensure_keypair()
    return public_key.read_text(encoding="utf-8")


def public_key_sha256() -> str:
    return sha256_bytes(public_key_pem().encode("utf-8"))


def sign_payload(payload: dict[str, Any]) -> str:
    private_key, _ = ensure_keypair()
    completed = subprocess.run(
        [
            openssl_bin(),
            "dgst",
            "-sha256",
            "-sign",
            str(private_key),
        ],
        input=canonical_json(payload),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "unable to sign verifier receipt: "
            + completed.stderr.decode(
                "utf-8",
                errors="replace",
            )[-500:]
        )
    return base64.b64encode(completed.stdout).decode("ascii")


def authority_identity() -> dict[str, Any]:
    manifest = load_manifest()
    identity = {
        "schema_version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "authority_version": AUTHORITY_VERSION,
        "authority_digest": authority_digest(),
        "manifest_digest": sha256_bytes(canonical_json(manifest)),
        "public_key_sha256": public_key_sha256(),
        "supported_capabilities": sorted(SUPPORTED_CAPABILITIES),
        "hidden_case_count": HIDDEN_CASE_COUNT,
        "metamorphic_pair_count": METAMORPHIC_PAIR_COUNT,
    }
    return {
        "identity": identity,
        "identity_signature": sign_payload(identity),
        "public_key_pem": public_key_pem(),
    }


def ledger_path() -> Path:
    return state_root() / "private_evaluations.jsonl"


def load_private_records() -> list[dict[str, Any]]:
    path = ledger_path()
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"invalid private authority ledger line {line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise RuntimeError(
                f"invalid private authority ledger line {line_number}"
            )
        records.append(row)
    return records


def append_private_record(row: dict[str, Any]) -> None:
    path = ledger_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                row,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )
    try:
        path.chmod(0o600)
    except OSError:
        pass


def find_consumed(
    capability: str,
    baseline_digest: str,
    finalist_digest: str,
) -> dict[str, Any] | None:
    current_authority = authority_digest()
    current_manifest = manifest_digest()
    for row in reversed(load_private_records()):
        receipt = row.get("receipt")
        if not isinstance(receipt, dict):
            continue
        if (
            receipt.get("capability") == capability
            and receipt.get("baseline_digest") == baseline_digest
            and receipt.get("finalist_digest") == finalist_digest
            and receipt.get("authority_digest") == current_authority
            and receipt.get("manifest_digest") == current_manifest
            and receipt.get("protocol_version") == PROTOCOL_VERSION
        ):
            return row
    return None


def validate_source(
    source: str,
    entrypoint: str,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if not isinstance(source, str):
        return False, ("candidate source must be text",)
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        reasons.append("candidate source exceeds byte limit")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, (f"syntax error: {exc}",)

    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        reasons.append("candidate AST exceeds node limit")

    functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
    ]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            continue
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        reasons.append(
            "candidate module may contain only a docstring and one function"
        )
        break

    if len(functions) != 1 or functions[0].name != entrypoint:
        reasons.append(
            f"candidate must define exactly one function named {entrypoint}"
        )
    elif isinstance(functions[0], ast.AsyncFunctionDef):
        reasons.append("async candidate functions are not supported")
    else:
        function = functions[0]
        if function.decorator_list:
            reasons.append("candidate decorators are not supported")
        if (
            function.args.vararg
            or function.args.kwarg
            or function.args.kwonlyargs
        ):
            reasons.append(
                "candidate functions must use fixed positional arguments"
            )
        if function.args.defaults:
            reasons.append(
                "candidate functions may not define default arguments"
            )

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.Import,
                ast.ImportFrom,
                ast.ClassDef,
                ast.Lambda,
                ast.Global,
                ast.Nonlocal,
            ),
        ):
            reasons.append(
                f"unsupported candidate syntax: {type(node).__name__}"
            )
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                reasons.append(
                    "private/dunder attribute access is forbidden: "
                    f"{node.attr}"
                )
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                reasons.append(
                    "candidate functions may not write or delete attributes"
                )
        if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            reasons.append(f"forbidden name: {node.id}")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id not in SAFE_CALL_NAMES
        ):
            reasons.append(
                "call is not in the pure builtin allowlist: "
                f"{node.func.id}"
            )

    unique = tuple(dict.fromkeys(reasons))
    return not unique, unique


_RUNNER_SOURCE = r'''
import json
import sys

try:
    import resource
except ImportError:
    resource = None

if resource is not None:
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
        resource.setrlimit(
            resource.RLIMIT_AS,
            (128 * 1024 * 1024, 128 * 1024 * 1024),
        )
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (1024 * 1024, 1024 * 1024),
        )
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    except (ValueError, OSError):
        pass

candidate_path, entrypoint, cases_path, result_path = sys.argv[1:]
source = open(candidate_path, "r", encoding="utf-8").read()
safe_builtins = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}
namespace = {"__builtins__": safe_builtins}
exec(
    compile(source, "<candidate>", "exec"),
    namespace,
    namespace,
)
function = namespace[entrypoint]
cases = json.load(open(cases_path, "r", encoding="utf-8"))
outputs = []
errors = []
for case in cases:
    try:
        outputs.append(function(*case["args"]))
        errors.append(None)
    except BaseException as exc:
        outputs.append(None)
        errors.append(type(exc).__name__)
with open(result_path, "w", encoding="utf-8") as handle:
    json.dump(
        {"outputs": outputs, "errors": errors},
        handle,
        allow_nan=False,
    )
'''


def evaluate_outputs(
    source: str,
    entrypoint: str,
    cases: list[dict[str, Any]],
) -> tuple[list[Any], tuple[str, ...]]:
    passed, reasons = validate_source(source, entrypoint)
    if not passed:
        return [None for _ in cases], reasons

    with tempfile.TemporaryDirectory(
        prefix="dgm-authority-"
    ) as tmp:
        root = Path(tmp)
        candidate = root / "candidate.py"
        case_file = root / "cases.json"
        result_file = root / "result.json"
        runner = root / "runner.py"
        candidate.write_text(source, encoding="utf-8")
        case_file.write_text(
            json.dumps(
                [{"args": item["args"]} for item in cases],
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        runner.write_text(_RUNNER_SOURCE, encoding="utf-8")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    str(runner),
                    str(candidate),
                    entrypoint,
                    str(case_file),
                    str(result_file),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return (
                [None for _ in cases],
                ("candidate execution timed out",),
            )
        if completed.returncode != 0 or not result_file.exists():
            detail = (
                completed.stderr
                or completed.stdout
                or "runner failed"
            ).strip()[-500:]
            return (
                [None for _ in cases],
                (f"runner failure: {detail}",),
            )
        try:
            payload = json.loads(
                result_file.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            return (
                [None for _ in cases],
                (f"invalid runner result: {exc}",),
            )
        outputs = payload.get("outputs")
        if (
            not isinstance(outputs, list)
            or len(outputs) != len(cases)
        ):
            return (
                [None for _ in cases],
                ("runner returned invalid output vector",),
            )
        return outputs, ()


def score_outputs(
    outputs: list[Any],
    cases: list[dict[str, Any]],
) -> float:
    if not cases or len(outputs) != len(cases):
        return 0.0
    passed = sum(
        output == case["expected"]
        for output, case in zip(outputs, cases)
    )
    return passed / len(cases)


def hidden_cases(
    capability: str,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)

    if capability == "normalize_text":
        vocabulary = (
            "Alpha",
            "BETA",
            "MiXeD",
            "CAFÉ",
            "delta",
            "OMEGA",
            "value42",
            "North",
        )
        separators = (
            " ",
            "  ",
            "\t",
            "\n",
            " \t ",
            "\r\n",
        )
        padding = ("", " ", "  ", "\t", "\n")
        cases: list[dict[str, Any]] = []
        for index in range(HIDDEN_CASE_COUNT):
            words = [
                rng.choice(vocabulary)
                for _ in range(rng.randint(1, 5))
            ]
            words = [
                word.lower()
                if rng.randrange(2)
                else word.upper()
                for word in words
            ]
            raw = rng.choice(padding)
            for position, word in enumerate(words):
                raw += (
                    rng.choice(separators)
                    if position
                    else ""
                ) + word
            raw += rng.choice(padding)
            cases.append(
                {
                    "name": f"hidden_normalize_{index}",
                    "args": [raw],
                    "expected": " ".join(
                        raw.lower().split()
                    ),
                }
            )
        return cases

    if capability == "sequence_span":
        cases = []
        for index in range(HIDDEN_CASE_COUNT):
            values = [
                rng.randint(-240, 240) / 4.0
                for _ in range(rng.randint(2, 9))
            ]
            cases.append(
                {
                    "name": f"hidden_span_{index}",
                    "args": [values],
                    "expected": max(values) - min(values),
                }
            )
        return cases

    if capability == "clamp_value":
        cases = []
        for index in range(HIDDEN_CASE_COUNT):
            lower = rng.randint(-160, 40) / 4.0
            upper = lower + rng.randint(1, 120) / 4.0
            value = rng.randint(
                int(lower * 4) - 80,
                int(upper * 4) + 80,
            ) / 4.0
            cases.append(
                {
                    "name": f"hidden_clamp_{index}",
                    "args": [value, lower, upper],
                    "expected": min(
                        max(value, lower),
                        upper,
                    ),
                }
            )
        return cases

    if capability == "python_error_diagnosis":
        names = (
            "payload",
            "matrix",
            "cursor",
            "cache",
            "record",
            "sample",
        )
        type_templates = (
            "TypeError: object of type 'float' has no len()",
            "TypeError: 'int' object is not iterable",
            (
                "TypeError: unsupported operand type(s) "
                "for -: 'str' and 'int'"
            ),
            (
                "TypeError: list indices must be "
                "integers or slices, not str"
            ),
        )
        index_templates = (
            "IndexError: list index out of range",
            "IndexError: tuple index out of range",
            "IndexError: string index out of range",
            (
                "IndexError: list assignment "
                "index out of range"
            ),
        )
        categories = (
            "undefined_name",
            "type_mismatch",
            "bad_index",
        )
        cases = []
        for index in range(HIDDEN_CASE_COUNT):
            category = categories[index % 3]
            if category == "undefined_name":
                message = (
                    "NameError: name "
                    f"'{rng.choice(names)}_{rng.randrange(10000)}' "
                    "is not defined"
                )
            elif category == "type_mismatch":
                message = rng.choice(type_templates)
            else:
                message = rng.choice(index_templates)
            cases.append(
                {
                    "name": f"hidden_python_{index}",
                    "args": [message],
                    "expected": category,
                }
            )
        rng.shuffle(cases)
        return cases

    raise ValueError("unsupported capability")


def metamorphic_pairs(
    capability: str,
    seed: int,
) -> list[
    tuple[
        dict[str, Any],
        dict[str, Any],
    ]
]:
    rng = random.Random(seed ^ 0x5A17D3E5)
    pairs: list[
        tuple[
            dict[str, Any],
            dict[str, Any],
        ]
    ] = []

    if capability == "normalize_text":
        words = (
            "Alpha",
            "Beta",
            "Gamma",
            "CAFÉ",
            "North",
        )
        for index in range(METAMORPHIC_PAIR_COUNT):
            selected = [
                rng.choice(words)
                for _ in range(rng.randint(1, 4))
            ]
            base = " ".join(selected)
            perturbed = (
                "\t  "
                + "\n ".join(
                    word.swapcase()
                    for word in selected
                )
                + "  \n"
            )
            expected = " ".join(
                base.lower().split()
            )
            pairs.append(
                (
                    {
                        "name": f"meta_norm_a_{index}",
                        "args": [base],
                        "expected": expected,
                    },
                    {
                        "name": f"meta_norm_b_{index}",
                        "args": [perturbed],
                        "expected": expected,
                    },
                )
            )
        return pairs

    if capability == "sequence_span":
        for index in range(METAMORPHIC_PAIR_COUNT):
            values = [
                rng.randint(-30, 30)
                for _ in range(rng.randint(2, 7))
            ]
            shift = rng.randint(-50, 50)
            transformed = list(
                reversed(
                    [
                        value + shift
                        for value in values
                    ]
                )
            )
            expected = max(values) - min(values)
            pairs.append(
                (
                    {
                        "name": f"meta_span_a_{index}",
                        "args": [values],
                        "expected": expected,
                    },
                    {
                        "name": f"meta_span_b_{index}",
                        "args": [transformed],
                        "expected": expected,
                    },
                )
            )
        return pairs

    if capability == "clamp_value":
        for index in range(METAMORPHIC_PAIR_COUNT):
            lower = rng.randint(-20, 0)
            upper = rng.randint(1, 20)
            value = rng.randint(-50, 50)
            clipped = min(
                max(value, lower),
                upper,
            )
            pairs.append(
                (
                    {
                        "name": f"meta_clamp_a_{index}",
                        "args": [
                            value,
                            lower,
                            upper,
                        ],
                        "expected": clipped,
                    },
                    {
                        "name": f"meta_clamp_b_{index}",
                        "args": [
                            clipped,
                            lower,
                            upper,
                        ],
                        "expected": clipped,
                    },
                )
            )
        return pairs

    if capability == "python_error_diagnosis":
        for index in range(METAMORPHIC_PAIR_COUNT):
            left = (
                "NameError: name "
                f"'symbol_{rng.randrange(10000)}' "
                "is not defined"
            )
            right = (
                "NameError: name "
                f"'renamed_{rng.randrange(10000)}' "
                "is not defined"
            )
            pairs.append(
                (
                    {
                        "name": f"meta_error_a_{index}",
                        "args": [left],
                        "expected": "undefined_name",
                    },
                    {
                        "name": f"meta_error_b_{index}",
                        "args": [right],
                        "expected": "undefined_name",
                    },
                )
            )
        return pairs

    raise ValueError("unsupported capability")


def metamorphic_score(
    outputs: list[Any],
    pairs: list[
        tuple[
            dict[str, Any],
            dict[str, Any],
        ]
    ],
) -> float:
    if not pairs or len(outputs) != 2 * len(pairs):
        return 0.0
    passed = 0
    for index, (left, right) in enumerate(pairs):
        left_output = outputs[2 * index]
        right_output = outputs[2 * index + 1]
        if (
            left_output == left["expected"]
            and right_output == right["expected"]
            and left_output == right_output
        ):
            passed += 1
    return passed / len(pairs)


def suite_digest(
    cases: list[dict[str, Any]],
    pairs: list[
        tuple[
            dict[str, Any],
            dict[str, Any],
        ]
    ],
) -> str:
    payload = {
        "hidden": cases,
        "metamorphic_pairs": pairs,
    }
    return sha256_bytes(canonical_json(payload))


def containment_self_test() -> tuple[
    bool,
    tuple[str, ...],
]:
    failures: list[str] = []
    forbidden = {
        "import": (
            "import os\n\n"
            "def solve(x0):\n"
            "    return x0\n"
        ),
        "filesystem": (
            "def solve(x0):\n"
            "    return open('probe.txt', 'w')\n"
        ),
        "dunder": (
            "def solve(x0):\n"
            "    return x0.__class__\n"
        ),
        "dynamic_import": (
            "def solve(x0):\n"
            "    return __import__('os')\n"
        ),
    }
    for name, source in forbidden.items():
        allowed, _ = validate_source(
            source,
            "solve",
        )
        if allowed:
            failures.append(
                f"{name}_probe_was_not_blocked"
            )

    _, errors = evaluate_outputs(
        (
            "def solve(x0):\n"
            "    while True:\n"
            "        pass\n"
        ),
        "solve",
        [
            {
                "name": "timeout",
                "args": [1],
                "expected": 1,
            }
        ],
    )
    if not errors or not any(
        (
            "timed out" in item
            or "runner failure" in item
        )
        for item in errors
    ):
        failures.append(
            "timeout_probe_was_not_terminated"
        )

    safe, reasons = validate_source(
        "def solve(x0):\n    return x0\n",
        "solve",
    )
    if not safe:
        failures.append(
            "safe_probe_rejected:"
            + "|".join(reasons)
        )

    return not failures, tuple(failures)


def require_score(
    value: Any,
    name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise ValueError(f"{name} must be numeric")
    score = float(value)
    if (
        not math.isfinite(score)
        or not 0.0 <= score <= 1.0
    ):
        raise ValueError(
            f"{name} must be finite and between 0 and 1"
        )
    return score


def validate_request(
    request: dict[str, Any],
) -> tuple[
    str,
    str,
    str,
    str,
    float,
    float,
]:
    if (
        request.get("protocol_version")
        != PROTOCOL_VERSION
    ):
        raise ValueError(
            "protocol version mismatch"
        )
    capability = request.get("capability")
    entrypoint = request.get("entrypoint")
    baseline_source = request.get(
        "baseline_source"
    )
    finalist_source = request.get(
        "finalist_source"
    )
    if capability not in SUPPORTED_CAPABILITIES:
        raise ValueError("unsupported capability")
    if (
        not isinstance(entrypoint, str)
        or not entrypoint.isidentifier()
        or entrypoint.startswith("_")
    ):
        raise ValueError("invalid entrypoint")
    if (
        not isinstance(baseline_source, str)
        or not baseline_source.strip()
    ):
        raise ValueError(
            "invalid baseline source"
        )
    if (
        not isinstance(finalist_source, str)
        or not finalist_source.strip()
    ):
        raise ValueError(
            "invalid finalist source"
        )

    required_score = require_score(
        request.get("required_score"),
        "required_score",
    )
    minimum_gain = require_score(
        request.get("minimum_gain"),
        "minimum_gain",
    )
    return (
        capability,
        entrypoint,
        baseline_source,
        finalist_source,
        required_score,
        minimum_gain,
    )


def evaluate_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    (
        capability,
        entrypoint,
        baseline_source,
        finalist_source,
        required_score,
        minimum_gain,
    ) = validate_request(request)

    baseline_digest = source_digest(
        baseline_source
    )
    finalist_digest = source_digest(
        finalist_source
    )

    consumed = find_consumed(
        capability,
        baseline_digest,
        finalist_digest,
    )
    if consumed is not None:
        receipt = consumed["receipt"]
        if (
            abs(
                float(receipt["required_score"])
                - required_score
            )
            > 1e-12
            or abs(
                float(receipt["minimum_gain"])
                - minimum_gain
            )
            > 1e-12
        ):
            raise ValueError(
                "authority evidence already consumed "
                "under different acceptance thresholds"
            )
        return {
            "receipt": receipt,
            "signature": consumed["signature"],
            "public_key_pem": public_key_pem(),
            "reused": True,
        }

    seed = secrets.randbits(63)
    cases = hidden_cases(
        capability,
        seed,
    )
    pairs = metamorphic_pairs(
        capability,
        seed,
    )
    pair_cases = [
        item
        for pair in pairs
        for item in pair
    ]

    (
        containment_passed,
        containment_failures,
    ) = containment_self_test()

    baseline_outputs, baseline_errors = (
        evaluate_outputs(
            baseline_source,
            entrypoint,
            cases,
        )
    )
    finalist_outputs, finalist_errors = (
        evaluate_outputs(
            finalist_source,
            entrypoint,
            cases,
        )
    )
    (
        baseline_meta_outputs,
        baseline_meta_errors,
    ) = evaluate_outputs(
        baseline_source,
        entrypoint,
        pair_cases,
    )
    (
        finalist_meta_outputs,
        finalist_meta_errors,
    ) = evaluate_outputs(
        finalist_source,
        entrypoint,
        pair_cases,
    )

    baseline_score = score_outputs(
        baseline_outputs,
        cases,
    )
    finalist_score = score_outputs(
        finalist_outputs,
        cases,
    )
    baseline_meta = metamorphic_score(
        baseline_meta_outputs,
        pairs,
    )
    finalist_meta = metamorphic_score(
        finalist_meta_outputs,
        pairs,
    )
    delta = finalist_score - baseline_score

    if not containment_passed:
        passed = False
        reason = "containment_probe_failed"
    elif finalist_digest == baseline_digest:
        passed = False
        reason = "identical_to_baseline"
    elif (
        finalist_score + 1e-12
        < required_score
    ):
        passed = False
        reason = (
            "hidden_suite_below_required_score"
        )
    elif (
        finalist_meta + 1e-12
        < required_score
    ):
        passed = False
        reason = (
            "metamorphic_suite_below_required_score"
        )
    elif delta + 1e-12 < minimum_gain:
        passed = False
        reason = "hidden_suite_insufficient_gain"
    else:
        passed = True
        reason = "passed"

    receipt = {
        "schema_version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "authority_version": AUTHORITY_VERSION,
        "authority_digest": authority_digest(),
        "manifest_digest": manifest_digest(),
        "public_key_sha256": public_key_sha256(),
        "evaluation_id": secrets.token_hex(16),
        "capability": capability,
        "baseline_digest": baseline_digest,
        "finalist_digest": finalist_digest,
        "suite_digest": suite_digest(
            cases,
            pairs,
        ),
        "hidden_case_count": len(cases),
        "metamorphic_pair_count": len(pairs),
        "containment_passed": (
            containment_passed
        ),
        "baseline_score": baseline_score,
        "finalist_score": finalist_score,
        "baseline_metamorphic_score": (
            baseline_meta
        ),
        "finalist_metamorphic_score": (
            finalist_meta
        ),
        "delta": delta,
        "required_score": required_score,
        "minimum_gain": minimum_gain,
        "passed": passed,
        "reason": reason,
        "created_at": time.time(),
    }
    signature = sign_payload(receipt)
    append_private_record(
        {
            "receipt": receipt,
            "signature": signature,
            "seed": seed,
            "entrypoint": entrypoint,
            "containment_failures": list(
                containment_failures
            ),
            "baseline_error_count": (
                len(baseline_errors)
                + len(baseline_meta_errors)
            ),
            "finalist_error_count": (
                len(finalist_errors)
                + len(finalist_meta_errors)
            ),
        }
    )

    return {
        "receipt": receipt,
        "signature": signature,
        "public_key_pem": public_key_pem(),
        "reused": False,
    }


def replay_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    if (
        request.get("protocol_version")
        != PROTOCOL_VERSION
    ):
        raise ValueError(
            "protocol version mismatch"
        )
    evaluation_id = request.get(
        "evaluation_id"
    )
    baseline_source = request.get(
        "baseline_source"
    )
    finalist_source = request.get(
        "finalist_source"
    )
    if (
        not isinstance(evaluation_id, str)
        or not evaluation_id
    ):
        raise ValueError(
            "evaluation_id must be non-empty"
        )
    if (
        not isinstance(baseline_source, str)
        or not baseline_source.strip()
    ):
        raise ValueError(
            "invalid baseline source"
        )
    if (
        not isinstance(finalist_source, str)
        or not finalist_source.strip()
    ):
        raise ValueError(
            "invalid finalist source"
        )

    record = next(
        (
            row
            for row in reversed(
                load_private_records()
            )
            if isinstance(
                row.get("receipt"),
                dict,
            )
            and row["receipt"].get(
                "evaluation_id"
            )
            == evaluation_id
        ),
        None,
    )
    if record is None:
        raise ValueError(
            "unknown evaluation_id"
        )

    receipt = record["receipt"]
    if (
        source_digest(baseline_source)
        != receipt.get("baseline_digest")
    ):
        raise ValueError(
            "baseline source does not match receipt"
        )
    if (
        source_digest(finalist_source)
        != receipt.get("finalist_digest")
    ):
        raise ValueError(
            "finalist source does not match receipt"
        )

    seed = record.get("seed")
    if (
        isinstance(seed, bool)
        or not isinstance(seed, int)
        or seed < 0
    ):
        raise RuntimeError(
            "private authority record has invalid seed"
        )

    capability = receipt["capability"]
    entrypoint = record["entrypoint"]
    cases = hidden_cases(
        capability,
        seed,
    )
    pairs = metamorphic_pairs(
        capability,
        seed,
    )
    pair_cases = [
        item
        for pair in pairs
        for item in pair
    ]

    baseline_outputs, _ = evaluate_outputs(
        baseline_source,
        entrypoint,
        cases,
    )
    finalist_outputs, _ = evaluate_outputs(
        finalist_source,
        entrypoint,
        cases,
    )
    baseline_meta_outputs, _ = (
        evaluate_outputs(
            baseline_source,
            entrypoint,
            pair_cases,
        )
    )
    finalist_meta_outputs, _ = (
        evaluate_outputs(
            finalist_source,
            entrypoint,
            pair_cases,
        )
    )

    replay = {
        "schema_version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "authority_version": AUTHORITY_VERSION,
        "authority_digest": authority_digest(),
        "manifest_digest": manifest_digest(),
        "public_key_sha256": public_key_sha256(),
        "evaluation_id": evaluation_id,
        "suite_digest": suite_digest(
            cases,
            pairs,
        ),
        "baseline_score": score_outputs(
            baseline_outputs,
            cases,
        ),
        "finalist_score": score_outputs(
            finalist_outputs,
            cases,
        ),
        "baseline_metamorphic_score": (
            metamorphic_score(
                baseline_meta_outputs,
                pairs,
            )
        ),
        "finalist_metamorphic_score": (
            metamorphic_score(
                finalist_meta_outputs,
                pairs,
            )
        ),
        "replay_of_signature": (
            record["signature"]
        ),
        "created_at": time.time(),
    }
    replay["matches_original"] = (
        replay["suite_digest"]
        == receipt.get("suite_digest")
        and abs(
            replay["baseline_score"]
            - float(
                receipt["baseline_score"]
            )
        )
        <= 1e-12
        and abs(
            replay["finalist_score"]
            - float(
                receipt["finalist_score"]
            )
        )
        <= 1e-12
        and abs(
            replay[
                "baseline_metamorphic_score"
            ]
            - float(
                receipt[
                    "baseline_metamorphic_score"
                ]
            )
        )
        <= 1e-12
        and abs(
            replay[
                "finalist_metamorphic_score"
            ]
            - float(
                receipt[
                    "finalist_metamorphic_score"
                ]
            )
        )
        <= 1e-12
    )

    return {
        "replay": replay,
        "replay_signature": sign_payload(
            replay
        ),
        "public_key_pem": public_key_pem(),
    }


def emit(
    value: dict[str, Any],
    code: int = 0,
) -> int:
    sys.stdout.write(
        json.dumps(
            value,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return code


def main(
    argv: list[str] | None = None,
) -> int:
    args = list(
        sys.argv[1:]
        if argv is None
        else argv
    )
    try:
        command = (
            args[0]
            if args
            else "describe"
        )
        if command == "describe":
            return emit(
                authority_identity()
            )

        request = json.loads(
            sys.stdin.read()
        )
        if not isinstance(request, dict):
            raise ValueError(
                "request must be a JSON object"
            )

        if command == "evaluate":
            return emit(
                evaluate_request(request)
            )
        if command == "replay":
            return emit(
                replay_request(request)
            )
        raise ValueError(
            f"unknown command: {command}"
        )
    except Exception as exc:
        return emit(
            {
                "protocol_version": (
                    PROTOCOL_VERSION
                ),
                "authority_version": (
                    AUTHORITY_VERSION
                ),
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            },
            2,
        )


if __name__ == "__main__":
    raise SystemExit(main())
