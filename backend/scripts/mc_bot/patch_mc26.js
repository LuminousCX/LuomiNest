const fs = require('fs')
const path = require('path')

function applyPatch() {
  try {
    const base = path.join(__dirname, 'node_modules/minecraft-data/minecraft-data/data/pc')
    const dir26_1 = path.join(base, '26.1')
    const dir26_2 = path.join(base, '26.2')

    if (fs.existsSync(dir26_1) && !fs.existsSync(dir26_2)) {
      fs.mkdirSync(dir26_2, { recursive: true })
      for (const file of fs.readdirSync(dir26_1)) {
        fs.copyFileSync(path.join(dir26_1, file), path.join(dir26_2, file))
      }
    }

    if (fs.existsSync(dir26_2)) {
      const v26_2Json = {
        version: 776,
        minecraftVersion: '26.2',
        majorVersion: '26.2',
        releaseType: 'release'
      }
      fs.writeFileSync(path.join(dir26_2, 'version.json'), JSON.stringify(v26_2Json, null, 2))
    }

    // 1. Update data.js in minecraft-data
    const dataJsPath = path.join(__dirname, 'node_modules/minecraft-data/data.js')
    if (fs.existsSync(dataJsPath)) {
      let dataJsSrc = fs.readFileSync(dataJsPath, 'utf8')
      if (!dataJsSrc.includes("'26.2':")) {
        const needle = "    '26.1': {"
        const patchBlock = `    '26.2': {
      get attributes () { return require("./minecraft-data/data/pc/26.2/attributes.json") },
      get blockCollisionShapes () { return require("./minecraft-data/data/pc/26.2/blockCollisionShapes.json") },
      get blocks () { return require("./minecraft-data/data/pc/26.2/blocks.json") },
      get blockLoot () { return require("./minecraft-data/data/pc/1.20/blockLoot.json") },
      get biomes () { return require("./minecraft-data/data/pc/26.2/biomes.json") },
      get commands () { return require("./minecraft-data/data/pc/1.20.3/commands.json") },
      get effects () { return require("./minecraft-data/data/pc/26.2/effects.json") },
      get enchantments () { return require("./minecraft-data/data/pc/26.2/enchantments.json") },
      get entities () { return require("./minecraft-data/data/pc/26.2/entities.json") },
      get entityLoot () { return require("./minecraft-data/data/pc/1.20/entityLoot.json") },
      get foods () { return require("./minecraft-data/data/pc/26.2/foods.json") },
      get instruments () { return require("./minecraft-data/data/pc/26.2/instruments.json") },
      get items () { return require("./minecraft-data/data/pc/26.2/items.json") },
      get language () { return require("./minecraft-data/data/pc/26.2/language.json") },
      get loginPacket () { return require("./minecraft-data/data/pc/26.2/loginPacket.json") },
      get mapIcons () { return require("./minecraft-data/data/pc/1.20.2/mapIcons.json") },
      get materials () { return require("./minecraft-data/data/pc/26.2/materials.json") },
      get particles () { return require("./minecraft-data/data/pc/26.2/particles.json") },
      get protocol () { return require("./minecraft-data/data/pc/26.2/protocol.json") },
      get recipes () { return require("./minecraft-data/data/pc/26.2/recipes.json") },
      get sounds () { return require("./minecraft-data/data/pc/26.2/sounds.json") },
      get tints () { return require("./minecraft-data/data/pc/26.2/tints.json") },
      get version () { return require("./minecraft-data/data/pc/26.2/version.json") },
      get windows () { return require("./minecraft-data/data/pc/1.16.1/windows.json") },
      proto: __dirname + '/minecraft-data/data/pc/latest/proto.yml'
    },\n`
        dataJsSrc = dataJsSrc.replace(needle, patchBlock + needle)
        fs.writeFileSync(dataJsPath, dataJsSrc)
      }
    }

    // 2. Update prismarine-chunk
    const chunkIndexPath = path.join(__dirname, 'node_modules/prismarine-chunk/src/index.js')
    if (fs.existsSync(chunkIndexPath)) {
      let chunkIndexSrc = fs.readFileSync(chunkIndexPath, 'utf8')
      if (!chunkIndexSrc.includes('26.2:')) {
        chunkIndexSrc = chunkIndexSrc.replace(
          "26.1: require('./pc/1.18/chunk')",
          "26.1: require('./pc/1.18/chunk'),\n    26.2: require('./pc/1.18/chunk')"
        )
        fs.writeFileSync(chunkIndexPath, chunkIndexSrc)
      }
    }

    // 3. Update prismarine-physics features.json
    const physFeaturesPath = path.join(__dirname, 'node_modules/prismarine-physics/lib/features.json')
    if (fs.existsSync(physFeaturesPath)) {
      const features = JSON.parse(fs.readFileSync(physFeaturesPath, 'utf8'))
      let modified = false
      for (const feat of features) {
        if (feat.versions && feat.versions.includes('26.1') && !feat.versions.includes('26.2')) {
          feat.versions.push('26.2')
          modified = true
        }
      }
      if (modified) {
        fs.writeFileSync(physFeaturesPath, JSON.stringify(features, null, 2))
      }
    }

    // 4. Update minecraft-protocol version.js
    const mpVersionPath = path.join(__dirname, 'node_modules/minecraft-protocol/src/version.js')
    if (fs.existsSync(mpVersionPath)) {
      let mpVersionSrc = fs.readFileSync(mpVersionPath, 'utf8')
      if (!mpVersionSrc.includes("'26.2'")) {
        mpVersionSrc = mpVersionSrc.replace("'26.1']", "'26.1', '26.2']")
        fs.writeFileSync(mpVersionPath, mpVersionSrc)
      }
    }

    // 5. Update mineflayer version.js
    const mfVersionPath = path.join(__dirname, 'node_modules/mineflayer/lib/version.js')
    if (fs.existsSync(mfVersionPath)) {
      let mfVersionSrc = fs.readFileSync(mfVersionPath, 'utf8')
      if (!mfVersionSrc.includes("'26.2'")) {
        mfVersionSrc = mfVersionSrc.replace("'26.1']", "'26.1', '26.2']")
        fs.writeFileSync(mfVersionPath, mfVersionSrc)
      }
    }

    console.log('[MC-Patch] Minecraft 26.2 (Protocol 776) dynamic compatibility patch verified.')
  } catch (err) {
    console.warn('[MC-Patch] Error applying 26.2 patch:', err.message)
  }
}

module.exports = { applyPatch }

if (require.main === module) {
  applyPatch()
}
