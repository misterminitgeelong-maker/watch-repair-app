import { describe, expect, it, vi } from 'vitest'
import { installDomMutationGuard } from '@/lib/domMutationGuard'

describe('installDomMutationGuard', () => {
  // A fresh prototype chain per test so the real Node.prototype stays untouched.
  function guardedProto() {
    const proto = Object.create(Node.prototype) as typeof Node.prototype
    proto.removeChild = Node.prototype.removeChild
    proto.insertBefore = Node.prototype.insertBefore
    installDomMutationGuard(proto)
    return proto
  }

  it('skips removing a node another script already moved, instead of throwing', () => {
    const proto = guardedProto()
    const parent = document.createElement('div')
    const elsewhere = document.createElement('div')
    const text = document.createTextNode('hello')
    elsewhere.appendChild(text) // e.g. Translate swapped it into a <font>
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(() => proto.removeChild.call(parent, text)).not.toThrow()
    expect(elsewhere.contains(text)).toBe(true)
    warn.mockRestore()
  })

  it('skips inserting next to a moved reference node, instead of throwing', () => {
    const proto = guardedProto()
    const parent = document.createElement('div')
    const moved = document.createTextNode('moved')
    document.createElement('font').appendChild(moved)
    const fresh = document.createElement('span')
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(() => proto.insertBefore.call(parent, fresh, moved)).not.toThrow()
    warn.mockRestore()
  })

  it('still removes and inserts normally', () => {
    const proto = guardedProto()
    const parent = document.createElement('div')
    const a = parent.appendChild(document.createElement('a'))
    const b = document.createElement('b')
    proto.insertBefore.call(parent, b, a)
    expect(parent.firstChild).toBe(b)
    proto.removeChild.call(parent, a)
    expect(parent.contains(a)).toBe(false)
  })
})
