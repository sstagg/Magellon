# Sample Plugin (test fixture)

Synthetic plugin source used by `CoreService/tests/services/` install
tests. Pure Python, zero deps, never actually runs — it just has to
be a valid `.mpn` archive so the install pipeline has something to
operate on.

## Rebuilding the fixture

```sh
python CoreService/tests/fixtures/plugins/build.py
```

That script regenerates `sample.mpn` next to this directory by
invoking `magellon-sdk plugin pack`. Run it whenever you change a
file under `sample_src/` — the committed `sample.mpn` is what tests
load, not the source.
