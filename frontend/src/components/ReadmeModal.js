import React, { useState, useEffect } from 'react';

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
            setReadmeContent('<p style="color: #e94560;">README.md is empty</p>');
          }
          setIsLoading(false);
        })
        .catch(error => {
          console.error('Error loading README:', error);
          setReadmeContent(`<p style="color: #e94560;">Failed to load README.md: ${error.message}</p>`);
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
      return `<pre style="background: #0f1729; padding: 15px; border-radius: 8px; overflow-x: auto; border: 1px solid #2a2a4e; margin: 15px 0;"><code style="color: #d0d0e0; font-family: 'Courier New', monospace; font-size: 13px;">${code.trim().replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code></pre>`;
    });
    
    // Parse markdown tables
    html = html.replace(/\n\|(.+)\|\n\|[\s\-:|]+\|\n((?:\|.+\|\n?)*)/g, (match, header, rows) => {
      const headers = header.split('|').filter(h => h.trim()).map(h => h.trim());
      const rowData = rows.trim().split('\n').map(row => 
        row.split('|').filter(cell => cell.trim()).map(cell => cell.trim())
      );
      
      let table = '<table style="border-collapse: collapse; width: 100%; margin: 20px 0; background: #16213e; border: 2px solid #2a2a4e; border-radius: 8px; overflow: hidden;">';
      table += '<thead><tr style="background: linear-gradient(135deg, #e94560 0%, #8b0000 100%);">';
      headers.forEach(h => {
        table += `<th style="padding: 12px; text-align: center; color: white; font-family: 'Cinzel', serif; border: 1px solid #2a2a4e;">${h}</th>`;
      });
      table += '</tr></thead><tbody>';
      
      rowData.forEach((row, idx) => {
        const bgColor = idx % 2 === 0 ? '#1a2340' : '#16213e';
        table += `<tr style="background: ${bgColor};">`;
        row.forEach(cell => {
          table += `<td style="padding: 10px; text-align: center; color: #b5b5c3; border: 1px solid #2a2a4e;">${cell}</td>`;
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
      return `<a href="${finalUrl}" target="_blank" rel="noopener noreferrer" style="color: #9d4edd; text-decoration: none; border-bottom: 1px dotted #9d4edd; transition: color 0.2s;">${text}</a>`;
    });
    
    // Headers (most specific first)
    html = html.replace(/^#### (.*$)/gim, '<h4 style="color: #b5b5c3; margin-top: 18px; margin-bottom: 8px; font-family: \'Cinzel\', serif; font-size: 16px;">$1</h4>');
    html = html.replace(/^### (.*$)/gim, '<h3 style="color: #ffd700; margin-top: 20px; margin-bottom: 10px; font-family: \'Cinzel\', serif; font-size: 18px;">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 style="color: #e94560; margin-top: 25px; margin-bottom: 12px; font-family: \'Cinzel\', serif; font-size: 22px;">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 style="color: #e94560; margin-top: 30px; margin-bottom: 15px; font-family: \'Cinzel\', serif; font-size: 28px; border-bottom: 2px solid #2a2a4e; padding-bottom: 10px;">$1</h1>');
    
    // Bold (before italic)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="color: #ffd700; font-weight: bold;">$1</strong>');
    
    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em style="color: #b5b5c3; font-style: italic;">$1</em>');
    
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code style="background: rgba(157, 78, 221, 0.2); padding: 2px 6px; border-radius: 4px; color: #9d4edd; font-family: \'Courier New\', monospace; font-size: 13px;">$1</code>');
    
    // Horizontal rules
    html = html.replace(/^---+$/gim, '<hr style="border: none; border-top: 2px solid #2a2a4e; margin: 20px 0;">');
    
    // Lists
    html = html.replace(/^\d+\.\s+(.*$)/gim, '<li style="color: #b5b5c3; margin-bottom: 5px;">$1</li>');
    html = html.replace(/^[\-\*]\s+(.*$)/gim, '<li style="color: #b5b5c3; margin-bottom: 5px;">$1</li>');
    
    // Wrap consecutive <li> in <ul> or <ol>
    html = html.replace(/(<li[^>]*>.*?<\/li>\s*)+/g, (match) => {
      return `<ul style="list-style-type: disc; padding-left: 20px; margin: 10px 0; color: #b5b5c3;">${match}</ul>`;
    });
    
    // Blockquotes
    html = html.replace(/^&gt;\s+(.*$)/gim, '<blockquote style="border-left: 4px solid #e94560; padding-left: 15px; margin: 15px 0; color: #8b8b9f; font-style: italic;">$1</blockquote>');
    html = html.replace(/^>\s+(.*$)/gim, '<blockquote style="border-left: 4px solid #e94560; padding-left: 15px; margin: 15px 0; color: #8b8b9f; font-style: italic;">$1</blockquote>');
    
    // Wrap remaining text in paragraphs (but avoid wrapping block elements)
    const lines = html.split('\n');
    let result = [];
    let paragraph = [];
    
    for (let line of lines) {
      const trimmed = line.trim();
      
      // Skip empty lines
      if (trimmed === '') {
        if (paragraph.length > 0) {
          result.push('<p style="color: #b5b5c3; line-height: 1.6; margin: 10px 0;">' + paragraph.join(' ') + '</p>');
          paragraph = [];
        }
        continue;
      }
      
      // Check if line is a block element
      if (trimmed.match(/^<(h[1-6]|pre|ul|ol|table|hr|blockquote|div)/i) || trimmed.match(/<\/(h[1-6]|pre|ul|ol|table|hr|blockquote|div)>$/i)) {
        if (paragraph.length > 0) {
          result.push('<p style="color: #b5b5c3; line-height: 1.6; margin: 10px 0;">' + paragraph.join(' ') + '</p>');
          paragraph = [];
        }
        result.push(line);
      } else {
        paragraph.push(line);
      }
    }
    
    if (paragraph.length > 0) {
      result.push('<p style="color: #b5b5c3; line-height: 1.6; margin: 10px 0;">' + paragraph.join(' ') + '</p>');
    }
    
    return result.join('\n');
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.85)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 3000,
      padding: '20px',
      animation: 'fadeIn 0.3s ease-out'
    }}
    onClick={onClose}
    >
      <div style={{
        background: 'linear-gradient(135deg, #16213e 0%, #0f1729 100%)',
        width: window.innerWidth < 768 ? '95%' : '75%',
        maxWidth: '1200px',
        height: window.innerWidth < 768 ? '95vh' : '85vh',
        borderRadius: '15px',
        boxShadow: '0 0 40px rgba(233, 69, 96, 0.6)',
        border: '2px solid #e94560',
        display: 'flex',
        flexDirection: 'column',
        animation: 'scaleIn 0.3s ease-out',
        position: 'relative',
        overflow: 'hidden'
      }}
      onClick={(e) => e.stopPropagation()}
      >
        {/* Header with Close Button */}
        <div style={{
          background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
          padding: '20px 25px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '2px solid #2a2a4e',
          flexShrink: 0
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            <button
              onClick={onClose}
              style={{
                background: 'rgba(255, 255, 255, 0.2)',
                color: 'white',
                border: '2px solid rgba(255, 255, 255, 0.5)',
                borderRadius: '8px',
                padding: '8px 16px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontFamily: 'Cinzel, serif',
                fontSize: '14px',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
              onMouseOver={(e) => {
                e.target.style.background = 'rgba(255, 255, 255, 0.3)';
                e.target.style.transform = 'scale(1.05)';
              }}
              onMouseOut={(e) => {
                e.target.style.background = 'rgba(255, 255, 255, 0.2)';
                e.target.style.transform = 'scale(1)';
              }}
            >
              ✕ Close
            </button>
            <h2 style={{
              margin: 0,
              color: 'white',
              fontFamily: 'Cinzel, serif',
              fontSize: '24px',
              textShadow: '0 2px 4px rgba(0,0,0,0.5)'
            }}>
              📜 ShadowRealms AI - README
            </h2>
          </div>
        </div>

        {/* Content Area */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          padding: '30px',
          background: '#16213e',
          fontFamily: 'Crimson Text, serif'
        }}>
          {isLoading ? (
            <div style={{ 
              textAlign: 'center', 
              color: '#b5b5c3', 
              fontSize: '18px',
              paddingTop: '50px'
            }}>
              <div style={{
                display: 'inline-block',
                width: '50px',
                height: '50px',
                border: '4px solid #2a2a4e',
                borderTop: '4px solid #e94560',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite'
              }}></div>
              <p style={{ marginTop: '20px' }}>Loading README...</p>
            </div>
          ) : (
            <div 
              dangerouslySetInnerHTML={{ __html: readmeContent }}
              style={{
                lineHeight: 1.6,
                fontSize: '15px'
              }}
            />
          )}
        </div>
      </div>

      {/* CSS animations */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleIn {
          from { transform: scale(0.9); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default ReadmeModal;

