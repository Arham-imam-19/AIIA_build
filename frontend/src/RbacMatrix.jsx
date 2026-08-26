// Who can do what, straight from the same table the API enforces.
//
// **RBAC (role-based access control)** means permissions attach to the job, not
// the person - like a hotel keycard that opens the rooms your role is allowed
// into, however senior you happen to be.
//
// This grid is generated from `ROLE_PERMISSIONS` in the backend, so it cannot
// drift out of date the way a hand-written table in a README would. Readable
// without logging in, because it describes the system, not anybody's data.

import { useEffect, useState } from 'react'
import { rbacMatrix } from './api'

export default function RbacMatrix({ highlightRole }) {
  const [matrix, setMatrix] = useState(null)
  const [failed, setFailed] = useState(null)

  useEffect(() => {
    rbacMatrix()
      .then(setMatrix)
      .catch((err) => setFailed(err.detail))
  }, [])

  if (failed) return <p className="text-sm text-red-700">{failed}</p>
  if (!matrix) return <p className="text-sm text-slate-400">Loading…</p>

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-800">Who can access what</h2>
      <p className="mt-0.5 text-xs text-slate-400">{matrix.note}</p>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 bg-white pb-2 pr-4 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
                Permission
              </th>
              {matrix.roles.map((role) => (
                <th
                  key={role.key}
                  className={`px-2 pb-2 text-center align-bottom text-xs font-medium ${
                    role.key === highlightRole ? 'text-aiia-700' : 'text-slate-500'
                  }`}
                >
                  <div className="mx-auto max-w-[6.5rem] leading-tight">{role.label}</div>
                  <div className="mt-1 font-normal text-slate-400">{role.scope}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.permissions.map((permission) => (
              <tr key={permission.key} className="border-t border-slate-100">
                <td className="sticky left-0 bg-white py-2 pr-4 text-slate-700">
                  {permission.label}
                  <span className="ml-2 font-mono text-xs text-slate-300">
                    {permission.key}
                  </span>
                </td>
                {matrix.roles.map((role) => {
                  const granted = role.granted.includes(permission.key)
                  return (
                    <td
                      key={role.key}
                      className={`px-2 py-2 text-center ${
                        role.key === highlightRole ? 'bg-aiia-50/60' : ''
                      }`}
                    >
                      <span className={granted ? 'text-emerald-600' : 'text-slate-200'}>
                        {granted ? '●' : '○'}
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-4 border-t border-slate-100 pt-3 text-xs leading-relaxed text-slate-500">
        A filled circle is a granted permission. &ldquo;Own site only&rdquo; is a second,
        separate limit: a Principal Investigator has <code>subject:read</code>, but only
        for participants at their own hospital - asking for another site&rsquo;s record
        returns 403, and widening the filter in the URL returns nothing.
      </p>
    </section>
  )
}
