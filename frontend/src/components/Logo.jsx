/** A stylised maple leaf, drawn from one polygon so it can take any colour. */
export default function Logo({ className = 'h-7 w-7', title }) {
  return (
    <svg viewBox="0 0 100 100" className={className} role={title ? 'img' : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
      <polygon
        fill="currentColor"
        points="50,3 55,15 60,12 61,26 68,20 67,33 79,28 76,42 93,36 87,51 97,60 72,70 74,80 56,74 54,96 46,96 44,74 26,80 28,70 3,60 13,51 7,36 24,42 21,28 33,33 32,20 39,26 40,12 45,15"
      />
    </svg>
  )
}
