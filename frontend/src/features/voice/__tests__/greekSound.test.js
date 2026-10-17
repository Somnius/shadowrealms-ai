import { greekToEnglishSound, greekWordsForEnglish } from '../greekSound';

test('Greek names become sounds an English voice can say (same rules as the speech server)', () => {
  expect(greekToEnglishSound('Κωνσταντίνος')).toBe('Konstandeenos');
  expect(greekToEnglishSound('Κατακουζηνός')).toBe('Katakoozeenos');
  expect(greekToEnglishSound('Γιώργος')).toBe('Yorgos');
  expect(greekToEnglishSound('Παναγιώτης')).toBe('Panayotees');
  expect(greekToEnglishSound('Ευάγγελος')).toBe('Evangelos');
  expect(greekToEnglishSound('Λευτέρης')).toBe('Lefterees');
  expect(greekToEnglishSound('Μπουράκ')).toBe('Boorak');
  expect(greekToEnglishSound('Ιωάννης')).toBe('Yoannees');
  expect(greekWordsForEnglish('Κωνσταντίνος: Roll 2 dice.')).toBe('Konstandeenos: Roll 2 dice.');
});
