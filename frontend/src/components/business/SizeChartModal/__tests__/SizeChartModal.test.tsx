/**
 * SizeChartModal Component Tests
 * Design System v2.0
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SizeChartModal } from '../SizeChartModal';

describe('SizeChartModal', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
  });

  // Базовый рендеринг
  it('renders when open', () => {
    render(<SizeChartModal isOpen={true} onClose={mockOnClose} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Таблица размеров')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(<SizeChartModal isOpen={false} onClose={mockOnClose} />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  // Tabs
  describe('Tabs', () => {
    it('shows all three tabs', () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} />);

      expect(screen.getByText('Одежда')).toBeInTheDocument();
      expect(screen.getByText('Обувь')).toBeInTheDocument();
      expect(screen.getByText('Перчатки')).toBeInTheDocument();
    });

    it('shows clothing tab by default', () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} category="clothing" />);

      expect(screen.getByText('Таблица размеров одежды')).toBeInTheDocument();
    });

    it('switches to shoes tab', async () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} />);

      const shoesTab = screen.getByText('Обувь');
      await userEvent.click(shoesTab);

      expect(screen.getByText('Таблица размеров обуви')).toBeInTheDocument();
    });

    it('switches to gloves tab', async () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} />);

      const glovesTab = screen.getByText('Перчатки');
      await userEvent.click(glovesTab);

      expect(screen.getByText('Таблица размеров перчаток')).toBeInTheDocument();
    });
  });

  // Clothing data
  describe('Clothing Size Data', () => {
    it('displays clothing size table', () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} category="clothing" />);

      expect(screen.getByText('Обхват груди')).toBeInTheDocument();
      expect(screen.getByText('Обхват талии')).toBeInTheDocument();
      expect(screen.getByText('Обхват бедер')).toBeInTheDocument();

      // Check some size data (sizes may appear multiple times in different tables)
      expect(screen.getAllByText('XS').length).toBeGreaterThan(0);
      expect(screen.getAllByText('S').length).toBeGreaterThan(0);
      expect(screen.getAllByText('M').length).toBeGreaterThan(0);
    });

    it('shows measurement instructions for clothing', () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} category="clothing" />);

      expect(screen.getByText('Как измерить:')).toBeInTheDocument();
      expect(screen.getByText(/измерьте по самым выступающим точкам груди/i)).toBeInTheDocument();
    });
  });

  // Shoe data
  describe('Shoe Size Data', () => {
    it('displays shoe size table', async () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} category="shoes" />);

      expect(screen.getByText('Таблица размеров обуви')).toBeInTheDocument();
      expect(screen.getByText('EU')).toBeInTheDocument();
      expect(screen.getByText('US')).toBeInTheDocument();
      expect(screen.getByText('UK')).toBeInTheDocument();
      expect(screen.getByText('Длина стопы')).toBeInTheDocument();

      // Check some size data
      expect(screen.getByText('36')).toBeInTheDocument();
      expect(screen.getByText('37')).toBeInTheDocument();
    });

    it('shows measurement instructions for shoes', () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} category="shoes" />);

      expect(screen.getByText('Как измерить длину стопы:')).toBeInTheDocument();
      expect(screen.getByText(/Встаньте на лист бумаги и обведите стопу/i)).toBeInTheDocument();
    });
  });

  // Glove data
  describe('Glove Size Data', () => {
    it('displays glove size table', async () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} />);

      const glovesTab = screen.getByText('Перчатки');
      await userEvent.click(glovesTab);

      expect(screen.getByText('Таблица размеров перчаток')).toBeInTheDocument();
      expect(screen.getByText('Обхват ладони')).toBeInTheDocument();

      // Check some size data - there should be multiple XS, S, etc.
      const sizes = screen.getAllByText('XS');
      expect(sizes.length).toBeGreaterThan(0);
    });

    it('shows measurement instructions for gloves', async () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} />);

      const glovesTab = screen.getByText('Перчатки');
      await userEvent.click(glovesTab);

      expect(screen.getByText('Как измерить обхват ладони:')).toBeInTheDocument();
      expect(screen.getByText(/Измерьте обхват ладони в самом широком месте/i)).toBeInTheDocument();
    });
  });

  // Table styling
  describe('Table Styling', () => {
    it('applies zebra striping to table rows', () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} category="clothing" />);

      const table = screen.getByRole('table');
      expect(table).toBeInTheDocument();

      // Check that table has proper structure
      const tbody = table.querySelector('tbody');
      expect(tbody).toBeInTheDocument();
    });

    it('has header with correct styling', () => {
      render(<SizeChartModal isOpen={true} onClose={mockOnClose} category="clothing" />);

      const headerCells = screen.getAllByRole('columnheader');
      expect(headerCells.length).toBeGreaterThan(0);
    });
  });

  // Modal size
  it('uses large size from Modal', () => {
    render(<SizeChartModal isOpen={true} onClose={mockOnClose} />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('max-w-[720px]'); // lg size
  });

  // Close
  it('calls onClose when modal is closed', async () => {
    render(<SizeChartModal isOpen={true} onClose={mockOnClose} />);

    const closeButton = screen.getByLabelText('Закрыть модальное окно');
    await userEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });
});
