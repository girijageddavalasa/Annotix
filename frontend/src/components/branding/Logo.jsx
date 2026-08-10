import { ScanLine } from 'lucide-react'

export function Logo() {
  return (
    <div className="brand" aria-label="Annotix home">
      <span className="brand__mark"><ScanLine size={21} strokeWidth={2.3} /></span>
      <span className="brand__name">Annotix</span>
      <span className="brand__tag">LOCAL</span>
    </div>
  )
}

