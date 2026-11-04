import { createClient } from '@supabase/supabase-js'

/*
 * Supabase Auth — REAL user accounts.
 * The publishable key is public by design (it only grants the anonymous
 * API role; security comes from the per-user JWTs Supabase issues).
 */
export const SUPABASE_URL = 'https://trqtuxsxajdquoyanfjr.supabase.co'
export const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_AhicOJJRac4k3fqqEfJ2tA_SHljWL69'

export const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)

// Demo accounts live in the app's local database (for the seeded demo data).
// They are NOT Supabase accounts — so manual/demo logins for these fall back
// to the local endpoint. Every other email is a real Supabase account.
export const DEMO_ACCOUNTS = [
  'admin@civic.demo',
  'citizen1@civic.demo',
  'citizen2@civic.demo',
  'team1@civic.demo',
  'team2@civic.demo',
  'team3@civic.demo',
  'team4@civic.demo',
  'team5@civic.demo',
  'team6@civic.demo',
  'team7@civic.demo',
  'team8@civic.demo',
]

export function isDemoEmail(email) {
  return DEMO_ACCOUNTS.includes((email || '').trim().toLowerCase())
}
