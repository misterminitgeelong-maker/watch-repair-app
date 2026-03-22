import { useRef, useEffect, useState, useCallback } from 'react'

interface Props {
  width?: number
  height?: number
  onSignatureChange?: (dataUrl: string | null) => void
  className?: string
}

export default function SignaturePad({ width = 300, height = 120, onSignatureChange, className = '' }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [hasDrawn, setHasDrawn] = useState(false)

  const getCtx = useCallback(() => canvasRef.current?.getContext('2d'), [])

  const emitSignature = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !hasDrawn) {
      onSignatureChange?.(null)
      return
    }
    const dataUrl = canvas.toDataURL('image/png')
    onSignatureChange?.(dataUrl)
  }, [hasDrawn, onSignatureChange])

  useEffect(() => {
    const ctx = getCtx()
    const canvas = canvasRef.current
    if (!ctx || !canvas) return
    ctx.strokeStyle = '#2C1810'
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.fillStyle = '#FFFCF8'
    ctx.fillRect(0, 0, width, height)
  }, [getCtx, width, height])

  useEffect(() => {
    emitSignature()
  }, [hasDrawn, emitSignature])

  const getPos = (e: React.TouchEvent | React.MouseEvent) => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    const scaleX = width / rect.width
    const scaleY = height / rect.height
    if ('touches' in e) {
      return { x: (e.touches[0].clientX - rect.left) * scaleX, y: (e.touches[0].clientY - rect.top) * scaleY }
    }
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY }
  }

  const startDrawing = (e: React.TouchEvent | React.MouseEvent) => {
    e.preventDefault()
    const pos = getPos(e)
    if (!pos) return
    const ctx = getCtx()
    if (!ctx) return
    ctx.beginPath()
    ctx.moveTo(pos.x, pos.y)
    setIsDrawing(true)
    setHasDrawn(true)
  }

  const draw = (e: React.TouchEvent | React.MouseEvent) => {
    e.preventDefault()
    if (!isDrawing) return
    const pos = getPos(e)
    if (!pos) return
    const ctx = getCtx()
    if (!ctx) return
    ctx.lineTo(pos.x, pos.y)
    ctx.stroke()
  }

  const stopDrawing = (e: React.TouchEvent | React.MouseEvent) => {
    e.preventDefault()
    setIsDrawing(false)
    emitSignature()
  }

  const clear = () => {
    const ctx = getCtx()
    const canvas = canvasRef.current
    if (!ctx || !canvas) return
    ctx.fillStyle = '#FFFCF8'
    ctx.fillRect(0, 0, width, height)
    setHasDrawn(false)
    onSignatureChange?.(null)
  }

  return (
    <div className={className}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ touchAction: 'none', border: '1px solid var(--cafe-border)', borderRadius: 8, cursor: 'crosshair' }}
        onMouseDown={startDrawing}
        onMouseMove={draw}
        onMouseUp={stopDrawing}
        onMouseLeave={stopDrawing}
        onTouchStart={startDrawing}
        onTouchMove={draw}
        onTouchEnd={stopDrawing}
      />
      <button
        type="button"
        onClick={clear}
        className="text-xs mt-1.5"
        style={{ color: 'var(--cafe-text-muted)' }}
      >
        Clear
      </button>
    </div>
  )
}
