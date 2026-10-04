import { forwardRef, useId } from 'react';
import Glyph from '../glyphs/Glyph';
import { cx } from './internal';
import './forms.css';

/**
 * Field: label + control + hint + error, wired with htmlFor / aria-describedby / aria-invalid.
 * The render-prop child receives the props to spread on the control.
 */
export function Field({ label, hint, error, required, id: idProp, className, hideLabel = false, children }) {
  const autoId = useId();
  const id = idProp || autoId;
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const control = {
    id,
    'aria-describedby': cx(hintId, errorId) || undefined,
    'aria-invalid': error ? true : undefined,
    required,
  };
  return (
    <div className={cx('sr-field', error && 'sr-field--error', className)}>
      {label ? (
        <label htmlFor={id} className={cx('sr-field__label', hideLabel && 'sr-visually-hidden')}>
          {label}
          {required ? (
            <span className="sr-field__req" aria-hidden="true">
              {' '}
              *
            </span>
          ) : null}
        </label>
      ) : null}
      {children(control)}
      {hint ? (
        <div id={hintId} className="sr-field__hint">
          {hint}
        </div>
      ) : null}
      {error ? (
        <div id={errorId} className="sr-field__error">
          <Glyph name="warning" size={14} /> <span>{error}</span>
        </div>
      ) : null}
    </div>
  );
}

const pickField = ({ label, hint, error, required, id, hideLabel, fieldClassName }) => ({
  label,
  hint,
  error,
  required,
  id,
  hideLabel,
  className: fieldClassName,
});

export const Input = forwardRef(function Input(
  { label, hint, error, required, id, hideLabel, fieldClassName, icon, className, type = 'text', ...rest },
  ref
) {
  return (
    <Field {...pickField({ label, hint, error, required, id, hideLabel, fieldClassName })}>
      {(control) => (
        <div className={cx('sr-input-wrap', icon && 'sr-input-wrap--icon')}>
          {icon ? <Glyph name={icon} size={16} className="sr-input__icon" /> : null}
          <input ref={ref} type={type} className={cx('sr-input', className)} {...control} {...rest} />
        </div>
      )}
    </Field>
  );
});

export const Textarea = forwardRef(function Textarea(
  { label, hint, error, required, id, hideLabel, fieldClassName, className, rows = 4, ...rest },
  ref
) {
  return (
    <Field {...pickField({ label, hint, error, required, id, hideLabel, fieldClassName })}>
      {(control) => <textarea ref={ref} rows={rows} className={cx('sr-input', 'sr-textarea', className)} {...control} {...rest} />}
    </Field>
  );
});

/** Native select (best mobile + a11y behaviour), styled. options: [{ value, label, disabled }] */
export const Select = forwardRef(function Select(
  { label, hint, error, required, id, hideLabel, fieldClassName, className, options, placeholder, children, ...rest },
  ref
) {
  return (
    <Field {...pickField({ label, hint, error, required, id, hideLabel, fieldClassName })}>
      {(control) => (
        <div className="sr-select-wrap">
          <select ref={ref} className={cx('sr-input', 'sr-select', className)} {...control} {...rest}>
            {placeholder ? (
              <option value="" disabled>
                {placeholder}
              </option>
            ) : null}
            {options
              ? options.map((o) => (
                  <option key={o.value} value={o.value} disabled={o.disabled}>
                    {o.label}
                  </option>
                ))
              : children}
          </select>
          <Glyph name="chevron-down" size={16} className="sr-select__chevron" />
        </div>
      )}
    </Field>
  );
});

/** Checkbox with label (native input, custom box). */
export const Checkbox = forwardRef(function Checkbox({ label, hint, id: idProp, className, ...rest }, ref) {
  const autoId = useId();
  const id = idProp || autoId;
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className={cx('sr-check', className)}>
      <input ref={ref} type="checkbox" id={id} className="sr-check__input" aria-describedby={hintId} {...rest} />
      <label htmlFor={id} className="sr-check__label">
        <span className="sr-check__box" aria-hidden="true">
          <Glyph name="check" size={14} strokeWidth={2.4} />
        </span>
        <span>{label}</span>
      </label>
      {hint ? (
        <div id={hintId} className="sr-field__hint sr-check__hint">
          {hint}
        </div>
      ) : null}
    </div>
  );
});

/** Switch: button role="switch". checked / onChange(nextBool). */
export const Switch = forwardRef(function Switch(
  { checked = false, onChange, label, hideLabel = false, disabled, className, id: idProp, ...rest },
  ref
) {
  const autoId = useId();
  const id = idProp || autoId;
  return (
    <button
      ref={ref}
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      className={cx('sr-switch', className)}
      onClick={() => onChange && onChange(!checked)}
      {...rest}
    >
      <span className="sr-switch__track" aria-hidden="true">
        <span className="sr-switch__thumb" />
      </span>
      <span className={cx('sr-switch__label', hideLabel && 'sr-visually-hidden')}>{label}</span>
    </button>
  );
});
