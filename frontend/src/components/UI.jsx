import { useEffect, useId, useRef, useState } from 'react'
import { Icon } from './Icon.jsx'

export function Button({ children, kind = 'primary', className = '', ...props }) {
  return (
    <button type="button" className={`btn btn-${kind} ${className}`} {...props}>
      {children}
    </button>
  )
}
export function Badge({ children, active = false }) {
  return (
    <span className={`badge ${active ? 'badge-active' : ''}`}>
      <span className="status-dot" />
      {children}
    </span>
  )
}
export function Field({ label, children, hint, ...props }) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children ? (
        <select id={id} aria-describedby={hint ? `${id}-hint` : undefined} {...props}>
          {children}
        </select>
      ) : props.multiline ? (
        <textarea
          id={id}
          aria-describedby={hint ? `${id}-hint` : undefined}
          rows={props.rows || 5}
          {...Object.fromEntries(Object.entries(props).filter(([key]) => key !== 'multiline'))}
        />
      ) : (
        <input id={id} aria-describedby={hint ? `${id}-hint` : undefined} {...props} />
      )}
      {hint && <small id={`${id}-hint`}>{hint}</small>}
    </div>
  )
}
export function ErrorNotice({ error, retry }) {
  if (!error) return null
  return (
    <div className="notice error-notice" role="alert">
      <strong>Something needs your attention</strong>
      <p>{error.message || error}</p>
      {retry && (
        <Button kind="secondary" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  )
}
export function Loading({ label = 'Loading your workspace' }) {
  return (
    <div className="loading-state" role="status" aria-label={label}>
      <span className="sr-only">{label}</span>
      <div className="skeleton skeleton-heading" />
      <div className="skeleton" />
      <div className="skeleton" />
      <div className="skeleton skeleton-short" />
    </div>
  )
}
export function Empty({ title, children, action, icon = 'book' }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} />
      </span>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  )
}
export function PageHeading({ eyebrow, title, description, action }) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  )
}
export function ResourceBoundary({ resource, children }) {
  if (resource.loading) return <Loading />
  if (resource.error) return <ErrorNotice error={resource.error} retry={resource.refresh} />
  return children
}
export function ProgressBar({ progress }) {
  if (!progress) return null
  return (
    <div className="progress-block">
      <div>
        <span>
          {progress.completed_lessons} of {progress.total_lessons} lessons
        </span>
        <strong>{progress.percent_complete}%</strong>
      </div>
      <progress max="100" value={progress.percent_complete} aria-label="Course completion" />
    </div>
  )
}
export function ActionDialog({
  title,
  children,
  onClose,
  action,
  onSaved,
  submitLabel = 'Save changes',
  explanation,
}) {
  const dialog = useRef(null)
  const headingId = useId()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  useEffect(() => {
    const element = dialog.current
    const previous = document.activeElement
    element.showModal()
    element.querySelector('input, textarea, select')?.focus()
    return () => {
      element.close()
      previous?.focus()
    }
  }, [])
  async function submit(event) {
    event.preventDefault()
    if (pending) return
    const values = Object.fromEntries(new FormData(event.currentTarget))
    setPending(true)
    setError(null)
    try {
      const result = await action(values)
      onSaved(result)
    } catch (failure) {
      setError(failure)
      setPending(false)
    }
  }
  return (
    <dialog
      ref={dialog}
      className="action-dialog"
      aria-labelledby={headingId}
      onCancel={(event) => {
        event.preventDefault()
        if (!pending) onClose()
      }}
    >
      <form onSubmit={submit}>
        <div className="dialog-heading">
          <h2 id={headingId}>{title}</h2>
          <Button kind="quiet" aria-label="Close form" disabled={pending} onClick={onClose}>
            <Icon name="close" />
          </Button>
        </div>
        {explanation && <p className="body-copy">{explanation}</p>}
        <fieldset disabled={pending}>{children}</fieldset>
        <ErrorNotice error={error} />
        <div className="dialog-actions">
          <Button kind="secondary" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button type="submit" disabled={pending}>
            {pending ? 'Saving…' : submitLabel}
          </Button>
        </div>
      </form>
    </dialog>
  )
}

export function Records({ rows, render, empty, page: controlledPage, onPageChange, total }) {
  const [internalPage, setInternalPage] = useState(0)
  const page = controlledPage ?? internalPage
  const setPage = onPageChange || setInternalPage
  const count = total ?? rows.length
  const pages = Math.max(1, Math.ceil(count / 10))
  const current = Math.min(page, pages - 1)
  if (!rows.length) return empty
  return (
    <>
      <ul className="record-list">
        {(total === undefined ? rows.slice(current * 10, current * 10 + 10) : rows).map(render)}
      </ul>
      {pages > 1 && (
        <div className="pagination">
          <span>
            {current * 10 + 1}–
            {Math.min(count, current * 10 + (total === undefined ? 10 : rows.length))} of {count}
          </span>
          <div className="actions">
            <Button kind="secondary" disabled={current === 0} onClick={() => setPage(current - 1)}>
              Previous
            </Button>
            <Button
              kind="secondary"
              disabled={current === pages - 1}
              onClick={() => setPage(current + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  )
}
