/**
 * Product Detail Loading Skeleton (Story 12.1)
 * Показывается во время загрузки данных товара
 */

export default function ProductLoading() {
  return (
    <div className="container mx-auto px-4 py-8 animate-pulse">
      {/* Breadcrumbs Skeleton */}
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <div className="h-4 w-16 bg-neutral-200 rounded"></div>
          <div className="h-4 w-4 bg-neutral-200 rounded"></div>
          <div className="h-4 w-24 bg-neutral-200 rounded"></div>
          <div className="h-4 w-4 bg-neutral-200 rounded"></div>
          <div className="h-4 w-32 bg-neutral-200 rounded"></div>
        </div>
      </div>

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
        {/* Left Column: Image Gallery */}
        <div className="lg:col-span-2 space-y-4">
          {/* Main Image */}
          <div className="aspect-square bg-neutral-200 rounded-lg"></div>

          {/* Thumbnails */}
          <div className="grid grid-cols-4 gap-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="aspect-square bg-neutral-200 rounded-lg"></div>
            ))}
          </div>

          {/* Specifications Skeleton */}
          <div className="mt-8 bg-white rounded-lg border border-neutral-200 p-6">
            <div className="h-6 w-40 bg-neutral-200 rounded mb-4"></div>
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex gap-4">
                  <div className="h-4 w-1/3 bg-neutral-200 rounded"></div>
                  <div className="h-4 w-2/3 bg-neutral-200 rounded"></div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Product Info */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg border border-neutral-200 p-6">
            {/* Title */}
            <div className="h-8 w-full bg-neutral-200 rounded mb-4"></div>
            <div className="h-8 w-3/4 bg-neutral-200 rounded mb-4"></div>

            {/* SKU & Brand */}
            <div className="flex gap-4 mb-4">
              <div className="h-4 w-32 bg-neutral-200 rounded"></div>
              <div className="h-4 w-32 bg-neutral-200 rounded"></div>
            </div>

            {/* Rating */}
            <div className="flex gap-1 mb-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-5 w-5 bg-neutral-200 rounded"></div>
              ))}
            </div>

            {/* Price */}
            <div className="h-10 w-40 bg-neutral-200 rounded mb-4"></div>

            {/* Stock Status */}
            <div className="h-8 w-32 bg-neutral-200 rounded mb-4"></div>

            {/* Description */}
            <div className="space-y-2 pt-4 border-t border-neutral-200">
              <div className="h-4 w-full bg-neutral-200 rounded"></div>
              <div className="h-4 w-full bg-neutral-200 rounded"></div>
              <div className="h-4 w-3/4 bg-neutral-200 rounded"></div>
            </div>

            {/* Add to Cart Button */}
            <div className="h-12 w-full bg-neutral-200 rounded mt-6"></div>
          </div>
        </div>
      </div>
    </div>
  );
}
