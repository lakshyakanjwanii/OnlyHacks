const { createClient } = require('@supabase/supabase-js');
const path = require('path');
const dotenv = require('dotenv');

// Load environment variables from the backend folder's .env file
const envPath = path.resolve(__dirname, '../../backend/.env'); 
dotenv.config({ path: envPath });

const supabaseUrl = process.env.SUPABASE_URL;
// Using the service key for admin rights on the ledger and anomalies
const supabaseKey = process.env.SUPABASE_SERVICE_KEY;

if (!supabaseUrl || !supabaseKey) {
  throw new Error("Missing Supabase URL or Key in backend/.env");
}

const supabase = createClient(supabaseUrl, supabaseKey);

module.exports = supabase;
