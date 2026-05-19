/** Stack of modal close handlers (e.g. Escape / programmatic dismiss). */
type CloseFn = () => void

const stack: CloseFn[] = []

export function pushModalCloseHandler(close: CloseFn): () => void {
  stack.push(close)
  return () => {
    const i = stack.lastIndexOf(close)
    if (i >= 0) stack.splice(i, 1)
  }
}
