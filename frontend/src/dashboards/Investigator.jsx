// Principal Investigator: the doctor legally responsible for the trial at one
// hospital. Everything on this screen is their own site - asking for another
// site's participant returns 403, by design.

import DashboardLayout from './layout'

export default function Investigator(props) {
  return (
    <DashboardLayout
      {...props}
      // The adverse-event table is the clinically important one, so it gets the
      // full width rather than being squeezed next to a chart.
      wide={['recent_aes']}
      simulateFirst
      note="Scoped to your site only. Safety first: an open adverse event is one that has not resolved yet, and a serious one has to reach the ethics committee within days."
    />
  )
}
