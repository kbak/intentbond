# Review a change while building software

From an installed IntentBond development environment with pinned OFT available:

```sh
python examples/development-review/demo.py --out /tmp/retry-development-review
```

Use a new output directory. The script creates a disposable Git project from
the granular-retries fixture; it leaves your checkout untouched. It uses
IntentBond's stdlib unittest JUnit producer and the current Python interpreter.

The example checks an accepted baseline, demonstrates strict and permissive
revision policies on the same editorial change, then changes the retry cap
from 8 to 16 seconds. A skipped required cap test rejects the change even though
the growth test passes. Reports retain the native coverage, required execution
gap, unannotated helper file and requirement hub as distinct observations.
The small-delay test supplies an additional test link; review still assesses
whether the linked assertions adequately check the promise.

It freezes a review queue, records a deferred item and resumes from disk. Repair
restores the cap test and adds the new boundary assertion. Resuming the old queue
is refused; a fresh check and queue retain pending review and start with no
completed work. No step claims semantic approval.

Inspect `results.json`, `observations.json`, the `changed/` and
`repaired/` evidence bundles, and the worklist directories. Review the generated
project and full change as well as its existing links.
