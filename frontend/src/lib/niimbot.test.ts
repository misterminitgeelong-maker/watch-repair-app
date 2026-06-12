import { describe, it, expect } from 'vitest'
import { buildPacket } from './niimbot'

/**
 * The Niimbot wire format is: 0x55 0x55 <cmd> <len> <data…> <xor> 0xaa 0xaa
 * where xor is over [cmd, len, ...data]. A wrong frame or checksum makes the
 * printer reject the job (feed-and-retract), so this format is load-bearing.
 */
describe('buildPacket', () => {
  it('frames a packet with the correct header, length, checksum, and trailer', () => {
    const pkt = Array.from(buildPacket(0x01, [0x01]))
    // 0x55 0x55 | cmd=01 len=01 data=01 | xor(01^01^01)=01 | 0xaa 0xaa
    expect(pkt).toEqual([0x55, 0x55, 0x01, 0x01, 0x01, 0x01, 0xaa, 0xaa])
  })

  it('computes the checksum as xor of cmd, len, and all data bytes', () => {
    const pkt = buildPacket(0x13, [0x00, 0xf0, 0x01, 0x90, 0x00, 0x02])
    const len = 6
    const expected = [0x13, len, 0x00, 0xf0, 0x01, 0x90, 0x00, 0x02].reduce((x, b) => x ^ b, 0)
    expect(pkt[pkt.length - 3]).toBe(expected)
  })

  it('sets len to the data length and keeps total size at data + 7', () => {
    const data = [1, 2, 3, 4, 5]
    const pkt = buildPacket(0x85, data)
    expect(pkt[3]).toBe(data.length)
    expect(pkt.length).toBe(data.length + 7) // 2 head + cmd + len + xor + 2 tail
  })

  it('handles an empty payload', () => {
    const pkt = Array.from(buildPacket(0xdc, []))
    // xor(cmd ^ len) = 0xdc ^ 0x00 = 0xdc
    expect(pkt).toEqual([0x55, 0x55, 0xdc, 0x00, 0xdc, 0xaa, 0xaa])
  })
})
