import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import setupUser from '../testing/setupUser';
import Tabs from '../components/Tabs';
import { Input, Select, Checkbox, Switch } from '../components/Fields';
import { Avatar, Badge, Divider } from '../components/Surface';

const TABS = [
  { id: 'a', label: 'Attributes', content: <p>Attr panel</p> },
  { id: 'b', label: 'Skills', content: <p>Skills panel</p>, disabled: true },
  { id: 'c', label: 'Notes', content: <p>Notes panel</p> },
];

test('Tabs use roving tabindex and arrow keys (skipping disabled tabs)', async () => {
  const user = setupUser();
  render(<Tabs label="Sheet" tabs={TABS} />);
  expect(screen.getByRole('tablist', { name: 'Sheet' })).toBeInTheDocument();
  const first = screen.getByRole('tab', { name: 'Attributes' });
  expect(first).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Attr panel');
  await user.tab();
  expect(first).toHaveFocus();
  await user.keyboard('{ArrowRight}');
  const notes = screen.getByRole('tab', { name: 'Notes' });
  expect(notes).toHaveFocus();
  expect(notes).toHaveAttribute('aria-selected', 'true');
  expect(first).toHaveAttribute('tabindex', '-1');
  expect(screen.getByRole('tabpanel', { name: 'Notes' })).toHaveTextContent('Notes panel');
  await user.keyboard('{Home}');
  expect(first).toHaveFocus();
});

test('Input wires label, hint and error', () => {
  render(<Input label="Email" hint="We never share it" error="Already taken" required />);
  const input = screen.getByLabelText(/Email/);
  expect(input).toHaveAttribute('aria-invalid', 'true');
  expect(input).toBeRequired();
  expect(input).toHaveAccessibleDescription('We never share it Already taken');
});

test('Select, Checkbox and Switch are labelled and operable', async () => {
  const user = setupUser();
  function S() {
    const [on, setOn] = useState(false);
    return <Switch label="Hidden roll" checked={on} onChange={setOn} />;
  }
  render(
    <>
      <Select label="Clan" options={[{ value: 'b', label: 'Brujah' }, { value: 'g', label: 'Gangrel' }]} defaultValue="b" />
      <Checkbox label="Specialty" />
      <S />
    </>
  );
  await user.selectOptions(screen.getByLabelText('Clan'), 'g');
  expect(screen.getByLabelText('Clan')).toHaveValue('g');
  await user.click(screen.getByLabelText('Specialty'));
  expect(screen.getByLabelText('Specialty')).toBeChecked();
  const sw = screen.getByRole('switch', { name: 'Hidden roll' });
  expect(sw).toHaveAttribute('aria-checked', 'false');
  await user.click(sw);
  expect(sw).toHaveAttribute('aria-checked', 'true');
});

test('Avatar falls back to a named sigil, Badge shows counts and editions, Divider is a separator', () => {
  render(
    <>
      <Avatar name="Lucita Vey" />
      <Badge count={120} />
      <Badge edition="V5" tone="blood" />
      <Divider />
    </>
  );
  expect(screen.getByRole('img', { name: 'Lucita Vey' })).toHaveTextContent('LV');
  expect(screen.getByText('99+')).toBeInTheDocument();
  expect(screen.getByText('V5')).toBeInTheDocument();
  expect(screen.getByRole('separator')).toBeInTheDocument();
});
