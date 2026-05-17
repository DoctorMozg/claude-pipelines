# Optimization Toolkit

The domain-agnostic vocabulary the `optimize` pipeline reasons with — a shared framework so every run classifies bottlenecks, generates hypotheses, and prioritizes them the same way, whatever the target. It is **not** a per-domain playbook and not a command catalog. The model already knows the domains (code, containers, LLM hyperparameters, build pipelines); what this file supplies is the disciplined frame. Anything genuinely unfamiliar is filled by a live `pipeline-researcher` pass in Phase 2, not from here.

Grep this file per section — never load the whole thing:

- **Phase 2** classifies the bottleneck with §1 and reads the profile with §3.
- **Phase 3** generates hypotheses from §2 and ranks them with §4.
- **§5** is the standing checklist every phase is measured against.

Concrete tools are named only inside lines clearly marked *illustrative* — they are examples, never instructions. The pipeline itself carries no domain-specific commands.

## 1. Bottleneck taxonomy

The resource class a system is bound by. Each class names how it **presents** in a profile and how to **confirm** it — because a spiking counter is a candidate, not a verdict.

**Compute-bound** — the metric is set by instruction throughput (CPU or GPU).

- *Presents as*: high processor utilization; self-time concentrated in arithmetic or transform code; the hot unit is on-CPU, not waiting.
- *Confirm by*: on-CPU time ≈ wall time for the hot unit, and its instruction count / FLOPs scale with the metric.

**Memory-bound** — the metric is set by memory bandwidth, cache behavior, or allocation churn.

- *Presents as*: the processor stalls waiting on memory; high cache-miss counters; significant allocation or garbage-collection time.
- *Confirm by*: the hot unit's time tracks data-set size more than instruction count; shrinking the working set moves the metric.

**I/O-bound** — the metric is set by disk, network, or an external service.

- *Presents as*: off-CPU / blocked time; the unit waits far more than it computes; throughput tracks request count, not compute.
- *Confirm by*: a gap between wall-clock time and CPU time; the metric scales with I/O volume or round-trip count.

**Contention / lock-bound** — the metric is set by serialization: locks, queues, connection pools, shared-resource waits.

- *Presents as*: threads blocked on the same lock; throughput stays flat as workers are added; queue depth grows under load.
- *Confirm by*: wait time attributed to a specific lock or queue; measuring single-threaded, or removing the contended resource, changes the metric.

**Algorithmic** — the metric is set by complexity class, not constant factors: an O(n²) where O(n log n) exists, redundant recomputation, a missing index.

- *Presents as*: time grows super-linearly with input size; the profile looks *flat* — no single hot line — because the cost is structural.
- *Confirm by*: measuring the metric at two or three input sizes and fitting the growth curve. A super-linear curve is the signature.

**Config / parameter-bound** — the metric is set by a tunable knob, not by code: a pool too small, a wrong batch size, an unset cache, a default timeout, a heavyweight base layer.

- *Presents as*: no hot code at all — the cost lives in a setting.
- *Confirm by*: the metric changes when the knob changes and nothing else does.

**Confirming any class.** Show the named bottleneck owns a *proportional share* of the metric (§4, Amdahl). A unit that is 3% of the metric is not the dominant bottleneck no matter how red its counter looks — and cannot deliver a large end-to-end gain.

## 2. Transformation catalog

The domain-agnostic *classes* of change a `change_space` draws from. Each is defined by the **mechanism it removes**, which is what lets it map onto any domain.

**Algorithmic improvement** — removes structural waste: a better complexity class, eliminated redundant work, a lookup where there was a scan. In code, a better algorithm; in a build pipeline, an incremental build instead of a full one; in an image build, a multi-stage build that stops shipping build-time dependencies.

**Caching / memoization** — removes *repeated* work by storing a result and reusing it. A memoized pure function, a cached query, a build layer cache, a dependency cache, an LLM prefix cache. One idea: pay once, reuse N times.

**Batching** — removes per-item fixed overhead by amortizing it over a group. Batched database writes, coalesced RPCs, combined image-build steps, batched inference requests. One fixed cost, many items.

**Parallelism / concurrency** — removes idle time by overlapping independent work, or removes serial time by splitting it across workers. A thread pool, async I/O, vectorization, parallel build jobs. Bounded by the serial fraction (Amdahl, §4) and by contention (§1).

**Lazy evaluation & precomputation** — removes work from the measured path: defer it (compute only when actually needed) or hoist it (compute once, before the path). Two directions, one principle — keep the work off the hot path.

**Data-structure change** — removes access-pattern waste by matching the structure to the access: a hash for point lookups, a contiguous array for scans, a tree for range queries, the right index type for a query shape.

**Allocation reduction** — removes memory-management overhead: object pooling and reuse, fewer copies, stack instead of heap. The direct answer to a memory-bound bottleneck.

**I/O reduction** — removes I/O operations or shrinks their payloads: fewer round trips, compression, a leaner wire format, reading less data. The direct answer to an I/O-bound bottleneck.

**Config / parameter tuning** — removes a mis-set knob: pool size, batch size, worker count, timeout, cache size, base-image choice, LLM sampling parameters. No code changes — the change is a value. The direct answer to a config-bound bottleneck.

**Match the class to the bottleneck.** An I/O-bound bottleneck is not addressed by allocation reduction; an algorithmic bottleneck is not addressed by a compute micro-optimization. The class names the mechanism removed — pick the one whose mechanism is the bottleneck.

## 3. Profiling principles

How to read a profile so it indicts the real bottleneck.

**Read self-time, not total width.** A unit looks wide in a call-tree profile when its callees are slow — but that does not make the unit itself the bottleneck. Self-time (exclusive time) attributes cost to the unit that actually spends it. Optimize by self-time.

**Off-CPU time is real time.** A CPU-only profiler shows nothing while a thread is blocked on I/O, a lock, or a queue — yet that wait is part of a latency metric. A flame graph that sums to less than wall-clock time is hiding the bottleneck; use a wall-clock or off-CPU-aware technique for latency work.

**One stable metric guides the loop.** The contract's `metric_name`, start to finish. A "win" measured on a metric switched mid-run is not comparable to the baseline and is not a win.

**Differential (A/B) profiling falsifies a hypothesis.** Profile before and after a candidate, then diff. If the hypothesised mechanism was real, the predicted unit shrinks in the diff. If the metric moved but the predicted unit did not, the gain came from elsewhere — the hypothesis is unverified even though the candidate may still win on measured merit.

**Attribute before you drill.** Find *where* the cost is before investigating *why*. For a `system` target this is component attribution: split the end-to-end metric across components first, then profile inside the dominant one.

**Profile the representative workload.** A profile of an unrepresentative input points confidently at the wrong bottleneck. Profile the workload the metric is defined over.

*Illustrative* — examples the orchestrator may choose from, never a prescribed command: a sampling profiler such as `py-spy` or `perf` for code; image layer-and-size inspection for containers; a distributed trace viewer for `system` targets; an eval-loss curve for LLM hyperparameters.

## 4. Prioritization

Turning a profile into a ranked backlog.

**Amdahl-bounding.** A transformation can never improve the metric by more than the share its bottleneck owns. If a bottleneck is 40% of the metric, eliminating it *entirely* caps the end-to-end speedup at 1 / (1 − 0.40) ≈ 1.67× — and a transformation that merely improves it predicts far less. Any predicted speedup above this bound is an arithmetic error; correct it before ranking.

**Rank by impact × confidence ÷ effort.** `impact` is the Amdahl-bounded predicted gain; `confidence` is how directly the profile supports the mechanism; `effort` is rough implementation cost. The ratio floats cheap, well-evidenced wins above expensive, speculative ones.

**The hottest unit is not always the highest-impact target.** A unit that is 60% of the metric but only 10%-improvable offers a 6% end-to-end gain. A unit that is 25% of the metric but fully eliminable offers 25%. Rank by *bounded gain*, not by position in the profile.

**Confidence comes from evidence, not optimism.** High confidence: the profile shows the mechanism plainly and a known transformation removes it. Low confidence: the mechanism is plausible but the profile supports it only indirectly. Never rate confidence by how clever the fix feels.

**Diversify the backlog.** Rank a spread of transformation classes, not several variants of one idea. If the top hypothesis dead-ends, the next entry should test a *different* mechanism — a backlog built on a single idea has nothing left to try.

## 5. Anti-patterns

The standing checklist. Every phase is measured against it.

**The streetlight method.** Optimizing the part you understand, or the part that is easy to measure, instead of the part the profile indicts. Follow the attribution — even into unfamiliar code.

**The random-change method.** Changing things and re-measuring until the number moves, with no hypothesis. It yields unexplained "wins" the next change silently reverts, and it cannot separate a real gain from noise.

**Premature micro-optimization.** Hand-tuning a constant factor on a bottleneck that is algorithmic. An O(n²) loop does not need a faster inner body — it needs to stop being O(n²).

**Trusting a stated Big-O.** "It is O(n) now" is a claim, not a measurement. A complexity argument predicts a *shape*; only the harness confirms the metric actually moved. Treat any unmeasured complexity claim as `HYPOTHESIS UNVERIFIED`.

**Keeping an unmeasured "obviously faster" change.** A change that looks faster but was never measured is not a speedup — it is an untested edit with a performance story attached. Most do nothing; some regress. Unmeasured is not banked.

**Optimizing past the noise floor.** Chasing a 2% gain when measurement CV is 5%. Below the noise floor the sign of the result is random. Stop when the remaining bottlenecks are smaller than the measurement can resolve.

**Banking a behavior change.** A faster result that is not the *same* result is a bug, not an optimization. Correctness gates every candidate; a faster wrong answer is discarded.
