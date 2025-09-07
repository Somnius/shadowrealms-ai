/**
 * PostCSS Configuration for ShadowRealms AI Frontend
 * 
 * PostCSS is a tool for transforming CSS with JavaScript plugins.
 * This configuration tells PostCSS which plugins to use when processing our CSS.
 * 
 * WHAT THIS CONFIGURATION DOES:
 * 1. Processes Tailwind CSS directives (@tailwind, @apply, etc.)
 * 2. Adds vendor prefixes to CSS properties for better browser compatibility
 * 3. Transforms our CSS before it's sent to the browser
 * 
 * PLUGINS USED:
 * - tailwindcss: Processes Tailwind CSS classes and directives
 * - autoprefixer: Automatically adds vendor prefixes (like -webkit-, -moz-, etc.)
 */

module.exports = {
  plugins: {
    // Tailwind CSS plugin - processes @tailwind directives and utility classes
    // This converts Tailwind's utility classes into actual CSS
    tailwindcss: {},
    
    // Autoprefixer plugin - adds vendor prefixes for better browser support
    // For example: 'display: flex' becomes 'display: -webkit-box; display: -ms-flexbox; display: flex'
    autoprefixer: {},
  },
}
