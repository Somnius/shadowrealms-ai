import { useEffect, useState } from 'react';
import { Button, Panel } from '../../design';
import { api } from '../../utils/api';
import { t } from '../../i18n';

/** Labels are read at render time so a language switch picks them up. */
export const roleLabels = () => ({
  storyteller_en: t('admin:ai.role.storyteller_en', 'Storyteller — English players'),
  storyteller_el: t('admin:ai.role.storyteller_el', 'Storyteller — Greek players'),
  utility: t('admin:ai.role.utility', 'Utility (quick dice/combat answers)'),
  classifier: t('admin:ai.role.classifier', 'Classifier fallback (OOC check when Laya/Jev are not used)'),
});

export const providerLabels = () => ({
  lm_studio: t('admin:ai.provider.lm_studio', 'LM Studio (local)'),
  ollama: t('admin:ai.provider.ollama', 'Ollama (local)'),
  anthropic: t('admin:ai.provider.anthropic', 'Anthropic (cloud, API key)'),
  openai: t('admin:ai.provider.openai', 'OpenAI (cloud, API key)'),
});

function AiTestResult({ result }) {
  if (!result) return null;
  return (
    <span data-testid="ai-test-result" className={`sr-admin__result ${result.ok ? 'is-ok' : 'is-warn'}`}>
      {result.ok ? t('admin:ai.test.ok', 'OK') : t('admin:ai.test.failed', 'Failed')}
      {result.ms != null ? ` (${result.ms} ms)` : ''}: {result.detail || (result.result ? JSON.stringify(result.result) : '')}
    </span>
  );
}

/** Write-only API key field: shows the masked tail, never the key. */
function AiKeyField({ label, status, draft, onDraft, onSave, onRemove, onTest, testResult, busy }) {
  const set = !!(status && status.set);
  return (
    <div className="sr-admin__group">
      <div className="sr-admin__group-title">
        {label}{' '}
        <span className={set ? 'sr-admin__ok' : 'sr-admin__muted'}>
          {set ? t('admin:ai.key.set', 'key set {{masked}}', { masked: status.masked }) : t('admin:ai.key.none', 'no key (off)')}
        </span>
      </div>
      <div className="sr-admin__row">
        <input
          type="password"
          autoComplete="new-password"
          className="sr-input sr-admin__grow"
          aria-label={t('admin:ai.key.inputLabel', '{{name}} API key', { name: label })}
          placeholder={set ? t('admin:ai.key.replace', 'Enter a new key to replace') : t('admin:ai.key.paste', 'Paste API key')}
          value={draft}
          onChange={(e) => onDraft(e.target.value)}
        />
        <Button size="sm" disabled={busy || !draft.trim()} onClick={onSave}>
          {t('admin:ai.key.save', 'Save key')}
        </Button>
        <Button size="sm" disabled={busy || !set} onClick={onRemove}>
          {t('admin:ai.key.remove', 'Remove')}
        </Button>
        {onTest && (
          <Button size="sm" variant="ghost" disabled={busy} onClick={onTest}>
            {t('admin:ai.key.test', 'Test connection')}
          </Button>
        )}
      </div>
      <AiTestResult result={testResult} />
    </div>
  );
}

export default function AiProvidersPanel({ token, lmModels, showSuccess, showError }) {
  const [data, setData] = useState(null);
  const [roles, setRoles] = useState({});
  const [classifierChoice, setClassifierChoice] = useState('auto');
  const [jevModel, setJevModel] = useState('');
  const [keyDrafts, setKeyDrafts] = useState({ anthropic: '', openai: '', jev: '' });
  const [tests, setTests] = useState({});
  const [classifierText, setClassifierText] = useState('*draws her knife and hisses at the Prince*');
  const [emb, setEmb] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const r = await api.getAiProviders(token);
      const d = await r.json().catch(() => null);
      if (!r.ok || !d) {
        showError((d && d.error) || t('admin:ai.error.load', 'Could not load AI providers'));
        return;
      }
      setData(d);
      const rs = {};
      Object.entries(d.roles || {}).forEach(([k, v]) => { rs[k] = { provider: v.provider, model: v.model || '' }; });
      setRoles(rs);
      setClassifierChoice((d.classifier && d.classifier.configured) || 'auto');
      setJevModel((d.classifier && d.classifier.jev && d.classifier.jev.model) || '');
    } catch {
      showError(t('admin:ai.error.load', 'Could not load AI providers'));
    }
    try {
      const r2 = await api.getEmbeddings(token);
      setEmb(await r2.json().catch(() => null));
    } catch {
      setEmb({ error: t('admin:ai.error.chroma', 'ChromaDB unavailable') });
    }
  };

  useEffect(() => { load(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const put = async (payload, okMsg) => {
    setBusy(true);
    try {
      const r = await api.putAiProviders(token, payload);
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(okMsg);
        await load();
        return true;
      }
      showError(d.error || t('admin:error.saveFailed', 'Save failed'));
    } catch {
      showError(t('admin:error.saveFailed', 'Save failed'));
    } finally {
      setBusy(false);
    }
    return false;
  };

  const saveKey = async (name, value) => {
    const msg = value === null ? t('admin:ai.key.removed', 'Key removed.') : t('admin:ai.key.saved', 'Key saved (stored encrypted).');
    if (await put({ keys: { [name]: value } }, msg)) {
      setKeyDrafts((k) => ({ ...k, [name]: '' }));
    }
  };

  const testing = () => ({ ok: false, detail: t('admin:ai.test.testing', 'testing…') });
  const badResponse = () => ({ ok: false, detail: t('admin:ai.test.badResponse', 'bad response') });

  const testProvider = async (provider) => {
    setTests((prev) => ({ ...prev, [provider]: testing() }));
    try {
      const model = Object.values(roles).find((r) => r.provider === provider && r.model)?.model || '';
      const r = await api.testAiProvider(token, provider, model);
      const d = await r.json().catch(badResponse);
      setTests((prev) => ({ ...prev, [provider]: d }));
    } catch (e) {
      setTests((prev) => ({ ...prev, [provider]: { ok: false, detail: String(e) } }));
    }
  };

  const testClassifier = async (provider) => {
    const key = `classifier_${provider}`;
    setTests((prev) => ({ ...prev, [key]: testing() }));
    try {
      const r = await api.testClassifier(token, provider, classifierText);
      const d = await r.json().catch(badResponse);
      setTests((prev) => ({ ...prev, [key]: d }));
    } catch (e) {
      setTests((prev) => ({ ...prev, [key]: { ok: false, detail: String(e) } }));
    }
  };

  const runReembed = async (force) => {
    setBusy(true);
    try {
      const r = await api.reembed(token, force);
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        const n = (d.rebuilt || []).length;
        showSuccess(
          n
            ? t('admin:ai.emb.rebuilt', { one: 'Re-embedded {{count}} collection with {{model}}.', other: 'Re-embedded {{count}} collections with {{model}}.' }, { count: n, model: d.model })
            : t('admin:ai.emb.allCurrent', 'All collections already use the current embedder.')
        );
        await load();
      } else {
        showError(d.error || t('admin:ai.emb.failed', 'Re-embed failed'));
      }
    } catch {
      showError(t('admin:ai.emb.failed', 'Re-embed failed'));
    } finally {
      setBusy(false);
    }
  };

  if (!data) return <p className="sr-admin__muted">{t('admin:ai.loadingProviders', 'Loading AI providers…')}</p>;
  const keys = data.cloud_keys || {};
  const cls = data.classifier || {};
  const laya = cls.laya || {};
  const ROLE_LABELS = roleLabels();
  const PROVIDER_LABELS = providerLabels();

  return (
    <div data-testid="ai-providers-panel" className="sr-admin__stack">
      <Panel title={t('admin:ai.roles.title', 'Models per role')} className="sr-admin__panel">
        <p className="sr-admin__muted">
          {t('admin:ai.roles.body', 'Greek messages go to the Greek Storyteller, everything else to the English one. If a cloud provider fails, the backend falls back to the local model. Leave the model empty for the default shown.')}
        </p>
        <datalist id="ai-lm-models">
          {(lmModels || []).map((m) => <option key={m.id} value={m.id} />)}
        </datalist>
        {Object.keys(ROLE_LABELS).map((role) => {
          const info = (data.roles || {})[role] || {};
          const cur = roles[role] || { provider: 'lm_studio', model: '' };
          const defaultModel = (info.default && info.default.model) || (data.default_models || {})[cur.provider] || t('admin:ai.roles.loadedModel', 'loaded LM Studio model');
          return (
            <div key={role} className="sr-admin__group">
              <div className="sr-admin__group-title">{ROLE_LABELS[role]}</div>
              <div className="sr-admin__row">
                <select
                  aria-label={t('admin:ai.roles.providerLabel', '{{role}}: provider', { role: ROLE_LABELS[role] })}
                  value={cur.provider}
                  onChange={(e) => setRoles((r) => ({ ...r, [role]: { ...cur, provider: e.target.value } }))}
                  className="sr-input sr-admin__select"
                >
                  {(data.providers || []).map((p) => {
                    const needsKey = p === 'anthropic' || p === 'openai';
                    const off = needsKey && !(keys[p] && keys[p].set);
                    return (
                      <option key={p} value={p} disabled={off}>
                        {PROVIDER_LABELS[p] || p}{off ? t('admin:ai.roles.needsKey', ' — add a key first') : ''}
                      </option>
                    );
                  })}
                </select>
                <input
                  aria-label={t('admin:ai.roles.modelLabel', '{{role}}: model', { role: ROLE_LABELS[role] })}
                  list={cur.provider === 'lm_studio' ? 'ai-lm-models' : undefined}
                  value={cur.model}
                  placeholder={t('admin:ai.roles.defaultModel', 'default: {{model}}', { model: defaultModel })}
                  onChange={(e) => setRoles((r) => ({ ...r, [role]: { ...cur, model: e.target.value } }))}
                  className="sr-input sr-admin__grow"
                />
              </div>
              <p className="sr-admin__muted">
                {t('admin:ai.roles.inUse', 'In use: {{chain}}', {
                  chain: (info.chain || []).map((c) => `${c.provider}/${c.model || t('admin:ai.roles.default', 'default')}`).join(' → ') || '—',
                })}
              </p>
            </div>
          );
        })}
        <div className="sr-admin__row">
          <Button variant="primary" size="sm" disabled={busy} onClick={() => put({ roles }, t('admin:ai.roles.saved', 'Model roles saved.'))}>
            {t('admin:ai.roles.save', 'Save roles')}
          </Button>
          <Button size="sm" disabled={busy} onClick={() => testProvider('lm_studio')}>{t('admin:ai.roles.testLm', 'Test LM Studio')}</Button>
          <Button size="sm" disabled={busy} onClick={() => testProvider('ollama')}>{t('admin:ai.roles.testOllama', 'Test Ollama')}</Button>
          <AiTestResult result={tests.lm_studio} />
          <AiTestResult result={tests.ollama} />
        </div>
      </Panel>

      <Panel title={t('admin:ai.cloud.title', 'Cloud providers (optional)')} className="sr-admin__panel">
        <p className="sr-admin__muted">
          {t('admin:ai.cloud.body', 'Off until a key is saved and a role uses the provider. Keys are stored encrypted on the server and are never sent back to the browser; only the last 4 characters are shown.')}
        </p>
        {['anthropic', 'openai'].map((p) => (
          <AiKeyField
            key={p}
            label={PROVIDER_LABELS[p]}
            status={keys[p]}
            draft={keyDrafts[p]}
            onDraft={(v) => setKeyDrafts((k) => ({ ...k, [p]: v }))}
            onSave={() => saveKey(p, keyDrafts[p])}
            onRemove={() => saveKey(p, null)}
            onTest={() => testProvider(p)}
            testResult={tests[p]}
            busy={busy}
          />
        ))}
      </Panel>

      <Panel title={t('admin:ai.classifier.title', 'Message classifier (OOC monitor + intent)')} className="sr-admin__panel">
        <p className="sr-admin__muted">
          {t('admin:ai.classifier.inUse', 'In use:')} <strong className="sr-admin__strong">{cls.active}</strong>.{' '}
          {laya.available
            ? t('admin:ai.classifier.layaInstalled', 'Laya: installed.')
            : t('admin:ai.classifier.layaMissing', 'Laya: not available ({{reason}}).', { reason: laya.reason || t('admin:ai.classifier.noModel', 'no model') })}{' '}
          {t('admin:ai.classifier.threshold', 'OOC warning threshold: P(in character) ≥ {{value}}.', { value: cls.ooc_threshold })}
        </p>
        <div className="sr-admin__row">
          <select
            aria-label={t('admin:ai.classifier.providerLabel', 'Classifier provider')}
            value={classifierChoice}
            onChange={(e) => setClassifierChoice(e.target.value)}
            className="sr-input sr-admin__select"
          >
            <option value="auto">{t('admin:ai.classifier.auto', 'Auto (Laya if installed, else LLM prompt)')}</option>
            <option value="laya">{t('admin:ai.classifier.laya', 'Laya (local)')}</option>
            <option value="jev">{t('admin:ai.classifier.jev', 'Typesafe Jev (hosted, API key)')}</option>
            <option value="llm">{t('admin:ai.classifier.llm', 'LLM prompt (classifier role)')}</option>
          </select>
          <input
            aria-label={t('admin:ai.classifier.jevModel', 'Jev model')}
            value={jevModel}
            placeholder="jev-latest"
            onChange={(e) => setJevModel(e.target.value)}
            className="sr-input sr-admin__select"
          />
          <Button
            variant="primary"
            size="sm"
            disabled={busy}
            onClick={() => put({ classifier_provider: classifierChoice, jev_model: jevModel }, t('admin:ai.classifier.saved', 'Classifier settings saved.'))}
          >
            {t('admin:ai.classifier.save', 'Save classifier')}
          </Button>
        </div>
        <AiKeyField
          label="Typesafe Jev"
          status={cls.jev && cls.jev.key}
          draft={keyDrafts.jev}
          onDraft={(v) => setKeyDrafts((k) => ({ ...k, jev: v }))}
          onSave={() => saveKey('jev', keyDrafts.jev)}
          onRemove={() => saveKey('jev', null)}
          busy={busy}
        />
        <div className="sr-admin__row">
          <input
            aria-label={t('admin:ai.classifier.testText', 'Classifier test text')}
            value={classifierText}
            onChange={(e) => setClassifierText(e.target.value)}
            className="sr-input sr-admin__grow"
          />
          {['laya', 'jev', 'llm'].map((p) => (
            <Button key={p} size="sm" disabled={busy} onClick={() => testClassifier(p)}>
              {t('admin:ai.classifier.test', 'Test {{name}}', { name: p })}
            </Button>
          ))}
        </div>
        {['laya', 'jev', 'llm'].map((p) => tests[`classifier_${p}`] && (
          <div key={p}><strong className="sr-admin__strong">{p}: </strong><AiTestResult result={tests[`classifier_${p}`]} /></div>
        ))}
      </Panel>

      <Panel title={t('admin:ai.emb.title', 'Embeddings (RAG memory)')} className="sr-admin__panel">
        {emb && emb.error && !emb.collections ? (
          <p className="sr-admin__warn">{emb.error}</p>
        ) : emb ? (
          <>
            <p className="sr-admin__muted">
              {t('admin:ai.emb.model', 'Model')} <code className="sr-admin__code">{emb.model}</code>{' '}
              {t('admin:ai.emb.dims', '({{dims}} dims), set with', { dims: emb.dimension || '?' })}{' '}
              <code className="sr-admin__code">EMBEDDING_MODEL</code>. {t('admin:ai.emb.changeNeedsReembed', 'Changing it needs a re-embed.')}
              {emb.embedder_error ? ` ${t('admin:ai.emb.embedderError', 'Embedder error: {{error}}', { error: emb.embedder_error })}` : ''}
            </p>
            <div className="sr-admin__tablewrap">
              <table className="sr-admin__table">
                <thead>
                  <tr>
                    <th>{t('admin:ai.emb.col.collection', 'Collection')}</th>
                    <th>{t('admin:ai.emb.col.items', 'Items')}</th>
                    <th>{t('admin:ai.emb.col.model', 'Model')}</th>
                    <th>{t('admin:ai.emb.col.dims', 'Dims')}</th>
                    <th>{t('admin:ai.emb.col.status', 'Status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(emb.collections || []).map((c) => (
                    <tr key={c.name}>
                      <td>{c.name}</td><td>{c.count}</td><td>{c.embedding_model || '—'}</td><td>{c.embedding_dim || '—'}</td>
                      <td className={c.needs_reembed ? 'sr-admin__warn' : 'sr-admin__ok'}>
                        {c.needs_reembed
                          ? t('admin:ai.emb.needsReembed', 'needs re-embed ({{reasons}})', { reasons: (c.reasons || []).join(', ') })
                          : t('admin:ai.emb.current', 'current')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="sr-admin__muted">{t('admin:loading', 'Loading…')}</p>
        )}
        <div className="sr-admin__row">
          <Button variant="primary" size="sm" disabled={busy} onClick={() => runReembed(false)}>{t('admin:ai.emb.reembedStale', 'Re-embed stale collections')}</Button>
          <Button size="sm" disabled={busy} onClick={() => runReembed(true)}>{t('admin:ai.emb.reembedAll', 'Re-embed everything')}</Button>
        </div>
      </Panel>
    </div>
  );
}

