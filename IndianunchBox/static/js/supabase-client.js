(function initSupabaseClientGlobal() {
  // Avoid redeclaring a non-configurable global like `const supabase = ...`.
  // Use `window.__indianLunchBoxSupabaseClient` as a stable, reusable singleton.
  window.getSupabaseClient = function getSupabaseClient(url, anonKey) {
    if (!url || !anonKey) {
      throw new Error('Supabase URL and anon key are required.');
    }

    if (!window.supabase || typeof window.supabase.createClient !== 'function') {
      throw new Error(
        'Supabase SDK not loaded. Include https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2 first.'
      );
    }

    if (!window.__indianLunchBoxSupabaseClient) {
      window.__indianLunchBoxSupabaseClient = window.supabase.createClient(url, anonKey);
    }

    return window.__indianLunchBoxSupabaseClient;
  };
})();
