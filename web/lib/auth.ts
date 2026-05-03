import type { NextAuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.username || !credentials?.password) return null

        // Try the backend API first
        try {
          const res = await fetch(`${API_URL}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: credentials.username,
              password: credentials.password,
            }),
            signal: AbortSignal.timeout(3000),
          })

          if (res.ok) {
            const data = await res.json() as { access_token: string }
            return {
              id: credentials.username,
              email: credentials.username,
              name: credentials.username,
              accessToken: data.access_token,
            }
          }
        } catch {
          // Backend not available — fall through to local credentials
        }

        // Local fallback: env-configured credentials (works without Docker)
        const localUser = process.env.LOCAL_USERNAME ?? 'admin'
        const localPass = process.env.LOCAL_PASSWORD ?? 'pead'
        if (credentials.username === localUser && credentials.password === localPass) {
          return { id: localUser, email: `${localUser}@pead.local`, name: localUser }
        }

        return null
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = (user as { accessToken?: string }).accessToken
      }
      return token
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string
      return session
    },
  },
  pages: {
    signIn: '/login',
  },
  session: {
    strategy: 'jwt',
    maxAge: 24 * 60 * 60, // 24 hours
  },
  secret: process.env.NEXTAUTH_SECRET,
}
