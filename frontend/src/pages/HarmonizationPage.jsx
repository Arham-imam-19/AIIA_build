import React, { useState } from 'react'
import { api, savedToken } from '../api'

export default function HarmonizationPage() {
  const [file, setFile] = useState(null)
  const [mappings, setMappings] = useState([])
  const [loading, setLoading] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [result, setResult] = useState(null)

  // Sample data simulating a messy CSV from a legacy hospital system
  const generateSampleData = () => {
    const csvContent = `patient_full_name,mobile_number,pt_id,years_old,gender,ht,wt,imbalance,symptom,intensity,date_of_onset
Rajesh Kumar,9876543210,SUB-1001,45,Male,175,72,Vata,Severe Headaches,Severe,2026-09-01
Priya Sharma,9988776655,SUB-1002,32,Female,160,55,Pitta,Stomach ache,Mild,2026-09-02
Amit Patel,9123456789,SUB-1003,50,Male,168,80,Kapha,Joint Pain,Moderate,2026-09-02`
    
    const blob = new Blob([csvContent], { type: 'text/csv' })
    blob.name = 'messy_site01_export.csv'
    handleFileUpload(blob)
  }

  const handleFileUpload = async (uploadedFile) => {
    setFile(uploadedFile)
    setLoading(true)
    setResult(null)

    const formData = new FormData()
    formData.append('file', uploadedFile, uploadedFile.name || 'upload.csv')

    try {
      const res = await fetch('/api/harmonization/preview', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${savedToken()}`
        },
        body: formData
      })
      if(!res.ok) throw new Error("Failed to process file")
      const data = await res.json()
      setMappings(data.mappings)
    } catch(err) {
      alert("Error: " + err.message)
    }
    setLoading(false)
  }

  const updateMapping = (index, val) => {
    const newMappings = [...mappings]
    newMappings[index].suggested_target = val
    setMappings(newMappings)
  }

  const ingestData = async () => {
    setIngesting(true)
    const mappingConfig = {}
    mappings.forEach(m => {
      mappingConfig[m.original_header] = m.suggested_target
    })

    const formData = new FormData()
    formData.append('file', file)
    formData.append('mapping_config', JSON.stringify(mappingConfig))

    try {
      const res = await fetch('/api/harmonization/commit', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${savedToken()}`
        },
        body: formData
      })
      const data = await res.json()
      setResult(data)
      setMappings([])
      setFile(null)
    } catch(e) {
      alert("Ingestion failed: " + e.message)
    }
    setIngesting(false)
  }

  const getBadgeColor = (confidence, target) => {
    if (target === 'DPDP_DROP') return 'bg-red-100 text-red-800 border-red-200'
    if (target === 'IGNORE') return 'bg-slate-100 text-slate-600 border-slate-200'
    if (confidence >= 85) return 'bg-emerald-100 text-emerald-800 border-emerald-200'
    if (confidence >= 60) return 'bg-amber-100 text-amber-800 border-amber-200'
    return 'bg-red-100 text-red-800 border-red-200'
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Data Harmonizer (CDISC Ingestion)</h1>
          <p className="text-sm text-slate-500 mt-1">AI-assisted pipeline for mapping messy external CSVs to global standards.</p>
        </div>
      </div>

      {!file && !result && (
        <div className="rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-12 text-center transition-colors hover:border-aiia-400 hover:bg-aiia-50">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-200 mb-4">
            <span className="text-2xl">📄</span>
          </div>
          <h3 className="text-lg font-semibold text-slate-900">Upload Messy Clinical Data</h3>
          <p className="text-sm text-slate-500 mt-1 mb-6">Drag and drop a CSV file containing non-standard hospital data.</p>
          
          <div className="flex justify-center gap-4">
            <label className="cursor-pointer rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white hover:bg-slate-800">
              Select CSV File
              <input type="file" accept=".csv" className="hidden" onChange={e => handleFileUpload(e.target.files[0])} />
            </label>
            <button type="button" 
              onClick={generateSampleData}
              className="rounded-lg border border-slate-300 bg-white px-6 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Load Sample Site Data
            </button>
          </div>
        </div>
      )}

      {loading && (
        <div className="text-center p-12 text-slate-500">
          <div className="text-4xl mb-4 animate-spin">⚙️</div>
          <p className="font-semibold text-lg">RapidFuzz Matching Engine Running...</p>
        </div>
      )}

      {result && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-8 text-center">
          <div className="text-5xl mb-4">✅</div>
          <h2 className="text-2xl font-bold text-emerald-900 mb-2">Ingestion Complete</h2>
          <p className="text-emerald-800 font-medium">Successfully mapped and stored the dataset.</p>
          <div className="mt-6 flex justify-center gap-8">
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <div className="text-3xl font-black text-emerald-600">{result.subjects_inserted}</div>
              <div className="text-xs uppercase font-bold text-slate-500 mt-1">Subjects Merged</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <div className="text-3xl font-black text-amber-500">{result.aes_inserted}</div>
              <div className="text-xs uppercase font-bold text-slate-500 mt-1">Adverse Events Split</div>
            </div>
          </div>
          <button type="button" 
            onClick={() => setResult(null)} 
            className="mt-8 rounded-lg bg-emerald-600 px-6 py-2 text-sm font-bold text-white hover:bg-emerald-700"
          >
            Process Another File
          </button>
        </div>
      )}

      {mappings.length > 0 && !result && (
        <div className="space-y-4">
          <div className="flex items-center justify-between bg-indigo-50 border border-indigo-100 p-4 rounded-lg">
            <div>
              <h3 className="font-bold text-indigo-900">Mapping Review</h3>
              <p className="text-sm text-indigo-700">The ML engine has suggested targets. DPDP rules have flagged PII for redaction. Please review and override if necessary.</p>
            </div>
            <button type="button" 
              onClick={ingestData}
              disabled={ingesting}
              className="bg-indigo-600 text-white font-bold py-2 px-6 rounded-lg shadow hover:bg-indigo-700 disabled:opacity-50"
            >
              {ingesting ? 'Committing...' : 'Approve & Ingest to Clinical Registry'}
            </button>
          </div>

          <div className="border border-slate-200 rounded-xl bg-white overflow-hidden shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="p-4 font-semibold text-slate-700">Incoming External Column</th>
                  <th className="p-4 font-semibold text-slate-700">Sample Data (3 rows)</th>
                  <th className="p-4 font-semibold text-slate-700">AI Confidence</th>
                  <th className="p-4 font-semibold text-slate-700 w-64">Target Database Field (CDISC/SUPPQUAL)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {mappings.map((m, i) => (
                  <tr key={i} className={m.suggested_target === 'DPDP_DROP' ? 'bg-red-50/30' : 'hover:bg-slate-50'}>
                    <td className="p-4 font-mono font-bold text-slate-800">{m.original_header}</td>
                    <td className="p-4">
                      <div className="flex flex-wrap gap-2">
                        {m.sample_values.map((v, idx) => (
                          <span key={idx} className="bg-slate-100 border border-slate-200 text-slate-600 text-xs px-2 py-1 rounded truncate max-w-[150px]">
                            {v}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="p-4">
                      <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border ${getBadgeColor(m.confidence, m.suggested_target)}`}>
                        {m.suggested_target === 'DPDP_DROP' ? '🚨 REDACT (DPDP ACT)' : `${m.confidence}% MATCH`}
                      </div>
                    </td>
                    <td className="p-4">
                      <select 
                        value={m.suggested_target}
                        onChange={(e) => updateMapping(i, e.target.value)}
                        className="w-full rounded border border-slate-300 p-2 text-xs font-mono shadow-sm focus:border-aiia-500 focus:ring-1 focus:ring-aiia-500"
                      >
                        <option value="IGNORE">-- Ignore / Do Not Import --</option>
                        <option value="DPDP_DROP">🚨 DPDP_DROP (Drop PII)</option>
                        <optgroup label="Demographics (DM)">
                          <option value="DM.USUBJID">DM.USUBJID (Subject ID)</option>
                          <option value="DM.AGE">DM.AGE (Age)</option>
                          <option value="DM.SEX">DM.SEX (Gender)</option>
                          <option value="DM.WEIGHT">DM.WEIGHT (Weight)</option>
                          <option value="DM.HEIGHT">DM.HEIGHT (Height)</option>
                        </optgroup>
                        <optgroup label="Supplemental (SUPPQUAL)">
                          <option value="SUPPQUAL.PRAKRITI">SUPPQUAL.PRAKRITI</option>
                          <option value="SUPPQUAL.DOSHA">SUPPQUAL.DOSHA</option>
                          <option value="SUPPQUAL.AGNI">SUPPQUAL.AGNI</option>
                        </optgroup>
                        <optgroup label="Adverse Events (AE)">
                          <option value="AE.AETERM">AE.AETERM (Symptom/Event)</option>
                          <option value="AE.AESEV">AE.AESEV (Severity)</option>
                          <option value="AE.AESTDAT">AE.AESTDAT (Onset Date)</option>
                        </optgroup>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
