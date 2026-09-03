import React from 'react'
import DataExportCenter from '../components/DataExportCenter'

export default function ExportPage() {
  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">CDISC & FHIR Export Center</h1>
          <p className="text-sm text-slate-500 mt-1">Generate regulatory-compliant study data packages for global interoperability.</p>
        </div>
      </div>
      <div className="mt-6">
        <DataExportCenter />
      </div>
    </div>
  )
}
