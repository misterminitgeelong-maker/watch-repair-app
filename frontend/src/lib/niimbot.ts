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
  GET_PRINT_STATUS: 0xa3,
  // 0x85 = full bitmap row (row, 3 black-pixel counts, repeat, packed bits).
  // 0x83 is the *indexed* row format with a different payload — sending packed
  // bitmap bytes as 0x83 makes the printer feed and retract a blank label.
  WRITE_IMAGE_ROW: 0x85,
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
  private pendingResponses: Array<{ respCmd: number | null; resolve: (v: DataView) => void }> = []
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
    const value = char.value
    if (!value || value.byteLength < 4) return
    // Packet layout: 0x55 0x55 <cmd> <len> <data…> <xor> 0xaa 0xaa — route the
    // response to the waiter expecting this command (printers also push
    // unsolicited status packets, so first-in-line matching mixes up replies).
    const cmd = value.getUint8(2)
    const i = this.pendingResponses.findIndex(p => p.respCmd === null || p.respCmd === cmd)
    if (i >= 0) this.pendingResponses.splice(i, 1)[0].resolve(value)
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

  private waitForResponse(respCmd: number | null, timeoutMs = 1500): Promise<DataView | null> {
    if (!this.notifyChar) return Promise.resolve(null)
    return new Promise(resolve => {
      const entry = {
        respCmd,
        resolve: (v: DataView) => { clearTimeout(timer); resolve(v) },
      }
      const timer = setTimeout(() => {
        const i = this.pendingResponses.indexOf(entry)
        if (i >= 0) this.pendingResponses.splice(i, 1)
        resolve(null)
      }, timeoutMs)
      this.pendingResponses.push(entry)
    })
  }

  /** Send a command and wait for its reply (response cmd = request cmd + respOffset). */
  private async transceive(cmd: number, data: number[], respOffset = 1, timeoutMs = 1500): Promise<DataView | null> {
    const waiter = this.waitForResponse(cmd + respOffset, timeoutMs)
    await this.send(cmd, data)
    return waiter
  }

  private async send(cmd: number, data: number[]): Promise<void> {
    if (!this.writeChar) throw new Error('Not connected to printer')
    const packet = buildPacket(cmd, data)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const anyChar = this.writeChar as any
    if (this.writeChar.properties.write) {
      // Prefer the newer writeValueWithResponse (handles MTU chunking automatically).
      // Fall back to deprecated writeValue if the newer API isn't available.
      if (typeof anyChar.writeValueWithResponse === 'function') {
        await anyChar.writeValueWithResponse(packet)
      } else {
        await this.writeChar.writeValue(packet)
      }
    } else {
      await this.writeChar.writeValueWithoutResponse(packet)
    }
  }

  /** Query the label dimensions from the printer's RFID tag.
   *  Response data layout (from niimprint): after 4-byte header,
   *  skip 33 bytes (uuid+barcode+serial+lengths+type), then width_mm, height_mm. */
  private async readLabelDots(): Promise<LabelDots | null> {
    try {
      const resp = await this.transceive(CMD.GET_RFID, [0x01], 1, 2000)
      if (!resp || resp.byteLength < 39) return null
      const widthMm = resp.getUint8(4 + 33)
      const heightMm = resp.getUint8(4 + 34)
      // Reject implausible sizes — a misparsed RFID reply otherwise produces a
      // wrong canvas/dimension and the printer rejects the page.
      if (widthMm < 10 || widthMm > 120 || heightMm < 10 || heightMm > 120) return null
      return {
        width: Math.round(widthMm * DOTS_PER_MM),
        height: Math.round(heightMm * DOTS_PER_MM),
      }
    } catch {
      return null
    }
  }

  async printCanvas(canvas: HTMLCanvasElement, quantity = 1): Promise<void> {
    // The M2 loads 50x30 labels with the 50mm side across the print head, so a
    // landscape canvas maps directly: width = printhead dots, height = feed
    // rows. Rotating here prints sideways and overruns the 30mm feed length,
    // which burns through several labels per page.
    const ctx = canvas.getContext('2d')!
    const { width, height } = canvas
    const imageData = ctx.getImageData(0, 0, width, height)

    // Pack each row to 1bpp. The 0x85 header carries black-pixel counts for
    // thirds of the print head (firmware uses them for heat management).
    // Every row is sent as a full bitmap row — the sparse 0x84 empty-row
    // packet is not handled consistently across firmware.
    const bytesPerRow = Math.ceil(width / 8)
    type Row = { bytes: number[]; counts: [number, number, number] }
    const rows: Row[] = []
    for (let y = 0; y < height; y++) {
      const row = new Array<number>(bytesPerRow).fill(0)
      const counts: [number, number, number] = [0, 0, 0]
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4
        const lum = 0.299 * imageData.data[idx] + 0.587 * imageData.data[idx + 1] + 0.114 * imageData.data[idx + 2]
        if (lum < 128) {
          row[Math.floor(x / 8)] |= 0x80 >> (x % 8)
          counts[Math.min(2, Math.floor((x * 3) / width))]++
        }
      }
      rows.push({ bytes: row, counts })
    }

    await this.send(CMD.SET_LABEL_TYPE, [0x01])
    await sleep(50)
    await this.send(CMD.SET_LABEL_DENSITY, [0x03])
    await sleep(50)
    // Newer firmware (B1/M2 generation) reads START_PRINT as a u16 total page
    // count and SET_DIMENSION as rows/cols/copies (3×u16). Sending the older
    // short forms leaves the copies field undefined and the printer spits out
    // a random number of duplicate labels.
    await this.send(CMD.START_PRINT, [(quantity >> 8) & 0xff, quantity & 0xff])
    await sleep(400)   // mobile BLE needs more time to initialise the print job
    await this.send(CMD.START_PAGE_PRINT, [0x01])
    await sleep(50)
    await this.send(CMD.SET_DIMENSION, [
      (height >> 8) & 0xff, height & 0xff,
      (width >> 8) & 0xff, width & 0xff,
      (quantity >> 8) & 0xff, quantity & 0xff,
    ])
    await sleep(50)

    for (let y = 0; y < rows.length; y++) {
      const row = rows[y]
      await this.send(CMD.WRITE_IMAGE_ROW, [
        (y >> 8) & 0xff, y & 0xff,
        Math.min(row.counts[0], 255), Math.min(row.counts[1], 255), Math.min(row.counts[2], 255),
        0x01, // repeat count: print this row once
        ...row.bytes,
      ])
      // Throttle every 4 packets — mobile GATT queues fill up faster than desktop
      if (y % 4 === 3) await sleep(20)
    }

    await sleep(300)   // let all row packets drain before closing the page
    await this.send(CMD.END_PAGE_PRINT, [0x01])

    // Wait for the printer to physically finish. Sending END_PRINT while it is
    // still feeding makes it abort the job and retract the label unprinted.
    await this.waitForPrintComplete(quantity)

    for (let attempt = 0; attempt < 10; attempt++) {
      const resp = await this.transceive(CMD.END_PRINT, [0x01], 1, 800)
      if (!resp) break                                   // no notify channel — assume done
      if (resp.byteLength > 4 && resp.getUint8(4) !== 0) break  // printer acked job end
      await sleep(200)                                   // not ready yet — retry
    }
  }

  /** Poll print status until the requested pages are out (or timeout). */
  private async waitForPrintComplete(quantity: number, timeoutMs = 30000): Promise<void> {
    if (!this.notifyChar) {
      await sleep(1500 + 1200 * quantity)
      return
    }
    const start = Date.now()
    let misses = 0
    while (Date.now() - start < timeoutMs) {
      const resp = await this.transceive(CMD.GET_PRINT_STATUS, [0x01], 16, 1000)
      if (resp && resp.byteLength >= 8) {
        misses = 0
        const page = (resp.getUint8(4) << 8) | resp.getUint8(5)
        const progress1 = resp.getUint8(6)
        const progress2 = resp.getUint8(7)
        if (page >= quantity && progress1 >= 100 && progress2 >= 100) return
      } else if (++misses >= 3) {
        // Firmware doesn't answer status queries — fall back to a generous wait
        await sleep(1500 + 1200 * quantity)
        return
      }
      await sleep(300)
    }
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
  customerPhone?: string
  watchTitle: string
  services?: string
  dateIn: string
  qrDataUrl: string
  isCustomerCopy: boolean
  depositLabel?: string
  balanceLabel?: string
  labelDots?: LabelDots
}

export async function renderWatchLabel(data: WatchLabelData): Promise<HTMLCanvasElement> {
  const { width: W, height: H } = data.labelDots ?? DEFAULT_DOTS
  const scale = W / 400
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, W, H)
  ctx.strokeStyle = '#000000'
  ctx.lineWidth = 1
  ctx.strokeRect(0.5, 0.5, W - 1, H - 1)

  // Header strip
  const headerH = Math.round(28 * scale)
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, W, headerH)
  ctx.fillStyle = '#ffffff'
  ctx.font = `bold ${Math.round(14 * scale)}px sans-serif`
  ctx.fillText('MAINSPRING', PAD, Math.round(19 * scale))
  const copyLabel = data.isCustomerCopy ? 'CUSTOMER COPY' : 'WORKSHOP COPY'
  ctx.font = `${Math.round(11 * scale)}px sans-serif`
  const copyW = ctx.measureText(copyLabel).width
  ctx.fillText(copyLabel, W - PAD - copyW, Math.round(19 * scale))

  // QR code — right block
  const qrSize = Math.round(Math.min(150 * scale, H - headerH - 10))
  const qrX = W - PAD - qrSize
  const qrY = headerH + 5
  if (data.qrDataUrl) {
    await drawImage(ctx, data.qrDataUrl, qrX, qrY, qrSize, qrSize)
  }

  // Text content — left column, constrained to not overlap the QR
  ctx.fillStyle = '#000000'

  // Job number
  ctx.font = `bold ${Math.round(34 * scale)}px monospace`
  ctx.fillText(`#${data.jobNumber}`, PAD, Math.round(66 * scale))

  // Customer name
  ctx.font = `bold ${Math.round(17 * scale)}px sans-serif`
  ctx.fillText(truncate(data.customerName, 22), PAD, Math.round(90 * scale))

  let nextY = 90

  // Phone
  if (data.customerPhone) {
    ctx.font = `${Math.round(15 * scale)}px sans-serif`
    ctx.fillText(data.customerPhone, PAD, Math.round((nextY + 20) * scale))
    nextY += 20
  }

  // Watch title
  ctx.font = `${Math.round(15 * scale)}px sans-serif`
  ctx.fillText(truncate(data.watchTitle, 24), PAD, Math.round((nextY + 20) * scale))
  nextY += 20

  // Services (job title)
  if (data.services) {
    ctx.fillText(truncate(data.services, 24), PAD, Math.round((nextY + 20) * scale))
    nextY += 20
  }

  // Date in
  ctx.fillText(data.dateIn, PAD, Math.round((nextY + 20) * scale))
  nextY += 20

  // Deposit + balance on one line (workshop only)
  if (!data.isCustomerCopy && data.depositLabel && data.balanceLabel) {
    ctx.font = `${Math.round(13 * scale)}px sans-serif`
    ctx.fillText(`Dep: ${data.depositLabel}  Bal: ${data.balanceLabel}`, PAD, Math.round((nextY + 18) * scale))
  }

  // Customer copy — scan prompt at bottom
  if (data.isCustomerCopy) {
    ctx.font = `${Math.round(11 * scale)}px sans-serif`
    ctx.fillStyle = '#444444'
    ctx.fillText('Scan QR for live repair updates', PAD, H - 8)
  }

  return canvas
}

export interface ShoeLabelData {
  jobNumber: string
  customerName: string
  customerPhone?: string
  shoeDescription: string
  services?: string
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
  ctx.lineWidth = 1
  ctx.strokeRect(0.5, 0.5, W - 1, H - 1)

  const headerH = Math.round(28 * scale)
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, W, headerH)
  ctx.fillStyle = '#ffffff'
  ctx.font = `bold ${Math.round(14 * scale)}px sans-serif`
  ctx.fillText('MAINSPRING', PAD, Math.round(19 * scale))
  const copyLabel = data.isCustomerCopy ? 'CUSTOMER COPY' : 'WORKSHOP COPY'
  ctx.font = `${Math.round(11 * scale)}px sans-serif`
  const copyW = ctx.measureText(copyLabel).width
  ctx.fillText(copyLabel, W - PAD - copyW, Math.round(19 * scale))

  const qrSize = Math.round(Math.min(150 * scale, H - headerH - 10))
  const qrX = W - PAD - qrSize
  const qrY = headerH + 5
  if (data.qrDataUrl) {
    await drawImage(ctx, data.qrDataUrl, qrX, qrY, qrSize, qrSize)
  }

  ctx.fillStyle = '#000000'

  ctx.font = `bold ${Math.round(34 * scale)}px monospace`
  ctx.fillText(`#${data.jobNumber}`, PAD, Math.round(66 * scale))

  ctx.font = `bold ${Math.round(17 * scale)}px sans-serif`
  ctx.fillText(truncate(data.customerName, 22), PAD, Math.round(90 * scale))

  let nextY = 90

  if (data.customerPhone) {
    ctx.font = `${Math.round(15 * scale)}px sans-serif`
    ctx.fillText(data.customerPhone, PAD, Math.round((nextY + 20) * scale))
    nextY += 20
  }

  ctx.font = `${Math.round(15 * scale)}px sans-serif`
  ctx.fillText(truncate(data.shoeDescription, 24), PAD, Math.round((nextY + 20) * scale))
  nextY += 20

  if (data.services) {
    ctx.fillText(truncate(data.services, 24), PAD, Math.round((nextY + 20) * scale))
    nextY += 20
  }

  ctx.fillText(data.dateIn, PAD, Math.round((nextY + 20) * scale))
  nextY += 20

  if (!data.isCustomerCopy && data.depositLabel && data.balanceLabel) {
    ctx.font = `${Math.round(13 * scale)}px sans-serif`
    ctx.fillText(`Dep: ${data.depositLabel}  Bal: ${data.balanceLabel}`, PAD, Math.round((nextY + 18) * scale))
  }

  if (data.isCustomerCopy) {
    ctx.font = `${Math.round(11 * scale)}px sans-serif`
    ctx.fillStyle = '#444444'
    ctx.fillText('Scan QR for live repair updates', PAD, H - 8)
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
