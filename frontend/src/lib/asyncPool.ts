/** Run async work over a list with a fixed number of in-flight tasks. */
export async function asyncPool<T, R>(
  items: readonly T[],
  concurrency: number,
  worker: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(items.length)
  if (items.length === 0) return results
  let next = 0
  const limit = Math.max(1, Math.min(concurrency, items.length))

  async function run(): Promise<void> {
    while (true) {
      const index = next
      next += 1
      if (index >= items.length) return
      results[index] = await worker(items[index], index)
    }
  }

  await Promise.all(Array.from({ length: limit }, () => run()))
  return results
}
