/**
 * Keep React working when something outside it rewrites the page.
 *
 * Chrome's "Translate this page", some extensions, and mail link scanners
 * (Outlook / Defender opening invite links) swap React's text nodes for their
 * own. React later tries to remove or insert next to a node that is no longer
 * where it left it, the DOM throws NotFoundError, and the error screen that
 * catches it hits the same error while rendering — about 50 times, until React
 * gives up with "Maximum update depth exceeded" and the page freezes
 * (Sentry JAVASCRIPT-REACT-3).
 *
 * The long-standing workaround (facebook/react#11538): when the node React
 * names is not actually a child, skip the move instead of throwing. React's
 * next render repairs the tree.
 */
export function installDomMutationGuard(proto: typeof Node.prototype = Node.prototype): void {
  const guarded = proto as typeof Node.prototype & { __msDomGuard?: boolean }
  if (guarded.__msDomGuard) return
  guarded.__msDomGuard = true

  const removeChild = proto.removeChild
  proto.removeChild = function <T extends Node>(this: Node, child: T): T {
    if (child.parentNode !== this) {
      console.warn('Skipped removeChild of a node another script moved', child)
      return child
    }
    return removeChild.call(this, child) as T
  }

  const insertBefore = proto.insertBefore
  proto.insertBefore = function <T extends Node>(this: Node, newNode: T, referenceNode: Node | null): T {
    if (referenceNode && referenceNode.parentNode !== this) {
      console.warn('Skipped insertBefore next to a node another script moved', referenceNode)
      return newNode
    }
    return insertBefore.call(this, newNode, referenceNode) as T
  }
}
