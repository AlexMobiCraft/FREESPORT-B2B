/**
 * Unit tests for BrandsBlock & BrandCard components
 *
 * Story 33.3 Acceptance Criteria:
 * - AC1: Component renders carousel of brand logos from props
 * - AC2: Responsive carousel with swipe (embla-carousel)
 * - AC3: Image optimization with next/image object-contain
 * - AC4: Navigation to /catalog?brand={slug} on click
 * - AC5: Accessibility (keyboard nav, alt text)
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrandsBlock } from './BrandsBlock';
import type { Brand } from '@/types/api';

// Mock embla-carousel-react
const mockEmblaRef = vi.fn();
vi.mock('embla-carousel-react', () => ({
  default: vi.fn(() => [mockEmblaRef, null]),
}));

// Mock embla-carousel-autoplay
vi.mock('embla-carousel-autoplay', () => ({
  default: vi.fn(() => ({})),
}));

// Mock next/link
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// Mock next/image
vi.mock('next/image', () => ({
  default: (props: {
    src: string;
    alt: string;
    width?: number;
    height?: number;
    fill?: boolean;
    sizes?: string;
    className?: string;
    loading?: string;
    onError?: () => void;
  }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={props.src}
      alt={props.alt}
      data-sizes={props.sizes}
      data-fill={props.fill ? 'true' : undefined}
      className={props.className}
      onError={props.onError}
    />
  ),
}));

// Mock motion/react
vi.mock('motion/react', () => ({
  motion: {
    div: ({
      children,
      ...props
    }: {
      children?: React.ReactNode;
      [key: string]: unknown;
    }) => <div {...filterMotionProps(props)}>{children}</div>,
  },
}));

// Helper to filter motion-specific props that aren't valid HTML attributes
function filterMotionProps(props: Record<string, unknown>) {
  const htmlProps: Record<string, unknown> = {};
  const motionKeys = [
    'whileHover',
    'whileTap',
    'whileFocus',
    'initial',
    'animate',
    'exit',
    'transition',
    'variants',
    'layout',
    'layoutId',
  ];
  for (const [key, value] of Object.entries(props)) {
    if (!motionKeys.includes(key)) {
      htmlProps[key] = value;
    }
  }
  return htmlProps;
}

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const mockBrands: Brand[] = [
  {
    id: 1,
    name: 'Nike',
    slug: 'nike',
    image: '/media/brands/nike.png',
    website: 'https://nike.com',
    description: null,
    is_featured: true,
  },
  {
    id: 2,
    name: 'Adidas',
    slug: 'adidas',
    image: '/media/brands/adidas.png',
    website: 'https://adidas.com',
    description: null,
    is_featured: true,
  },
  {
    id: 3,
    name: 'Puma',
    slug: 'puma',
    image: '/media/brands/puma.png',
    website: null,
    description: null,
    is_featured: true,
  },
];

const singleBrand: Brand[] = [mockBrands[0]];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('BrandsBlock', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // AC1: Rendering
  // -------------------------------------------------------------------------
  describe('AC1: Rendering', () => {
    it('renders section with brand logos', () => {
      render(<BrandsBlock brands={mockBrands} />);

      expect(
        screen.getByTestId('brands-block')
      ).toBeInTheDocument();
    });

    it('renders all provided brands', () => {
      render(<BrandsBlock brands={mockBrands} />);

      expect(screen.getByAltText('Nike')).toBeInTheDocument();
      expect(screen.getByAltText('Adidas')).toBeInTheDocument();
      expect(screen.getByAltText('Puma')).toBeInTheDocument();
    });

    it('renders nothing when brands array is empty', () => {
      const { container } = render(<BrandsBlock brands={[]} />);
      expect(container.innerHTML).toBe('');
    });

    it('renders single brand without crashing', () => {
      render(<BrandsBlock brands={singleBrand} />);

      expect(screen.getByAltText('Nike')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // AC3: Image optimization with next/image
  // -------------------------------------------------------------------------
  describe('AC3: Image optimization', () => {
    it('renders images with object-contain class', () => {
      render(<BrandsBlock brands={singleBrand} />);

      const img = screen.getByAltText('Nike');
      expect(img.className).toContain('object-contain');
    });

    it('uses fill layout for responsive image sizing', () => {
      render(<BrandsBlock brands={singleBrand} />);

      const img = screen.getByAltText('Nike');
      expect(img).toHaveAttribute('data-fill', 'true');
    });

    it('renders images with appropriate sizes prop', () => {
      render(<BrandsBlock brands={singleBrand} />);

      const img = screen.getByAltText('Nike');
      expect(img).toHaveAttribute('data-sizes');
    });

    it('handles brands with null image gracefully', () => {
      const brandsWithNullImage: Brand[] = [
        { ...mockBrands[0], image: null },
        mockBrands[1],
      ];
      render(<BrandsBlock brands={brandsWithNullImage} />);

      // Brand with null image should not render an image
      expect(screen.queryByAltText('Nike')).not.toBeInTheDocument();
      expect(screen.getByAltText('Adidas')).toBeInTheDocument();
    });

    it('hides brand card when image fails to load', () => {
      render(<BrandsBlock brands={singleBrand} />);

      const img = screen.getByAltText('Nike');
      fireEvent.error(img);

      expect(screen.queryByAltText('Nike')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // AC4: Navigation to /catalog?brand={slug}
  // -------------------------------------------------------------------------
  describe('AC4: Navigation', () => {
    it('wraps each brand in a link to /catalog?brand={slug}', () => {
      render(<BrandsBlock brands={mockBrands} />);

      const links = screen.getAllByRole('link');
      expect(links).toHaveLength(3);
      expect(links[0]).toHaveAttribute('href', '/catalog?brand=nike');
      expect(links[1]).toHaveAttribute('href', '/catalog?brand=adidas');
      expect(links[2]).toHaveAttribute('href', '/catalog?brand=puma');
    });
  });

  // -------------------------------------------------------------------------
  // AC5: Accessibility
  // -------------------------------------------------------------------------
  describe('AC5: Accessibility', () => {
    it('has aria-label on section', () => {
      render(<BrandsBlock brands={mockBrands} />);

      expect(
        screen.getByLabelText('Популярные бренды')
      ).toBeInTheDocument();
    });

    it('all images have alt text with brand name', () => {
      render(<BrandsBlock brands={mockBrands} />);

      mockBrands.forEach((brand) => {
        expect(screen.getByAltText(brand.name)).toBeInTheDocument();
      });
    });

    it('carousel has role=region', () => {
      render(<BrandsBlock brands={mockBrands} />);

      const section = screen.getByTestId('brands-block');
      expect(section.tagName).toBe('SECTION');
    });

    it('brand links are keyboard-focusable via Tab', () => {
      render(<BrandsBlock brands={mockBrands} />);

      const links = screen.getAllByRole('link');
      links.forEach((link) => {
        // Links are natively focusable, verify no negative tabIndex
        expect(link).not.toHaveAttribute('tabindex', '-1');
      });
    });

    it('each link has accessible name from aria-label', () => {
      render(<BrandsBlock brands={mockBrands} />);

      const links = screen.getAllByRole('link');
      expect(links[0]).toHaveAttribute('aria-label', 'Nike');
      expect(links[1]).toHaveAttribute('aria-label', 'Adidas');
      expect(links[2]).toHaveAttribute('aria-label', 'Puma');
    });
  });

  // -------------------------------------------------------------------------
  // AC2: Embla carousel integration
  // -------------------------------------------------------------------------
  describe('AC2: Carousel', () => {
    it('initializes embla-carousel-react', async () => {
      const useEmblaCarousel = await import('embla-carousel-react');

      render(<BrandsBlock brands={mockBrands} />);

      expect(useEmblaCarousel.default).toHaveBeenCalled();
    });

    it('passes configured options to embla', async () => {
      const useEmblaCarousel = await import('embla-carousel-react');

      render(<BrandsBlock brands={mockBrands} />);

      const callArgs = vi.mocked(useEmblaCarousel.default).mock.calls[0];
      // Check for constants usage indirectly by checking values
      expect(callArgs[0]).toMatchObject({
        align: 'start',
        loop: true,
        breakpoints: {
          '(min-width: 640px)': { slidesToScroll: 2 },
          '(min-width: 1024px)': { slidesToScroll: 3 },
        },
      });
    });

    it('initializes Autoplay with stopOnMouseEnter: true', async () => {
      const Autoplay = await import('embla-carousel-autoplay');

      render(<BrandsBlock brands={mockBrands} />);

      expect(Autoplay.default).toHaveBeenCalledWith({
        delay: 3000,
        stopOnInteraction: true,
        stopOnMouseEnter: true, // Verification
      });
    });
  });
});
