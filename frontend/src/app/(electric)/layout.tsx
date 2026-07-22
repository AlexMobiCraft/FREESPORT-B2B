import '../globals-electric-orange.css';
import ElectricHeader from '@/components/layout/ElectricHeader';
import ElectricFooter from '@/components/layout/ElectricFooter';
import Providers from '@/components/providers/Providers';

export default function ElectricLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <div className="theme-electric min-h-screen bg-[var(--bg-body)] font-sans">
        <ElectricHeader />
        <main>{children}</main>
        <ElectricFooter />
      </div>
    </Providers>
  );
}
