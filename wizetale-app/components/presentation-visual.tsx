import type { PresentationVisual } from '@/lib/teacher-content'

export function PresentationVisualFigure({visual, className = ''}: {visual?: PresentationVisual; className?: string}) {
  if (visual?.status !== 'ready' || !visual.image_url) return null
  return <figure className={`prep-slide-visual ${className}`}>
    {/* The authenticated visual service supplies an owner-scoped signed URL. */}
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={visual.image_url} alt={visual.alt_text} />
    {visual.caption && <figcaption>{visual.caption}</figcaption>}
  </figure>
}
