import '../globals.css';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import LayoutWrapper from '@/components/layout/LayoutWrapper';
import Providers from '@/components/providers/Providers';

export default function BlueLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <LayoutWrapper header={<Header />} footer={<Footer />}>
        {children}
      </LayoutWrapper>
    </Providers>
  );
}
