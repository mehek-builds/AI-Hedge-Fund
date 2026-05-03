'use client'

import { useSession } from 'next-auth/react'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopNav } from '@/components/layout/TopNav'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'

export function AppShell({ children }: { children: React.ReactNode }) {
  const { status } = useSession()
  const router = useRouter()
  const pathname = usePathname()

  const isLoginPage = pathname === '/login'

  useEffect(() => {
    if (status === 'unauthenticated' && !isLoginPage) {
      router.push('/login')
    }
    if (status === 'authenticated' && isLoginPage) {
      router.push('/')
    }
  }, [status, isLoginPage, router])

  // Show spinner while session is loading (except on login page)
  if (status === 'loading' && !isLoginPage) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Login page: no shell, just render content
  if (isLoginPage) {
    return <>{children}</>
  }

  // Unauthenticated but not on login: render nothing while redirect fires
  if (status === 'unauthenticated') {
    return null
  }

  // Authenticated: full app shell
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-y-auto bg-background p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
