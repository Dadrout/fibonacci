import SlushLanding from '@/components/slush-landing'
import './landing/globals.css'

export default function HomePage() {
  const previewEnabled = process.env.NEXT_PUBLIC_ENABLE_DASHBOARD_PREVIEW === 'true'

  return <SlushLanding previewEnabled={previewEnabled} />
}
