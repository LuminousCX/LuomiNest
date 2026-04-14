module.exports = {
  hooks: {
    readPackage: function (pkg) {
      // 修复某些包的兼容性问题
      if (pkg.name === 'electron-vite') {
        pkg.peerDependencies = pkg.peerDependencies || {}
        pkg.peerDependencies.vite = '*'
      }
      return pkg
    }
  }
}
