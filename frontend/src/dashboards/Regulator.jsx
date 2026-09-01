// Regulator (CDSCO / Ministry of Ayush): read-only across every site, plus the
// audit trail. An inspector's first question is not "how is recruitment" but
// "was this trial allowed to start, and can you prove what happened since".

import DashboardLayout from './layout'

export default function Regulator(props) {
  const exportCDISC = () => {
    const data = "<?xml version='1.0'?><ODM><ClinicalData></ClinicalData></ODM>"
    const blob = new Blob([data], { type: 'text/xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'define.xml'
    a.click()
  }

  return (
    <div>
      <div className="flex justify-end mb-6">
        <button onClick={exportCDISC} className="bg-slate-800 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-900 flex items-center gap-2 shadow-sm">
          📥 Export CDISC / Define-XML
        </button>
      </div>
      <DashboardLayout
        {...props}
        wide={['audit_trail']}
        note="You have strict read-only access to all trial data and the immutable ALCOA+ audit trail."
      />
    </div>
  )
}
