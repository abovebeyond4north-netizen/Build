/* postcss.config.cjs
   PostCSS configuration for verified-coding-loop-dashboard.

   Tailwind v4+ moved the PostCSS plugin to @tailwindcss/postcss.
   Install the new plugin and Tailwind + autoprefixer as devDependencies:

     npm install -D @tailwindcss/postcss tailwindcss autoprefixer

   Or with pnpm:
     pnpm add -D @tailwindcss/postcss tailwindcss autoprefixer

   This file replaces any previous use of `require('tailwindcss')` as a PostCSS
   plugin. If you have other PostCSS plugins (postcss-import, etc.) keep them
   in this list.
*/

module.exports = {
  plugins: [
    require('@tailwindcss/postcss'),
    require('autoprefixer'),
  ],
};
