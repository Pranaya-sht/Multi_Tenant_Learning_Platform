const paths = {
  close: 'M6 6l12 12M6 18L18 6',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  check: 'M5 12l4 4L19 6',
  plus: 'M12 5v14M5 12h14',
  logout: 'M10 4H4v16h6M14 8l4 4-4 4M8 12h10',
  assignment: 'M9 4H5v17h14V4h-4M9 3h6v4H9V3ZM8 12h8M8 16h5',
  book: 'M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 1 4 18.5V5.5ZM4 18.5A2.5 2.5 0 0 1 6.5 16H20M9 7h6M9 11h4',
  overview: 'M3 3h7v7H3V3Zm11 0h7v7h-7V3ZM3 14h7v7H3v-7Zm11 0h7v7h-7v-7Z',
  learners:
    'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  organization: 'M3 21V5h12v16M15 9h6v12M7 9h4M7 13h4M7 17h4M18 13h1M18 17h1M1 21h22',
  refresh: 'M20 7v5h-5M4 17v-5h5M6.2 7a7 7 0 0 1 11.5-2L20 8M4 16l2.3 3a7 7 0 0 0 11.5-2',
  menu: 'M4 6h16M4 12h16M4 18h16',
}

export function Icon({ name, className = '' }) {
  return (
    <svg
      className={`icon ${className}`}
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name]} />
    </svg>
  )
}
