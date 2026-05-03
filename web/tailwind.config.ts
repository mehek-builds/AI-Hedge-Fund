import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0D0D0D',
        surface: '#111111',
        border: '#222222',
        primary: '#3B82F6',
        positive: '#22C55E',
        negative: '#EF4444',
        warning: '#F59E0B',
        'text-primary': '#FFFFFF',
        'text-muted': '#6B7280',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        micro: '12px',
        table: '14px',
        body: '16px',
        'card-title': '20px',
        'page-header': '28px',
      },
    },
  },
  plugins: [],
}

export default config
