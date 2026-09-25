import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { api } from '../../lib/api'
import { useSession } from '../../lib/auth'
import { useWebSocket } from '../../lib/ws'
import { ComingSoon } from './ComingSoon'
import { LaunchVideo } from './LaunchVideo'

interface LaunchStatus {
  ok: boolean
  launch_at: number | null
  now: number
  live: boolean
}

const VIDEO_SEEN = 'paula5-launch-video-seen'

function videoSeen() {
  try {
    return localStorage.getItem(VIDEO_SEEN) === '1'
  } catch {
    return true
  }
}

/** Coming-soon page until the launch time (the server decides), then the
 *  launch video once per device, then the app. */
export function LaunchGate({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const { user } = useSession()
  const [preview, setPreview] = useState(false)
  const [sawGate, setSawGate] = useState(false)
  const [videoDone, setVideoDone] = useState(false)

  const q = useQuery({
    queryKey: ['launch'],
    queryFn: () => api.get<LaunchStatus>('/api/launch'),
    refetchInterval: 30_000,
    staleTime: 5_000,
  })
  useWebSocket((e) => {
    if (e.event === 'launch') void qc.invalidateQueries({ queryKey: ['launch'] })
  })

  const status = q.data
  // dataUpdatedAt is this device's clock when the answer arrived.
  const skew = status ? status.now * 1000 - q.dataUpdatedAt : 0

  // At zero, ask the server (it holds the real clock) instead of trusting ours.
  useEffect(() => {
    if (!status || status.live || !status.launch_at) return
    const ms = status.launch_at * 1000 - (Date.now() + skew)
    const id = setTimeout(() => void qc.invalidateQueries({ queryKey: ['launch'] }), Math.max(0, ms) + 400)
    return () => clearTimeout(id)
  }, [status, skew, qc])

  const gated = !!status && !status.live && !(preview && user?.is_admin)
  if (gated && !sawGate) setSawGate(true)

  // Launch video: for anyone who watched the countdown, and once for
  // everyone else arriving after launch.
  const playVideo = !!status?.live && !videoDone && (sawGate || !videoSeen())

  if (!status) return q.isError ? <>{children}</> : null
  if (gated && status.launch_at) {
    return (
      <ComingSoon
        launchAt={status.launch_at}
        skew={skew}
        onChanged={() => void qc.invalidateQueries({ queryKey: ['launch'] })}
        onPreview={() => setPreview(true)}
      />
    )
  }
  if (playVideo) {
    return (
      <LaunchVideo
        onDone={() => {
          try {
            localStorage.setItem(VIDEO_SEEN, '1')
          } catch {
            /* ignore */
          }
          setVideoDone(true)
        }}
      />
    )
  }
  return <>{children}</>
}
