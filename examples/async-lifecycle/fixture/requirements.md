# Accepted requirements

### form-wire
`req~form-wire~1`

The client component name and outgoing payload key remain display_name. The API returns only ok, field and error, with field display_name. The component implementation must be retained.

Needs: impl, utest

### form-nonblank
`req~form-nonblank~1`

The server rejects non-string values and strings empty after Python Unicode whitespace stripping with error required. All other strings are accepted, including Unicode names; the client must submit the original value.

Needs: impl, utest

### form-label
`req~form-label~2`

The rendered display label is exactly Continue. This label does not rename the wire field or replace the retained component.

Needs: impl, utest

### form-async
`req~form-async~1`

Validate asynchronously without changing the wire or nonblank rules. Only the most recently started validation may set error and pending; an earlier response arriving later must not overwrite it. Pending becomes false when the latest response completes.

Needs: impl, utest

