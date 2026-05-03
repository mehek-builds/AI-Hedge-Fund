'use client'

import { useSession, signOut } from 'next-auth/react'
import { LogOut, User } from 'lucide-react'
import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'

function useConnectionStatus() {
  const [isLive, setIsLive] = useState(true)

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/health`, {
          signal: AbortSignal.timeout(3000),
        })
        setIsLive(res.ok)
      } catch {
        setIsLive(false)
      }
    }

    check()
    const interval = setInterval(check, 30_000)
    return () => clearInterval(interval)
  }, [])

  return isLive
}

export function TopNav() {
  const { data: session } = useSession()
  const isLive = useConnectionStatus()
  const [showUserMenu, setShowUserMenu] = useState(false)

  return (
    <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-4 flex-shrink-0">
      {/* Left: App name */}
      <div className="flex items-center gap-3">
        <h1 className="text-body font-semibold text-text-primary tracking-tight">PEAD System</h1>
        <span className="text-border text-sm">|</span>
        <span className="text-micro text-text-muted">Autonomous Trading Dashboard</span>
      </div>

      {/* Right: status + user */}
      <div className="flex items-center gap-4">
        {/* Connection status */}
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'w-2 h-2 rounded-full animate-pulse',
              isLive ? 'bg-positive' : 'bg-negative'
            )}
          />
          <span className={cn('text-micro font-medium', isLive ? 'text-positive' : 'text-negative')}>
            {isLive ? 'Live' : 'Offline'}
          </span>
        </div>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-border/50 transition-colors"
          >
            <User size={14} className="text-text-muted" />
            <span className="text-micro text-text-muted">
              {session?.user?.email ?? 'User'}
            </span>
          </button>

          {showUserMenu && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowUserMenu(false)}
              />
              <div className="absolute right-0 top-full mt-1 z-20 bg-surface border border-border rounded-lg shadow-xl min-w-[160px] py-1">
                <div className="px-3 py-2 border-b border-border">
                  <p className="text-micro text-text-muted">Signed in as</p>
                  <p className="text-table text-text-primary truncate font-medium">
                    {session?.user?.email ?? 'User'}
                  </p>
                </div>
                <button
                  onClick={() => signOut()}
                  className="flex items-center gap-2 w-full px-3 py-2 text-table text-text-muted hover:text-text-primary hover:bg-border/40 transition-colors"
                >
                  <LogOut size={14} />
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
