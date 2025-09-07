/**
 * Tailwind CSS Configuration for ShadowRealms AI Frontend
 * 
 * This file configures Tailwind CSS, a utility-first CSS framework.
 * It defines custom colors, fonts, animations, and other design tokens
 * that we use throughout our application.
 * 
 * WHAT THIS CONFIGURATION DOES:
 * 1. Defines custom color palettes for our dark fantasy theme
 * 2. Sets up custom fonts (Inter for UI, JetBrains Mono for code)
 * 3. Creates custom animations for smooth user interactions
 * 4. Tells Tailwind which files to scan for CSS classes
 * 5. Extends Tailwind's default theme with our custom values
 */

/** @type {import('tailwindcss').Config} */
module.exports = {
  // Tell Tailwind which files to scan for CSS classes
  // This ensures that only the classes we actually use are included in the final CSS
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",  // Scan all JS/TS files in src directory
  ],
  
  // Extend Tailwind's default theme with our custom values
  theme: {
    extend: {
      // Custom color palettes for our dark fantasy theme
      colors: {
        // Primary color palette - Deep blue/cyan tones
        // Used for main UI elements like buttons, links, and highlights
        primary: {
          50: '#f0f9ff',   // Lightest blue - for very light backgrounds
          100: '#e0f2fe',  // Very light blue - for subtle highlights
          200: '#bae6fd',  // Light blue - for hover states
          300: '#7dd3fc',  // Medium light blue - for secondary elements
          400: '#38bdf8',  // Medium blue - for accents
          500: '#0ea5e9',  // Base blue - primary color
          600: '#0284c7',  // Medium dark blue - for active states
          700: '#0369a1',  // Dark blue - for pressed states
          800: '#075985',  // Very dark blue - for dark themes
          900: '#0c4a6e',  // Darkest blue - for very dark themes
          950: '#082f49',  // Almost black blue - for extreme dark themes
        },
        
        // Secondary color palette - Gold/amber tones
        // Used for warnings, highlights, and secondary actions
        secondary: {
          50: '#fffbeb',   // Lightest gold - for very light backgrounds
          100: '#fef3c7',  // Very light gold - for subtle highlights
          200: '#fde68a',  // Light gold - for hover states
          300: '#fcd34d',  // Medium light gold - for secondary elements
          400: '#fbbf24',  // Medium gold - for accents
          500: '#f59e0b',  // Base gold - secondary color
          600: '#d97706',  // Medium dark gold - for active states
          700: '#b45309',  // Dark gold - for pressed states
          800: '#92400e',  // Very dark gold - for dark themes
          900: '#78350f',  // Darkest gold - for very dark themes
          950: '#451a03',  // Almost black gold - for extreme dark themes
        },
        
        // Dark color palette - Slate/gray tones
        // Used for backgrounds, text, and neutral elements
        dark: {
          50: '#f8fafc',   // Lightest gray - for very light backgrounds
          100: '#f1f5f9',  // Very light gray - for subtle backgrounds
          200: '#e2e8f0',  // Light gray - for borders and dividers
          300: '#cbd5e1',  // Medium light gray - for disabled elements
          400: '#94a3b8',  // Medium gray - for placeholder text
          500: '#64748b',  // Base gray - for secondary text
          600: '#475569',  // Medium dark gray - for primary text
          700: '#334155',  // Dark gray - for dark backgrounds
          800: '#1e293b',  // Very dark gray - for main dark backgrounds
          900: '#0f172a',  // Darkest gray - for very dark backgrounds
          950: '#020617',  // Almost black - for extreme dark backgrounds
        }
      },
      
      // Custom font families
      fontFamily: {
        // Sans-serif font for UI elements - clean and modern
        'sans': ['Inter', 'system-ui', 'sans-serif'],
        // Monospace font for code and technical content
        'mono': ['JetBrains Mono', 'monospace'],
      },
      
      // Custom animations for smooth user interactions
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',           // Smooth fade in effect
        'slide-up': 'slideUp 0.3s ease-out',            // Slide up from bottom
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',  // Slow pulsing effect
      },
      
      // Keyframes for custom animations
      keyframes: {
        // Fade in animation - starts transparent, becomes opaque
        fadeIn: {
          '0%': { opacity: '0' },    // Start completely transparent
          '100%': { opacity: '1' },  // End completely opaque
        },
        // Slide up animation - starts below, slides up and fades in
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },  // Start 10px down and transparent
          '100%': { transform: 'translateY(0)', opacity: '1' },   // End in position and opaque
        },
      },
    },
  },
  
  // Tailwind plugins (none currently used)
  plugins: [],
}
