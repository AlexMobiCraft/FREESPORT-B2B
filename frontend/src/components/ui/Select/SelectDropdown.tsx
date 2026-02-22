/**
 * SelectDropdown Component
 * Custom dropdown select с keyboard navigation согласно Design System v2.0
 *
 * @see docs/stories/epic-12/12.5.story.md#AC4
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectDropdownProps {
  /** Опции выбора */
  options: SelectOption[];
  /** Текущее значение */
  value?: string;
  /** Плейсхолдер */
  placeholder?: string;
  /** Метка поля */
  label?: string;
  /** Callback при изменении */
  onChange: (value: string) => void;
  /** Disabled состояние */
  disabled?: boolean;
  /** Дополнительные классы */
  className?: string;
}

/**
 * Custom Select компонент с dropdown menu и keyboard navigation
 */
export const SelectDropdown = React.forwardRef<HTMLDivElement, SelectDropdownProps>(
  (
    { options, value, placeholder = 'Выберите...', label, onChange, disabled = false, className },
    ref
  ) => {
    const [isOpen, setIsOpen] = useState(false);
    const [focusedIndex, setFocusedIndex] = useState(-1);
    const containerRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);

    // Находим выбранную опцию
    const selectedOption = options.find(opt => opt.value === value);

    // Закрытие dropdown при клике вне компонента
    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
          setIsOpen(false);
          setFocusedIndex(-1);
        }
      };

      if (isOpen) {
        document.addEventListener('mousedown', handleClickOutside);
      }

      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }, [isOpen]);

    // Keyboard navigation
    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (disabled) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          if (!isOpen) {
            setIsOpen(true);
            setFocusedIndex(0);
          } else {
            setFocusedIndex(prev => (prev < options.length - 1 ? prev + 1 : prev));
          }
          break;

        case 'ArrowUp':
          e.preventDefault();
          if (isOpen) {
            setFocusedIndex(prev => (prev > 0 ? prev - 1 : 0));
          }
          break;

        case 'Enter':
          e.preventDefault();
          if (isOpen && focusedIndex >= 0) {
            onChange(options[focusedIndex].value);
            setIsOpen(false);
            setFocusedIndex(-1);
            triggerRef.current?.focus();
          } else {
            setIsOpen(!isOpen);
          }
          break;

        case 'Escape':
          e.preventDefault();
          setIsOpen(false);
          setFocusedIndex(-1);
          triggerRef.current?.focus();
          break;

        case ' ':
          e.preventDefault();
          if (!isOpen) {
            setIsOpen(true);
            setFocusedIndex(0);
          }
          break;
      }
    };

    const handleOptionClick = (optionValue: string) => {
      onChange(optionValue);
      setIsOpen(false);
      setFocusedIndex(-1);
      triggerRef.current?.focus();
    };

    return (
      <div ref={ref} className={cn('w-full', className)}>
        {/* Label */}
        {label && (
          <label className="block text-body-s font-medium text-text-primary mb-1">{label}</label>
        )}

        {/* Select Container */}
        <div ref={containerRef} className="relative">
          {/* Trigger Button */}
          <button
            ref={triggerRef}
            type="button"
            role="combobox"
            aria-expanded={isOpen}
            aria-haspopup="listbox"
            aria-controls="select-dropdown-menu"
            disabled={disabled}
            onClick={() => !disabled && setIsOpen(!isOpen)}
            onKeyDown={handleKeyDown}
            className={cn(
              // Базовые стили - Design System v2.0
              'w-full h-10 px-4 rounded-sm', // 40px height, 16px padding, 6px radius
              'flex items-center justify-between',
              'text-body-m text-left',
              'bg-white',
              'border border-[#D0D7E6]', // Design System v2.0 border
              'transition-colors duration-[180ms]',

              // Focus state - Design System v2.0
              'focus:outline-none focus:border-primary focus:border-[1.5px]',

              // Disabled state
              disabled && 'opacity-50 cursor-not-allowed bg-neutral-200',

              // Open state
              isOpen && 'border-primary border-[1.5px]',

              !disabled && 'cursor-pointer'
            )}
          >
            <span className={cn('truncate', !selectedOption && 'text-neutral-500')}>
              {selectedOption ? selectedOption.label : placeholder}
            </span>

            {/* ChevronDown Icon */}
            <ChevronDown
              className={cn(
                'w-5 h-5 text-neutral-600 flex-shrink-0 ml-2',
                'transition-transform duration-[180ms]',
                isOpen && 'rotate-180'
              )}
              aria-hidden="true"
            />
          </button>

          {/* Dropdown Menu */}
          {isOpen && (
            <div
              id="select-dropdown-menu"
              role="listbox"
              className={cn(
                // Позиционирование
                'absolute top-full left-0 right-0 mt-1 z-50',

                // Стили - Design System v2.0
                'bg-white rounded-md',
                'border border-[#E3E8F2]',
                'shadow-lg', // shadow-dropdown

                // Скролл для длинных списков
                'max-h-60 overflow-y-auto',

                // Анимация появления
                'animate-in fade-in-0 zoom-in-95 duration-100'
              )}
            >
              {options.map((option, index) => {
                const isSelected = option.value === value;
                const isFocused = index === focusedIndex;

                return (
                  <button
                    key={option.value}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleOptionClick(option.value)}
                    onMouseEnter={() => setFocusedIndex(index)}
                    className={cn(
                      // Базовые стили
                      'w-full text-left px-4 py-2 cursor-pointer',
                      'text-body-m',
                      'transition-colors duration-[120ms]',

                      // Hover state - Design System v2.0
                      'hover:bg-[#F5F7FA]',

                      // Selected state - Design System v2.0
                      isSelected && 'bg-primary-subtle text-primary',

                      // Focused state (keyboard navigation)
                      isFocused && !isSelected && 'bg-[#F5F7FA]'
                    )}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  }
);

SelectDropdown.displayName = 'SelectDropdown';
