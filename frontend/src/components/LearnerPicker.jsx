import { useId, useState } from 'react'

const MAX_LEARNERS = 50

export function LearnerPicker({ learners, selectedIds, onChange }) {
  const inputId = useId()
  const listId = useId()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const selected = learners.filter((learner) => selectedIds.includes(learner.id))
  const suggestions = learners
    .filter(
      (learner) =>
        !selectedIds.includes(learner.id) &&
        `${learner.name} ${learner.email}`.toLowerCase().includes(query.trim().toLowerCase()),
    )
    .slice(0, 8)
  const showing = open && selectedIds.length < MAX_LEARNERS && suggestions.length > 0

  function add(learner) {
    if (selectedIds.includes(learner.id) || selectedIds.length >= MAX_LEARNERS) return
    onChange([...selectedIds, learner.id])
    setQuery('')
    setActive(0)
    setOpen(true)
    document.getElementById(inputId)?.focus()
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
      add(suggestions[active] || suggestions[0])
    } else if (event.key === 'Backspace' && !query && selectedIds.length) {
      onChange(selectedIds.slice(0, -1))
    }
  }

  return (
    <div className="field">
      <label htmlFor={inputId}>Learners</label>
      <div className="picker-wrap">
        <div className="picker-input">
          {selected.map((learner) => (
            <span className="picker-chip" key={learner.id}>
              <span>{learner.name}</span>
              <button
                type="button"
                aria-label={`Remove ${learner.name}`}
                onClick={() => onChange(selectedIds.filter((id) => id !== learner.id))}
              >
                ×
              </button>
            </span>
          ))}
          <input
            id={inputId}
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={showing}
            aria-controls={listId}
            aria-activedescendant={showing ? `${listId}-${active}` : undefined}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value)
              setActive(0)
              setOpen(true)
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
            onKeyDown={onKeyDown}
            placeholder={selectedIds.length ? 'Add another learner' : 'Search by name or email'}
            disabled={selectedIds.length >= MAX_LEARNERS}
            autoComplete="off"
          />
        </div>
        {showing && (
          <ul id={listId} role="listbox" className="picker-list">
            {suggestions.map((learner, index) => (
              <li
                id={`${listId}-${index}`}
                key={learner.id}
                role="option"
                aria-selected={index === active}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => add(learner)}
              >
                <strong>{learner.name}</strong>
                <small>{learner.email}</small>
              </li>
            ))}
          </ul>
        )}
      </div>
      <small>
        {selectedIds.length} of {MAX_LEARNERS} learners selected. Type to find more.
      </small>
    </div>
  )
}
