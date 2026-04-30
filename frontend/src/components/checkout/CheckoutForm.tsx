'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { User } from '@/types/api';
import {
  checkoutSchema,
  CheckoutFormData,
  CheckoutFormInput,
  defaultCheckoutFormValues,
} from '@/schemas/checkoutSchema';
import { useOrderStore } from '@/stores/orderStore';
import { useCartStore } from '@/stores/cartStore';
import { addressService } from '@/services/addressService';
import type { Address } from '@/types/address';
import type { CheckoutAddressFields } from '@/utils/checkout/addressMapping';
import {
  addressToFormValues,
  formValuesToAddressPayload,
  isFormDirtyVsAddress,
} from '@/utils/checkout/addressMapping';
import { ContactSection } from './ContactSection';
import { AddressSection } from './AddressSection';
import { DeliveryOptions } from './DeliveryOptions';
import { OrderCommentSection } from './OrderCommentSection';
import { OrderSummary } from './OrderSummary';
import { InfoPanel } from '@/components/ui';

export interface CheckoutFormProps {
  user: User | null;
}

const ADDRESS_FIELDS = [
  'firstName',
  'lastName',
  'phone',
  'city',
  'street',
  'house',
  'buildingSection',
  'apartment',
  'postalCode',
] as const;

/**
 * Главная форма оформления заказа.
 *
 * Story 15.1 / 15.2 + spec checkout-address-ux-improvements:
 * - React Hook Form + Zod валидация
 * - Контактные данные автозаполняются из user
 * - Shipping-адреса грузятся отдельным запросом GET /api/v1/users/addresses/
 *   (не из user.addresses — сериализатор /users/me/ не возвращает массив)
 * - Default-адрес автозаполняет поля; селектор — при 2+ адресах
 * - После ручного редактирования предлагается сохранить адрес в профиль
 *   (POST /api/v1/users/addresses/ выполняется fire-and-forget после успеха
 *   создания заказа, чтобы не блокировать UX перехода на success-страницу)
 */
export function CheckoutForm({ user }: CheckoutFormProps) {
  const router = useRouter();

  const { createOrder, isSubmitting, error: orderError, clearOrder } = useOrderStore();
  const { items: cartItems } = useCartStore();

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null);
  const [saveAddress, setSaveAddress] = useState(false);
  // True после первого resolve getAddresses. Защищает от race-условия:
  // юзер успевает заполнить и засабмитить форму до того как API ответит,
  // тогда `addresses.length === 0` ложно сигнализирует «новый адрес → is_default=true».
  const [addressesLoaded, setAddressesLoaded] = useState(false);

  const isAuthenticated = !!user;

  const form = useForm<CheckoutFormInput, unknown, CheckoutFormData>({
    resolver: zodResolver(checkoutSchema),
    mode: 'onBlur',
    reValidateMode: 'onChange',
    defaultValues: {
      email: user?.email || defaultCheckoutFormValues.email,
      phone: user?.phone || defaultCheckoutFormValues.phone,
      firstName: user?.first_name || defaultCheckoutFormValues.firstName,
      lastName: user?.last_name || defaultCheckoutFormValues.lastName,
      city: defaultCheckoutFormValues.city,
      street: defaultCheckoutFormValues.street,
      house: defaultCheckoutFormValues.house,
      buildingSection: defaultCheckoutFormValues.buildingSection,
      apartment: defaultCheckoutFormValues.apartment,
      postalCode: defaultCheckoutFormValues.postalCode,
      deliveryMethod: defaultCheckoutFormValues.deliveryMethod,
      paymentMethod: defaultCheckoutFormValues.paymentMethod,
      comment: defaultCheckoutFormValues.comment,
    },
  });

  // Очистка ошибок заказа при монтировании
  useEffect(() => {
    clearOrder();
  }, [clearOrder]);

  // Применяет данные адреса в поля формы и обнуляет флаг "запомнить".
  const applyAddressToForm = useCallback(
    (address: Address) => {
      const values = addressToFormValues(address);
      ADDRESS_FIELDS.forEach(field => {
        form.setValue(field, values[field], {
          shouldDirty: false,
          shouldTouch: false,
          shouldValidate: false,
        });
      });
      // Очищаем фантом-ошибки, оставшиеся от ручных правок до автозаполнения.
      form.clearErrors([...ADDRESS_FIELDS]);
      setSelectedAddressId(address.id);
      setSaveAddress(false);
    },
    [form]
  );

  // Загрузка сохранённых shipping-адресов авторизованного пользователя.
  useEffect(() => {
    if (!isAuthenticated) {
      // Logout: гарантируем, что адреса от прежнего пользователя не «протекут».
      setAddresses([]);
      setSelectedAddressId(null);
      setAddressesLoaded(false);
      return;
    }

    let cancelled = false;
    addressService
      .getAddresses()
      .then(list => {
        if (cancelled) return;
        const shipping = list.filter(a => a.address_type === 'shipping');
        setAddresses(shipping);
        setAddressesLoaded(true);
        if (shipping.length === 0) return;

        // Race-guard: если пользователь уже что-то ввёл в адресные поля до
        // резолва промиса, не перезаписываем его данные.
        const current = form.getValues(['city', 'street', 'house', 'postalCode']);
        const userTyped = current.some(v => !!v && v.trim().length > 0);
        if (userTyped) return;

        const initial = shipping.find(a => a.is_default) ?? shipping[0];
        applyAddressToForm(initial);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setAddressesLoaded(true);
        // Деградация: форма остаётся доступной для ручного ввода.
        console.error('Failed to load addresses:', err);
        toast.error('Не удалось загрузить сохранённые адреса. Введите данные вручную.');
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, applyAddressToForm, form]);

  // Подписка на изменения адресных полей: вычисляем «правил ли пользователь вручную».
  const watchedValues = form.watch(ADDRESS_FIELDS);

  const showSaveCheckbox = useMemo(() => {
    if (!isAuthenticated) return false;
    const [
      firstName,
      lastName,
      phone,
      city,
      street,
      house,
      buildingSection,
      apartment,
      postalCode,
    ] = watchedValues;

    const values = {
      firstName: firstName ?? '',
      lastName: lastName ?? '',
      phone: phone ?? '',
      city: city ?? '',
      street: street ?? '',
      house: house ?? '',
      buildingSection: buildingSection ?? '',
      apartment: apartment ?? '',
      postalCode: postalCode ?? '',
    };

    // Если хотя бы одно адресное поле заполнено — есть что сохранять.
    const hasAddressContent = values.city || values.street || values.house || values.postalCode;
    if (!hasAddressContent) return false;

    if (selectedAddressId !== null) {
      const selected = addresses.find(a => a.id === selectedAddressId);
      if (!selected) return true;
      return isFormDirtyVsAddress(values, selected);
    }

    // Адрес не выбран из списка — данные уникальны для текущего ввода.
    return true;
  }, [isAuthenticated, watchedValues, selectedAddressId, addresses]);

  // Сбросить чекбокс, если редактирование «отменено» (поля совпали с выбранным адресом).
  useEffect(() => {
    if (!showSaveCheckbox && saveAddress) {
      setSaveAddress(false);
    }
  }, [showSaveCheckbox, saveAddress]);

  const handleSelectAddress = useCallback(
    (id: number) => {
      const target = addresses.find(a => a.id === id);
      if (!target) return;
      applyAddressToForm(target);
    },
    [addresses, applyAddressToForm]
  );

  const onSubmit = async (data: CheckoutFormData) => {
    try {
      if (!cartItems || cartItems.length === 0) {
        useOrderStore.getState().setError('Корзина пуста, невозможно оформить заказ');
        return;
      }

      // Снимаем dirty-флаг по уже валидированному `data` — `showSaveCheckbox`
      // от watch-замыкания может отстать на один tick при быстром submit.
      const dirtyVsSelected = ((): boolean => {
        if (selectedAddressId === null) return true;
        const selected = addresses.find(a => a.id === selectedAddressId);
        if (!selected) return true;
        const fieldsForCompare: CheckoutAddressFields = {
          firstName: data.firstName,
          lastName: data.lastName,
          phone: data.phone,
          city: data.city,
          street: data.street,
          house: data.house,
          buildingSection: data.buildingSection ?? '',
          apartment: data.apartment ?? '',
          postalCode: data.postalCode,
        };
        return isFormDirtyVsAddress(fieldsForCompare, selected);
      })();

      const shouldSaveAddress =
        isAuthenticated && saveAddress && dirtyVsSelected && addressesLoaded;

      await createOrder(data);

      const orderId = useOrderStore.getState().currentOrder?.id;
      if (!orderId) return;

      // Fire-and-forget сохранение адреса в профиль. Заказ уже создан —
      // ошибка POST /users/addresses/ не должна блокировать редирект.
      // Toast не показываем: пользователь уже на success-странице и
      // ошибка о сохранении адреса там создаст путаницу.
      if (shouldSaveAddress) {
        const payload = formValuesToAddressPayload(data, {
          isDefault: addresses.length === 0,
        });
        addressService.createAddress(payload).catch((err: Error) => {
          console.error('Failed to save address:', err);
        });
      }

      router.push(`/checkout/success/${orderId}`);
    } catch (err) {
      console.error('Order creation failed:', err);
    }
  };

  const {
    formState: { errors },
  } = form;

  const hasFormErrors = Object.keys(errors).length > 0;
  const isCartEmpty = !cartItems || cartItems.length === 0;

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
      {isCartEmpty && (
        <InfoPanel
          variant="warning"
          title="Корзина пуста"
          message="Добавьте товары в корзину для оформления заказа"
          className="mb-6"
        />
      )}

      {orderError && (
        <InfoPanel
          variant="error"
          title="Ошибка оформления заказа"
          message={orderError}
          className="mb-6"
        />
      )}

      {hasFormErrors && (
        <InfoPanel
          variant="error"
          title="Ошибки в форме"
          message="Пожалуйста, исправьте ошибки в форме перед отправкой"
          className="mb-6"
        />
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <ContactSection form={form} />

          <AddressSection
            form={form}
            addresses={addresses}
            selectedAddressId={selectedAddressId}
            onSelectAddress={handleSelectAddress}
            showSaveCheckbox={showSaveCheckbox}
            saveAddress={saveAddress}
            onToggleSaveAddress={setSaveAddress}
          />

          <DeliveryOptions form={form} />

          <OrderCommentSection form={form} />
        </div>

        <div className="lg:col-span-1">
          <OrderSummary
            isSubmitting={isSubmitting}
            submitError={orderError}
            isCartEmpty={isCartEmpty}
          />
        </div>
      </div>
    </form>
  );
}
