import { useState } from 'react';
import { Button, useOptionalToast } from '../design';
import { downloadSheetPdf } from '../app/sheetPdf';
import { t } from '../i18n';

/** Downloads the character's fillable, printer-friendly PDF sheet. */
export default function SheetPdfButton({ character, size = 'sm', variant = 'ghost' }) {
  const toaster = useOptionalToast();
  const [busy, setBusy] = useState(false);
  if (!character || character.id == null) return null;
  const run = async () => {
    setBusy(true);
    try {
      const r = await downloadSheetPdf(character.id, character.name);
      if (!r.ok && toaster) toaster.toast({ tone: 'danger', title: t('sheet:pdf.failed', 'Could not export the PDF.') });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button size={size} variant={variant} icon="book" loading={busy} onClick={run} title={t('sheet:pdf.hint', 'Fillable sheet for black-and-white printing')}>
      {t('sheet:pdf.export', 'Export PDF')}
    </Button>
  );
}
