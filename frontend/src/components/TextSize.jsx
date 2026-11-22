import { useEffect, useState } from 'react'

/*
 * Text-size control: three clear steps — A / A / A — stored on this device and
 * applied to the whole app through <html data-size="s|m|l">. Everything is
 * sized in rem, so text, buttons and spacing all scale together.
 */
const KEY = 'civic_text_size_v2'
const SIZES = [
  { id: 's', label: 'Small text' },
  { id: 'm', label: 'Medium text' },
  { id: 'l', label: 'Large text' },
]

function readSize() {
  try {
    const v = window.localStorage.getItem(KEY)
    if (SIZES.some((s) => s.id === v)) return v
  } catch {
    /* storage unavailable */
  }
  return 's'
}

export default function TextSize() {
  const [size, setSize] = useState(readSize)

  useEffect(() => {
    document.documentElement.setAttribute('data-size', size)
    try {
      window.localStorage.setItem(KEY, size)
    } catch {
      /* in-memory only */
    }
  }, [size])

  return (
    <div className="textsize" role="group" aria-label="Change text size">
      <span className="textsize-label" aria-hidden="true">Text size</span>
      {SIZES.map((s, i) => (
        <button
          key={s.id}
          type="button"
          className={'textsize-btn textsize-' + (i + 1) + (size === s.id ? ' active' : '')}
          onClick={() => setSize(s.id)}
          aria-label={s.label}
          aria-pressed={size === s.id}
          title={s.label}
        >
          A
        </button>
      ))}
    </div>
  )
}
