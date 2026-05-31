import { defineStore } from 'pinia'
import { api } from '@/utils/api.js'

export const useWatchlistStore = defineStore('watchlist', {
  state: () => ({
    items: [],
    loading: false,
    error: '',
  }),
  actions: {
    async fetch() {
      this.loading = true
      this.error = ''
      try {
        this.items = await api.getWatchlist()
      } catch (e) {
        this.error = '加载失败：' + (e.message || e)
        this.items = []
      } finally {
        this.loading = false
      }
    },
    async add(ticker, name) {
      await api.addWatchlist(ticker.toUpperCase(), name)
      await this.fetch()
    },
    async remove(ticker) {
      await api.removeWatchlist(ticker)
      await this.fetch()
    },
  },
})
