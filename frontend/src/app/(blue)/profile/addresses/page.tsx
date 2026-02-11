/**
 * Addresses Page - Страница управления адресами доставки
 * Story 16.3: Управление адресами доставки (AC: 1, 2, 3)
 *
 * Функционал:
 * - Отображение списка адресов пользователя
 * - Добавление нового адреса через модальное окно
 * - Редактирование существующего адреса
 * - Удаление адреса с подтверждением
 * - Optimistic UI для всех операций
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { AddressList } from '@/components/business/AddressList';
import { AddressModal } from '@/components/business/AddressModal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog/ConfirmDialog';
import Button from '@/components/ui/Button';
import { addressService, AddressValidationError } from '@/services/addressService';
import type { Address, AddressFormData } from '@/types/address';

/**
 * Страница управления адресами доставки
 */
export default function AddressesPage() {
  // State
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingAddress, setEditingAddress] = useState<Address | undefined>(undefined);
  const [isSaving, setIsSaving] = useState(false);

  // Delete confirmation state
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [addressToDelete, setAddressToDelete] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  /**
   * Загрузка адресов при монтировании
   */
  const fetchAddresses = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await addressService.getAddresses();
      setAddresses(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка загрузки адресов';
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAddresses();
  }, [fetchAddresses]);

  /**
   * Открыть модальное окно для добавления адреса
   */
  const handleAddNew = () => {
    setEditingAddress(undefined);
    setIsModalOpen(true);
  };

  /**
   * Открыть модальное окно для редактирования адреса
   */
  const handleEdit = (address: Address) => {
    setEditingAddress(address);
    setIsModalOpen(true);
  };

  /**
   * Закрыть модальное окно
   */
  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingAddress(undefined);
  };

  /**
   * Создать новый адрес (AC: 1)
   */
  const handleCreate = async (data: AddressFormData) => {
    setIsSaving(true);
    try {
      const newAddress = await addressService.createAddress(data);
      // Optimistic UI: добавляем адрес в список
      setAddresses(prev => [...prev, newAddress]);
      toast.success('Адрес добавлен');
      handleCloseModal();
    } catch (err) {
      if (err instanceof AddressValidationError) {
        // Показываем ошибки валидации
        const messages = Object.values(err.errors).flat().join(', ');
        toast.error(messages || 'Ошибка валидации');
      } else {
        const message = err instanceof Error ? err.message : 'Ошибка создания адреса';
        toast.error(message);
      }
      throw err; // Пробрасываем для обработки в модале
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * Обновить адрес (AC: 2)
   */
  const handleUpdate = async (id: number, data: AddressFormData) => {
    setIsSaving(true);
    // Сохраняем старый адрес для отката
    const oldAddress = addresses.find(a => a.id === id);

    try {
      const updatedAddress = await addressService.updateAddress(id, data);
      // Optimistic UI: обновляем адрес в списке
      setAddresses(prev => prev.map(a => (a.id === id ? updatedAddress : a)));
      toast.success('Адрес обновлён');
      handleCloseModal();
    } catch (err) {
      // Откат при ошибке
      if (oldAddress) {
        setAddresses(prev => prev.map(a => (a.id === id ? oldAddress : a)));
      }
      if (err instanceof AddressValidationError) {
        const messages = Object.values(err.errors).flat().join(', ');
        toast.error(messages || 'Ошибка валидации');
      } else {
        const message = err instanceof Error ? err.message : 'Ошибка обновления адреса';
        toast.error(message);
      }
      throw err;
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * Открыть диалог подтверждения удаления (AC: 3)
   */
  const handleDeleteClick = (addressId: number) => {
    setAddressToDelete(addressId);
    setDeleteConfirmOpen(true);
  };

  /**
   * Подтвердить удаление адреса (AC: 3)
   */
  const handleConfirmDelete = async () => {
    if (!addressToDelete) return;

    const id = addressToDelete;
    // Сохраняем адрес для отката
    const deletedAddress = addresses.find(a => a.id === id);

    setDeleteConfirmOpen(false);
    setDeletingId(id);

    // Optimistic UI: мгновенно удаляем из списка
    setAddresses(prev => prev.filter(a => a.id !== id));

    try {
      await addressService.deleteAddress(id);
      toast.success('Адрес удалён');
    } catch (err) {
      // Откат при ошибке
      if (deletedAddress) {
        setAddresses(prev => [...prev, deletedAddress]);
      }
      const message = err instanceof Error ? err.message : 'Ошибка удаления адреса';
      toast.error(message);
    } finally {
      setDeletingId(null);
      setAddressToDelete(null);
    }
  };

  /**
   * Отмена удаления
   */
  const handleCancelDelete = () => {
    setDeleteConfirmOpen(false);
    setAddressToDelete(null);
  };

  // Ошибка загрузки
  if (error && !isLoading && addresses.length === 0) {
    return (
      <div className="p-6">
        <h1 className="text-[24px] leading-[32px] font-semibold text-[var(--color-text-primary)] mb-6">
          Адреса доставки
        </h1>
        <div className="bg-[var(--color-accent-danger-bg)] text-[var(--color-accent-danger)] p-4 rounded-lg">
          {error}
          <Button variant="tertiary" size="small" onClick={fetchAddresses} className="ml-4">
            Попробовать снова
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Заголовок страницы */}
      <h1 className="text-[24px] leading-[32px] font-semibold text-[var(--color-text-primary)] mb-6">
        Адреса доставки
      </h1>

      {/* Список адресов */}
      <AddressList
        addresses={addresses}
        onEdit={handleEdit}
        onDelete={handleDeleteClick}
        onAddNew={handleAddNew}
        deletingId={deletingId}
        isLoading={isLoading}
      />

      {/* Модальное окно добавления/редактирования */}
      <AddressModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        address={editingAddress}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
        isSaving={isSaving}
      />

      {/* Диалог подтверждения удаления */}
      <ConfirmDialog
        isOpen={deleteConfirmOpen}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        title="Удалить адрес?"
        message="Вы уверены, что хотите удалить этот адрес? Это действие нельзя отменить."
        confirmText="Удалить"
        cancelText="Отмена"
        variant="danger"
      />
    </div>
  );
}
