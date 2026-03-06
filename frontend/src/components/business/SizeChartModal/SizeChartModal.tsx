/**
 * SizeChartModal Component
 * Таблица размеров для товаров (одежда, обувь, перчатки)
 * Design System v2.0
 */

import React, { useState } from 'react';
import { Modal, Tabs } from '@/components/ui';
import type { Tab } from '@/components/ui';

export interface SizeChartModalProps {
  /** Открыт ли модал */
  isOpen: boolean;
  /** Callback при закрытии */
  onClose: () => void;
  /** Категория товара */
  category?: 'clothing' | 'shoes' | 'gloves';
  /** Пол */
  gender?: 'men' | 'women' | 'unisex';
}

interface SizeRow {
  size?: string;
  chest?: string;
  waist?: string;
  hips?: string;
  eu?: string;
  us?: string;
  uk?: string;
  cm?: string;
}

// Данные размерных сеток
const CLOTHING_SIZES: SizeRow[] = [
  { size: 'XS', chest: '82-86 см', waist: '62-66 см', hips: '87-90 см' },
  { size: 'S', chest: '86-90 см', waist: '66-70 см', hips: '90-94 см' },
  { size: 'M', chest: '90-96 см', waist: '70-76 см', hips: '94-100 см' },
  { size: 'L', chest: '96-102 см', waist: '76-82 см', hips: '100-106 см' },
  { size: 'XL', chest: '102-108 см', waist: '82-88 см', hips: '106-112 см' },
  { size: 'XXL', chest: '108-114 см', waist: '88-94 см', hips: '112-118 см' },
];

const SHOE_SIZES: SizeRow[] = [
  { eu: '36', us: '6', uk: '3.5', cm: '22.5 см' },
  { eu: '37', us: '7', uk: '4', cm: '23 см' },
  { eu: '38', us: '7.5', uk: '4.5', cm: '23.5 см' },
  { eu: '39', us: '8', uk: '5.5', cm: '24 см' },
  { eu: '40', us: '8.5', uk: '6', cm: '25 см' },
  { eu: '41', us: '9', uk: '7', cm: '25.5 см' },
  { eu: '42', us: '9.5', uk: '7.5', cm: '26 см' },
  { eu: '43', us: '10', uk: '8.5', cm: '27 см' },
  { eu: '44', us: '11', uk: '9.5', cm: '27.5 см' },
  { eu: '45', us: '12', uk: '10.5', cm: '28 см' },
];

const GLOVE_SIZES: SizeRow[] = [
  { size: 'XS', cm: '16-17 см' },
  { size: 'S', cm: '18-19 см' },
  { size: 'M', cm: '20-21 см' },
  { size: 'L', cm: '22-23 см' },
  { size: 'XL', cm: '24-25 см' },
];

export const SizeChartModal: React.FC<SizeChartModalProps> = ({
  isOpen,
  onClose,
  category = 'clothing',
  gender = 'unisex',
}) => {
  const [activeCategory, setActiveCategory] = useState(category);
  const genderLabel = gender === 'men' ? 'мужчин' : gender === 'women' ? 'женщин' : 'унисекс';

  const tabs: Tab[] = [
    {
      id: 'clothing',
      label: 'Одежда',
      content: (
        <div>
          <h3 className="text-[16px] leading-[24px] font-semibold text-[#1B1B1B] mb-4">
            Таблица размеров одежды
          </h3>

          <div className="overflow-x-auto mb-6">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[#F5F7FB]">
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    Размер
                  </th>
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    Обхват груди
                  </th>
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    Обхват талии
                  </th>
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    Обхват бедер
                  </th>
                </tr>
              </thead>
              <tbody>
                {CLOTHING_SIZES.map((row, index) => (
                  <tr key={row.size} className={index % 2 === 0 ? '' : 'bg-[#FAFBFC]'}>
                    <td className="p-3 text-[14px] leading-[20px] text-[#1B1B1B] border border-[#E3E8F2] font-medium">
                      {row.size}
                    </td>
                    <td className="p-3 text-[14px] leading-[20px] text-[#4D4D4D] border border-[#E3E8F2]">
                      {row.chest}
                    </td>
                    <td className="p-3 text-[14px] leading-[20px] text-[#4D4D4D] border border-[#E3E8F2]">
                      {row.waist}
                    </td>
                    <td className="p-3 text-[14px] leading-[20px] text-[#4D4D4D] border border-[#E3E8F2]">
                      {row.hips}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 bg-[#F5F7FB] rounded-xl">
            <h4 className="text-[14px] leading-[20px] font-semibold text-[#1B1B1B] mb-2">
              Как измерить:
            </h4>
            <ul className="space-y-1 text-[14px] leading-[20px] text-[#4D4D4D]">
              <li>• Обхват груди: измерьте по самым выступающим точкам груди</li>
              <li>• Обхват талии: измерьте по самому узкому месту</li>
              <li>• Обхват бедер: измерьте по самым выступающим точкам ягодиц</li>
            </ul>
          </div>
        </div>
      ),
    },
    {
      id: 'shoes',
      label: 'Обувь',
      content: (
        <div>
          <h3 className="text-[16px] leading-[24px] font-semibold text-[#1B1B1B] mb-4">
            Таблица размеров обуви
          </h3>

          <div className="overflow-x-auto mb-6">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[#F5F7FB]">
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    EU
                  </th>
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    US
                  </th>
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    UK
                  </th>
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    Длина стопы
                  </th>
                </tr>
              </thead>
              <tbody>
                {SHOE_SIZES.map((row, index) => (
                  <tr key={row.eu} className={index % 2 === 0 ? '' : 'bg-[#FAFBFC]'}>
                    <td className="p-3 text-[14px] leading-[20px] text-[#1B1B1B] border border-[#E3E8F2] font-medium">
                      {row.eu}
                    </td>
                    <td className="p-3 text-[14px] leading-[20px] text-[#4D4D4D] border border-[#E3E8F2]">
                      {row.us}
                    </td>
                    <td className="p-3 text-[14px] leading-[20px] text-[#4D4D4D] border border-[#E3E8F2]">
                      {row.uk}
                    </td>
                    <td className="p-3 text-[14px] leading-[20px] text-[#4D4D4D] border border-[#E3E8F2]">
                      {row.cm}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 bg-[#F5F7FB] rounded-xl">
            <h4 className="text-[14px] leading-[20px] font-semibold text-[#1B1B1B] mb-2">
              Как измерить длину стопы:
            </h4>
            <p className="text-[14px] leading-[20px] text-[#4D4D4D]">
              Встаньте на лист бумаги и обведите стопу. Измерьте расстояние от пятки до кончика
              большого пальца.
            </p>
          </div>
        </div>
      ),
    },
    {
      id: 'gloves',
      label: 'Перчатки',
      content: (
        <div>
          <h3 className="text-[16px] leading-[24px] font-semibold text-[#1B1B1B] mb-4">
            Таблица размеров перчаток
          </h3>

          <div className="overflow-x-auto mb-6">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[#F5F7FB]">
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    Размер
                  </th>
                  <th className="p-3 text-left text-[14px] leading-[20px] font-semibold text-[#1B1B1B] border border-[#E3E8F2]">
                    Обхват ладони
                  </th>
                </tr>
              </thead>
              <tbody>
                {GLOVE_SIZES.map((row, index) => (
                  <tr key={row.size} className={index % 2 === 0 ? '' : 'bg-[#FAFBFC]'}>
                    <td className="p-3 text-[14px] leading-[20px] text-[#1B1B1B] border border-[#E3E8F2] font-medium">
                      {row.size}
                    </td>
                    <td className="p-3 text-[14px] leading-[20px] text-[#4D4D4D] border border-[#E3E8F2]">
                      {row.cm}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 bg-[#F5F7FB] rounded-xl">
            <h4 className="text-[14px] leading-[20px] font-semibold text-[#1B1B1B] mb-2">
              Как измерить обхват ладони:
            </h4>
            <p className="text-[14px] leading-[20px] text-[#4D4D4D]">
              Измерьте обхват ладони в самом широком месте, не включая большой палец.
            </p>
          </div>
        </div>
      ),
    },
  ];

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Таблица размеров" size="lg">
      <p className="text-[14px] leading-[20px] text-[#4D4D4D] mb-4">
        Рекомендации для: <span className="font-semibold text-[#1B1B1B]">{genderLabel}</span>
      </p>
      <Tabs
        tabs={tabs}
        defaultTab={activeCategory}
        onChange={(tabId: string) => setActiveCategory(tabId as typeof activeCategory)}
      />
    </Modal>
  );
};

SizeChartModal.displayName = 'SizeChartModal';
