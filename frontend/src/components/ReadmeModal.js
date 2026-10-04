import { useState, useEffect, useMemo } from 'react';
import { t } from '../i18n';
import { Modal, Spinner } from '../design';
import { sanitizeRichHtml } from '../utils/security';
import { renderMarkdown } from '../utils/markdown';
import './readme.css';

const ReadmeModal = ({ isOpen, onClose }) => {
  const [readmeContent, setReadmeContent] = useState('Loading...');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (isOpen) {
      setIsLoading(true);
      // Fetch README.md from the backend API
      fetch('/api/readme')
        .then(response => {
          if (!response.ok) {
            throw new Error(`Failed to load README: ${response.status}`);
          }
          return response.text();
        })
        .then(text => {
          if (text && text.length > 0) {
            const parsed = renderMarkdown(text);
            setReadmeContent(parsed);
          } else {
            setReadmeContent('<p style="color: var(--sr-blood-500);">README.md is empty</p>');
          }
          setIsLoading(false);
        })
        .catch(error => {
          console.error('Error loading README:', error);
          setReadmeContent(`<p style="color: var(--sr-blood-500);">${t('footer:readme.failed', 'Failed to load README.md: {{error}}', { error: error.message })}</p>`);
          setIsLoading(false);
        });
    }
  }, [isOpen]);

  // Every string set above (README, empty notice, error) is sanitized right before rendering.
  const safeHtml = useMemo(() => sanitizeRichHtml(readmeContent), [readmeContent]);

  // "#section" links scroll inside the modal instead of changing the app's URL.
  const onContentClick = (event) => {
    const link = event.target.closest && event.target.closest('a[href^="#"]');
    if (!link) return;
    event.preventDefault();
    let id = link.getAttribute('href').slice(1);
    try {
      id = decodeURIComponent(id);
    } catch {
      // "#%" and similar: look the id up as written
    }
    const target = document.getElementById(id);
    if (target && event.currentTarget.contains(target) && target.scrollIntoView) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <Modal
      open={!!isOpen}
      onClose={onClose}
      title={t('footer:readme.title', 'ShadowRealms AI: README')}
      icon="scroll"
      size="lg"
      closeLabel={t('footer:readme.close', 'Close')}
      className="sr-readme"
    >
      {isLoading ? (
        <div className="sr-readme__loading">
          <Spinner variant="candle" label={t('footer:readme.loading', 'Loading the README…')} />
        </div>
      ) : (
        <div
          className="sr-readme__content sr-prose"
          onClick={onContentClick}
          dangerouslySetInnerHTML={{ __html: safeHtml }}
        />
      )}
    </Modal>
  );
};

export default ReadmeModal;

