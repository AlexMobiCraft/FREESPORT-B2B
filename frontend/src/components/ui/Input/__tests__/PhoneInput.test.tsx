import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PhoneInput } from '../PhoneInput';

describe('PhoneInput', () => {
  it('без страны работает как российское поле: +7 и 10 цифр', async () => {
    const user = userEvent.setup();
    render(<PhoneInput label="Телефон" />);
    const input = screen.getByLabelText('Телефон');

    expect(input).toHaveAttribute('placeholder', '+79001234567');
    await user.type(input, '900123456799');

    expect(input).toHaveValue('+79001234567');
  });

  it('для Беларуси подставляет +375 и ограничивает 9 цифрами', async () => {
    const user = userEvent.setup();
    render(<PhoneInput label="Телефон" country="Беларусь" />);
    const input = screen.getByLabelText('Телефон');

    expect(input).toHaveAttribute('placeholder', '+375291234567');
    await user.type(input, '29123456799');

    expect(input).toHaveValue('+375291234567');
  });

  it('префикс нельзя стереть', async () => {
    const user = userEvent.setup();
    render(<PhoneInput label="Телефон" country="Беларусь" />);
    const input = screen.getByLabelText('Телефон');

    await user.type(input, '29');
    await user.type(input, '{backspace}{backspace}{backspace}{backspace}{backspace}{backspace}');

    expect(input).toHaveValue('+375');
  });

  it('вставка 8900… превращается в +7900…', () => {
    render(<PhoneInput label="Телефон" />);
    const input = screen.getByLabelText('Телефон');

    fireEvent.change(input, { target: { value: '89001234567' } });

    expect(input).toHaveValue('+79001234567');
  });

  it('не пробрасывает country в DOM', () => {
    render(<PhoneInput label="Телефон" country="Беларусь" />);

    expect(screen.getByLabelText('Телефон')).not.toHaveAttribute('country');
  });
});
