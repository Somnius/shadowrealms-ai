import React, { forwardRef } from 'react';
import Glyph from '../glyphs/Glyph';
import Spinner from './Spinner';
import Tooltip from './Tooltip';
import { cx } from './internal';
import './button.css';

const renderIcon = (icon, size) =>
  typeof icon === 'string' ? <Glyph name={icon} size={size} /> : icon || null;

const ICON_SIZE = { sm: 16, md: 18, lg: 20 };

/**
 * Button.
 * variant: 'primary' | 'secondary' | 'ghost' | 'danger' | 'arcane' | 'icon'
 * size: 'sm' (32) | 'md' (40) | 'lg' (48)
 * icon / iconEnd: glyph name or node. loading: shows a spinner, sets aria-busy/aria-disabled and blocks clicks
 * (not the native disabled attribute, so keyboard focus stays on the button).
 */
const Button = forwardRef(function Button(
  {
    variant = 'secondary',
    size = 'md',
    icon,
    iconEnd,
    loading = false,
    loadingLabel = 'Loading',
    block = false,
    disabled,
    type = 'button',
    className,
    children,
    onClick,
    ...rest
  },
  ref
) {
  const isDisabled = disabled || loading;
  const iconSize = ICON_SIZE[size] || 18;
  return (
    <button
      ref={ref}
      type={type}
      className={cx(
        'sr-btn',
        `sr-btn--${variant}`,
        `sr-btn--${size}`,
        block && 'sr-btn--block',
        loading && 'sr-btn--loading',
        className
      )}
      disabled={disabled}
      aria-disabled={loading || undefined}
      aria-busy={loading || undefined}
      onClick={(event) => {
        if (isDisabled) {
          event.preventDefault(); // also stops type="submit" while loading
          return;
        }
        if (onClick) onClick(event);
      }}
      {...rest}
    >
      {loading ? (
        <>
          <Spinner size={iconSize} decorative className="sr-btn__spinner" />
          <span className="sr-visually-hidden">{loadingLabel}</span>
        </>
      ) : (
        renderIcon(icon, iconSize)
      )}
      {children != null ? <span className="sr-btn__label">{children}</span> : null}
      {!loading ? renderIcon(iconEnd, iconSize) : null}
    </button>
  );
});

export default Button;

/**
 * Square icon-only button. `label` is required: it becomes the aria-label and the tooltip.
 */
export const IconButton = forwardRef(function IconButton(
  { icon, label, size = 'md', variant = 'ghost', tooltip = true, className, ...rest },
  ref
) {
  if (process.env.NODE_ENV !== 'production' && !label) {
    // eslint-disable-next-line no-console
    console.warn('[design] IconButton needs a `label` for screen readers');
  }
  const button = (
    <Button
      ref={ref}
      variant={variant === 'ghost' ? 'icon' : variant}
      size={size}
      icon={icon}
      aria-label={label}
      className={cx('sr-btn--square', className)}
      {...rest}
    />
  );
  return tooltip && label ? (
    <Tooltip content={label} describe={false}>
      {button}
    </Tooltip>
  ) : (
    button
  );
});
