import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import setupUser from '../testing/setupUser';
import DotTrack from '../components/DotTrack';

function Controlled(props) {
  const [v, setV] = useState(props.initial ?? 2);
  return <DotTrack label="Strength" value={v} onChange={setV} {...props} />;
}

describe('DotTrack', () => {
  test('is a labelled slider operable from the keyboard', async () => {
    const user = setupUser();
    render(<Controlled />);
    const slider = screen.getByRole('slider', { name: 'Strength' });
    expect(slider).toHaveAttribute('aria-valuenow', '2');
    expect(slider).toHaveAttribute('aria-valuetext', '2 of 5');

    await user.tab();
    expect(slider).toHaveFocus();
    await user.keyboard('{ArrowRight}');
    expect(slider).toHaveAttribute('aria-valuenow', '3');
    await user.keyboard('{ArrowUp}{ArrowUp}{ArrowUp}'); // clamps at max
    expect(slider).toHaveAttribute('aria-valuenow', '5');
    await user.keyboard('{Home}');
    expect(slider).toHaveAttribute('aria-valuenow', '0');
    await user.keyboard('{End}');
    expect(slider).toHaveAttribute('aria-valuenow', '5');
    await user.keyboard('4');
    expect(slider).toHaveAttribute('aria-valuenow', '4');
    await user.keyboard('{ArrowLeft}{ArrowDown}');
    expect(slider).toHaveAttribute('aria-valuenow', '2');
  });

  test('locked dots set the floor', async () => {
    const user = setupUser();
    render(<Controlled initial={3} locked={2} />);
    const slider = screen.getByRole('slider', { name: 'Strength' });
    expect(slider).toHaveAttribute('aria-valuemin', '2');
    slider.focus();
    await user.keyboard('{Home}');
    expect(slider).toHaveAttribute('aria-valuenow', '2');
    await user.keyboard('{ArrowLeft}');
    expect(slider).toHaveAttribute('aria-valuenow', '2');
  });

  test('clicking a dot sets it; clicking the top filled dot clears it', () => {
    const { container } = render(<Controlled initial={2} />);
    const slider = screen.getByRole('slider');
    fireEvent.click(container.querySelector('[data-dot="4"]'));
    expect(slider).toHaveAttribute('aria-valuenow', '4');
    fireEvent.click(container.querySelector('[data-dot="4"]'));
    expect(slider).toHaveAttribute('aria-valuenow', '3');
    expect(container.querySelectorAll('.sr-dots__dot.is-filled')).toHaveLength(3);
  });

  test('read-only renders an image with the value in its name', () => {
    render(<DotTrack label="Blood Potency" value={2} max={10} readOnly />);
    expect(screen.getByRole('img', { name: 'Blood Potency: 2 of 10' })).toBeInTheDocument();
    expect(screen.queryByRole('slider')).toBeNull();
  });
});
