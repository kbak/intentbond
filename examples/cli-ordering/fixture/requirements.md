# Accepted requirements

### export-text
`req~export-text~1`

Without a format flag emit exactly name, a tab, integer quantity and a newline per row; empty input emits empty text.

Needs: impl, utest

### export-order
`req~export-order~1`

Every format sorts rows by name ascending, preserving input order among equal names; never drop duplicates.

Needs: impl, utest

### export-errors
`req~export-errors~1`

Unknown or conflicting options return code 2, empty stdout and exactly invalid options plus newline on stderr.

Needs: impl, utest

### export-json
`req~export-json~1`

With --json emit a JSON array preserving all name/qty rows and the same stable ordering, followed by one newline. Empty input is []. Default text/errors remain unchanged.

Needs: impl, utest

### export-stream
`req~export-stream~1`

With --stream emit one JSON object per line in the same stable order; empty input emits empty text. --json remains supported and combining format flags is invalid.

Needs: impl, utest

