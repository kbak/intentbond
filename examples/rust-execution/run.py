"""The caller provides the service and the pinned toolchain in the environment."""

import os
import subprocess
import sys

cargo = [
    sys.executable,
    "-m",
    "intentbond.cargo_junit",
    "--bindings",
    "src/lib.rs",
    "--bindings",
    "tests/service.rs",
]
service = ["execution-example::service", "tests::round_trip"]
commands = [
    [*cargo, "--report", "ordinary.xml", "--exclude", *service],
    [*cargo, "--report", "service.xml", "--ignored", *service],
    [
        sys.executable,
        "-m",
        "intentbond.verus_junit",
        "--source",
        "proofs/arithmetic.rs",
        "--report",
        "proofs.xml",
        "--verus",
        os.environ.get("VERUS", "verus"),
        "--",
        "--edition=2024",
        "--crate-type=lib",
        "--crate-name=arithmetic",
        "--no-cheating",
        "--output-json",
        "--time-expanded",
    ],
]
# Run all producers so one failure still leaves evidence from the other runners.
results = [subprocess.run(command).returncode for command in commands]
sys.exit(int(any(results)))
