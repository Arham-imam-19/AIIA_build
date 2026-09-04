// The live dashboard: one WebSocket, one dashboard object, kept current.
//
// A **WebSocket** is a phone line the browser holds open. Ordinary HTTP is a
// letter - the browser has to ask before it hears anything - which is why "live"
// dashboards usually end up asking every few seconds whether anything changed.
// Here the server speaks first, the moment somebody enrols a participant.
//
// The server sends the whole dashboard every time, not a description of what
// changed. That is deliberate: a patch has to be applied to whatever the browser
// already had, and one missed message leaves the numbers quietly wrong.

import { useCallback, useEffect, useRef, useState } from 'react'
import { api, liveUrl } from './api'

// Reconnect backoff, in milliseconds. Grows so a backend that is down does not
// get hammered, caps so a laptop waking from sleep reconnects promptly.
const RETRY_MS = [500, 1000, 2000, 4000, 8000]

export function useLiveDashboard(token, { onExpired } = {}) {
  const [dashboard, setDashboard] = useState(null)
  // 'connecting' | 'live' | 'reconnecting' | 'refused'
  const [status, setStatus] = useState('connecting')
  const [error, setError] = useState(null)
  // The most recent thing that happened, for the "what just changed" line.
  const [lastEvent, setLastEvent] = useState(null)
  const [updatedAt, setUpdatedAt] = useState(null)

  const socketRef = useRef(null)
  const attemptRef = useRef(0)
  const timerRef = useRef(null)
  const closedByUs = useRef(false)

  const connect = useCallback(() => {
    if (!token) return
    const ws = new WebSocket(liveUrl(token))
    socketRef.current = ws

    ws.onopen = () => {
      attemptRef.current = 0
    }

    ws.onmessage = (raw) => {
      const msg = JSON.parse(raw.data)
      if (msg.type === 'error') {
        // The server accepted the socket only to explain why it will not serve
        // us - almost always an expired token.
        setStatus('refused')
        setError(msg.detail)
        closedByUs.current = true
        if (/token/i.test(msg.detail || '') && onExpired) onExpired()
        return
      }
      if (msg.type === 'hello') {
        setStatus('live')
        setError(null)
        return
      }
      if (msg.type === 'ping') return
      if (msg.type === 'snapshot') {
        setDashboard(msg.dashboard)
        setUpdatedAt(msg.at)
        setStatus('live')
        // 'connected' is the first paint, not news. Only a real event is worth
        // announcing on screen.
        if (msg.reason === 'event' && msg.event) setLastEvent({ ...msg.event, at: msg.at })
      }
    }

    ws.onclose = () => {
      if (closedByUs.current) return
      const wait = RETRY_MS[Math.min(attemptRef.current, RETRY_MS.length - 1)]
      attemptRef.current += 1
      setStatus('reconnecting')
      timerRef.current = setTimeout(connect, wait)
    }

    // onerror always arrives with an onclose right behind it, so the reconnect
    // is handled there and there is nothing to do here.
    ws.onerror = () => {}
  }, [token, onExpired])

  useEffect(() => {
    closedByUs.current = false
    if (token) {
      api('/api/dashboard', { token })
        .then((data) => {
          if (data && !data.detail) {
            setDashboard(data)
            setStatus('live')
            setError(null)
          }
        })
        .catch(() => {})
    }
    connect()
    return () => {
      closedByUs.current = true
      clearTimeout(timerRef.current)
      socketRef.current?.close()
    }
  }, [connect, token])

  // Ask for the numbers again. Anything sent up the socket means "resend", which
  // keeps the refresh button on the same code path as a live update.
  const refresh = useCallback(() => {
    const ws = socketRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('refresh')
    } else if (token) {
      api('/api/dashboard', { token }).then((data) => {
        if (data && !data.detail) setDashboard(data)
      })
    }
  }, [token])

  return { dashboard, status, error, lastEvent, updatedAt, refresh }
}
