/**
 * Security utilities test suite
 */

import {
  sanitizeHtml,
  sanitizeUrl,
  isValidEmail,
  isValidUsername,
  validatePassword,
  sanitizeName,
  sanitizeDescription,
  htmlToText,
  sanitizeRichHtml,
  validateChatMessage,
  RateLimiter,
  sanitizeSearchQuery,
  validateCampaignData,
  generateCSRFToken
} from '../security';

describe('Security Utilities', () => {
  
  describe('sanitizeHtml', () => {
    it('should escape HTML tags', () => {
      const input = '<script>alert("xss")</script>';
      const result = sanitizeHtml(input);
      expect(result).not.toContain('<script>');
      expect(result).toContain('&lt;script&gt;');
    });
    
    it('should handle empty input', () => {
      expect(sanitizeHtml('')).toBe('');
      expect(sanitizeHtml(null)).toBe('');
      expect(sanitizeHtml(undefined)).toBe('');
    });
    
    it('should escape dangerous characters', () => {
      const input = '<img src=x onerror="alert(1)">';
      const result = sanitizeHtml(input);
      // Escaped into inert text: no real tag left, so the handler can't fire
      expect(result).not.toContain('<img');
      expect(result).toContain('&lt;img');
    });
  });
  
  describe('sanitizeUrl', () => {
    it('should encode URL components', () => {
      const input = 'hello world & stuff';
      const result = sanitizeUrl(input);
      expect(result).toBe('hello%20world%20%26%20stuff');
    });
    
    it('should handle empty input', () => {
      expect(sanitizeUrl('')).toBe('');
      expect(sanitizeUrl(null)).toBe('');
    });
  });
  
  describe('isValidEmail', () => {
    it('should validate correct email formats', () => {
      expect(isValidEmail('user@example.com')).toBe(true);
      expect(isValidEmail('test.user+tag@domain.co.uk')).toBe(true);
    });
    
    it('should reject invalid email formats', () => {
      expect(isValidEmail('notanemail')).toBe(false);
      expect(isValidEmail('@example.com')).toBe(false);
      expect(isValidEmail('user@')).toBe(false);
      expect(isValidEmail('')).toBe(false);
    });
  });
  
  describe('isValidUsername', () => {
    it('should validate correct usernames', () => {
      expect(isValidUsername('user123')).toBe(true);
      expect(isValidUsername('test_user')).toBe(true);
      expect(isValidUsername('some-name')).toBe(true);
    });
    
    it('should reject invalid usernames', () => {
      expect(isValidUsername('ab')).toBe(false); // too short
      expect(isValidUsername('a'.repeat(21))).toBe(false); // too long
      expect(isValidUsername('user name')).toBe(false); // spaces
      expect(isValidUsername('user@123')).toBe(false); // special chars
    });
  });
  
  describe('validatePassword', () => {
    it('should accept strong passwords', () => {
      const result = validatePassword('SecurePass123');
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });
    
    it('should reject weak passwords', () => {
      const tooShort = validatePassword('Short1');
      expect(tooShort.valid).toBe(false);
      expect(tooShort.errors).toContain('Password must be at least 8 characters long');
      
      const noUpper = validatePassword('lowercase123');
      expect(noUpper.valid).toBe(false);
      expect(noUpper.errors.some(e => e.includes('uppercase'))).toBe(true);
      
      const noNumber = validatePassword('NoNumbers');
      expect(noNumber.valid).toBe(false);
      expect(noNumber.errors.some(e => e.includes('number'))).toBe(true);
    });
  });
  
  describe('sanitizeName', () => {
    it('should remove HTML tags', () => {
      const input = 'Marcus<script>alert(1)</script>';
      const result = sanitizeName(input);
      expect(result).not.toContain('<script>');
      // Script content is dropped with the element
      expect(result).toBe('Marcus');
    });

    it('never leaves a tag when tags are nested or split', () => {
      for (const input of ['<<script>script>x', '<scr<script>ipt>Bad</script>', 'A<img src=x onerror=alert(1)>B']) {
        const result = sanitizeName(input);
        expect(result).not.toMatch(/[<>]/);
      }
      expect(sanitizeName('A<img src=x onerror=alert(1)>B')).toBe('AB');
    });
    
    it('should allow basic punctuation', () => {
      const input = "O'Brien, Jr.";
      const result = sanitizeName(input);
      expect(result).toBe("O'Brien, Jr.");
    });
    
    it('should limit length', () => {
      const input = 'a'.repeat(200);
      const result = sanitizeName(input);
      expect(result.length).toBeLessThanOrEqual(100);
    });
    
    it('should remove special characters', () => {
      const input = 'Name@#$%^&*';
      const result = sanitizeName(input);
      expect(result).toBe('Name');
    });
  });
  
  describe('sanitizeDescription', () => {
    it('should remove script tags', () => {
      const input = 'Description<script>alert("xss")</script>text';
      const result = sanitizeDescription(input);
      expect(result).not.toContain('<script>');
      expect(result).toContain('Descriptiontext');
    });
    
    it('should remove event handlers', () => {
      const input = '<div onclick="alert(1)">Text</div>';
      const result = sanitizeDescription(input);
      expect(result).not.toContain('onclick');
    });
    
    it('should remove dangerous tags', () => {
      const input = '<iframe src="evil.com"></iframe>Normal text';
      const result = sanitizeDescription(input);
      expect(result).not.toContain('iframe');
      expect(result).toContain('Normal text');
    });
    
    it('should limit length', () => {
      const input = 'a'.repeat(20000);
      const result = sanitizeDescription(input);
      expect(result.length).toBeLessThanOrEqual(10000);
    });
  });
  
  describe('htmlToText', () => {
    it('returns the text of markup without any tags', () => {
      expect(htmlToText('<b>Bold</b> and <i>italic</i>')).toBe('Bold and italic');
      expect(htmlToText('')).toBe('');
      expect(htmlToText(null)).toBe('');
    });

    it('drops script/style/iframe contents and handles tricky inputs', () => {
      expect(htmlToText('a<script>alert(1)</script>b<style>p{}</style>c')).toBe('abc');
      expect(htmlToText('<scr<script>ipt>alert(1)</script>')).not.toMatch(/<script/i);
      expect(htmlToText('<!-- <!-- -->x-->')).not.toContain('<!--');
      expect(htmlToText('1 < 2 & 3 > 2')).toBe('1 < 2 & 3 > 2');
    });

    it('does not run scripts or handlers while parsing', () => {
      window.__xssProbe = false;
      htmlToText('<img src=x onerror="window.__xssProbe=true"><script>window.__xssProbe=true</script>');
      expect(window.__xssProbe).toBe(false);
      delete window.__xssProbe;
    });
  });

  describe('sanitizeRichHtml', () => {
    it('keeps safe formatting, links and images', () => {
      const out = sanitizeRichHtml(
        '<h2 style="color: red">T</h2><a href="https://example.com" target="_blank" rel="noopener noreferrer">l</a><img src="https://x/y.png" alt="b">'
      );
      expect(out).toContain('<h2 style="color: red">T</h2>');
      expect(out).toContain('href="https://example.com"');
      expect(out).toContain('target="_blank"');
      expect(out).toContain('<img');
    });

    it('removes scripts, handlers, javascript: URLs, comments and forms', () => {
      const out = sanitizeRichHtml(
        '<p onclick="x()">a</p><script>bad()</script><a href="javascript:alert(1)">j</a>'
        + '<!-- note --><iframe src="https://e"></iframe><form><input></form><img src=x onerror=alert(1)>'
      );
      expect(out).not.toMatch(/onclick|onerror|<script|javascript:|<!--|<iframe|<form|<input/i);
      expect(out).toContain('<p>a</p>');
    });

    it('returns an empty string for empty input', () => {
      expect(sanitizeRichHtml('')).toBe('');
      expect(sanitizeRichHtml(null)).toBe('');
    });
  });

  describe('validateChatMessage', () => {
    it('should accept valid messages', () => {
      const result = validateChatMessage('Hello, world!');
      expect(result.valid).toBe(true);
      expect(result.sanitized).toBe('Hello, world!');
      expect(result.error).toBeNull();
    });
    
    it('should reject empty messages', () => {
      const result = validateChatMessage('');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('empty');
    });
    
    it('should reject too long messages', () => {
      const longMessage = 'a'.repeat(2001);
      const result = validateChatMessage(longMessage);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('too long');
    });
    
    it('should sanitize HTML in messages', () => {
      const result = validateChatMessage('<script>alert(1)</script>');
      expect(result.sanitized).not.toContain('<script>');
    });
  });
  
  describe('RateLimiter', () => {
    it('should allow actions under limit', () => {
      const limiter = new RateLimiter(3, 1000); // 3 actions per second
      
      expect(limiter.isAllowed()).toBe(true);
      expect(limiter.isAllowed()).toBe(true);
      expect(limiter.isAllowed()).toBe(true);
    });
    
    it('should block actions over limit', () => {
      const limiter = new RateLimiter(2, 1000); // 2 actions per second
      
      expect(limiter.isAllowed()).toBe(true);
      expect(limiter.isAllowed()).toBe(true);
      expect(limiter.isAllowed()).toBe(false); // blocked
    });
    
    it('should reset after time window', async () => {
      const limiter = new RateLimiter(1, 100); // 1 action per 100ms
      
      expect(limiter.isAllowed()).toBe(true);
      expect(limiter.isAllowed()).toBe(false);
      
      await new Promise(resolve => setTimeout(resolve, 150));
      
      expect(limiter.isAllowed()).toBe(true);
    });
    
    it('should calculate time until allowed', () => {
      const limiter = new RateLimiter(1, 1000);
      
      limiter.isAllowed();
      limiter.isAllowed(); // blocked
      
      const timeUntil = limiter.getTimeUntilAllowed();
      expect(timeUntil).toBeGreaterThan(0);
      expect(timeUntil).toBeLessThanOrEqual(1000);
    });
  });
  
  describe('sanitizeSearchQuery', () => {
    it('should remove SQL injection attempts', () => {
      const input = "test'; DROP TABLE users; --";
      const result = sanitizeSearchQuery(input);
      expect(result).not.toContain("'");
      expect(result).not.toContain(';');
      expect(result).not.toContain('\\');
    });
    
    it('should limit wildcard usage', () => {
      const input = 'test****search';
      const result = sanitizeSearchQuery(input);
      expect(result).toBe('test*search');
    });
    
    it('should limit length', () => {
      const input = 'a'.repeat(300);
      const result = sanitizeSearchQuery(input);
      expect(result.length).toBeLessThanOrEqual(200);
    });
  });
  
  describe('validateCampaignData', () => {
    it('should validate and sanitize correct campaign data', () => {
      const data = {
        name: 'Test Campaign',
        description: 'A great adventure',
        game_system: 'vampire'
      };
      
      const result = validateCampaignData(data);
      expect(result.valid).toBe(true);
      expect(result.sanitized.name).toBe('Test Campaign');
      expect(result.sanitized.game_system).toBe('vampire');
    });
    
    it('should reject missing required fields', () => {
      const data = {
        description: 'No name provided'
      };
      
      const result = validateCampaignData(data);
      expect(result.valid).toBe(false);
      expect(result.errors.name).toBeDefined();
      expect(result.errors.game_system).toBeDefined();
    });
    
    it('should reject invalid game system', () => {
      const data = {
        name: 'Test',
        game_system: 'invalid_system'
      };
      
      const result = validateCampaignData(data);
      expect(result.valid).toBe(false);
      expect(result.errors.game_system).toBeDefined();
    });
    
    it('should sanitize HTML in descriptions', () => {
      const data = {
        name: 'Test',
        description: '<script>alert(1)</script>Normal text',
        game_system: 'vampire'
      };
      
      const result = validateCampaignData(data);
      expect(result.sanitized.description).not.toContain('<script>');
    });
  });
  
  describe('generateCSRFToken', () => {
    it('should generate random tokens', () => {
      const token1 = generateCSRFToken();
      const token2 = generateCSRFToken();
      
      expect(token1).not.toBe(token2);
      expect(token1.length).toBeGreaterThan(0);
      expect(token2.length).toBeGreaterThan(0);
    });
    
    it('should generate hex strings', () => {
      const token = generateCSRFToken();
      expect(token).toMatch(/^[0-9a-f]+$/);
    });
  });
  
});

