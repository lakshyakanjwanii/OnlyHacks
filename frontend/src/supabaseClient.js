/**
 * Supabase client singleton for the frontend.
 *
 * Reads credentials from Vite env vars — add these to your .env:
 *   VITE_SUPABASE_URL=https://your-project-ref.supabase.co
 *   VITE_SUPABASE_ANON_KEY=your-anon-public-key
 *
 * The anon key is safe to ship in the browser bundle — Supabase RLS
 * is the security layer; the anon key alone can't bypass it.
 */
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    "[supabaseClient] VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY is not set. " +
    "Auth features will not work. Add both vars to frontend/.env"
  );
}

export const supabase = createClient(
  supabaseUrl || "https://placeholder.supabase.co",
  supabaseAnonKey || "placeholder-anon-key"
);
