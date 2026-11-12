from intentbond.unittest_junit import main

raise SystemExit(
    main(["--start", "tests", "--links", "tests/links.json", "--report", "test-results.xml"])
)
