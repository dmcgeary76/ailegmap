// Visit analytics via a self-hosted Umami (deploy/umami/). Loaded only when
// the build carries both variables, so `npm run dev` and any build without
// frontend/.env.production report nothing:
//
//   VITE_UMAMI_SRC          https://analytics.example.com/script.js
//   VITE_UMAMI_WEBSITE_ID   the site's id from the Umami dashboard
//
// Umami sets no cookies and stores no personal data; the script also honours
// the browser's Do Not Track setting. Events are a name plus a few words of
// context, nothing about the visitor.

const SRC = import.meta.env.VITE_UMAMI_SRC
const WEBSITE_ID = import.meta.env.VITE_UMAMI_WEBSITE_ID

export const ANALYTICS = Boolean(SRC && WEBSITE_ID)

export function loadAnalytics() {
  if (!ANALYTICS || document.querySelector('script[data-website-id]')) return
  const s = document.createElement('script')
  s.defer = true
  s.src = SRC
  s.dataset.websiteId = WEBSITE_ID
  s.dataset.doNotTrack = 'true'
  document.head.appendChild(s)
}

// track('state-open', { state: 'CA', layer: 'legislation' })
export function track(name, data) {
  if (!ANALYTICS) return
  try {
    window.umami?.track(name, data)
  } catch {
    // never let analytics break the map
  }
}
