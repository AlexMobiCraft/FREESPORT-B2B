import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import favoriteService from '@/services/favoriteService';
import type { Favorite } from '@/types/favorite';
import { useAuthStore } from './authStore';

interface FavoritesState {
  favorites: Favorite[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchFavorites: () => Promise<void>;
  addFavorite: (productId: number) => Promise<void>;
  removeFavorite: (productId: number) => Promise<void>;
  isFavorite: (productId: number) => boolean;
  toggleFavorite: (productId: number) => Promise<void>;
  clearFavorites: () => void;
}

export const useFavoritesStore = create<FavoritesState>()(
  devtools(
    (set, get) => ({
      favorites: [],
      isLoading: false,
      error: null,

      fetchFavorites: async () => {
        const { isAuthenticated } = useAuthStore.getState();
        if (!isAuthenticated) {
          set({ favorites: [], error: null });
          return;
        }

        set({ isLoading: true, error: null });
        try {
          const favorites = await favoriteService.getFavorites();
          set({ favorites, isLoading: false });
        } catch (error) {
          // Basic error handling
          const message = error instanceof Error ? error.message : 'Не удалось загрузить избранное';
          set({ error: message, isLoading: false });
        }
      },

      addFavorite: async (productId: number) => {
        set({ isLoading: true, error: null });
        try {
          const newFavorite = await favoriteService.addFavorite(productId);
          set(state => ({
            favorites: [newFavorite, ...state.favorites],
            isLoading: false,
          }));
        } catch (error) {
          const message =
            error instanceof Error ? error.message : 'Не удалось добавить в избранное';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      removeFavorite: async (productId: number) => {
        // Find favorite ID by product ID
        const state = get();
        const favorite = state.favorites.find(f => f.product === productId);

        if (!favorite) return;

        set({ isLoading: true, error: null });
        try {
          await favoriteService.removeFavorite(favorite.id);
          set(state => ({
            favorites: state.favorites.filter(f => f.id !== favorite.id),
            isLoading: false,
          }));
        } catch (error) {
          const message =
            error instanceof Error ? error.message : 'Не удалось удалить из избранного';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      isFavorite: (productId: number) => {
        return get().favorites.some(f => f.product === productId);
      },

      toggleFavorite: async (productId: number) => {
        const isFav = get().isFavorite(productId);
        if (isFav) {
          await get().removeFavorite(productId);
        } else {
          await get().addFavorite(productId);
        }
      },

      clearFavorites: () => {
        set({ favorites: [], error: null });
      },
    }),
    { name: 'FavoritesStore' }
  )
);
