// 主题初始化：必须在 Vue 应用挂载前同步执行，避免主题闪烁。
// 抽成外部脚本以避免 CSP 'unsafe-inline'（生产环境 script-src 不含 'unsafe-inline'）。
;(function () {
  try {
    var t = localStorage.getItem('luominest-theme')
    if (t !== 'dark') document.documentElement.setAttribute('data-theme', 'light')
  } catch (e) {
    // localStorage 不可用时（如隐私模式/沙箱），默认浅色主题
    document.documentElement.setAttribute('data-theme', 'light')
  }
})()
