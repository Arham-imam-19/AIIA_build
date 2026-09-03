import { useEffect, useState } from 'react'
import {
  downloadTrialCdiscSdtmZip,
  fetchTrialCdiscJson,
  fetchTrialFhirBundle,
  fetchTrials,
} from '../api'

function JsonViewerModal({ title, data, filename, onClose }) {
  const [copied, setCopied] = useState(false)
  const jsonStr = JSON.stringify(data, null, 2)

  function handleCopy() {
    navigator.clipboard.writeText(jsonStr)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function handleDownload() {
    const blob = new Blob([jsonStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || 'export.json'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="flex h-[85vh] w-full max-w-4xl flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 dark:border-slate-800">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">{title}</h3>
            <p className="text-xs text-slate-500">Universal Medicine Standard Interoperability Payload</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {copied ? '✅ Copied' : '📋 Copy JSON'}
            </button>
            <button
              onClick={handleDownload}
              className="rounded-lg bg-aiia-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-aiia-700 shadow-sm"
            >
              ⬇️ Download File
            </button>
            <button
              onClick={onClose}
              className="ml-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto bg-slate-950 p-4 font-mono text-xs text-emerald-400">
          <pre className="whitespace-pre-wrap">{jsonStr}</pre>
        </div>
      </div>
    </div>
  )
}

export default function DataExportCenter() {
  const [trial, setTrial] = useState(null)
  const [loading, setLoading] = useState(false)
  const [modalData, setModalData] = useState(null)
  const [modalTitle, setModalTitle] = useState('')
  const [modalFilename, setModalFilename] = useState('')
  const [statusMsg, setStatusMsg] = useState('')

  useEffect(() => {
    fetchTrials()
      .then((res) => {
        if (res.items?.[0]) setTrial(res.items[0])
      })
      .catch(() => {})
  }, [])

  const trialId = trial?.id || 1
  const protocol = trial?.protocol_number || 'AIIA-ASH-2026-01'

  async function handleDownloadZip() {
    setLoading(true)
    setStatusMsg('Compiling CDISC SDTM domains (DM, AE, SV, DV, TS) into ZIP...')
    try {
      await downloadTrialCdiscSdtmZip(trialId)
      setStatusMsg('✅ CDISC SDTM Package downloaded successfully.')
      setTimeout(() => setStatusMsg(''), 4000)
    } catch (err) {
      setStatusMsg(`❌ Download failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  async function handleInspectCdiscJson() {
    setLoading(true)
    setStatusMsg('Generating CDISC Dataset-JSON v1.1 structure...')
    try {
      const data = await fetchTrialCdiscJson(trialId)
      setModalData(data)
      setModalTitle(`CDISC SDTM Dataset-JSON (v1.1) — ${protocol}`)
      setModalFilename(`CDISC_DatasetJSON_${protocol}.json`)
      setStatusMsg('')
    } catch (err) {
      setStatusMsg(`❌ Fetch failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  async function handleInspectFhirBundle() {
    setLoading(true)
    setStatusMsg('Generating HL7 FHIR R4 ResearchStudy Collection Bundle...')
    try {
      const data = await fetchTrialFhirBundle(trialId)
      setModalData(data)
      setModalTitle(`HL7 FHIR R4 Clinical Trial Bundle — ${protocol}`)
      setModalFilename(`HL7_FHIR_Bundle_${protocol}.json`)
      setStatusMsg('')
    } catch (err) {
      setStatusMsg(`❌ Fetch failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 dark:border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-indigo-600"></span>
            Universal Clinical Data Interoperability & Export Center
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            CDISC SDTM (IG 3.3) and HL7 FHIR R4 Universal Medicine Standard Data Formats
          </p>
        </div>
        <span className="rounded-md bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
          GCP & FDA / EMA / CDSCO Interoperable
        </span>
      </div>

      {statusMsg && (
        <div className="mt-3 rounded-lg bg-slate-50 p-2 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          {statusMsg}
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: CDISC SDTM ZIP */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-200 bg-slate-50/50 p-4 transition-all hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-800/40">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900 dark:text-white">CDISC SDTM Package</span>
              <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-mono font-bold text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                .ZIP (CSV)
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Standard Study Data Tabulation Model package containing tabulated domains (<strong>DM</strong>, <strong>AE</strong>, <strong>SV</strong>, <strong>DV</strong>, <strong>TS</strong>) with <code>define.json</code> metadata.
            </p>
          </div>
          <button
            type="button"
            onClick={handleDownloadZip}
            disabled={loading}
            className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 transition"
          >
            📦 Download SDTM Package (.ZIP)
          </button>
        </div>

        {/* Card 2: CDISC Dataset-JSON */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-200 bg-slate-50/50 p-4 transition-all hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-800/40">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900 dark:text-white">CDISC Dataset-JSON</span>
              <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-mono font-bold text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
                v1.1 (JSON)
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Modern CDISC Dataset-JSON v1.1.0 standard representation for automated statistical ingestion, FDA technical conformance, and API interchange.
            </p>
          </div>
          <button
            type="button"
            onClick={handleInspectCdiscJson}
            disabled={loading}
            className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 transition"
          >
            📄 Inspect Dataset-JSON
          </button>
        </div>

        {/* Card 3: HL7 FHIR R4 Bundle */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-200 bg-slate-50/50 p-4 transition-all hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-800/40">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900 dark:text-white">HL7 FHIR R4 Bundle</span>
              <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-mono font-bold text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">
                FHIR R4
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Universal clinical research resource bundle linking <strong>ResearchStudy</strong>, <strong>ResearchSubject</strong>, <strong>Patient</strong>, <strong>Encounter</strong>, and <strong>AdverseEvent</strong> (MedDRA coded).
            </p>
          </div>
          <button
            type="button"
            onClick={handleInspectFhirBundle}
            disabled={loading}
            className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 transition"
          >
            🔥 Inspect FHIR R4 Bundle
          </button>
        </div>

        {/* Card 4: CDISC Import Pipeline */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-200 bg-aiia-50/50 p-4 transition-all hover:border-aiia-300 dark:border-slate-800 dark:bg-slate-800/40">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900 dark:text-white">CDISC AI Harmonizer</span>
              <span className="rounded bg-aiia-100 px-1.5 py-0.5 text-[10px] font-mono font-bold text-aiia-800 dark:bg-aiia-900 dark:text-aiia-200">
                IMPORT (CSV)
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Inbound pipeline using <strong>RapidFuzz ML</strong> to automatically map messy external hospital spreadsheets to strict CDISC SDTM target fields while redacting PII.
            </p>
          </div>
          <button
            type="button"
            onClick={() => window.location.href = '#'}
            className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-lg bg-aiia-600 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-aiia-700 transition"
          >
            📥 Go to Ingestion Pipeline
          </button>
        </div>
      </div>

      {modalData && (
        <JsonViewerModal
          title={modalTitle}
          data={modalData}
          filename={modalFilename}
          onClose={() => setModalData(null)}
        />
      )}
    </div>
  )
}
