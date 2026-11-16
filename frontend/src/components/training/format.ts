/** "77 kg × 3", "2.25 min × 2" */
export const formatAmount = (weight: number, sets: number, unit: string) => `${weight.toLocaleString()} ${unit} × ${sets}`

/** "29.05." for this year, "29.05.25" otherwise */
export function formatDay(iso: string) {
  const day = new Date(`${iso}T00:00:00`)
  const sameYear = day.getFullYear() === new Date().getFullYear()
  return day.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', ...(sameYear ? {} : { year: '2-digit' }) })
}

/** "Fr, 29.05.2026" */
export const formatLongDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })
