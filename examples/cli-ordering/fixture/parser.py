# [impl->req~export-text~1]
# [impl->req~export-order~1]
# [impl->req~export-errors~1]
# [impl->req~export-json~1]
# [impl->req~export-stream~1]
FORMATS = {"--json": "json", "--stream": "stream"}


def parse(argv):
    if not argv:
        return "text"
    if len(argv) != 1 or argv[0] not in FORMATS:
        raise ValueError("invalid options")
    return FORMATS[argv[0]]
