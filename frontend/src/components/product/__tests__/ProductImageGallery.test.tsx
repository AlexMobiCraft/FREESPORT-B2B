/**
 * Unit тесты для ProductImageGallery (Story 12.1 - QA Fix UX-001)
 * Тестирует функциональность zoom/lightbox галереи изображений
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ProductImageGallery from '../ProductImageGallery';
import type { ProductImage } from '@/types/api';

// Mock Next.js Image component
vi.mock('next/image', () => ({
  default: ({
    src,
    alt,
    fill,
    priority,
    className,
  }: {
    src: string;
    alt: string;
    fill?: boolean;
    priority?: boolean;
    className?: string;
  }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} data-fill={fill} data-priority={priority} className={className} />
  ),
}));

const mockImages: ProductImage[] = [
  {
    id: 1,
    image: 'https://example.com/image1.jpg',
    alt_text: 'Product view 1',
    is_primary: true,
  },
  {
    id: 2,
    image: 'https://example.com/image2.jpg',
    alt_text: 'Product view 2',
    is_primary: false,
  },
  {
    id: 3,
    image: 'https://example.com/image3.jpg',
    alt_text: 'Product view 3',
    is_primary: false,
  },
];

describe('ProductImageGallery', () => {
  it('должен отобразить основное изображение', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    const images = screen.getAllByAltText('Product view 1');
    expect(images.length).toBeGreaterThan(0);
    expect(images[0]).toHaveAttribute('src', 'https://example.com/image1.jpg');
  });

  it('должен отобразить thumbnails когда больше одного изображения', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    const thumbnails = screen.getAllByRole('button', { name: /Показать изображение/i });
    expect(thumbnails).toHaveLength(3);
  });

  it('НЕ должен отображать thumbnails когда только одно изображение', () => {
    const singleImage = [mockImages[0]];
    render(<ProductImageGallery images={singleImage} productName="Test Product" />);

    const thumbnails = screen.queryAllByRole('button', { name: /Показать изображение/i });
    expect(thumbnails).toHaveLength(0);
  });

  it('должен переключать изображения при клике на thumbnail', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Изначально показано первое изображение
    const initialImages = screen.getAllByAltText('Product view 1');
    expect(initialImages.length).toBeGreaterThan(0);

    // Кликаем на второй thumbnail
    const secondThumbnail = screen.getByRole('button', { name: 'Показать изображение 2' });
    fireEvent.click(secondThumbnail);

    // Проверяем что второе изображение стало главным
    const images = screen.getAllByAltText('Product view 2');
    expect(images.length).toBeGreaterThan(0);
  });

  it('должен открывать lightbox при клике на основное изображение', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Находим контейнер с курсором zoom-in
    const zoomableContainer = document.querySelector('.cursor-zoom-in');
    expect(zoomableContainer).toBeInTheDocument();

    // Кликаем на изображение
    if (zoomableContainer) {
      fireEvent.click(zoomableContainer);
    }

    // Проверяем что lightbox открылся
    const closeButton = screen.getByLabelText('Закрыть');
    expect(closeButton).toBeInTheDocument();
  });

  it('должен закрывать lightbox при клике на кнопку закрытия', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Открываем lightbox
    const zoomableContainer = document.querySelector('.cursor-zoom-in');
    if (zoomableContainer) {
      fireEvent.click(zoomableContainer);
    }

    // Проверяем что lightbox открыт
    expect(screen.getByLabelText('Закрыть')).toBeInTheDocument();

    // Кликаем на кнопку закрытия
    const closeButton = screen.getByLabelText('Закрыть');
    fireEvent.click(closeButton);

    // Проверяем что lightbox закрылся
    expect(screen.queryByLabelText('Закрыть')).not.toBeInTheDocument();
  });

  it('должен закрывать lightbox при клике на overlay', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Открываем lightbox
    const zoomableContainer = document.querySelector('.cursor-zoom-in');
    if (zoomableContainer) {
      fireEvent.click(zoomableContainer);
    }

    // Находим overlay (контейнер с bg-black/90)
    const overlay = document.querySelector('.bg-black\\/90');
    expect(overlay).toBeInTheDocument();

    // Кликаем на overlay
    if (overlay) {
      fireEvent.click(overlay);
    }

    // Проверяем что lightbox закрылся
    expect(screen.queryByLabelText('Закрыть')).not.toBeInTheDocument();
  });

  it('должен показывать навигационные кнопки в lightbox когда больше одного изображения', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Открываем lightbox
    const zoomableContainer = document.querySelector('.cursor-zoom-in');
    if (zoomableContainer) {
      fireEvent.click(zoomableContainer);
    }

    // Проверяем наличие кнопок навигации
    expect(screen.getByLabelText('Предыдущее изображение')).toBeInTheDocument();
    expect(screen.getByLabelText('Следующее изображение')).toBeInTheDocument();
  });

  it('должен показывать счетчик изображений в lightbox', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Открываем lightbox
    const zoomableContainer = document.querySelector('.cursor-zoom-in');
    if (zoomableContainer) {
      fireEvent.click(zoomableContainer);
    }

    // Проверяем счетчик
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });

  it('должен переключаться на следующее изображение в lightbox', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Открываем lightbox
    const zoomableContainer = document.querySelector('.cursor-zoom-in');
    if (zoomableContainer) {
      fireEvent.click(zoomableContainer);
    }

    // Проверяем начальный счетчик
    expect(screen.getByText('1 / 3')).toBeInTheDocument();

    // Кликаем на "Следующее"
    const nextButton = screen.getByLabelText('Следующее изображение');
    fireEvent.click(nextButton);

    // Проверяем что счетчик обновился
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
  });

  it('должен переключаться на предыдущее изображение в lightbox', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Открываем lightbox
    const zoomableContainer = document.querySelector('.cursor-zoom-in');
    if (zoomableContainer) {
      fireEvent.click(zoomableContainer);
    }

    // Кликаем на "Предыдущее" (должно перейти к последнему изображению)
    const prevButton = screen.getByLabelText('Предыдущее изображение');
    fireEvent.click(prevButton);

    // Проверяем что перешли к последнему изображению
    expect(screen.getByText('3 / 3')).toBeInTheDocument();
  });

  it('должен показывать placeholder когда нет изображений', () => {
    render(<ProductImageGallery images={[]} productName="Test Product" />);

    expect(screen.getByText('Изображение отсутствует')).toBeInTheDocument();
  });

  it('должен использовать is_primary для начального изображения', () => {
    const imagesWithPrimary: ProductImage[] = [
      { id: 1, image: 'image1.jpg', alt_text: 'Image 1', is_primary: false },
      { id: 2, image: 'image2.jpg', alt_text: 'Image 2', is_primary: true },
      { id: 3, image: 'image3.jpg', alt_text: 'Image 3', is_primary: false },
    ];

    render(<ProductImageGallery images={imagesWithPrimary} productName="Test Product" />);

    // Основным должно быть изображение с is_primary: true
    const mainImages = screen.getAllByAltText('Image 2');
    expect(mainImages.length).toBeGreaterThan(0);
  });

  it('должен предотвращать закрытие lightbox при клике на изображение', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Открываем lightbox
    const zoomableContainer = document.querySelector('.cursor-zoom-in');
    if (zoomableContainer) {
      fireEvent.click(zoomableContainer);
    }

    // Находим изображение внутри lightbox
    const lightboxImages = screen.getAllByAltText('Product view 1');
    const lightboxImage = lightboxImages[lightboxImages.length - 1]; // Последнее - в lightbox

    // Кликаем на изображение (не должно закрыть lightbox)
    fireEvent.click(lightboxImage.closest('div')!);

    // Lightbox все еще открыт
    expect(screen.getByLabelText('Закрыть')).toBeInTheDocument();
  });

  it('должен корректно обрабатывать навигацию по кругу (последнее -> первое)', () => {
    render(<ProductImageGallery images={mockImages} productName="Test Product" />);

    // Открываем lightbox
    const zoomableContainer = document.querySelector('.cursor-zoom-in');
    if (zoomableContainer) {
      fireEvent.click(zoomableContainer);
    }

    // Переходим к последнему изображению
    const nextButton = screen.getByLabelText('Следующее изображение');
    fireEvent.click(nextButton); // -> 2
    fireEvent.click(nextButton); // -> 3

    expect(screen.getByText('3 / 3')).toBeInTheDocument();

    // Еще раз кликаем "Следующее" - должно вернуться к первому
    fireEvent.click(nextButton); // -> 1

    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });
});
