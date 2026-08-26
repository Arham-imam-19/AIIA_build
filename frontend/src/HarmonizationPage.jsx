import { useState } from 'react'
import { previewHarmonization, commitHarmonization } from './api'

export default function HarmonizationPage({ user }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [mappings, setMappings] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [targetSiteId, setTargetSiteId] = useState(user?.site_id || 1)

  // Hardcoded for demo since we only have one seeded trial
  const TRIAL_ID = 1

  const handleFileUpload = async (e) => {
    const selected = e.target.files[0]
    if (!selected) return

    setFile(selected)
    setLoading(true)
    setError(null)
    setSuccess(null)
    setPreview(null)

    try {
      const data = await previewHarmonization(selected)
      setPreview(data)
      setMappings(data.proposals)
    } catch (err) {
      setError(err.detail || 'Failed to analyze file.')
    } finally {
      setLoading(false)
    }
  }

  const handleMappingChange = (originalHeader, newTarget) => {
    setMappings((prev) =>
      prev.map((m) => {
        if (m.original_header === originalHeader) {
          return {
            ...m,
            suggested_target: newTarget,
            action: newTarget ? 'MAP_CORE' : 'UNRESOLVED',
            target_label: newTarget || 'Unmapped'
          }
        }
        return m
      })
    )
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)

    const payload = {
      trial_id: TRIAL_ID,
      site_id: targetSiteId,
      mappings: mappings.map((m) => ({
        original_header: m.original_header,
        action: m.action,
        target: m.suggested_target
      })),
      data: preview.preview_rows // Sending the preview rows as the dataset for the demo
    }

    try {
      const res = await commitHarmonization(payload)
      setSuccess(res.message)
      setFile(null)
      setPreview(null)
    } catch (err) {
      setError(err.detail || 'Failed to commit data.')
    } finally {
      setLoading(false)
    }
  }

  const getBadgeColor = (action, confidence) => {
    if (action === 'DROP_PII') return 'bg-gray-100 text-gray-800 border-gray-300'
    if (action === 'MAP_SUPPLEMENTAL') return 'bg-blue-50 text-blue-800 border-blue-200'
    if (confidence >= 85) return 'bg-emerald-50 text-emerald-800 border-emerald-200'
    if (confidence >= 65) return 'bg-amber-50 text-amber-800 border-amber-200'
    return 'bg-red-50 text-red-800 border-red-200'
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Data Harmonization</h1>
          <p className="text-slate-500 mt-1">
            Algorithmic CDISC SDTM mapping and DPDP-compliant PII filtering.
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded">
          {success}
        </div>
      )}

      {!preview ? (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm text-center space-y-4">
          <div className="max-w-md mx-auto">
            <label className="block w-full cursor-pointer border-2 border-dashed border-slate-300 rounded-lg p-8 hover:bg-slate-50 transition-colors">
              <span className="text-slate-600 font-medium block">
                {loading ? 'Analyzing...' : 'Drop a messy CSV here or click to browse'}
              </span>
              <input
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileUpload}
                disabled={loading}
              />
            </label>
          </div>
          <p className="text-sm text-slate-500">
            For this demo, find sample files in <code>backend/app/harmonization/samples/</code>
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <h2 className="font-medium text-slate-800">Review Mappings</h2>
            
            {!user.is_site_scoped && (
              <div className="flex items-center space-x-2">
                <label className="text-sm text-slate-600">Target Site:</label>
                <select
                  value={targetSiteId}
                  onChange={(e) => setTargetSiteId(parseInt(e.target.value))}
                  className="text-sm border border-slate-300 rounded px-2 py-1 bg-white"
                >
                  <option value={1}>Site 1 (AIIA New Delhi)</option>
                  <option value={2}>Site 2 (NIA Jaipur)</option>
                  <option value={3}>Site 3 (IPGAE Kolkata)</option>
                  <option value={4}>Site 4 (GAU Jamnagar)</option>
                </select>
              </div>
            )}
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 uppercase bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3 font-medium">Source Column</th>
                  <th className="px-6 py-3 font-medium">Sample Values</th>
                  <th className="px-6 py-3 font-medium">Target Standard</th>
                  <th className="px-6 py-3 font-medium">Confidence & Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {mappings.map((m, idx) => (
                  <tr key={idx} className="hover:bg-slate-50">
                    <td className="px-6 py-4 font-medium text-slate-900 bg-slate-50/50">
                      {m.original_header}
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      <div className="flex flex-wrap gap-1">
                        {m.sample_values.map((val, i) => (
                          <span key={i} className="inline-block bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-xs truncate max-w-[120px]">
                            {val}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {m.action === 'DROP_PII' ? (
                        <span className="text-slate-400 italic">Excluded</span>
                      ) : m.action === 'MAP_SUPPLEMENTAL' ? (
                        <span className="text-blue-700 font-medium text-xs">{m.target_label}</span>
                      ) : (
                        <select
                          value={m.suggested_target || ''}
                          onChange={(e) => handleMappingChange(m.original_header, e.target.value)}
                          className="w-full border-slate-300 rounded text-sm py-1.5 focus:border-emerald-500 focus:ring-emerald-500"
                        >
                          <option value="">-- Ignore / Do not map --</option>
                          <optgroup label="Demographics (DM)">
                            <option value="DM.USUBJID">Subject ID (USUBJID)</option>
                            <option value="DM.AGE">Age</option>
                            <option value="DM.BRTHDTC">Date of Birth</option>
                            <option value="DM.SEX">Sex</option>
                            <option value="DM.ARM">Study Arm</option>
                          </optgroup>
                          <optgroup label="Adverse Events (AE)">
                            <option value="AE.AETERM">Reported Term (AETERM)</option>
                            <option value="AE.AESEV">Severity (AESEV)</option>
                          </optgroup>
                          <optgroup label="Vital Signs (VS)">
                            <option value="VS.SYSBP">Systolic BP</option>
                            <option value="VS.DIABP">Diastolic BP</option>
                          </optgroup>
                        </select>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getBadgeColor(m.action, m.confidence)}`}>
                        {m.action === 'DROP_PII' ? 'DPDP Drop' : `${m.confidence}%`}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <div className="p-6 bg-slate-50 border-t border-slate-200 flex justify-end space-x-3">
            <button
              onClick={() => {
                setPreview(null)
                setFile(null)
              }}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 border border-transparent rounded-md hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 flex items-center shadow-sm"
            >
              {loading ? 'Processing...' : 'Approve & Ingest to Registry'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
