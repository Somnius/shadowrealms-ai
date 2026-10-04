import React, { useState, useEffect } from 'react';
import { t } from '../i18n';
import { Modal, Spinner } from '../design';

const ReadmeModal = ({ isOpen, onClose }) => {
  const [readmeContent, setReadmeContent] = useState('Loading...');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (isOpen) {
      setIsLoading(true);
      // Fetch README.md from the backend API
      fetch('/api/readme')
        .then(response => {
          console.log('Fetch response status:', response.status);
          if (!response.ok) {
            throw new Error(`Failed to load README: ${response.status}`);
          }
          return response.text();
        })
        .then(text => {
          console.log('README text length:', text.length);
          if (text && text.length > 0) {
            const parsed = parseMarkdown(text);
            console.log('Parsed HTML length:', parsed.length);
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

  // Enhanced markdown parser
  const parseMarkdown = (markdown) => {
    let html = markdown;
    
    // Remove or simplify HTML comments
    html = html.replace(/<!--[\s\S]*?-->/g, '');
    
    // Handle <div align="center"> and similar HTML tags - just remove them but keep content
    html = html.replace(/<div[^>]*>/gi, '<div style="text-align: center; margin: 20px 0;">');
    html = html.replace(/<\/div>/gi, '</div>');
    
    // Code blocks (must be before inline code)
    html = html.replace(/```(\w+)?\s*\n([\s\S]*?)```/g, (match, lang, code) => {
      return `<pre style="background: var(--sr-night-850); padding: 15px; border-radius: 8px; overflow-x: auto; border: 1px solid var(--sr-night-700); margin: 15px 0;"><code style="color: var(--sr-bone-100); font-family: 'Courier New', monospace; font-size: 13px;">${code.trim().replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code></pre>`;
    });
    
    // Parse markdown tables
    html = html.replace(/\n\|(.+)\|\n\|[\s\-:|]+\|\n((?:\|.+\|\n?)*)/g, (match, header, rows) => {
      const headers = header.split('|').filter(h => h.trim()).map(h => h.trim());
      const rowData = rows.trim().split('\n').map(row => 
        row.split('|').filter(cell => cell.trim()).map(cell => cell.trim())
      );
      
      let table = '<table style="border-collapse: collapse; width: 100%; margin: 20px 0; background: var(--sr-night-800); border: 2px solid var(--sr-night-700); border-radius: 8px; overflow: hidden;">';
      table += '<thead><tr style="background: linear-gradient(135deg, var(--sr-blood-500) 0%, var(--sr-blood-700) 100%);">';
      headers.forEach(h => {
        table += `<th style="padding: 12px; text-align: center; color: white; font-family: 'Cinzel', serif; border: 1px solid var(--sr-night-700);">${h}</th>`;
      });
      table += '</tr></thead><tbody>';
      
      rowData.forEach((row, idx) => {
        const bgColor = idx % 2 === 0 ? 'var(--sr-night-750)' : 'var(--sr-night-800)';
        table += `<tr style="background: ${bgColor};">`;
        row.forEach(cell => {
          table += `<td style="padding: 10px; text-align: center; color: var(--sr-bone-300); border: 1px solid var(--sr-night-700);">${cell}</td>`;
        });
        table += '</tr>';
      });
      
      table += '</tbody></table>';
      return table;
    });
    
    // Images/Badges (before links)
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="display: inline-block; margin: 2px 5px; max-width: 100%; vertical-align: middle;">');
    
    // Links - convert relative URLs to GitHub URLs
    const githubBaseUrl = 'https://github.com/Somnius/shadowrealms-ai/blob/main/';
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
      // Check if URL is relative (not starting with http://, https://, mailto:, or #)
      let finalUrl = url;
      if (!url.match(/^(https?:\/\/|mailto:|#)/i)) {
        // It's a relative URL, convert to GitHub URL
        finalUrl = githubBaseUrl + url;
      }
      return `<a href="${finalUrl}" target="_blank" rel="noopener noreferrer" style="color: var(--sr-arcane-500); text-decoration: none; border-bottom: 1px dotted var(--sr-arcane-500); transition: color 0.2s;">${text}</a>`;
    });
    
    // Headers (most specific first)
    html = html.replace(/^#### (.*$)/gim, '<h4 style="color: var(--sr-bone-300); margin-top: 18px; margin-bottom: 8px; font-family: \'Cinzel\', serif; font-size: 16px;">$1</h4>');
    html = html.replace(/^### (.*$)/gim, '<h3 style="color: var(--sr-gold-500); margin-top: 20px; margin-bottom: 10px; font-family: \'Cinzel\', serif; font-size: 18px;">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 style="color: var(--sr-blood-500); margin-top: 25px; margin-bottom: 12px; font-family: \'Cinzel\', serif; font-size: 22px;">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 style="color: var(--sr-blood-500); margin-top: 30px; margin-bottom: 15px; font-family: \'Cinzel\', serif; font-size: 28px; border-bottom: 2px solid var(--sr-night-700); padding-bottom: 10px;">$1</h1>');
    
    // Bold (before italic)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="color: var(--sr-gold-500); font-weight: bold;">$1</strong>');
    
    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em style="color: var(--sr-bone-300); font-style: italic;">$1</em>');
    
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code style="background: rgba(157, 78, 221, 0.2); padding: 2px 6px; border-radius: 4px; color: var(--sr-arcane-500); font-family: \'Courier New\', monospace; font-size: 13px;">$1</code>');
    
    // Horizontal rules
    html = html.replace(/^---+$/gim, '<hr style="border: none; border-top: 2px solid var(--sr-night-700); margin: 20px 0;">');
    
    // Lists
    html = html.replace(/^\d+\.\s+(.*$)/gim, '<li style="color: var(--sr-bone-300); margin-bottom: 5px;">$1</li>');
    html = html.replace(/^[\-\*]\s+(.*$)/gim, '<li style="color: var(--sr-bone-300); margin-bottom: 5px;">$1</li>');
    
    // Wrap consecutive <li> in <ul> or <ol>
    html = html.replace(/(<li[^>]*>.*?<\/li>\s*)+/g, (match) => {
      return `<ul style="list-style-type: disc; padding-left: 20px; margin: 10px 0; color: var(--sr-bone-300);">${match}</ul>`;
    });
    
    // Blockquotes
    html = html.replace(/^&gt;\s+(.*$)/gim, '<blockquote style="border-left: 4px solid var(--sr-blood-500); padding-left: 15px; margin: 15px 0; color: var(--sr-bone-500); font-style: italic;">$1</blockquote>');
    html = html.replace(/^>\s+(.*$)/gim, '<blockquote style="border-left: 4px solid var(--sr-blood-500); padding-left: 15px; margin: 15px 0; color: var(--sr-bone-500); font-style: italic;">$1</blockquote>');
    
    // Wrap remaining text in paragraphs (but avoid wrapping block elements)
    const lines = html.split('\n');
    let result = [];
    let paragraph = [];
    
    for (let line of lines) {
      const trimmed = line.trim();
      
      // Skip empty lines
      if (trimmed === '') {
        if (paragraph.length > 0) {
          result.push('<p style="color: var(--sr-bone-300); line-height: 1.6; margin: 10px 0;">' + paragraph.join(' ') + '</p>');
          paragraph = [];
        }
        continue;
      }
      
      // Check if line is a block element
      if (trimmed.match(/^<(h[1-6]|pre|ul|ol|table|hr|blockquote|div)/i) || trimmed.match(/<\/(h[1-6]|pre|ul|ol|table|hr|blockquote|div)>$/i)) {
        if (paragraph.length > 0) {
          result.push('<p style="color: var(--sr-bone-300); line-height: 1.6; margin: 10px 0;">' + paragraph.join(' ') + '</p>');
          paragraph = [];
        }
        result.push(line);
      } else {
        paragraph.push(line);
      }
    }
    
    if (paragraph.length > 0) {
      result.push('<p style="color: var(--sr-bone-300); line-height: 1.6; margin: 10px 0;">' + paragraph.join(' ') + '</p>');
    }
    
    return result.join('\n');
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
        <div className="sr-readme__content sr-prose" dangerouslySetInnerHTML={{ __html: readmeContent }} />
      )}
    </Modal>
  );
};

export default ReadmeModal;

