import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('UI Runtime Error caught by ErrorBoundary:', error, errorInfo)
    this.setState({ errorInfo })
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-slate-100 p-6 text-slate-800">
          <div className="w-full max-w-lg border border-slate-300 bg-white p-6 shadow-xl">
            <div className="flex items-center gap-3 border-b border-slate-200 pb-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-red-100 text-red-600 font-bold">
                ⚠️
              </span>
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900">
                  Application View Encountered an Issue
                </h2>
                <p className="text-xs text-slate-500">
                  The clinical portal intercepted a runtime error and prevented data loss.
                </p>
              </div>
            </div>

            <div className="mt-4 rounded bg-slate-50 p-3 font-mono text-xs text-red-700 border border-slate-200 overflow-x-auto">
              {this.state.error?.toString() || 'Unknown runtime error'}
            </div>

            <div className="mt-5 flex items-center justify-end gap-3 pt-3 border-t border-slate-200">
              <button
                onClick={() => {
                  localStorage.removeItem('aiia_token')
                  window.location.href = '/'
                }}
                className="border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Log Out &amp; Return to Login
              </button>
              <button
                onClick={this.handleReset}
                className="border border-slate-900 bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-black"
              >
                Reload Dashboard
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
