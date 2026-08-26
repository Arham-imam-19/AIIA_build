// Clinical Research Coordinator: the person who actually books the visits and
// enters the data. Their screen is a worklist, not a report - it answers "what
// do I have to do this week", so both tables are worth the full width.

import DashboardLayout from './layout'

export default function Coordinator(props) {
  return (
    <DashboardLayout
      {...props}
      wide={['upcoming', 'screening']}
      simulateFirst
      note="Your worklist for the next two weeks. An overdue visit becomes a protocol deviation if it slips outside its window, so these dates are the ones that matter."
    />
  )
}
