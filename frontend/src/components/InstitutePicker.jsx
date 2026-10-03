import { useEffect, useId, useState } from 'react'
import { apiRequest } from '../lib/api.js'

export function InstitutePicker({ value, selectedSlug, onChange, onSelect }) {
  const inputId = useId()
  const listId = useId()
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    const term = value.trim()
    if (selectedSlug || term.length < 2) return
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const rows = await apiRequest(`/auth/institutes?q=${encodeURIComponent(term)}`, {
          signal: controller.signal,
        })
        setSuggestions(rows)
      } catch {
        if (!controller.signal.aborted) setSuggestions([])
      } finally {
        if (!controller.signal.aborted) setSearching(false)
      }
    }, 200)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [value, selectedSlug])

  const showing = open && !selectedSlug && suggestions.length > 0
  function select(item) {
    onSelect(item)
    setOpen(false)
  }
  function onKeyDown(event) {
    if (event.key === 'Escape') {
      setOpen(false)
      event.stopPropagation()
    } else if (event.key === 'ArrowDown' && suggestions.length) {
      event.preventDefault()
      setOpen(true)
      setActive((index) => (index + 1) % suggestions.length)
    } else if (event.key === 'ArrowUp' && suggestions.length) {
      event.preventDefault()
      setOpen(true)
      setActive((index) => (index - 1 + suggestions.length) % suggestions.length)
    } else if (event.key === 'Enter' && showing) {
      event.preventDefault()
      select(suggestions[active] || suggestions[0])
    }
  }

  return (
    <div className="field">
      <label htmlFor={inputId}>Institute</label>
      <div className="picker-wrap">
        <input
          id={inputId}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showing}
          aria-controls={listId}
          aria-activedescendant={showing ? `${listId}-${active}` : undefined}
          value={value}
          onChange={(event) => {
            onChange(event.target.value)
            setSuggestions([])
            setActive(0)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          placeholder="Search your institute"
          required
          minLength={2}
          maxLength={150}
          autoCapitalize="none"
          autoComplete="off"
          spellCheck={false}
        />
        {showing && (
          <ul id={listId} role="listbox" className="picker-list">
            {suggestions.map((item, index) => (
              <li
                id={`${listId}-${index}`}
                key={item.slug}
                role="option"
                aria-selected={index === active}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => select(item)}
              >
                <strong>{item.name}</strong>
                <small>{item.slug}</small>
              </li>
            ))}
          </ul>
        )}
      </div>
      <small>
        {searching ? 'Searching institutes…' : 'Choose a result or enter its identifier.'}
      </small>
    </div>
  )
}
