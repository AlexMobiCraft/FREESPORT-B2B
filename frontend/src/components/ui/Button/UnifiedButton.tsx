/**
 * Unified Button Component
 *
 * This component automatically selects the appropriate button style
 * based on the current theme (classic or electric-orange).
 *
 * Usage:
 * import { UnifiedButton } from '@/components/ui/Button';
 *
 * <UnifiedButton variant="primary" size="md">
 *   Click me
 * </UnifiedButton>
 */

import React from 'react';
import { isElectricOrange } from '@/config/theme';
import { Button, ButtonProps } from './Button';
import { ElectricButton } from './ElectricButton';

// Map classic sizes to electric sizes
const sizeMap = {
  small: 'sm',
  medium: 'md',
  large: 'lg',
} as const;

// Map classic variants to electric variants
const variantMap = {
  primary: 'primary',
  secondary: 'outline',
  tertiary: 'ghost',
  subtle: 'ghost',
  danger: 'primary', // ElectricButton doesn't have danger, fallback to primary
} as const;

export type UnifiedButtonProps = ButtonProps;

/**
 * UnifiedButton - Theme-aware button component
 *
 * Automatically renders:
 * - Classic Button for 'classic' theme
 * - ElectricButton for 'electric-orange' theme
 */
export const UnifiedButton = React.forwardRef<HTMLButtonElement, UnifiedButtonProps>(
  (props, ref) => {
    if (isElectricOrange()) {
      const { variant = 'primary', size = 'medium', ...rest } = props;

      return (
        <ElectricButton ref={ref} variant={variantMap[variant]} size={sizeMap[size]} {...rest} />
      );
    }

    return <Button ref={ref} {...props} />;
  }
);

UnifiedButton.displayName = 'UnifiedButton';

export default UnifiedButton;
