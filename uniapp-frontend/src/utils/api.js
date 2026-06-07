/**
 * 统一封装与 C# 后端的 HTTP 通信。
 * H5 dev 模式下走 vite 代理 (/api -> localhost:28200)，避免跨域问题。
 * 小程序模式必须使用绝对地址，因此通过 BASE_URL 切换。
 */

const BASE_URL =
  // #ifdef H5
  '' // H5 走 vite 代理，相对路径
  // #endif
  // #ifndef H5
  + 'http://localhost:28200'
  // #endif

function request({ url, method = 'GET', data, header }) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE_URL + url,
      method,
      data,
      header: { 'Content-Type': 'application/json', ...(header || {}) },
      timeout: 30000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${JSON.stringify(res.data)}`))
        }
      },
      fail: (err) => reject(err),
    })
  })
}

export const api = {
  health: () => request({ url: '/health' }),

  // 阶段一已有的 endpoint
  triggerAnalysis: (ticker, date) =>
    request({ url: '/api/analysis/trigger', method: 'POST', data: { ticker, date } }),
  getJob: (jobId) =>
    request({ url: `/api/analysis/jobs/${jobId}` }),

  // 阶段二即将添加的 endpoint
  getWatchlist: () => request({ url: '/api/watchlist' }),
  addWatchlist: (ticker, name) =>
    request({ url: '/api/watchlist', method: 'POST', data: { ticker, name } }),
  removeWatchlist: (ticker) =>
    request({ url: `/api/watchlist/${ticker}`, method: 'DELETE' }),
  getHistory: (params) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request({ url: '/api/history' + qs })
  },

  // 设置页：推送时间 + LLM 默认模型
  getSettings: () => request({ url: '/api/settings' }),
  updateSettings: (data) =>
    request({ url: '/api/settings', method: 'POST', data }),
  getProviders: () => request({ url: '/api/settings/providers' }),
}
