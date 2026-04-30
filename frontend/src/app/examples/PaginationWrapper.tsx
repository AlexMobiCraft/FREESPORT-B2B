'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Pagination } from '@/components/ui/Pagination/Pagination';

interface PaginationWrapperProps {
  currentPage: number;
  totalPages: number;
}

/**
 * Клиентский компонент для обработки переключения страниц пагинации
 */
export function PaginationWrapper({ currentPage, totalPages }: PaginationWrapperProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const handlePageChange = (page: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('page', page.toString());
    router.push(`/examples?${params.toString()}`);
  };

  return (
    <Pagination
      currentPage={currentPage}
      totalPages={totalPages}
      onPageChange={handlePageChange}
      showFirstLast
    />
  );
}
