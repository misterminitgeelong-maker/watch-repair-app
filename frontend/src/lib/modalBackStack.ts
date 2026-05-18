/** Lets Android hardware back close the top modal before navigating history. */
type CloseFn = () => void

const stack: CloseFn[] = []

export function pushModalCloseHandler(close: CloseFn): () => void {
  stack.push(close)
  return () => {
    const i = stack.lastIndexOf(close)
    if (i >= 0) stack.splice(i, 1)
  }
}

export function handleNativeBackButton(): boolean {
  const top = stack[stack.length - 1]
  if (top) {
    top()
    return true
  }
  return false
}
