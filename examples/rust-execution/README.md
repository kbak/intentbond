# Cargo and Verus execution evidence

Use the [scope](.intentbond/scope.json) and [test command](run.py) together.
They produce one JUnit report per invocation and require passing observations
for two Rust tests and a Verus lemma. Both Rust tests have the same full test
name. Nextest's package-qualified binary ID distinguishes their targets.

## Toolchain and installation

CI qualifies stable Rust/Cargo 1.99.1, cargo-nextest 0.9.152, and Verus
0.2026.11.02.8bf68ee on Linux x86-64. Install IntentBond from the selected
commit into a virtual environment **outside** the project. Activate it so both
`ib` and the scope's `python3` resolve there. Run `ib install-oft` once.
Install the Rust toolchain and both runner releases outside the checkout.
Put Cargo, rustc, and cargo-nextest on PATH. Set `RUSTUP_TOOLCHAIN=1.99.1`
and point `VERUS` to the absolute path of the pinned release's `verus` executable.
The [CI workflow](../../.github/workflows/ci.yml) gives the exact Linux releases
and checksum verification steps.

Inside `ib check`, the command runs in an exported candidate. Keep Cargo.lock
in source control. A populated external Cargo registry/git cache can supply
dependencies, including offline builds with `CARGO_NET_OFFLINE=true`. Each
producer invocation builds into a fresh directory by default. The adapter uses nextest's
native JUnit and JSON discovery on stable Rust. It does not use unstable
libtest JSON or set RUSTC_BOOTSTRAP. Cargo features are selectable with
`--features`; repeat `--package` to restrict workspace packages.

## Cargo

Put the explicit nextest binary ID and full test name on the existing named
OFT declaration in a Rust file passed with `--bindings`. Use one declaration
per bound runner identity. The same source line supplies the artifact revision
to OFT and to the producer.

```rust
// [utest~service~1->req~readiness~1] ib-cargo execution-example::service tests::round_trip
```

Run the ignored service-backed test separately. The caller starts the service
before invoking IntentBond, supplies its connection settings through the
environment, and stops it afterwards. The sample expects a TCP endpoint in
`EXAMPLE_READY_ADDR` that sends the line `ready`. PostgreSQL or Moto users can
supply their own fixtures and connection settings in exactly the same way.

```sh
python -m intentbond.cargo_junit --report ordinary.xml \
  --bindings src/lib.rs --bindings tests/service.rs \
  --exclude execution-example::service tests::round_trip
python -m intentbond.cargo_junit --report service.xml --bindings tests/service.rs \
  --ignored execution-example::service tests::round_trip
```

Use `cargo nextest list --run-ignored all --message-format json` to inspect
the binary IDs, package/target metadata, full names and ignored flags. Both
selectors match an exact binary/test pair. Each explicitly selected ignored
test must be present and marked ignored. Ordinary runs count each selected
ignored case as skipped using discovery. The native run must report one
unambiguous final result for each expected execution. Missing, duplicate,
retry and conflicting outcomes fail the run. An artifact reported as skipped
in one report and passing in another has mixed evidence and fails the gate.

The adapter runs workspace libtest tests using its own nextest profile with
zero retries. Rustdoc tests, custom harnesses with other output conventions,
and repository nextest profiles are outside the qualified interface. Run
additional project commands in the scope's wrapper and propagate their failures.

### Reuse one captured build

1. Install the same IntentBond pin for the checker and the Python environment
   that invokes the producers. Add `"cargo_build": {}` to `tests` in the trusted
   scope. An empty object selects the locked workspace with its default features.
   For a narrower build, use e.g. `{"packages": ["server"], "features": "postgres"}`.
   Put compile-time settings in the environment of `ib check`.
2. Once that scope is accepted as the baseline, add `--use-captured-build` to
   each participating Cargo invocation above. Move any package/feature options
   to the scope. Keep the separate reports, bindings, exact selectors and
   service observations, including per-invocation environment variables.
   Other producers can keep their existing command lines.

IntentBond prepares one [nextest archive](https://nexte.st/docs/ci-features/archiving/)
in a new private directory outside the exported candidate, before running the
fixture driver. The target and intermediate build directories start empty. Each
producer checks the captured root, source manifest, tool versions and Cargo/Rust
environment, then verifies a private copy against the preparation digest. Both
discovery and execution use that copy. Each invocation gets a separate nextest
store, native JUnit destination and linked report. Fixture variables supplied to
the driver affect execution only. To compile with different settings, use a
fresh-target invocation or a separate check. The linked suite records the
archive digest, captured source digest and scope build options. Check and verify
match these fields to the preparation record. Archive reuse requires test
binaries that can run from an extracted nextest target directory.

The archive lives for one test command. A new check builds again, even at the
same commit. IntentBond accepts no target directory or archive supplied by the
caller. Keep external Cargo configuration, tool installations and build inputs
stable for the check. Use an isolated worker with trusted tools, dependencies, build scripts,
test driver and filesystem for the duration of the check. Commands run as the
worker account and can alter its files or fabricate reports. The digest checks
detect mismatched source and archive contents within this trust boundary.

To retain doctest coverage without compiling dependencies again, enable
`"cargo_build": {"doctests": true}`. The checker runs doctests in the private
compilation directory before discarding it, using the same packages and features.
The outcome, timing and hashed `cargo-doctests.log` are retained separately from
JUnit observations. A failure stops preparation. Zero or ignored doctests retain
Cargo's usual command semantics, visible in that log.

During scope migration, keep a standalone doctest command for a baseline that
does not enable the option. Remove that command only when the active trusted
capture binding's build configuration has `doctests: true`; the checker has
already required those doctests to pass before invoking the driver. Old readers
must be upgraded before consuming scopes with the new field.

## Verus

Put the exact function identity printed by the pinned verifier on the proof
declaration. By default the producer reads bindings from the source file.
Use repeated `--bindings` to specify the complete set of binding files for
a multi-module crate.

```rust
// [proof~increment~1->req~increment~1] ib-verus arithmetic::increment
```

```sh
python -m intentbond.verus_junit --verus "$VERUS" --source proofs/arithmetic.rs \
  --report proofs.xml -- --edition=2024 --crate-type=lib --crate-name=arithmetic \
  --no-cheating --output-json --time-expanded
```

Use whole-crate verification with expanded JSON timing. A testcase comes
from an actual `function` and boolean `success` in the native
`function-breakdown` array. Aggregate success alone cannot generate a
testcase. A failed run keeps its failure even when a sibling function passes.
A missing function supplies no observation. A pass refers to the function
under the modeled assumptions, including the chosen crate, toolchain and flags.
Separate mutation checks remain the caller's responsibility.

Include the JUnit path in `tests.verus_reports` to retain the original bytes
from `proofs.xml.verus.json`. For the third configured JUnit report, the
bundle contains `tests-3.xml` and `verus-3.json`. The suite records its
invocation, exit status, and native report digest. The JSON records the Verus
toolchain and function results. On a passing check, `ib verify` validates the
native file, its relationship to the JUnit cases, and the source/scope binding.
The adapter inherits the caller's environment without serializing it. Supply
credentials through that environment and keep them out of arguments and logs.

## Run the checks

In a standalone Git copy of this project, commit the example as the baseline,
provision the readiness endpoint, and run:

```sh
ib check --repo . --base HEAD --out ../rust-evidence
ib explain 'proof~increment~1' --evidence ../rust-evidence/evidence.json
ib verify --repo . --base HEAD --evidence ../rust-evidence/evidence.json
```

To exercise the complete example from the IntentBond source distribution with
the same installed tools, run
`python scripts/check_rust_example.py --out ../rust-qualification`. It creates
a standalone project and provisions its own disposable readiness service. It
exercises pass, absent proof, failed proof, skip/pass conflict, zero matches,
build error, crash, baseline policy and evidence tampering.
