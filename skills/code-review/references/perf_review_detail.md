# Weak review: performance and resources

Prioritize high-frequency, high-volume and critical paths. State realistic scale assumptions before judging performance.

## Content points

- Has complexity worsened through nested iteration, duplicate traversal or unnecessary intermediates?
- Are database/network/disk operations inside loops producing N+1 behavior or avoidable repeated IO?
- Are complete datasets/files loaded into memory where streaming, pagination or batching is needed?
- Are lists, caches, queues, retries or work submissions unbounded?
- Are files, connections, threads, processes and temporary resources released on success and failure?
- Is expensive computation or serialization repeated unnecessarily, and is a safe batch/reuse opportunity demonstrated?
- Are caches correct for permissions, invalidation and memory limits rather than an unsupported optimization suggestion?
- Does abstraction multiply calls on a demonstrated hot path?

## Scan and challenge

Trace critical loops, queries, resource acquisition/cleanup and caller frequency. Compare work/IO counts at relevant sizes such as 100 and 10,000, including duplicate/cyclic data where applicable. Use measurements when available and distinguish observations from asymptotic estimates. Do not demand benchmarks across every size or speculative caching on unrelated paths.
