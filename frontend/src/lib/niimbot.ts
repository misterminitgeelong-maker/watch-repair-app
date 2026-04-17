/**
 * Niimbot BLE protocol implementation for Web Bluetooth API.
 *
 * Protocol reverse-engineered from the open-source niimprint (Python) and
 * niimblue (TypeScript web) projects. Tested against the M2 model.
 *
 * BLE service UUID is the same across the B1/B21/B3/D11/M2 family.
 * If your M2 firmware is very new, scan the GATT services in nRF Connect
 * and update NIIMBOT_SERVICE_UUID if it differs.
 */

const NIIMBOT_SERVICE_UUID = 'e7810a71-73ae-499d-8c15-faa9aef0c3f2'

// Command bytes (from niimprint reverse engineering)
const CMD = {
  GET_INFO: 0x40,
  HEARTBEAT: 0xdc,
  SET_LABEL_TYPE: 0x23,
  SET_LABEL_DENSITY: 0x21,
  START_PRINT: 0x01,
  END_PRINT: 0xf3,
  START_PAGE_PRINT: 0x03,
  END_PAGE_PRINT: 0xe3,
  SET_DIMENSION: 0x13,
  SET_QUANTITY: 0x15,
  WRITE_BITMAP: 0x85,
  GET_PRINT_STATUS: 0xa3,
}

function buildPacket(cmd: number, data: number[]): Uint8Array<ArrayBuffer> {
  const len = data.length
  const checksum = [cmd, len, ...data].reduce((xor, b) => xor ^ b, 0)
  const bytes = [0x55, 0x55, cmd, len, ...data, checksum, 0xaa, 0xaa]
  const buf = new ArrayBuffer(bytes.length)
  const view = new Uint8Array(buf)
  view.set(bytes)
  return view
}

export class NiimbotPrinter {
  private device: BluetoothDevice | null = null
  private writeChar: BluetoothRemoteGATTCharacteristic | null = null

  get connected() {
    return this.device?.gatt?.connected ?? false
  }

  get deviceName() {
    return this.device?.name ?? null
  }

  async connect(): Promise<void> {
    const device = await navigator.bluetooth.requestDevice({
      filters: [{ namePrefix: 'M2' }],
      optionalServices: [NIIMBOT_SERVICE_UUID],
    })
    const server = await device.gatt!.connect()
    const service = await server.getPrimaryService(NIIMBOT_SERVICE_UUID)
    const chars = await service.getCharacteristics()

    // Find the characteristic we can write to (with or without response)
    const writable = chars.find(
      c => c.properties.writeWithoutResponse || c.properties.write
    )
    if (!writable) throw new Error('No writable characteristic found on Niimbot service')

    this.device = device
    this.writeChar = writable

    // Heartbeat to confirm comms
    await this.send(CMD.HEARTBEAT, [0x00])
  }

  disconnect() {
    this.device?.gatt?.disconnect()
    this.device = null
    this.writeChar = null
  }

  private async send(cmd: number, data: number[]): Promise<void> {
    if (!this.writeChar) throw new Error('Not connected to printer')
    const packet = buildPacket(cmd, data)
    const useResponse = this.writeChar.properties.write
    if (useResponse) {
      await this.writeChar.writeValue(packet)
    } else {
      await this.writeChar.writeValueWithoutResponse(packet)
    }
    // Small gap between commands to avoid buffer overrun
    await sleep(10)
  }

  /**
   * Print a canvas element as a label.
   * The canvas should be sized to the printer's dot resolution:
   *   M2 at 203 DPI on 40x30mm labels → 320 wide × 240 tall
   */
  async printCanvas(canvas: HTMLCanvasElement, quantity = 1): Promise<void> {
    const ctx = canvas.getContext('2d')!
    const { width, height } = canvas
    const imageData = ctx.getImageData(0, 0, width, height)

    // Convert RGBA pixels to 1-bit rows (black = set bit, white = unset)
    const rows: Uint8Array[] = []
    for (let y = 0; y < height; y++) {
      const bytesPerRow = Math.ceil(width / 8)
      const row = new Uint8Array(bytesPerRow)
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4
        const r = imageData.data[idx]
        const g = imageData.data[idx + 1]
        const b = imageData.data[idx + 2]
        const luminance = 0.299 * r + 0.587 * g + 0.114 * b
        if (luminance < 128) {
          // Dark pixel → set bit (MSB first within each byte)
          row[Math.floor(x / 8)] |= 0x80 >> (x % 8)
        }
      }
      rows.push(row)
    }

    await this.send(CMD.SET_LABEL_TYPE, [0x01])
    await this.send(CMD.SET_LABEL_DENSITY, [0x03]) // medium density
    await this.send(CMD.START_PRINT, [0x01])
    await this.send(CMD.START_PAGE_PRINT, [0x01])
    await this.send(CMD.SET_DIMENSION, [
      (height >> 8) & 0xff, height & 0xff,
      (width >> 8) & 0xff, width & 0xff,
    ])
    await this.send(CMD.SET_QUANTITY, [(quantity >> 8) & 0xff, quantity & 0xff])

    for (let y = 0; y < rows.length; y++) {
      const rowData = rows[y]
      // Packet: [rowIndex high, rowIndex low, ...row bytes]
      const data = [(y >> 8) & 0xff, y & 0xff, ...Array.from(rowData)]
      await this.send(CMD.WRITE_BITMAP, data)
    }

    await this.send(CMD.END_PAGE_PRINT, [0x01])
    await this.send(CMD.END_PRINT, [0x01])
  }
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// ---------------------------------------------------------------------------
// Canvas label renderers
// ---------------------------------------------------------------------------

// M2 label dimensions at 203 DPI: 40mm × 30mm = 320 × 240 dots
const LABEL_W = 320
const LABEL_H = 240
const PAD = 10

export interface WatchLabelData {
  jobNumber: string
  customerName: string
  watchTitle: string
  dateIn: string
  qrDataUrl: string    // small QR — generate with width:120, margin:1
  isCustomerCopy: boolean
  depositLabel?: string
  balanceLabel?: string
}

export async function renderWatchLabel(data: WatchLabelData): Promise<HTMLCanvasElement> {
  const canvas = document.createElement('canvas')
  canvas.width = LABEL_W
  canvas.height = LABEL_H
  const ctx = canvas.getContext('2d')!

  // White background
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, LABEL_W, LABEL_H)

  // Border
  ctx.strokeStyle = '#000000'
  ctx.lineWidth = 2
  ctx.strokeRect(1, 1, LABEL_W - 2, LABEL_H - 2)

  // Header strip
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, LABEL_W, 28)
  ctx.fillStyle = '#ffffff'
  ctx.font = 'bold 13px sans-serif'
  ctx.fillText('MAINSPRING', PAD, 18)
  ctx.font = '11px sans-serif'
  const copyLabel = data.isCustomerCopy ? 'CUSTOMER COPY' : 'WORKSHOP COPY'
  const copyW = ctx.measureText(copyLabel).width
  ctx.fillText(copyLabel, LABEL_W - PAD - copyW, 18)

  ctx.fillStyle = '#000000'

  // Ticket number — large
  ctx.font = 'bold 22px monospace'
  ctx.fillText(`#${data.jobNumber}`, PAD, 56)

  // Customer and item
  ctx.font = 'bold 12px sans-serif'
  ctx.fillText(truncate(data.customerName, 28), PAD, 78)
  ctx.font = '11px sans-serif'
  ctx.fillText(truncate(data.watchTitle, 30), PAD, 94)
  ctx.fillText(data.dateIn, PAD, 110)

  // Pricing (internal copy only)
  if (!data.isCustomerCopy && data.depositLabel && data.balanceLabel) {
    ctx.font = '10px sans-serif'
    ctx.fillText(`Deposit: ${data.depositLabel}`, PAD, 126)
    ctx.fillText(`Balance: ${data.balanceLabel}`, PAD, 140)
  }

  // Customer copy tagline
  if (data.isCustomerCopy) {
    ctx.font = '10px sans-serif'
    ctx.fillStyle = '#555555'
    ctx.fillText('Scan QR for live repair updates', PAD, 200)
    ctx.fillStyle = '#000000'
  }

  // QR code image (right side)
  if (data.qrDataUrl) {
    const qrSize = 100
    const qrX = LABEL_W - PAD - qrSize
    const qrY = 35
    await drawImage(ctx, data.qrDataUrl, qrX, qrY, qrSize, qrSize)
  }

  return canvas
}

export interface ShoeLabelData {
  jobNumber: string
  customerName: string
  shoeDescription: string
  dateIn: string
  qrDataUrl: string
  isCustomerCopy: boolean
  depositLabel?: string
  balanceLabel?: string
}

export async function renderShoeLabel(data: ShoeLabelData): Promise<HTMLCanvasElement> {
  const canvas = document.createElement('canvas')
  canvas.width = LABEL_W
  canvas.height = LABEL_H
  const ctx = canvas.getContext('2d')!

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, LABEL_W, LABEL_H)
  ctx.strokeStyle = '#000000'
  ctx.lineWidth = 2
  ctx.strokeRect(1, 1, LABEL_W - 2, LABEL_H - 2)

  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, LABEL_W, 28)
  ctx.fillStyle = '#ffffff'
  ctx.font = 'bold 13px sans-serif'
  ctx.fillText('MAINSPRING', PAD, 18)
  ctx.font = '11px sans-serif'
  const copyLabel = data.isCustomerCopy ? 'CUSTOMER COPY' : 'WORKSHOP COPY'
  const copyW = ctx.measureText(copyLabel).width
  ctx.fillText(copyLabel, LABEL_W - PAD - copyW, 18)

  ctx.fillStyle = '#000000'

  ctx.font = 'bold 22px monospace'
  ctx.fillText(`#${data.jobNumber}`, PAD, 56)

  ctx.font = 'bold 12px sans-serif'
  ctx.fillText(truncate(data.customerName, 28), PAD, 78)
  ctx.font = '11px sans-serif'
  ctx.fillText(truncate(data.shoeDescription, 30), PAD, 94)
  ctx.fillText(data.dateIn, PAD, 110)

  if (!data.isCustomerCopy && data.depositLabel && data.balanceLabel) {
    ctx.font = '10px sans-serif'
    ctx.fillText(`Deposit: ${data.depositLabel}`, PAD, 126)
    ctx.fillText(`Balance: ${data.balanceLabel}`, PAD, 140)
  }

  if (data.isCustomerCopy) {
    ctx.font = '10px sans-serif'
    ctx.fillStyle = '#555555'
    ctx.fillText('Scan QR for live repair updates', PAD, 200)
    ctx.fillStyle = '#000000'
  }

  if (data.qrDataUrl) {
    const qrSize = 100
    const qrX = LABEL_W - PAD - qrSize
    const qrY = 35
    await drawImage(ctx, data.qrDataUrl, qrX, qrY, qrSize, qrSize)
  }

  return canvas
}

function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text
  return text.slice(0, maxChars - 1) + '…'
}

function drawImage(
  ctx: CanvasRenderingContext2D,
  src: string,
  x: number, y: number,
  w: number, h: number
): Promise<void> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => { ctx.drawImage(img, x, y, w, h); resolve() }
    img.onerror = reject
    img.src = src
  })
}
