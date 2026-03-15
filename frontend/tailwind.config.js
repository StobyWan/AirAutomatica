/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        card: 'var(--card)',
        muted: 'var(--muted)',
        connected: 'var(--connected)',
        stale: 'var(--stale)',
        disconnected: 'var(--disconnected)',
        backoff: 'var(--backoff)',
        connecting: 'var(--connecting)',
        starting: 'var(--starting)',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
