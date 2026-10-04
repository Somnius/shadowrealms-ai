import React, { Suspense, lazy } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { DesignProvider, Spinner, ToastProvider } from '../design';
import { AuthProvider, useAuth } from './AuthContext';
import { ChroniclesProvider } from './ChroniclesContext';
import { SheetProvider } from './SheetContext';
import AppShell, { PageBody, TopBar } from './AppShell';
import { RedirectIfAuthed, RequireAdmin, RequireAuth } from './guards';
import SessionNotices from './SessionNotices';
import LoginPage from '../features/auth/LoginPage';
import ChronicleHallPage from '../features/hall/ChronicleHallPage';
import CreateChroniclePage from '../features/hall/CreateChroniclePage';
import ChronicleSettingsPage from '../features/chronicle/ChronicleSettingsPage';
import ProfilePage from '../features/profile/ProfilePage';
import CharacterCreatePage from '../features/profile/CharacterCreatePage';
import PlayPage, { PlayRedirect } from '../features/play/PlayPage';
import { t, useLanguage } from '../i18n';

const AdminPage = lazy(() => import('../pages/AdminPage'));
const ShowcasePage = lazy(() => import('../pages/showcase/ShowcasePage'));
const DesignPlayground = lazy(() => import('../design/DesignPlayground'));

function Loading() {
  return (
    <div className="sr-loading">
      <Spinner variant="candle" label={t('common:loading', 'Loading')} />
    </div>
  );
}

function AdminRoute() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  return (
    <>
      <TopBar title={t('admin:title', 'Admin panel')} icon="crown" />
      <PageBody className="sr-page--legacy">
        <Suspense fallback={<Loading />}>
          <AdminPage
            token={token}
            user={user}
            displayTimezone={user?.display_timezone || null}
            onAdminOpenCampaign={(campaign) => campaign && navigate(`/c/${campaign.id}`)}
          />
        </Suspense>
      </PageBody>
    </>
  );
}

function ShowcaseRoute() {
  const navigate = useNavigate();
  return (
    <Suspense fallback={<Loading />}>
      <ShowcasePage onBack={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))} />
    </Suspense>
  );
}

/** All routes. Kept separate from <BrowserRouter> so tests can mount it in a MemoryRouter. */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<RedirectIfAuthed><LoginPage /></RedirectIfAuthed>} />
      <Route path="/showcase" element={<ShowcaseRoute />} />
      <Route
        path="/showcase/design"
        element={
          <Suspense fallback={<Loading />}>
            <DesignPlayground />
          </Suspense>
        }
      />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/chronicles" replace />} />
        <Route path="/chronicles" element={<ChronicleHallPage />} />
        <Route path="/chronicles/new" element={<CreateChroniclePage />} />
        <Route path="/chronicles/:id" element={<ChronicleSettingsPage />} />
        <Route path="/c/:id" element={<PlayRedirect />} />
        <Route path="/c/:id/:locationId" element={<PlayPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/profile/characters/new" element={<CharacterCreatePage />} />
        <Route path="/profile/:section" element={<ProfilePage />} />
        <Route path="/admin/*" element={<RequireAdmin><AdminRoute /></RequireAdmin>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

/**
 * Language switch = remount everything below the auth session. Call sites use the plain t()
 * (not a hook), so this is what makes them render again; a switch is rare and the session,
 * token and stored preferences survive it.
 */
export default function App() {
  const lang = useLanguage();
  return (
    <DesignProvider className="sr-root" lang={lang}>
      <ToastProvider>
        <AuthProvider>
          <SessionNotices />
          <ChroniclesProvider key={lang}>
            <SheetProvider>
              <AppRoutes />
            </SheetProvider>
          </ChroniclesProvider>
        </AuthProvider>
      </ToastProvider>
    </DesignProvider>
  );
}
