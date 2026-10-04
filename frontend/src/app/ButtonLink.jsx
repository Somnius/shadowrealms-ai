import React from 'react';
import { Link } from 'react-router-dom';
import { Glyph } from '../design';
import '../design/components/button.css';

/** A router link styled as a design-system Button (navigation must stay a link, not a button). */
export default function ButtonLink({ to, variant = 'secondary', size = 'md', icon, children, className = '', ...rest }) {
  const iconSize = size === 'sm' ? 16 : size === 'lg' ? 20 : 18;
  return (
    <Link to={to} className={`sr-btn sr-btn--${variant} sr-btn--${size} ${className}`.trim()} {...rest}>
      {icon ? <Glyph name={icon} size={iconSize} /> : null}
      {children != null ? <span className="sr-btn__label">{children}</span> : null}
    </Link>
  );
}
