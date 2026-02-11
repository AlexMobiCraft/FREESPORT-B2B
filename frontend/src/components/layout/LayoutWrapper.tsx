'use client';

import { usePathname } from 'next/navigation';
import ElectricHeader from './ElectricHeader';
import ElectricFooter from './ElectricFooter';

export default function LayoutWrapper({
  children,
  header,
  footer,
}: {
  children: React.ReactNode;
  header: React.ReactNode;
  footer: React.ReactNode;
}) {
  const pathname = usePathname();
  const isHomePage = pathname === '/';
  const isElectricTestPage = pathname === '/electric-orange-test';
  const isElectricPage = pathname.startsWith('/electric');

  if (isHomePage || isElectricTestPage) {
    return <main className="flex-grow">{children}</main>;
  }

  // Use Electric components for /electric/* pages
  if (isElectricPage) {
    return (
      <div className="min-h-screen flex flex-col">
        <ElectricHeader />
        <main className="flex-grow relative z-0">{children}</main>
        <ElectricFooter />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {header}
      <main className="flex-grow relative z-0">{children}</main>
      {footer}
    </div>
  );
}
