/**
 * Business Components Exports
 */

export { ProductCard } from './ProductCard';
export type { ProductCardProps, UserRole } from './ProductCard';

export { ProductGrid } from './ProductGrid';
export type { ProductGridProps } from './ProductGrid';

export { SidebarFilters } from './SidebarFilters';
export type { SidebarFiltersProps, FilterValues, Category, Brand, Color } from './SidebarFilters';

export { SizeChartModal } from './SizeChartModal';
export type { SizeChartModalProps } from './SizeChartModal';

export { default as ProfileForm } from './ProfileForm';
export { profileSchema, defaultProfileValues } from './ProfileForm';
export type { ProfileFormData } from './ProfileForm';

// Story 16.2: Order components
export { OrderStatusBadge } from './OrderStatusBadge';
export type { OrderStatusBadgeProps } from './OrderStatusBadge';

export { OrderCard } from './OrderCard';
export type { OrderCardProps } from './OrderCard';

export { OrdersList } from './OrdersList';
export type { OrdersListProps } from './OrdersList';

export { OrderDetail, OrderItemsTable } from './OrderDetail';
export type { OrderDetailProps, OrderItemsTableProps } from './OrderDetail';

// Story 16.3: Address components
export { AddressCard } from './AddressCard';
export type { AddressCardProps } from './AddressCard';

export { AddressList } from './AddressList';
export type { AddressListProps } from './AddressList';

export { AddressModal } from './AddressModal';
export type { AddressModalProps } from './AddressModal';

// Story 16.3: Favorites components
export { FavoriteProductCard } from './FavoriteProductCard';
export type { FavoriteProductCardProps } from './FavoriteProductCard';

export { FavoritesList } from './FavoritesList';
export type { FavoritesListProps } from './FavoritesList';

// Story 18.1: Search components
export { SearchAutocomplete } from './SearchAutocomplete';
export type { SearchAutocompleteProps } from './SearchAutocomplete';

// Story 18.3: Search History components
export { SearchHistory } from './SearchHistory';
export type { SearchHistoryProps } from './SearchHistory';

// Story 18.2: Search Page components
export { SearchPageClient } from './SearchPageClient';
export type { SearchPageClientProps } from './SearchPageClient';

export { SearchResults } from './SearchResults';
export type { SearchResultsProps } from './SearchResults';

export { EmptySearchResults } from './EmptySearchResults';
export type { EmptySearchResultsProps } from './EmptySearchResults';
