import { useCallback, useRef, useState } from 'react'
import { NiimbotPrinter, type LabelDots } from '@/lib/niimbot'

export type PrinterStatus = 'disconnected' | 'connecting' | 'connected' | 'printing' | 'error'

export function useNiimbotPrinter() {
  const printerRef = useRef<NiimbotPrinter | null>(null)
  const [status, setStatus] = useState<PrinterStatus>('disconnected')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [labelDots, setLabelDots] = useState<LabelDots | null>(null)

  const connect = useCallback(async () => {
    setStatus('connecting')
    setErrorMessage(null)
    try {
      if (!printerRef.current) printerRef.current = new NiimbotPrinter()
      await printerRef.current.connect()
      setLabelDots(printerRef.current.labelDots)
      setStatus('connected')
    } catch (err) {
      printerRef.current = null
      setErrorMessage(err instanceof Error ? err.message : 'Connection failed')
      setStatus('error')
    }
  }, [])

  const autoConnect = useCallback(async (): Promise<boolean> => {
    setStatus('connecting')
    setErrorMessage(null)
    try {
      if (!printerRef.current) printerRef.current = new NiimbotPrinter()
      const ok = await printerRef.current.reconnectIfPaired()
      if (ok) setLabelDots(printerRef.current.labelDots)
      setStatus(ok ? 'connected' : 'disconnected')
      return ok
    } catch {
      setStatus('disconnected')
      return false
    }
  }, [])

  const disconnect = useCallback(() => {
    printerRef.current?.disconnect()
    printerRef.current = null
    setStatus('disconnected')
    setErrorMessage(null)
    setLabelDots(null)
  }, [])

  const print = useCallback(async (canvases: HTMLCanvasElement[]) => {
    if (!printerRef.current?.connected) throw new Error('Printer not connected')
    setStatus('printing')
    setErrorMessage(null)
    try {
      for (const canvas of canvases) {
        await printerRef.current.printCanvas(canvas)
      }
      setStatus('connected')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Print failed'
      setErrorMessage(msg)
      setStatus('error')
    }
  }, [])

  const isSupported = typeof navigator !== 'undefined' && 'bluetooth' in navigator

  return { status, errorMessage, isSupported, labelDots, connect, autoConnect, disconnect, print }
}
