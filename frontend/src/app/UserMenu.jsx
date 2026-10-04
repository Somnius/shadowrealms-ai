import React from 'react';
import { useNavigate } from 'react-router';
import { Avatar, Glyph, useAtmosphere } from '../design';
import MenuButton from './Menu';
import { useAuth } from './AuthContext';
import { useSignOutEverywhere } from './SignOutEverywhere';
import { LANGUAGE_NAMES, setLanguage, t, useLanguage } from '../i18n';

/** The one user menu of the app: profile, language, atmosphere (motion), admin, theme preview, logout. */
export default function UserMenu({ compact = false }) {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const { choice, level, setLevel, systemReduced } = useAtmosphere();
  const name = user?.username || '';
  const lang = useLanguage();
  const everywhere = useSignOutEverywhere();

  const signOut = async () => {
    await logout();
    navigate('/login');
  };

  const items = [
    { id: 'profile', icon: 'user', label: t('shell:menu.profile', 'Profile & characters'), onSelect: () => navigate('/profile') },
    { divider: true },
    { id: 'language', icon: 'globe', heading: t('shell:menu.language', 'Language') },
    ...Object.entries(LANGUAGE_NAMES).map(([code, label]) => ({
      id: `lang-${code}`,
      label,
      lang: code,
      radio: true,
      checked: lang === code,
      onSelect: () => setLanguage(code),
    })),
    { divider: true },
    {
      id: 'atmosphere',
      icon: 'candle',
      heading: t('shell:menu.atmosphere', 'Atmosphere'),
    },
    ...[
      ['full', t('shell:menu.atmosphereFull', 'Full'), t('shell:menu.atmosphereFullHint', 'Fog, candlelight, animated sigils')],
      ['subtle', t('shell:menu.atmosphereSubtle', 'Subtle'), t('shell:menu.atmosphereSubtleHint', 'Still ambience, short transitions')],
      ['off', t('shell:menu.atmosphereOff', 'Off'), t('shell:menu.atmosphereOffHint', 'No motion at all')],
    ].map(([value, label, hint]) => ({
      id: `atmosphere-${value}`,
      label,
      hint: systemReduced && value !== 'off' ? t('shell:menu.atmosphereSystem', 'Motion is off in your system settings') : hint,
      radio: true,
      checked: systemReduced ? value === 'off' : choice === value,
      disabled: systemReduced,
      onSelect: () => setLevel(value),
    })),
    { divider: true },
    ...(isAdmin ? [{ id: 'admin', icon: 'crown', label: t('shell:menu.admin', 'Admin panel'), onSelect: () => navigate('/admin') }] : []),
    { id: 'showcase', icon: 'eye', label: t('shell:menu.showcase', 'Theme preview'), onSelect: () => navigate('/showcase') },
    { divider: true },
    { id: 'logout', icon: 'logout', label: t('shell:menu.logout', 'Log out'), danger: true, onSelect: signOut },
    {
      id: 'logout-all',
      icon: 'logout',
      label: t('shell:menu.logoutAll', 'Sign out everywhere'),
      hint: t('shell:menu.logoutAllHint', 'Ends your sessions on every device, this one too'),
      danger: true,
      onSelect: everywhere.ask,
    },
  ];

  return (
    <>
    <MenuButton
      label={t('shell:menu.button', 'Account menu for {{name}}', { name })}
      menuLabel={t('shell:menu.title', 'Account')}
      items={items}
      renderButton={(props, open) => (
        <button {...props} className={`sr-usermenu__btn${open ? ' is-open' : ''}`} data-atmosphere-level={level}>
          <Avatar src={user?.player_avatar_url} name={name} size={32} alt="" />
          {!compact ? <span className="sr-usermenu__name">{name}</span> : null}
          <Glyph name="chevron-down" size={16} />
        </button>
      )}
    />
    {everywhere.dialog}
    </>
  );
}
