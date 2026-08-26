// Regulator (CDSCO / Ministry of Ayush): read-only across every site, plus the
// audit trail. An inspector's first question is not "how is recruitment" but
// "was this trial allowed to start, and can you prove what happened since".

import DashboardLayout from './layout'

export default function Regulator(props) {
  return (
    <DashboardLayout
      {...props}
      wide={['audit_tail', 'sae_reporting']}
      note="The gates below are the legal sequence under India's NDCT Rules 2019: ethics approval, then CDSCO permission, then CTRI registration - and registration has to come before the first participant is enrolled."
    />
  )
}
