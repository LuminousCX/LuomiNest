const sharp = require('sharp');
const pngToIco = require('png-to-ico');
const fs = require('fs');
const path = require('path');
const os = require('os');

const svgPath = path.join(__dirname, 'resources', 'icon.svg');
const icoPath = path.join(__dirname, 'resources', 'icon.ico');
const tmpDir = os.tmpdir();

const sizes = [256, 48, 32, 16];

async function generateIcon() {
  const pngPaths = await Promise.all(
    sizes.map(async (size) => {
      const pngPath = path.join(tmpDir, `icon-${size}.png`);
      await sharp(svgPath)
        .resize(size, size)
        .ensureAlpha()
        .png()
        .toFile(pngPath);
      return pngPath;
    })
  );

  const icoBuffer = await pngToIco.default(pngPaths);
  fs.writeFileSync(icoPath, icoBuffer);

  pngPaths.forEach(p => fs.unlinkSync(p));
  console.log(`✅ icon.ico generated with sizes: ${sizes.join(', ')}px`);
}

generateIcon().catch(console.error);
