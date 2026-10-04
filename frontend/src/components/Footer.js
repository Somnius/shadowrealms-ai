import { useState } from 'react';
import ReadmeModal from './ReadmeModal';
// Only the version: a named import lets Vite leave the rest of package.json out of the bundle.
import { version as packageVersion } from '../../package.json';
import { t } from '../i18n';
import { Glyph } from '../design';

/**
 * SPA build version — from `frontend/package.json`, bumped by `scripts/version-bump.sh`.
 * We do not call `/api/version` here: backend `VERSION` in `.env` can lag behind the
 * built bundle and was overwriting this badge with stale values (e.g. v0.7.17).
 */
const displayVersion = `v${packageVersion}`;

function Footer() {
  const [showReadme, setShowReadme] = useState(false);

  return (
    <>
    <footer style={{
      background: 'linear-gradient(135deg, var(--sr-night-850) 0%, var(--sr-night-800) 100%)',
      borderTop: '2px solid var(--sr-night-700)',
      padding: '20px',
      textAlign: 'center',
      boxShadow: '0 -2px 10px rgba(0, 0, 0, 0.5)',
      width: '100%',
      flexShrink: 0
    }}>
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
        display: 'flex',
        flexDirection: window.innerWidth < 768 ? 'column' : 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '15px',
        flexWrap: 'wrap'
      }}>
        {/* Version & Project Info */}
        <div style={{
          color: 'var(--sr-bone-500)',
          fontSize: '14px',
          fontFamily: 'var(--sr-font-body)'
        }}>
          <span style={{ 
            color: 'var(--sr-blood-400)', 
            fontWeight: 'bold',
            fontFamily: 'var(--sr-font-display)'
          }}>
            ShadowRealms AI
          </span>
          {' '}
          <span 
            onClick={() => setShowReadme(true)}
            style={{ 
              color: 'var(--sr-arcane-400)',
              fontSize: '12px',
              padding: '2px 8px',
              background: 'rgba(157, 78, 221, 0.2)',
              borderRadius: '10px',
              border: '1px solid var(--sr-arcane-500)',
              cursor: 'pointer',
              transition: 'all 0.2s',
              display: 'inline-block'
            }}
            onMouseOver={(e) => {
              e.target.style.background = 'rgba(157, 78, 221, 0.4)';
              e.target.style.transform = 'scale(1.05)';
              e.target.style.boxShadow = '0 0 10px rgba(157, 78, 221, 0.6)';
            }}
            onMouseOut={(e) => {
              e.target.style.background = 'rgba(157, 78, 221, 0.2)';
              e.target.style.transform = 'scale(1)';
              e.target.style.boxShadow = 'none';
            }}
            title={t('footer:readmeTitle', 'Show the README')}
          >
            {displayVersion}
          </span>
        </div>

        {/* Creator Info */}
        <div style={{
          color: 'var(--sr-bone-300)',
          fontSize: '14px',
          fontFamily: 'var(--sr-font-body)'
        }}>
          {t('footer:madeWith', 'Made with')} <Glyph name="blood-drop" size={14} title={t('footer:love', 'love')} style={{ color: 'var(--sr-blood-500)', verticalAlign: '-2px' }} /> {t('footer:madeFor', 'for tabletop RPG games by')}{' '}
          <span style={{ 
            color: 'var(--sr-blood-400)',
            fontWeight: 'bold',
            fontFamily: 'var(--sr-font-display)'
          }}>
            Lefteris Iliadis
          </span>
        </div>

        {/* Social Links */}
        <div style={{
          display: 'flex',
          gap: '15px',
          alignItems: 'center'
        }}>
          <a
            href="https://github.com/Somnius/shadowrealms-ai"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: 'var(--sr-bone-300)',
              textDecoration: 'none',
              fontSize: '14px',
              fontFamily: 'var(--sr-font-body)',
              transition: 'color 0.2s',
              display: 'flex',
              alignItems: 'center',
              gap: '5px'
            }}
            onMouseOver={(e) => {
              e.target.style.color = 'var(--sr-blood-400)';
            }}
            onMouseOut={(e) => {
              e.target.style.color = 'var(--sr-bone-300)';
            }}
          >
            <svg 
              height="16" 
              width="16" 
              viewBox="0 0 16 16" 
              fill="currentColor"
              style={{ marginRight: '3px' }}
            >
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
            </svg>
            Somnius
          </a>
          
          <span aria-hidden="true" style={{ color: 'var(--sr-bone-500)' }}>|</span>
          
          <span style={{
            color: 'var(--sr-bone-500)',
            fontSize: '14px',
            fontFamily: 'var(--sr-font-body)'
          }}>
            @SomniusX
          </span>
        </div>
      </div>

      {/* Cursor Credit */}
      <div style={{
        marginTop: '15px',
        paddingTop: '15px',
        borderTop: '1px solid var(--sr-night-700)',
        color: 'var(--sr-bone-500)',
        fontSize: '12px',
        fontFamily: 'var(--sr-font-body)'
      }}>
        {t('footer:builtWith', 'Built with the help of')}{' '}
        <a 
          href="https://cursor.sh" 
          target="_blank" 
          rel="noopener noreferrer"
          style={{
            color: 'var(--sr-arcane-400)',
            textDecoration: 'none',
            fontWeight: 'bold',
            transition: 'color 0.2s'
          }}
          onMouseOver={(e) => {
            e.target.style.color = 'var(--sr-arcane-300)';
          }}
          onMouseOut={(e) => {
            e.target.style.color = 'var(--sr-arcane-400)';
          }}
        >
          Cursor AI
        </a>
        {' '}<Glyph name="ai-sigil" size={14} style={{ color: 'var(--sr-arcane-400)', verticalAlign: '-2px' }} />
      </div>
    </footer>

    {/* README Modal */}
    <ReadmeModal 
      isOpen={showReadme} 
      onClose={() => setShowReadme(false)} 
    />
    </>
  );
}

export default Footer;

