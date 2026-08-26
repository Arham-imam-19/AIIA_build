// Sponsor: funds and oversees the study but never touches the data. The question
// is always the same - is this trial on track, across every site?

import DashboardLayout from './layout'

export default function Sponsor(props) {
  return (
    <DashboardLayout
      {...props}
      wide={['site_performance']}
      note="Every site, all sites. A Sponsor cannot enter or edit trial data: a monitor who could change the numbers would undermine the numbers. Leave this screen open and have the coordinator enrol someone - it moves on its own."
    />
  )
}
