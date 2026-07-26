/**
 * Product Detail Page (Story 12.1, 13.5b)
 * SSR страница детального просмотра товара
 * Интегрирует ProductOptions с ProductGallery и ProductSummary
 *
 * @see docs/stories/epic-13/13.5b.productoptions-api-integration.md
 */

import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { cookies } from 'next/headers';
import productsService from '@/services/productsService';
import ProductBreadcrumbs from '@/components/product/ProductBreadcrumbs';
import ProductPageClient from '@/components/product/ProductPageClient';
import type { UserRole } from '@/utils/pricing';

interface ProductPageProps {
  params: Promise<{
    slug: string;
  }>;
}

import { getUserRole } from '@/utils/server-auth';

/**
 * Генерирует метаданные для SEO
 */
export async function generateMetadata({ params }: ProductPageProps): Promise<Metadata> {
  try {
    const { slug } = await params;
    const product = await productsService.getProductBySlug(slug);

    const primaryImage = product.images.find(img => img.is_primary) || product.images[0];

    return {
      title: `${product.name} - ${product.brand} | FREESPORT`,
      description: product.description.substring(0, 160),
      openGraph: {
        title: product.name,
        description: product.description,
        images: primaryImage
          ? [{ url: primaryImage.image, alt: primaryImage.alt_text || product.name }]
          : [],
        type: 'website',
      },
      alternates: {
        canonical: `/product/${product.slug}`,
      },
    };
  } catch {
    return {
      title: 'Товар не найден | FREESPORT',
      description: 'Запрошенный товар не найден',
    };
  }
}

/**
 * Product Detail Page Component
 */
export default async function ProductPage({ params }: ProductPageProps) {
  const { slug } = await params;
  let product;
  let userRole: UserRole = 'guest';

  try {
    // Получаем сессию для авторизованного запроса
    const cookieStore = await cookies();
    const sessionId = cookieStore.get('sessionid')?.value;
    const headers = sessionId ? { Cookie: `sessionid=${sessionId}` } : undefined;

    // Загружаем данные товара и роль пользователя параллельно
    [product, userRole] = await Promise.all([
      productsService.getProductBySlug(slug, headers),
      getUserRole(),
    ]);
  } catch (error) {
    console.error('Error loading product:', error);
    notFound();
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Breadcrumbs */}
      <ProductBreadcrumbs
        breadcrumbs={product.category?.breadcrumbs || []}
        productName={product.name}
      />

      {/* Main Content - Client Component для интеграции с вариантами */}
      <ProductPageClient product={product} userRole={userRole} />
    </div>
  );
}
