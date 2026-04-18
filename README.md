# IndianLunchBox
IndianLunchBox can feel like a mix of nostalgia + modern social platform (kind of like a cultural version of Instagram + Pinterest but focused on Indian food).

## Supabase JavaScript fix (redeclaration error)
If you hit this browser error:

`Uncaught SyntaxError: redeclaration of non-configurable global property supabase`

it means the page is declaring a top-level `supabase` variable more than once (for example with `const supabase = ...` in multiple scripts).

### Correct pattern used in this project
1. Load the Supabase SDK only once.
2. Use `window.getSupabaseClient(url, anonKey)` (from `static/js/supabase-client.js`) instead of declaring `const supabase` globally.
3. Reuse the same singleton client instance.

Example:

```html
<script>
  const SUPABASE_URL = 'https://YOUR_PROJECT.supabase.co';
  const SUPABASE_ANON_KEY = 'YOUR_ANON_KEY';
  const client = window.getSupabaseClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  // use client.from(...)
</script>
```
