import { useEffect, useRef } from 'react'
import { useMapsLibrary } from '@vis.gl/react-google-maps'
import {
  parseAuAddressFromComponents,
  parseAuAddressFromFormatted,
  type ResolvedAuAddress,
} from '@/lib/auAddress'

const labelClass = 'text-[10px] font-bold uppercase'
const labelStyle: React.CSSProperties = { color: 'var(--ms-text-muted)', letterSpacing: '0.10em', marginBottom: 5 }
const inputStyle: React.CSSProperties = {
  height: 36,
  border: '1px solid var(--ms-border)',
  backgroundColor: 'var(--ms-surface)',
  color: 'var(--ms-text)',
  borderRadius: 'var(--ms-radius-sm)',
  fontSize: 13,
  padding: '0 12px',
  outline: 'none',
  transition: 'box-shadow 0.15s',
  width: '100%',
}

export interface AddressAutocompleteInputProps {
  label?: string
  value: string
  onChange: (val: string) => void
  /** Called when a Places result (or blur parse fallback) yields suburb/state. */
  onPlaceResolved?: (place: ResolvedAuAddress) => void
  placeholder?: string
  required?: boolean
}

function resolveFromFormatted(formatted: string): ResolvedAuAddress {
  const parsed = parseAuAddressFromFormatted(formatted)
  return { formattedAddress: formatted, ...parsed }
}

function AutocompleteInner({ label, value, onChange, onPlaceResolved, placeholder, required }: AddressAutocompleteInputProps) {
  const places = useMapsLibrary('places')
  const inputRef = useRef<HTMLInputElement>(null)
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null)
  const onPlaceResolvedRef = useRef(onPlaceResolved)
  onPlaceResolvedRef.current = onPlaceResolved

  useEffect(() => {
    if (!places || !inputRef.current || autocompleteRef.current) return
    autocompleteRef.current = new places.Autocomplete(inputRef.current, {
      componentRestrictions: { country: 'au' },
      fields: ['formatted_address', 'address_components'],
      types: ['address'],
    })
    autocompleteRef.current.addListener('place_changed', () => {
      const place = autocompleteRef.current!.getPlace()
      const formatted = place.formatted_address?.trim()
      if (!formatted) return
      onChange(formatted)
      const parsed = parseAuAddressFromComponents(place.address_components)
      onPlaceResolvedRef.current?.({
        formattedAddress: formatted,
        suburb: parsed.suburb,
        stateCode: parsed.stateCode,
      })
    })
  }, [places, onChange])

  useEffect(() => {
    if (inputRef.current && document.activeElement !== inputRef.current) {
      inputRef.current.value = value
    }
  }, [value])

  return (
    <div className="flex flex-col">
      {label && <label className={labelClass} style={labelStyle}>{label}</label>}
      <input
        ref={inputRef}
        defaultValue={value}
        onChange={e => onChange(e.target.value)}
        onBlur={e => {
          const formatted = e.target.value.trim()
          if (!formatted || !onPlaceResolvedRef.current) return
          onPlaceResolvedRef.current(resolveFromFormatted(formatted))
        }}
        placeholder={placeholder}
        required={required}
        autoComplete="off"
        className="w-full border outline-none transition focus:ring-2"
        style={inputStyle}
      />
    </div>
  )
}

export function AddressAutocompleteInput(props: AddressAutocompleteInputProps) {
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
  if (!apiKey) {
    return (
      <div className="flex flex-col">
        {props.label && <label className={labelClass} style={labelStyle}>{props.label}</label>}
        <input
          value={props.value}
          onChange={e => props.onChange(e.target.value)}
          onBlur={e => {
            const formatted = e.target.value.trim()
            if (!formatted || !props.onPlaceResolved) return
            props.onPlaceResolved(resolveFromFormatted(formatted))
          }}
          placeholder={props.placeholder}
          required={props.required}
          className="w-full border outline-none transition focus:ring-2"
          style={inputStyle}
        />
      </div>
    )
  }
  return <AutocompleteInner {...props} />
}
