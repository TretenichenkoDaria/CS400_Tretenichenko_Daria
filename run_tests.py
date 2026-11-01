import os
import subprocess
import sys
import tempfile

python = sys.executable
lli = "/usr/local/Cellar/llvm@15/15.0.7/bin/lli"

opt_flag = ["--remove-unused"] if ("--remove-unused" in sys.argv or os.environ.get("REMOVE_UNUSED") == "1") else []

passed = 0
failed = 0

def run(args, stdin=None):
    r = subprocess.run(args, capture_output=True, text=True, input=stdin)
    return r.stdout, r.stderr, r.returncode

def check(label, actual, expected):
    global passed, failed
    actual = actual.rstrip("\n")
    expected = expected.rstrip("\n")
    if actual == expected:
        print(f"  ok  {label}")
        passed += 1
    else:
        print(f" fail {label}")
        print(f"       expected: {repr(expected)}")
        print(f"       got:      {repr(actual)}")
        failed += 1

print("=== tests/ok ===")
ok_dir = "tests/ok"
for name in sorted(os.listdir(ok_dir)):
    if not name.endswith(".txt"):
        continue
    base = name[:-4]
    src = os.path.join(ok_dir, name)
    exp_file = os.path.join(ok_dir, base + ".expected")
    ast_file = os.path.join(ok_dir, base + ".ast")
    in_file = os.path.join(ok_dir, base + ".in")

    with tempfile.NamedTemporaryFile(suffix=".ll", delete=False) as tmp:
        ll_path = tmp.name

    try:
        out, err, rc = run([python, "compiler.py"] + opt_flag + [src, ll_path])
        if rc != 0:
            print(f" fail {base} (compile failed): {err.strip()}")
            failed += 1
            continue

        if os.path.exists(exp_file):
            stdin_data = None
            if os.path.exists(in_file):
                with open(in_file) as f:
                    stdin_data = f.read()
            stdout, _, rc2 = run([lli, ll_path], stdin=stdin_data)
            with open(exp_file) as f:
                expected = f.read()
            check(base, stdout, expected)

        if os.path.exists(ast_file):
            ast_out, _, _ = run([python, "compiler.py", "--ast", src])
            with open(ast_file) as f:
                expected_ast = f.read()
            check(base + " (--ast)", ast_out, expected_ast)
    finally:
        if os.path.exists(ll_path):
            os.unlink(ll_path)

print()
print("=== tests/err ===")
err_dir = "tests/err"
for name in sorted(os.listdir(err_dir)):
    if not name.endswith(".txt"):
        continue
    base = name[:-4]
    src = os.path.join(err_dir, name)
    exp_file = os.path.join(err_dir, base + ".expected")
    if not os.path.exists(exp_file):
        continue

    with tempfile.NamedTemporaryFile(suffix=".ll", delete=False) as tmp:
        ll_path = tmp.name

    try:
        out, err, rc = run([python, "compiler.py"] + opt_flag + [src, ll_path])
        if rc == 0:
            print(f" fail {base} (expected compile error, got success)")
            failed += 1
            continue
        with open(exp_file) as f:
            expected = f.read()
        check(base, err, expected)
    finally:
        if os.path.exists(ll_path):
            os.unlink(ll_path)

opt_dir = "tests/opt"
if os.path.exists(opt_dir):
    print()
    print("=== tests/opt ===")
    for name in sorted(os.listdir(opt_dir)):
        if not name.endswith(".txt"):
            continue
        base = name[:-4]
        src = os.path.join(opt_dir, name)
        exp_file = os.path.join(opt_dir, base + ".expected")
        astc_file = os.path.join(opt_dir, base + ".astc")
        in_file = os.path.join(opt_dir, base + ".in")

        with tempfile.NamedTemporaryFile(suffix=".ll", delete=False) as tmp:
            ll_path = tmp.name

        try:
            out, err, rc = run([python, "compiler.py", "--remove-unused", src, ll_path])
            if rc != 0:
                print(f" fail {base} (compile with --remove-unused failed): {err.strip()}")
                failed += 1
                continue

            if os.path.exists(exp_file):
                stdin_data = None
                if os.path.exists(in_file):
                    with open(in_file) as f:
                        stdin_data = f.read()
                stdout, _, rc2 = run([lli, ll_path], stdin=stdin_data)
                with open(exp_file) as f:
                    expected = f.read()
                check(base + " (--remove-unused)", stdout, expected)

            if os.path.exists(astc_file):
                astc_out, _, _ = run([python, "compiler.py", "--remove-unused", "--ast-checked", src])
                with open(astc_file) as f:
                    expected_astc = f.read()
                check(base + " (--ast-checked)", astc_out, expected_astc)

            out_noopt, err_noopt, rc_noopt = run([python, "compiler.py", src, ll_path])
            if rc_noopt == 0 and os.path.exists(exp_file):
                stdin_data = None
                if os.path.exists(in_file):
                    with open(in_file) as f:
                        stdin_data = f.read()
                stdout_noopt, _, _ = run([lli, ll_path], stdin=stdin_data)
                with open(exp_file) as f:
                    expected = f.read()
                check(base + " (without flag)", stdout_noopt, expected)
        finally:
            if os.path.exists(ll_path):
                os.unlink(ll_path)

print()
total = passed + failed
print(f"results: {passed}/{total} passed")
if failed:
    sys.exit(1)
