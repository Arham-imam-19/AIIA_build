import React, { useState, useEffect } from 'react'
import { fetchSponsorAnalytics } from '../api'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

export default function AnalyticsCharts({ onSelectSite, onConsentRateLoaded }) {
  const [enrollmentData, setEnrollmentData] = useState([])
  const [safetyData, setSafetyData] = useState([])
  const [deltas, setDeltas] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)
        const res = await fetchSponsorAnalytics()
        setEnrollmentData(res.enrollment_curve || [])
        setSafetyData(res.safety_distribution || [])
        setDeltas(res.deltas || null)
        if (res.consent_compliance_pct !== undefined && onConsentRateLoaded) {
          onConsentRateLoaded(res.consent_compliance_pct)
        }
      } catch (err) {
        console.error('Failed to load live sponsor analytics:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-xs text-slate-500">
        Querying live clinical enrollment and safety datasets...
      </div>
    )
  }

  const handleBarClick = (entry) => {
    if (entry && entry.site_id && onSelectSite) {
      onSelectSite(entry.site_id)
    }
  }

  return (
    <div className="space-y-4">
      {/* Live Trend Overview Banner */}
      {deltas && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-3 text-xs shadow-sm">
          <span className="font-semibold text-slate-700 flex items-center gap-1.5">
            <span>📈</span>
            <span>Portfolio Activity (Past 7 Days):</span>
          </span>
          <div className="flex flex-wrap items-center gap-4">
            <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-1 font-medium text-blue-700">
              <span>Enrolled:</span>
              <span className="font-bold">+{deltas.enrolled_this_week || 0}</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 font-medium text-emerald-700">
              <span>Screened:</span>
              <span className="font-bold">+{deltas.screened_this_week || 0}</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-1 font-medium text-amber-700">
              <span>New AEs:</span>
              <span className="font-bold">+{deltas.aes_this_week || 0}</span>
            </span>
            <span className="text-[11px] text-slate-400 font-mono">
              Live SQL Database Aggregations
            </span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Patient Enrollment Curve */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm flex flex-col">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Patient Enrollment Trajectory
              </h3>
              <p className="text-xs text-slate-500">
                Live recruitment curve derived from subject database records
              </p>
            </div>
            <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-600">
              Actual vs Target
            </span>
          </div>
          <div className="flex-1 w-full" style={{ minHeight: '260px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={enrollmentData}
                margin={{ top: 5, right: 20, left: -20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    fontSize: '12px',
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Line
                  type="monotone"
                  dataKey="Total"
                  name="Cumulative Enrolled"
                  stroke="#0284c7"
                  strokeWidth={3}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
                <Line
                  type="monotone"
                  dataKey="New"
                  name="New This Month"
                  stroke="#94a3b8"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Safety Distribution across Participating Sites */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm flex flex-col">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Adverse Event Distribution Across Sites
              </h3>
              <p className="text-xs text-slate-500">
                Click any site bar to drill down into institute studies
              </p>
            </div>
            <span className="rounded bg-amber-50 border border-amber-200 px-2 py-0.5 font-mono text-[10px] font-medium text-amber-800">
              Interactive Drill-Down
            </span>
          </div>
          <div className="flex-1 w-full" style={{ minHeight: '260px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={safetyData}
                margin={{ top: 5, right: 20, left: -20, bottom: 5 }}
                onClick={(state) => {
                  if (state && state.activePayload && state.activePayload.length) {
                    handleBarClick(state.activePayload[0].payload)
                  }
                }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="site_code" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    fontSize: '12px',
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                  }}
                  cursor={{ fill: '#f8fafc' }}
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Bar dataKey="SAE" name="Serious (SAE)" stackId="a" fill="#ef4444" radius={[0, 0, 4, 4]} />
                <Bar dataKey="Severe" name="Severe (Non-SAE)" stackId="a" fill="#f59e0b" />
                <Bar dataKey="Mild" name="Mild / Moderate" stackId="a" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>
    </div>
  )
}
