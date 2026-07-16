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

// Serenity 独立模块直连 Python FastAPI（C# appsettings.PythonApi.BaseUrl 同口径），
// 不走 C# proxy 层；后端 CORS allow_origins=["*"]。
const SERENITY_BASE_URL = 'http://localhost:28100'

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

function serenityRequest({ url, method = 'GET', data, header }) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: SERENITY_BASE_URL + url,
      method,
      data,
      header: { 'Content-Type': 'application/json', ...(header || {}) },
      timeout: 60000,
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
  // 手动推已完成的分析报告到 Server酱（设置页"自动推送"关时由前端按钮触发）
  pushAnalysis: (jobId) =>
    request({ url: `/api/analysis/jobs/${jobId}/push`, method: 'POST' }),

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

// Serenity 产业链卡点研究（独立模块，详见 docs/spec-serenity-research.md）
export const serenityApi = {
  health: () => serenityRequest({ url: '/api/v1/serenity/health' }),
  scan: (payload) =>
    serenityRequest({ url: '/api/v1/serenity/scan', method: 'POST', data: payload }),
  getJob: (jobId) =>
    serenityRequest({ url: `/api/v1/serenity/jobs/${jobId}` }),
  listJobs: () => serenityRequest({ url: '/api/v1/serenity/jobs' }),
}

// 量化工具箱：存储板块杠杆产品成交额 / 正股成交额。
export const quantApi = {
  memoryLeverage: (days = 730, refresh = false) =>
    serenityRequest({
      url: `/api/v1/quant/memory-leverage-ratios?days=${days}&refresh=${refresh}`,
    }),
}
