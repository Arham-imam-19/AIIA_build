// Ethics Committee: the independent body that approved the trial and has to be
// told about serious events. They see every site, but only safety and
// deviations - they have no reason to browse participant records, so they cannot.

import DashboardLayout from './layout'

export default function Ethics(props) {
  return (
    <DashboardLayout
      {...props}
      wide={['sae_reporting', 'deviations']}
      note="Severity is how bad an event felt; seriousness is a regulatory category - death, hospitalisation, disability - that starts a reporting clock. A severe headache is not serious. Only the serious ones are listed below."
    />
  )
}
