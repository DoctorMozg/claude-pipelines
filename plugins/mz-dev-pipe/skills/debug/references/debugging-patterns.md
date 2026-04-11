# Debugging Patterns

Sources (official docs, per Rule 19):

- `git bisect`: https://git-scm.com/docs/git-bisect
- pytest ordering / flaky detection: https://docs.pytest.org/en/stable/how-to/randomorder.html, https://docs.pytest.org/en/stable/how-to/cache.html
- jest ordering: https://jestjs.io/docs/cli
- Python stack traces: https://docs.python.org/3/library/traceback.html
- Node.js heap snapshots: https://nodejs.org/en/learn/diagnostics/memory/using-heap-snapshot
- Chrome DevTools memory: https://developer.chrome.com/docs/devtools/memory
- JVM heap: https://docs.oracle.com/en/java/javase/21/troubleshoot/troubleshoot-memory-leaks.html

Use via grep — locate the section, copy the command sequence, adapt arguments. Do not load the whole file.

## git bisect

**When to use**: a bug that exists at `HEAD` but did not exist at a known-good revision. You want to find the first bad commit in logarithmic time.

**Preconditions**:

- A deterministic reproducer (test command, script, curl + grep).
- Both endpoints confirmed — good commit passes, bad commit fails.

**Manual sequence**:

```bash
git bisect start
git bisect bad HEAD
git bisect good <known-good-sha>
# git checks out midpoint; run reproducer, then:
git bisect good      # or: git bisect bad
# repeat until bisect announces the first bad commit
git bisect reset     # return to original HEAD
```

**Automated via predicate**: write a script that exits `0` on good, `1` on bad, `125` on skip (untestable commit):

```bash
#!/usr/bin/env bash
set -e
# build / install deps for this commit
pytest tests/test_bug.py::test_regression -x -q
# exit 0 = good, non-zero = bad
```

Then:

```bash
git bisect start HEAD <known-good-sha>
git bisect run ./scripts/bisect_predicate.sh
git bisect reset
```

**Gotchas**:

- If the reproducer depends on a dep version, pin it in the predicate or use `125` to skip uninstallable revisions.
- `git bisect run` stops on any exit other than `0/1/125`; make the script robust.
- If tests themselves changed across the range, use `git bisect --first-parent` or hold the test file constant with `git checkout <sha> -- tests/test_bug.py` inside the predicate.

## test pollution bisection

**Symptom**: a test passes in isolation but fails when run with others, or the failure depends on the order.

**Identify pollution**:

```bash
# pytest: run only the suspect test
pytest tests/test_x.py::test_y

# pytest: run the full suite in a fixed order and confirm fail
pytest -p no:randomly tests/

# pytest with random order (pytest-randomly): confirm order-dependence
pytest -p randomly tests/
pytest -p randomly --randomly-seed=12345 tests/

# jest: run in band (no parallel) for deterministic order
jest --runInBand --testSequencer=./alphabetical-sequencer.js
```

**Bisect the offending predecessor**:

```bash
# pytest: fail-fast + narrowing
pytest -x tests/                              # stops on first failure
pytest --lf tests/                            # reruns only last failures
pytest tests/test_a.py tests/test_b.py tests/test_y.py::test_y
# binary-chop the predecessor set until you find the single test
# whose presence makes test_y fail.
```

**Shard strategy** for large suites:

```bash
pytest --test-group-count=4 --test-group=1 tests/   # pytest-split
jest --shard=1/4                                     # jest built-in sharding
```

Run each shard alone to locate the polluting shard, then binary-chop within it.

**Root causes to look for**:

- Shared module-level state (caches, singletons, os.environ).
- Database fixtures not rolled back.
- Monkey-patches not undone (missing `yield` + `setattr` cleanup).
- File system writes under `tmp_path` the next test reads.
- Import-time side effects.

## flaky test heuristics

Classify first, fix second. A flaky test falls into exactly one bucket — naming it unlocks the fix.

**Timing-dependent**:

- Smell: `time.sleep(0.1)` waiting for async work, `assert elapsed < 100ms`, `datetime.now()` comparisons.
- Detect: run under CPU pressure (`stress-ng --cpu 4 &`) and see if failure rate spikes.
- Fix: replace sleeps with explicit condition polling, freeze clocks (`freezegun`, `jest.useFakeTimers()`), use relative tolerances not absolute.

**Order-dependent**:

- Smell: passes alone, fails in suite. Covered under "test pollution bisection" above.
- Detect: run with `pytest -p randomly --randomly-seed=<N>` repeatedly; if seed determines pass/fail, it's order-dependent.
- Fix: identify shared state and isolate per-test (fresh fixture scope, reset singletons in teardown).

**Environment-dependent**:

- Smell: passes on macOS fails on Linux, passes with Python 3.11 fails on 3.12, depends on `TZ=`, depends on locale.
- Detect: diff env between pass and fail runs (`env > pass.env` vs `env > fail.env`).
- Fix: pin env in test setup (`os.environ["TZ"] = "UTC"`, fixture that sets `LANG=C.UTF-8`).

**Async/concurrency-dependent**:

- Smell: uses `Promise.all`, `asyncio.gather`, multi-threaded. Sometimes the assertion runs before the work finishes.
- Detect: add deterministic schedulers (`asyncio.run` single-threaded) and see if flake disappears.
- Fix: explicit `await` on every task, avoid "fire and forget", use `asyncio.Event` / `threading.Event` instead of sleeps.

**Network-dependent**:

- Smell: real HTTP calls in tests, DNS lookups, rate-limited APIs.
- Fix: record-and-replay (`vcr.py`, `nock`, `responses`), never hit the network in unit tests.

## stack trace parsing

Read a stack trace **bottom-up** for root cause and **top-down** for effect path — both directions tell you different things.

**Python format** (traceback grows down, oldest frame at top):

```
Traceback (most recent call last):
  File "app/server.py", line 42, in handle_request
    result = process(payload)
  File "app/core.py", line 17, in process
    return db.fetch(payload["id"])
KeyError: 'id'
```

- Top frame = entry point; bottom frame = site of exception.
- Split frames into **app frames** (your code) and **library frames** (site-packages). The first app frame *before* the library call is usually the bug — you passed bad data into a library.
- Chained exceptions: look for `During handling of the above exception, another exception occurred:` and `The above exception was the direct cause of the following exception:`. The *first* exception in the chain is almost always the root cause.

**JavaScript/Node format** (newest frame at top):

```
TypeError: Cannot read properties of undefined (reading 'id')
    at process (app/core.js:17:18)
    at handleRequest (app/server.js:42:20)
    at /node_modules/express/lib/router/layer.js:95:5
```

- First line = exception; frames below = call path (top is site of failure).
- Library vs app distinction: anything under `node_modules/` is library.
- Minified production traces need source maps — without them, `webpack:///./src/...` lines are unreadable.

**Async stitching** (Python ≥3.11, Node ≥12):

- Python: `asyncio` exceptions show the awaiter chain. Look for `task.exception()` in logs; `loop.set_debug(True)` expands the visible chain.
- Node: `--async-stack-traces` (default in modern Node) threads async frames. Missing async context usually means the frame was scheduled via `setTimeout`/`setImmediate` and the stack was cut there.
- JVM: `CompletableFuture` exceptions wrap in `CompletionException`; unwrap via `ex.getCause()`.

**Red flags in stack traces**:

- Same library frame at the bottom across multiple unrelated bugs → the library has a wrapper swallowing context.
- Exception type doesn't match app semantics (`IndexError` in a REST handler) → missing input validation at the boundary.
- Frames all in vendored code → re-enable source maps / symbol files; you're debugging blind.

## memory leak hunting

**Symptoms**:

- RSS grows monotonically under steady load.
- GC pauses get longer over time.
- Eventual OOM kill.

**Strategy**: take two heap snapshots — one at steady state, one after N minutes of load — then diff them. Retained objects that grow are the leak.

**Node.js**:

```bash
# start with inspector
node --inspect-brk app.js
# or programmatically:
# const heap = require('node:v8');
# heap.writeHeapSnapshot('./snap1.heapsnapshot');
```

- Open Chrome DevTools → `chrome://inspect` → attach.
- Take snapshot 1 → generate load → wait → take snapshot 2.
- Use "Comparison" view: sort by `# Delta` to find objects that grew.
- In "Containment" view, check the **retainer tree**: follow references back until you hit a long-lived object (module-level map, global cache, event emitter listener list).
- Common leak shapes: unbounded `Map`/`Set` caches, `EventEmitter.on` without `.off`, closures captured by `setTimeout`/`setInterval`.

**Python**:

```python
import tracemalloc
tracemalloc.start(25)   # 25 = stack depth per allocation
# ... workload ...
snap1 = tracemalloc.take_snapshot()
# ... more workload ...
snap2 = tracemalloc.take_snapshot()
for stat in snap2.compare_to(snap1, 'lineno')[:10]:
    print(stat)
```

- For object-level leaks: `objgraph.show_growth()` and `objgraph.show_backrefs(obj, max_depth=5)` to draw the retainer graph.
- `gc.get_referrers(obj)` — who holds a reference to this object.
- Common causes: global dict caches, circular refs across classes with `__del__`, frames captured by exception traceback kept in logs.

**JVM**:

- `jcmd <pid> GC.heap_dump /path/to/snap1.hprof`
- Two dumps, open in Eclipse Memory Analyzer (MAT), use "Compare Basket" / "Leak Suspects Report".
- MAT highlights **dominator tree** — the single object whose removal would free the largest retained set is usually the leak root.
- Common causes: static collections, `ThreadLocal` without cleanup, unbounded caches without eviction, `ClassLoader` leaks after hot redeploy.

**Go**:

```bash
# enable pprof in code: import _ "net/http/pprof"; go http.ListenAndServe(":6060", nil)
go tool pprof http://localhost:6060/debug/pprof/heap
# in pprof: top, list <func>, web
```

- Two captures, compare with `-base snap1.pprof snap2.pprof`.
- `inuse_space` vs `alloc_space` — leaks show up in `inuse_space` growth.
- Common causes: goroutines blocked on unbuffered channels, slices appended without capping, map keys never deleted.

**Red flags**:

- "Leak went away when I restarted" — it's still there; the restart reset the counter.
- Suspect is a library → check issue tracker before filing, but also profile to confirm you're not holding the retainer yourself.
- GC tuning "fixed" it → you raised the limit, the leak is still there.
