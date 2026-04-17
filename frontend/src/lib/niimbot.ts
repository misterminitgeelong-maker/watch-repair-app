/**
 * Niimbot BLE protocol implementation for Web Bluetooth API.
 * Protocol reverse-engineered from niimprint (Python) and community docs.
 * Tested against M2 with 50x30mm labels.
 */

const NIIMBOT_SERVICE_UUID = 'e7810a71-73ae-499d-8c15-faa9aef0c3f2'
const DOTS_PER_MM = 203 / 25.4  // 203 DPI

const CMD = {
  GET_RFID: 0x1a,
  HEARTBEAT: 0xdc,
  SET_LABEL_TYPE: 0x23,
  SET_LABEL_DENSITY: 0x21,
  START_PRINT: 0x01,
  END_PRINT: 0xf3,
  START_PAGE_PRINT: 0x03,
  END_PAGE_PRINT: 0xe3,
  SET_DIMENSION: 0x13,
  SET_QUANTITY: 0x15,
  WRITE_IMAGE_LINE: 0x83,
}

export interface LabelDots { width: number; height: number }

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
  private notifyChar: BluetoothRemoteGATTCharacteristic | null = null
  private responseResolvers: Array<(v: DataView) => void> = []
  private _labelDots: LabelDots | null = null

  get connected() { return this.device?.gatt?.connected ?? false }
  get deviceName() { return this.device?.name ?? null }
  get labelDots(): LabelDots | null { return this._labelDots }

  async connect(): Promise<void> {
    const device = await navigator.bluetooth.requestDevice({
      filters: [{ namePrefix: 'M2' }],
      optionalServices: [NIIMBOT_SERVICE_UUID],
    })
    await this.setupGatt(device)
  }

  async reconnectIfPaired(): Promise<boolean> {
    if (!('getDevices' in navigator.bluetooth)) return false
    const devices = await (navigator.bluetooth as Bluetooth & { getDevices(): Promise<BluetoothDevice[]> }).getDevices()
    const m2 = devices.find(d => d.name?.startsWith('M2'))
    if (!m2) return false
    await this.setupGatt(m2)
    return true
  }

  private onNotification = (e: Event) => {
    const char = e.target as BluetoothRemoteGATTCharacteristic
    if (char.value && this.responseResolvers.length > 0) {
      this.responseResolvers.shift()!(char.value)
    }
  }

  private async setupGatt(device: BluetoothDevice): Promise<void> {
    const server = await device.gatt!.connect()
    const service = await server.getPrimaryService(NIIMBOT_SERVICE_UUID)
    const chars = await service.getCharacteristics()

    const writable = chars.find(c => c.properties.writeWithoutResponse || c.properties.write)
    if (!writable) throw new Error('No writable characteristic found on Niimbot service')

    const notifiable = chars.find(c => c.properties.notify || c.properties.indicate)
    if (notifiable) {
      await notifiable.startNotifications()
      notifiable.addEventListener('characteristicvaluechanged', this.onNotification)
    }

    this.device = device
    this.writeChar = writable
    this.notifyChar = notifiable ?? null
    this._labelDots = null

    await this.send(CMD.HEARTBEAT, [0x00])
    this._labelDots = await this.readLabelDots()
  }

  disconnect() {
    if (this.notifyChar) {
      this.notifyChar.removeEventListener('characteristicvaluechanged', this.onNotification)
    }
    this.device?.gatt?.disconnect()
    this.device = null
    this.writeChar = null
    this.notifyChar = null
    this._labelDots = null
  }

  private waitForResponse(timeoutMs = 1500): Promise<DataView | null> {
    if (!this.notifyChar) return Promise.resolve(null)
    return new Promise(resolve => {
      const timer = setTimeout(() => {
        const i = this.responseResolvers.indexOf(resolve)
        if (i >= 0) this.responseResolvers.splice(i, 1)
        resolve(null)
      }, timeoutMs)
      this.responseResolvers.push(v => { clearTimeout(timer); resolve(v) })
    })
  }

  private async send(cmd: number, data: number[]): Promise<void> {
    if (!this.writeChar) throw new Error('Not connected to printer')
    const packet = buildPacket(cmd, data)
    if (this.writeChar.properties.write) {
      await this.writeChar.writeValue(packet)
    } else {
      await this.writeChar.writeValueWithoutResponse(packet)
    }
  }

  /** Query the label dimensions from the printer's RFID tag.
   *  Response data layout (from niimprint): after 4-byte header,
   *  skip 33 bytes (uuid+barcode+serial+lengths+type), then width_mm, height_mm. */
  private async readLabelDots(): Promise<LabelDots | null> {
    try {
      await this.send(CMD.GET_RFID, [0x01])
      const resp = await this.waitForResponse(2000)
      if (!resp || resp.byteLength < 39) return null
      const widthMm = resp.getUint8(4 + 33)
      const heightMm = resp.getUint8(4 + 34)
      if (!widthMm || !heightMm) return null
      return {
        width: Math.round(widthMm * DOTS_PER_MM),
        height: Math.round(heightMm * DOTS_PER_MM),
      }
    } catch {
      return null
    }
  }

  async printCanvas(canvas: HTMLCanvasElement, quantity = 1): Promise<void> {
    // M2 feeds along the long axis. If the canvas is landscape (wider than tall),
    // rotate 90° CW so height = feed direction, width = printhead width.
    // Portrait canvases are already in the correct orientation.
    let src = canvas
    if (canvas.width > canvas.height) {
      const rotated = document.createElement('canvas')
      rotated.width = canvas.height
      rotated.height = canvas.width
      const rctx = rotated.getContext('2d')!
      rctx.translate(rotated.width, 0)
      rctx.rotate(Math.PI / 2)
      rctx.drawImage(canvas, 0, 0)
      src = rotated
    }

    const ctx = src.getContext('2d')!
    const { width, height } = src
    const imageData = ctx.getImageData(0, 0, width, height)

    const rows: number[][] = []
    for (let y = 0; y < height; y++) {
      const bytesPerRow = Math.ceil(width / 8)
      const row = new Array<number>(bytesPerRow).fill(0)
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4
        const lum = 0.299 * imageData.data[idx] + 0.587 * imageData.data[idx + 1] + 0.114 * imageData.data[idx + 2]
        if (lum < 128) row[Math.floor(x / 8)] |= 0x80 >> (x % 8)
      }
      rows.push(row)
    }

    await this.send(CMD.SET_LABEL_TYPE, [0x01])
    await sleep(30)
    await this.send(CMD.SET_LABEL_DENSITY, [0x03])
    await sleep(30)
    await this.send(CMD.START_PRINT, [0x01])
    await sleep(200)   // printer needs time to initialise the print job
    await this.send(CMD.START_PAGE_PRINT, [0x01])
    await sleep(30)
    await this.send(CMD.SET_DIMENSION, [
      (height >> 8) & 0xff, height & 0xff,
      (width >> 8) & 0xff, width & 0xff,
    ])
    await sleep(30)
    await this.send(CMD.SET_QUANTITY, [0x00, quantity & 0xff])
    await sleep(30)

    for (let y = 0; y < rows.length; y++) {
      await this.send(CMD.WRITE_IMAGE_LINE, [(y >> 8) & 0xff, y & 0xff, ...rows[y]])
      // Small throttle every 8 rows to avoid flooding the BLE buffer
      if (y % 8 === 7) await sleep(5)
    }

    await sleep(100)
    await this.send(CMD.END_PAGE_PRINT, [0x01])
    await sleep(100)
    await this.send(CMD.END_PRINT, [0x01])
  }
}

function sleep(ms: number) {
  return new Promise<void>(resolve => setTimeout(resolve, ms))
}

// ---------------------------------------------------------------------------
// Canvas label renderers
// Dimensions default to 50x30mm at 203 DPI = 400x240 dots.
// Pass labelDots from the connected printer to auto-fit any label size.
// ---------------------------------------------------------------------------

const DEFAULT_DOTS: LabelDots = { width: 400, height: 240 }
const PAD = 12

export interface WatchLabelData {
  jobNumber: string
  customerName: string
  watchTitle: string
  dateIn: string
  qrDataUrl: string
  isCustomerCopy: boolean
  depositLabel?: string
  balanceLabel?: string
  labelDots?: LabelDots
}

export async function renderWatchLabel(data: WatchLabelData): Promise<HTMLCanvasElement> {
  const { width: W, height: H } = data.labelDots ?? DEFAULT_DOTS
  const scale = W / 400  // scale fonts/positions relative to reference 400-wide
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, W, H)
  ctx.strokeStyle = '#000000'
  ctx.lineWidth = 2
  ctx.strokeRect(1, 1, W - 2, H - 2)

  const headerH = Math.round(28 * scale)
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, W, headerH)
  ctx.fillStyle = '#ffffff'
  ctx.font = `bold ${Math.round(13 * scale)}px sans-serif`
  ctx.fillText('MAINSPRING', PAD, Math.round(18 * scale))
  const copyLabel = data.isCustomerCopy ? 'CUSTOMER COPY' : 'WORKSHOP COPY'
  ctx.font = `${Math.round(11 * scale)}px sans-serif`
  const copyW = ctx.measureText(copyLabel).width
  ctx.fillText(copyLabel, W - PAD - copyW, Math.round(18 * scale))

  ctx.fillStyle = '#000000'
  ctx.font = `bold ${Math.round(22 * scale)}px monospace`
  ctx.fillText(`#${data.jobNumber}`, PAD, Math.round(56 * scale))

  ctx.font = `bold ${Math.round(12 * scale)}px sans-serif`
  ctx.fillText(truncate(data.customerName, 30), PAD, Math.round(78 * scale))
  ctx.font = `${Math.round(11 * scale)}px sans-serif`
  ctx.fillText(truncate(data.watchTitle, 32), PAD, Math.round(94 * scale))
  ctx.fillText(data.dateIn, PAD, Math.round(110 * scale))

  if (!data.isCustomerCopy && data.depositLabel && data.balanceLabel) {
    ctx.font = `${Math.round(10 * scale)}px sans-serif`
    ctx.fillText(`Deposit: ${data.depositLabel}`, PAD, Math.round(126 * scale))
    ctx.fillText(`Balance: ${data.balanceLabel}`, PAD, Math.round(140 * scale))
  }

  if (data.isCustomerCopy) {
    ctx.font = `${Math.round(10 * scale)}px sans-serif`
    ctx.fillStyle = '#555555'
    ctx.fillText('Scan QR for live repair updates', PAD, H - 12)
    ctx.fillStyle = '#000000'
  }

  if (data.qrDataUrl) {
    const qrSize = Math.round(100 * scale)
    await drawImage(ctx, data.qrDataUrl, W - PAD - qrSize, headerH + 4, qrSize, qrSize)
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
  labelDots?: LabelDots
}

export async function renderShoeLabel(data: ShoeLabelData): Promise<HTMLCanvasElement> {
  const { width: W, height: H } = data.labelDots ?? DEFAULT_DOTS
  const scale = W / 400
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, W, H)
  ctx.strokeStyle = '#000000'
  ctx.lineWidth = 2
  ctx.strokeRect(1, 1, W - 2, H - 2)

  const headerH = Math.round(28 * scale)
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, W, headerH)
  ctx.fillStyle = '#ffffff'
  ctx.font = `bold ${Math.round(13 * scale)}px sans-serif`
  ctx.fillText('MAINSPRING', PAD, Math.round(18 * scale))
  const copyLabel = data.isCustomerCopy ? 'CUSTOMER COPY' : 'WORKSHOP COPY'
  ctx.font = `${Math.round(11 * scale)}px sans-serif`
  const copyW = ctx.measureText(copyLabel).width
  ctx.fillText(copyLabel, W - PAD - copyW, Math.round(18 * scale))

  ctx.fillStyle = '#000000'
  ctx.font = `bold ${Math.round(22 * scale)}px monospace`
  ctx.fillText(`#${data.jobNumber}`, PAD, Math.round(56 * scale))

  ctx.font = `bold ${Math.round(12 * scale)}px sans-serif`
  ctx.fillText(truncate(data.customerName, 30), PAD, Math.round(78 * scale))
  ctx.font = `${Math.round(11 * scale)}px sans-serif`
  ctx.fillText(truncate(data.shoeDescription, 32), PAD, Math.round(94 * scale))
  ctx.fillText(data.dateIn, PAD, Math.round(110 * scale))

  if (!data.isCustomerCopy && data.depositLabel && data.balanceLabel) {
    ctx.font = `${Math.round(10 * scale)}px sans-serif`
    ctx.fillText(`Deposit: ${data.depositLabel}`, PAD, Math.round(126 * scale))
    ctx.fillText(`Balance: ${data.balanceLabel}`, PAD, Math.round(140 * scale))
  }

  if (data.isCustomerCopy) {
    ctx.font = `${Math.round(10 * scale)}px sans-serif`
    ctx.fillStyle = '#555555'
    ctx.fillText('Scan QR for live repair updates', PAD, H - 12)
    ctx.fillStyle = '#000000'
  }

  if (data.qrDataUrl) {
    const qrSize = Math.round(100 * scale)
    await drawImage(ctx, data.qrDataUrl, W - PAD - qrSize, headerH + 4, qrSize, qrSize)
  }

  return canvas
}

function truncate(text: string, maxChars: number): string {
  return text.length <= maxChars ? text : text.slice(0, maxChars - 1) + '…'
}

function drawImage(ctx: CanvasRenderingContext2D, src: string, x: number, y: number, w: number, h: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => { ctx.drawImage(img, x, y, w, h); resolve() }
    img.onerror = reject
    img.src = src
  })
}
