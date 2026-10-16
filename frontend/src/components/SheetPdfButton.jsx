import { useState } from 'react';
import { Button, useOptionalToast } from '../design';
import { downloadSheetPdf } from '../app/sheetPdf';
import { t } from '../i18n';
import './sheet.css';

/**
 * The character's PDF sheet, two ways: the fillable one (edit in a PDF app) and the print version
 * (values drawn as page text, looks the same in every viewer: the one to share).
 */
export default function SheetPdfButton({ character, size = 'sm', variant = 'ghost' }) {
  const toaster = useOptionalToast();
  const [busy, setBusy] = useState('');
  if (!character || character.id == null) return null;
  const run = async (kind) => {
    setBusy(kind);
    const failed = () => {
      if (toaster) toaster.toast({ tone: 'danger', title: t('sheet:pdf.failed', 'Could not export the PDF.') });
    };
    try {
      const r = await downloadSheetPdf(character.id, character.name, { flat: kind === 'print' });
      if (!r.ok) failed();
    } catch {
      failed();
    } finally {
      setBusy('');
    }
  };
  return (
    <>
      <Button size={size} variant={variant} icon="book" loading={busy === 'fill'} disabled={!!busy} onClick={() => run('fill')}
        title={t('sheet:pdf.hint', 'Fillable sheet for black-and-white printing')}>
        {t('sheet:pdf.export', 'Export PDF')}
      </Button>
      <Button size={size} variant={variant} icon="scroll" loading={busy === 'print'} disabled={!!busy} onClick={() => run('print')}
        title={t('sheet:pdf.printHint', 'Looks the same in every PDF viewer; not fillable')}>
        {t('sheet:pdf.print', 'Download print version')}
      </Button>
      <span className="sr-muted sr-sheet-pdf__note">
        {t('sheet:pdf.which', 'Print version: looks the same everywhere, share this one. Fillable: edit in a PDF app.')}
      </span>
    </>
  );
}
