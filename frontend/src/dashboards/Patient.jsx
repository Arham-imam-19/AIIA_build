// Patient Portal: trial participant dashboard with Full Bilingual Support & Digital e-Consent (NDCT Rules 2019 & 21 CFR Part 11).

import { useEffect, useState } from 'react'
import { createPatientRequest, getMyEConsent, signEConsent } from '../api'
import SignaturePad from '../components/SignaturePad'
import DashboardLayout from './layout'

const HINDI_MAP = {
  // Tiles
  'Participant ID': 'प्रतिभागी पहचान (ID)',
  'Trial Status': 'परीक्षण स्थिति',
  'Next Appointment': 'अगली नियुक्ति',
  'Completed Visits': 'पूर्ण यात्राएं',
  'My Inquiries': 'मेरी पूछताछ',
  'Resolved': 'समाधान',
  'Hospital': 'अस्पताल',
  'Protocol': 'प्रोटोकॉल',
  'None scheduled': 'कोई निर्धारित नहीं',
  'Enrolled': 'नामांकित',
  'Active': 'सक्रिय',
  'Completed': 'पूर्ण',

  // Table titles
  'My Inquiries & Hospital Communications': 'मेरी पूछताछ एवं अस्पताल संवाद',
  'My Protocol Visit Schedule': 'मेरा प्रोटोकॉल यात्रा कार्यक्रम',
  'Care Team & Emergency Contacts': 'देखभाल दल एवं आपातकालीन संपर्क',

  // Column headers
  'Category': 'श्रेणी',
  'Subject': 'विषय',
  'Status': 'स्थिति',
  'Submitted': 'जमा तिथि',
  'Hospital Admin Response': 'अस्पताल प्रशासन की प्रतिक्रिया',
  'Visit': 'यात्रा',
  'Scheduled Date': 'निर्धारित तिथि',
  'Clinical Notes': 'नैदानिक निर्देश',
  'Name': 'नाम',
  'Role': 'भूमिका',
  'Contact': 'संपर्क',

  // Statuses & categories
  'SUBMITTED': 'जमा किया गया',
  'IN_REVIEW': 'समीक्षाधीन',
  'RESOLVED': 'समाधान',
  'ESCALATED': 'अग्रेषित',
  'Scheduled': 'निर्धारित',
  'Symptom Inquiry': 'लक्षण / दुष्प्रभाव रिपोर्ट',
  'Appointment Reschedule': 'यात्रा पुनर्निर्धारण अनुरोध',
  'Medication Query': 'दवा / खुराक प्रश्न',
  'General Inquiry': 'सामान्य रसद पूछताछ',
  'Grievance': 'शिकायत / अधिकार',
  'Pending review by hospital admin': 'अस्पताल प्रशासन द्वारा समीक्षा लंबित',
  'Principal Investigator': 'प्रधान अन्वेषक (डॉक्टर)',
  'Study Coordinator': 'अध्ययन समन्वयक',
}

function translateValue(val) {
  if (typeof val === 'string' && HINDI_MAP[val]) return HINDI_MAP[val]
  return val
}

function translateDashboard(dashboard, isHi) {
  if (!isHi || !dashboard) return dashboard

  try {
    return {
      ...dashboard,
      title: 'रोगी पोर्टल (Patient Portal)',
      subtitle: 'मेरी नैदानिक परीक्षण समय सारणी, देखभाल दल और अस्पताल प्रशासन संवाद',
      tiles: (dashboard.tiles || []).map((tile) => ({
        ...tile,
        label: HINDI_MAP[tile.label] || tile.label,
        value: translateValue(tile.value),
        hint: translateValue(tile.hint),
      })),
      blocks: (dashboard.blocks || []).map((block) => {
        const newBlock = {
          ...block,
          title: HINDI_MAP[block.title] || block.title,
          note: block.note ? 'प्रोटोकॉल अनुपालन और सुरक्षा निगरानी' : undefined,
          empty: block.empty ? 'कोई डेटा उपलब्ध नहीं है।' : undefined,
        }
        if (Array.isArray(block.columns)) {
          newBlock.columns = block.columns.map((col) => {
            if (col && typeof col === 'object' && !Array.isArray(col)) {
              return {
                ...col,
                label: HINDI_MAP[col.label] || col.label,
              }
            }
            if (Array.isArray(col)) {
              return {
                key: col[0],
                label: HINDI_MAP[col[1]] || col[1],
              }
            }
            return col
          })
        }
        if (Array.isArray(block.rows)) {
          newBlock.rows = block.rows.map((row) => {
            if (!row || typeof row !== 'object') return row
            const newRow = { ...row }
            for (const k of Object.keys(newRow)) {
              newRow[k] = translateValue(newRow[k])
            }
            return newRow
          })
        }
        return newBlock
      }),
    }
  } catch (err) {
    console.error('Translation error:', err)
    return dashboard
  }
}

function ShieldCheckIcon({ className = 'w-6 h-6' }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
    </svg>
  )
}

function PenLineIcon({ className = 'w-4 h-4' }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
    </svg>
  )
}

function GlobeIcon({ className = 'w-3.5 h-3.5' }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418" />
    </svg>
  )
}

function FileTextIcon({ className = 'w-3.5 h-3.5' }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
    </svg>
  )
}

function CheckCircleIcon({ className = 'w-4 h-4' }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  )
}

function XIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  )
}

function ConsentModal({ infoSheet, onClose, onSuccess, initialLang = 'en' }) {
  const [lang, setLang] = useState(initialLang)
  const [signerName, setSignerName] = useState('')
  const [abhaId, setAbhaId] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [signatureData, setSignatureData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSign(e) {
    e.preventDefault()
    if (!signatureData) {
      setError(lang === 'hi' ? 'कृपया नीचे दिए गए बॉक्स में हस्ताक्षर करें।' : 'Please draw your digital signature below.')
      return
    }
    if (!agreed) {
      setError(lang === 'hi' ? 'कृपया सभी शर्तों की सहमति स्वीकार करें।' : 'Please check the consent agreement checkbox.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await signEConsent({
        signer_name: signerName,
        language: lang,
        abha_id: abhaId.trim() || null,
        signature_data_url: signatureData,
      })
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.detail || err.message)
    } finally {
      setBusy(false)
    }
  }

  const isHi = lang === 'hi'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="w-full max-w-2xl rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl border border-slate-200 dark:border-slate-800 my-8">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheckIcon className="w-6 h-6 text-aiia-600 dark:text-aiia-400" />
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                {isHi ? 'इलेक्ट्रॉनिक सूचित सहमति पत्र (e-Consent)' : 'Electronic Informed Consent (e-Consent)'}
              </h3>
              <p className="text-xs text-slate-500">
                {isHi ? 'एनडीसीटी नियम 2019 एवं 21 सीएफआर भाग 11 के तहत डिजिटल सत्यापन' : 'Verified under India NDCT Rules 2019 & 21 CFR Part 11'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-aiia-50 text-aiia-700 border border-aiia-200 hover:bg-aiia-100 transition"
            >
              <GlobeIcon className="w-3.5 h-3.5" />
              {isHi ? 'English' : 'हिन्दी'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <XIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-3 rounded-lg bg-red-50 dark:bg-red-950/30 p-3 text-xs text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800">
            {error}
          </div>
        )}

        <form onSubmit={handleSign} className="mt-4 space-y-4">
          {/* Protocol Summary Card */}
          <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-4 border border-slate-200/80 dark:border-slate-700 text-xs space-y-2.5 max-h-56 overflow-y-auto">
            <div className="font-semibold text-slate-900 dark:text-slate-100">
              {isHi ? infoSheet.trial_title_hi : infoSheet.trial_title_en}
            </div>
            <div className="text-slate-600 dark:text-slate-300">
              <span className="font-semibold">{isHi ? 'अध्ययन अवधि:' : 'Study Duration:'} </span>
              {infoSheet.duration}
            </div>
            <div className="text-slate-600 dark:text-slate-300">
              <span className="font-semibold">{isHi ? 'दवा खुराक (Posology):' : 'Investigational Product:'} </span>
              {infoSheet.investigation_product}
            </div>
            <div className="pt-1 border-t border-slate-200 dark:border-slate-700">
              <div className="font-semibold text-slate-800 dark:text-slate-200 mb-1">
                {isHi ? 'प्रमुख अधिकार एवं शर्तें:' : 'Participant Rights & Clinical Safeguards:'}
              </div>
              <ul className="list-disc pl-4 space-y-1 text-slate-600 dark:text-slate-400">
                {(isHi ? infoSheet.key_points_hi : infoSheet.key_points_en).map((pt, idx) => (
                  <li key={idx}>{pt}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Form fields */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                {isHi ? 'प्रतिभागी का पूरा कानूनी नाम' : 'Participant Legal Full Name'} *
              </label>
              <input
                type="text"
                required
                value={signerName}
                onChange={(e) => setSignerName(e.target.value)}
                placeholder={isHi ? 'उदा. आरव शर्मा' : 'e.g. Aarav Sharma'}
                className="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 p-2.5 text-xs text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-aiia-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center justify-between">
                <span>{isHi ? 'आभा आईडी (ABHA ID)' : 'ABHA ID (Ayushman Bharat)'}</span>
                <span className="text-[10px] text-slate-400 font-normal">{isHi ? '(वैकल्पिक)' : '(Optional)'}</span>
              </label>
              <input
                type="text"
                value={abhaId}
                onChange={(e) => setAbhaId(e.target.value)}
                placeholder="14-XXXX-XXXX-XXXX"
                className="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 p-2.5 text-xs text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-aiia-500"
              />
            </div>
          </div>

          {/* Signature Canvas */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1.5">
              <PenLineIcon className="w-3.5 h-3.5 text-aiia-600" />
              {isHi ? 'डिजिटल हस्ताक्षर पैड (उंगली या माउस से साइन करें)' : 'Digital Signature Pad (Draw with finger or mouse)'} *
            </label>
            <SignaturePad onSign={setSignatureData} onClear={() => setSignatureData(null)} />
          </div>

          {/* Agreement Checkbox */}
          <label className="flex items-start gap-2.5 rounded-lg border border-slate-200 dark:border-slate-700 p-3 bg-slate-50/60 dark:bg-slate-800/40 cursor-pointer">
            <input
              type="checkbox"
              required
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-aiia-600 focus:ring-aiia-500"
            />
            <span className="text-xs text-slate-600 dark:text-slate-300 leading-snug">
              {isHi
                ? 'मैं प्रमाणित करता/करती हूँ कि मैंने उपरोक्त अध्ययन जानकारी पत्रक को पढ़ व समझ लिया है और स्वेच्छा से इस नैदानिक परीक्षण में भाग लेने की सहमति देता/देती हूँ।'
                : 'I confirm that I have read and understood the study information sheet, and I voluntarily consent to participate in this clinical trial under NDCT Rules 2019.'}
            </span>
          </label>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 dark:border-slate-700 px-4 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              {isHi ? 'रद्द करें' : 'Cancel'}
            </button>
            <button
              type="submit"
              disabled={busy || !signatureData || !agreed || !signerName}
              className="inline-flex items-center gap-1.5 rounded-lg bg-aiia-600 px-5 py-2 text-xs font-semibold text-white shadow hover:bg-aiia-700 disabled:opacity-50 transition"
            >
              <CheckCircleIcon className="w-4 h-4" />
              {busy ? (isHi ? 'सत्यापित किया जा रहा है...' : 'Verifying...') : isHi ? 'ई-सहमति जमा करें' : 'Submit Digital Consent'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function CertificateModal({ consent, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl border-2 border-emerald-500/40 relative">
        <div className="text-center pb-4 border-b border-slate-100 dark:border-slate-800">
          <div className="mx-auto w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950 flex items-center justify-center text-emerald-600 mb-2">
            <ShieldCheckIcon className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-slate-900 dark:text-white">
            Digital e-Consent Verification Certificate
          </h3>
          <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
            Legally Binding under India NDCT Rules 2019 & 21 CFR Part 11
          </p>
        </div>

        <div className="mt-4 space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-2 bg-slate-50 dark:bg-slate-800/70 p-3 rounded-lg">
            <div>
              <span className="text-slate-400 block text-[10px]">PARTICIPANT CODE</span>
              <span className="font-semibold text-slate-800 dark:text-slate-200">{consent.subject_code}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px]">SIGNER NAME</span>
              <span className="font-semibold text-slate-800 dark:text-slate-200">{consent.signer_name}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px]">INSTITUTION</span>
              <span className="font-semibold text-slate-800 dark:text-slate-200">{consent.site_name}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px]">ABHA ID</span>
              <span className="font-semibold text-slate-800 dark:text-slate-200">{consent.abha_id || 'Not Linked'}</span>
            </div>
            <div className="col-span-2">
              <span className="text-slate-400 block text-[10px]">TIMESTAMP (UTC)</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">{consent.signed_at}</span>
            </div>
          </div>

          <div className="rounded-lg border border-blue-200 bg-blue-50/70 p-2.5 dark:border-blue-900 dark:bg-blue-950/40">
            <span className="text-[10px] font-semibold text-blue-900 dark:text-blue-300 block mb-0.5">
              21 CFR PART 11 & GCP-ASU SIGNATURE ATTESTATION
            </span>
            <p className="text-[11px] italic text-blue-800 dark:text-blue-200">
              "{consent.meaning_of_signature || 'I confirm my informed voluntary consent to participate in protocol AIIA-ASH-2026-01 under GCP-ASU and ICMR ethical guidelines.'}"
            </p>
          </div>

          <div>
            <span className="text-slate-400 block text-[10px] mb-1">DIGITAL SIGNATURE CAPTURE</span>
            <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-2 bg-white flex justify-center h-20 items-center">
              <img src={consent.signature_data_url} alt="Signature" className="max-h-16 object-contain" />
            </div>
          </div>

          <div className="bg-slate-100 dark:bg-slate-800 p-2.5 rounded-lg font-mono text-[11px] break-all">
            <span className="text-slate-400 block text-[9px] font-sans">SHA-256 CRYPTOGRAPHIC INTEGRITY HASH</span>
            <span className="text-slate-700 dark:text-slate-300">{consent.sha256_hash}</span>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <a
              href={`/api/econsent/subjects/${consent.subject_id}/fhir`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            >
              📄 HL7 FHIR R4 JSON
            </a>
            <a
              href={`/api/econsent/subjects/${consent.subject_id}/abdm-artefact`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-medium text-indigo-700 hover:bg-indigo-100 dark:border-indigo-900 dark:bg-indigo-950 dark:text-indigo-300"
            >
              🇮🇳 ABDM Consent Artefact
            </a>
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 text-xs font-semibold hover:opacity-90 transition"
          >
            Close Certificate
          </button>
        </div>
      </div>
    </div>
  )
}

function SubmitRequestModal({ onClose, onSuccess, isHi = false }) {
  const [category, setCategory] = useState('symptom_inquiry')
  const [subjectLine, setSubjectLine] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await createPatientRequest({
        category,
        subject_line: subjectLine,
        message,
      })
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.detail || err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white dark:bg-slate-900 p-6 shadow-xl border border-slate-200 dark:border-slate-800">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white">
          {isHi ? 'अस्पताल प्रशासन एवं देखभाल दल से संपर्क करें' : 'Contact Hospital Administration & Care Team'}
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          {isHi
            ? 'अपनी पूछताछ, लक्षण रिपोर्ट या यात्रा पुनर्निर्धारण अनुरोध सीधे अपने समन्वयक को भेजें।'
            : 'Submit an inquiry, symptom report, or reschedule request directly to your trial coordinator and hospital administration.'}
        </p>

        {error && (
          <div className="mt-3 rounded-lg bg-red-50 dark:bg-red-950/30 p-3 text-xs text-red-700 dark:text-red-400">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              {isHi ? 'पूछताछ श्रेणी' : 'Inquiry Category'}
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-2.5 text-sm text-slate-800 dark:text-slate-200 outline-none focus:border-aiia-500"
            >
              <option value="symptom_inquiry">{isHi ? 'लक्षण / दुष्प्रभाव रिपोर्ट' : 'Symptom / Side-effect Report'}</option>
              <option value="appointment_reschedule">{isHi ? 'यात्रा पुनर्निर्धारण अनुरोध' : 'Visit Reschedule Request'}</option>
              <option value="medication_query">{isHi ? 'दवा / खुराक प्रश्न' : 'Medication / Posology Question'}</option>
              <option value="general_inquiry">{isHi ? 'सामान्य परीक्षण रसद' : 'General Trial Logistics'}</option>
              <option value="grievance">{isHi ? 'शिकायत / अधिकार चिंता' : 'Grievance / Patient Rights Concern'}</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              {isHi ? 'विषय' : 'Subject'}
            </label>
            <input
              type="text"
              required
              value={subjectLine}
              onChange={(e) => setSubjectLine(e.target.value)}
              placeholder={isHi ? 'अपने प्रश्न या अनुरोध का संक्षिप्त सारांश' : 'Brief summary of your question or request'}
              className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-2.5 text-sm text-slate-800 dark:text-slate-200 outline-none focus:border-aiia-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              {isHi ? 'विस्तृत संदेश' : 'Detailed Message'}
            </label>
            <textarea
              required
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={isHi ? 'अपने प्रश्न, लक्षण विवरण या पसंदीदा नई तिथि का वर्णन करें...' : 'Describe your question, symptom details, or preferred reschedule dates...'}
              className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-2.5 text-sm text-slate-800 dark:text-slate-200 outline-none focus:border-aiia-500 focus:ring-1 focus:ring-aiia-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-200 dark:border-slate-700 px-4 py-2 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              {isHi ? 'रद्द करें' : 'Cancel'}
            </button>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-aiia-600 px-4 py-2 text-xs font-medium text-white hover:bg-aiia-700 disabled:opacity-50"
            >
              {busy ? (isHi ? 'भेजा जा रहा है…' : 'Sending…') : isHi ? 'अनुरोध भेजें' : 'Submit Request'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Patient(props) {
  const [openRequestModal, setOpenRequestModal] = useState(false)
  const [openConsentModal, setOpenConsentModal] = useState(false)
  const [openCertModal, setOpenCertModal] = useState(false)
  const [consentData, setConsentData] = useState(null)
  const [portalLang, setPortalLang] = useState('en')

  async function loadConsent() {
    try {
      const res = await getMyEConsent()
      setConsentData(res)
    } catch {
      // Non-blocking
    }
  }

  useEffect(() => {
    loadConsent()
  }, [])

  const isHi = portalLang === 'hi'
  const isConsented = consentData?.has_signed

  // Seamlessly translate the dashboard object (tiles, tables, headers, notes) when Hindi is selected
  const displayDashboard = translateDashboard(props.dashboard, isHi)

  return (
    <div>
      {/* Top Banner: Bilingual & e-Consent Status Bar */}
      <div className="mb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3 rounded-2xl border border-slate-200 dark:border-slate-800 bg-gradient-to-r from-slate-900 to-slate-800 p-4 text-white shadow-md">
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-xl ${isConsented ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-300'}`}>
            {isConsented ? <ShieldCheckIcon className="w-6 h-6" /> : <PenLineIcon className="w-6 h-6" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold">
                {isHi ? 'डिजिटल सूचित सहमति (e-Consent)' : 'Digital Informed Consent (e-Consent)'}
              </h3>
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${isConsented ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'}`}>
                {isConsented ? (isHi ? 'सत्यापित एवं हस्ताक्षरित ✓' : 'Verified & Signed ✓') : (isHi ? 'हस्ताक्षर लंबित ⏳' : 'Signature Pending ⏳')}
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-0.5">
              {isConsented
                ? (isHi ? `हस्ताक्षरकर्ता: ${consentData.consent?.signer_name} • एनडीसीटी नियम 2019 प्रमाणित` : `Signed by: ${consentData.consent?.signer_name} • Sealed under NDCT Rules 2019`)
                : (isHi ? 'कृपया परीक्षण में भागीदारी जारी रखने हेतु डिजिटल सहमति पत्र पर हस्ताक्षर करें।' : 'Please review the protocol information sheet and sign before study visits.')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          {isConsented ? (
            <button
              onClick={() => setOpenCertModal(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/40 border border-emerald-500/50 px-3.5 py-1.5 text-xs font-semibold text-emerald-200 transition"
            >
              <FileTextIcon className="w-3.5 h-3.5" />
              {isHi ? 'प्रमाणपत्र देखें' : 'View Certificate'}
            </button>
          ) : (
            <button
              onClick={() => setOpenConsentModal(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-aiia-500 hover:bg-aiia-600 px-4 py-2 text-xs font-bold text-white shadow-md transition animate-pulse"
            >
              <PenLineIcon className="w-3.5 h-3.5" />
              {isHi ? 'डिजिटल हस्ताक्षर करें' : 'Sign Digital Consent'}
            </button>
          )}

          {/* Bilingual Language Switcher */}
          <button
            onClick={() => setPortalLang(portalLang === 'en' ? 'hi' : 'en')}
            className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 hover:bg-white/20 border border-white/20 px-3 py-1.5 text-xs font-semibold text-white transition"
          >
            <GlobeIcon className="w-3.5 h-3.5" />
            {isHi ? 'English' : 'हिन्दी'}
          </button>
        </div>
      </div>

      <DashboardLayout
        {...props}
        dashboard={displayDashboard}
        wide={['my_requests', 'my_schedule']}
        note={isHi ? 'प्रतिभागी पोर्टल: अपनी निर्धारित यात्राओं को ट्रैक करें और अस्पताल प्रशासन से सीधे संपर्क करें।' : 'Participant Portal: Track your scheduled appointments, consult your research team, and message the hospital administration directly.'}
      />

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h4 className="text-sm font-semibold text-slate-900">
              {isHi ? 'कोई प्रश्न या लक्षण है?' : 'Need assistance or experiencing a symptom?'}
            </h4>
            <p className="text-xs text-slate-500">
              {isHi ? 'अपने संस्थान के व्यवस्थापक और अनुसंधान दल को सुरक्षित संदेश भेजें।' : 'Send a secure message directly to your Institution Administrator and Lead Clinical Team.'}
            </p>
          </div>
          <button
            onClick={() => setOpenRequestModal(true)}
            className="inline-flex items-center justify-center rounded-lg bg-aiia-600 px-4 py-2 text-xs font-medium text-white shadow-sm hover:bg-aiia-700 transition"
          >
            + {isHi ? 'अस्पताल प्रशासन से संपर्क करें' : 'Contact Hospital Admin'}
          </button>
        </div>
      </div>

      {openRequestModal && (
        <SubmitRequestModal
          onClose={() => setOpenRequestModal(false)}
          onSuccess={props.onRefresh}
          isHi={isHi}
        />
      )}

      {openConsentModal && consentData?.info_sheet && (
        <ConsentModal
          infoSheet={consentData.info_sheet}
          initialLang={portalLang}
          onClose={() => setOpenConsentModal(false)}
          onSuccess={() => {
            loadConsent()
            props.onRefresh?.()
          }}
        />
      )}

      {openCertModal && consentData?.consent && (
        <CertificateModal
          consent={consentData.consent}
          onClose={() => setOpenCertModal(false)}
        />
      )}
    </div>
  )
}
