import { useEffect, useRef } from 'react'
import { useMapsLibrary } from '@vis.gl/react-google-maps'

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

interface Props {
  label?: string
  value: string
  onChange: (val: string) => void
  placeholder?: string
  required?: boolean
}

function AutocompleteInner({ label, value, onChange, placeholder, required }: Props) {
  const places = useMapsLibrary('places')
  const inputRef = useRef<HTMLInputElement>(null)
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null)

  useEffect(() => {
    if (!places || !inputRef.current || autocompleteRef.current) return
    autocompleteRef.current = new places.Autocomplete(inputRef.current, {
      componentRestrictions: { country: 'au' },
      fields: ['formatted_address'],
      types: ['address'],
    })
    autocompleteRef.current.addListener('place_changed', () => {
      const place = autocompleteRef.current!.getPlace()
      if (place.formatted_address) onChange(place.formatted_address)
    })
  }, [places, onChange])

  // Keep the input value in sync when controlled value changes externally
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
        placeholder={placeholder}
        required={required}
        autoComplete="off"
        className="w-full border outline-none transition focus:ring-2"
        style={inputStyle}
      />
    </div>
  )
}

export function AddressAutocompleteInput(props: Props) {
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
  if (!apiKey) {
    // No key — render plain input matching the same visual style
    return (
      <div className="flex flex-col">
        {props.label && <label className={labelClass} style={labelStyle}>{props.label}</label>}
        <input
          value={props.value}
          onChange={e => props.onChange(e.target.value)}
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
