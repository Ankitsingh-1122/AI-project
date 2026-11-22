import { useEffect, useState } from 'react'

/*
 * Text-size control for readers who need bigger letters.
 * Three clear steps — A / A / A — stored on this device and applied to the
 * whole app through <html data-size="…">. Everything is sized in rem, so all
 * text, buttons and spacing grow together.
 */
const KEY = 'civic_text_size'
const SIZES = [
  { id: 'normal', label: 'Normal text size' },
  { id: 'large', label: 'Large text size' },
  { id: 'xlarge', label: 'Extra large text size' },
]

function readSize() {
  try {
    const v = window.localStorage.getItem(KEY)
    if (SIZES.some((s) => s.id === v)) return v
  } catch {
    /* storage unavailable */
  }
  return 'large' // default: comfortable for everyone
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
