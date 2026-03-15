type LoginContext = {
  ip?: string
  city?: string
  region?: string
  country_name?: string
  latitude?: number | null
  longitude?: number | null
}

const IPAPI_URL = 'https://ipapi.co/json/'
const TIMEOUT_MS = 2500

export async function fetchLoginContext(): Promise<LoginContext | null> {
  const timeoutPromise = new Promise<null>((resolve) => {
    window.setTimeout(() => resolve(null), TIMEOUT_MS)
  })

  const requestPromise = fetch(IPAPI_URL, {
    headers: {
      Accept: 'application/json',
    },
  })
    .then(async (response) => {
      if (!response.ok) return null
      const data = await response.json()
      return {
        ip: typeof data.ip === 'string' ? data.ip : undefined,
        city: typeof data.city === 'string' ? data.city : undefined,
        region: typeof data.region === 'string' ? data.region : undefined,
        country_name: typeof data.country_name === 'string' ? data.country_name : undefined,
        latitude: typeof data.latitude === 'number' ? data.latitude : null,
        longitude: typeof data.longitude === 'number' ? data.longitude : null,
      } satisfies LoginContext
    })
    .catch(() => null)

  return Promise.race([requestPromise, timeoutPromise])
}

export type { LoginContext }
