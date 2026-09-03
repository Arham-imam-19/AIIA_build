// Sponsor: funds and oversees the study with strict oversight-only permissions.
// The Sponsor never touches or mutates patient data, ensuring independence and ALCOA+ compliance.

import { useState } from 'react'
import DashboardLayout from './layout'
import AnalyticsCharts from './AnalyticsCharts'
import RegulatoryMilestonesPanel from '../components/RegulatoryMilestonesPanel'
import SaeRegulatoryClockQueue from '../components/SaeRegulatoryClockQueue'
import InstituteDrilldownModal from '../components/InstituteDrilldownModal'
import AuditTrailModal from '../components/AuditTrailModal'

export default function Sponsor(props) {
  const [selectedSiteId, setSelectedSiteId] = useState(null)
  const [showAuditModal, setShowAuditModal] = useState(false)
  const [auditScopeSiteId, setAuditScopeSiteId] = useState(null)
  const [consentPct, setConsentPct] = useState(100)

  // Attach interactive onRowClick to the site_performance block in dashboard
  const enhancedDashboard = {
    ...props.dashboard,
    blocks: (props.dashboard?.blocks || []).map((block) => {
      if (block.key === 'site_performance') {
        return {
          ...block,
          note: 'Click any institute row to drill down into study breakdown, PIs, recruitment, and safety.',
          onRowClick: (row) => {
            if (row.site_id) setSelectedSiteId(row.site_id)
          },
        }
      }
      return block
    }),
  }

  const handleOpenAuditForSite = (siteId) => {
    setSelectedSiteId(null)
    setAuditScopeSiteId(siteId)
    setShowAuditModal(true)
  }

  const handleOpenPortfolioAudit = () => {
    setAuditScopeSiteId(null)
    setShowAuditModal(true)
  }

  return (
    <div className="space-y-6">
      {/* Sponsor Governance & Inspection Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50/80 px-5 py-3 text-xs text-blue-950 shadow-sm">
        <div className="flex items-center gap-2 font-medium">
          <span className="flex h-2.5 w-2.5 rounded-full bg-blue-600 animate-pulse"></span>
          <span>🔒 DPDP Act 2023 & ICH E6 GCP: Blinded Sponsor Executive Oversight Mode</span>
          <span className="text-blue-700 hidden md:inline">
            (Participant PII is masked; system is strictly read-only)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleOpenPortfolioAudit}
            className="inline-flex items-center gap-1.5 rounded-lg border border-blue-300 bg-white px-3 py-1.5 text-xs font-semibold text-blue-900 shadow-sm hover:bg-blue-100 transition"
          >
            <span>📜</span>
            <span>View Inspection Audit Trail</span>
          </button>
        </div>
      </div>

      {/* 1. Regulatory & Ethics Milestone Panel */}
      <RegulatoryMilestonesPanel consentPct={consentPct} />

      {/* 2. Open SAE Statutory 24-Hour Reporting Clock Queue */}
      <SaeRegulatoryClockQueue />

      {/* 3. Live Recruitment Trajectory & Safety Distribution Charts */}
      <AnalyticsCharts
        onSelectSite={(siteId) => setSelectedSiteId(siteId)}
        onConsentRateLoaded={(pct) => setConsentPct(pct)}
      />

      {/* 4. Core Portfolio Summary & Site Performance Table */}
      <DashboardLayout
        {...props}
        dashboard={enhancedDashboard}
        wide={['site_performance']}
        note="Every site, all sites. A Sponsor cannot enter or edit trial data: a monitor who could change the numbers would undermine the numbers. Numbers update automatically from the live clinical database."
      />

      {/* Modals */}
      {selectedSiteId && (
        <InstituteDrilldownModal
          siteId={selectedSiteId}
          onClose={() => setSelectedSiteId(null)}
          onOpenAudit={handleOpenAuditForSite}
        />
      )}

      {showAuditModal && (
        <AuditTrailModal
          scopeSiteId={auditScopeSiteId}
          onClose={() => {
            setShowAuditModal(false)
            setAuditScopeSiteId(null)
          }}
        />
      )}
    </div>
  )
}
