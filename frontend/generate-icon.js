const sharp = require('sharp');
const pngToIco = require('png-to-ico');
const fs = require('fs');
const path = require('path');
const os = require('os');

const svgPath = path.join(__dirname, 'resources', 'icon.svg');
const icoPath = path.join(__dirname, 'resources', 'icon.ico');
const pngPath = path.join(__dirname, 'resources', 'icon.png');
const tmpDir = os.tmpdir();

const sizes = [256, 48, 32, 16];

async function generateIcon() {
  if (!fs.existsSync(svgPath)) {
    console.error(`Error: SVG file not found at ${svgPath}`);
    process.exit(1);
  }

  // Generate icon.png (256x256 for tray and window icon)
  await sharp(svgPath)
    .resize(256, 256)
    .ensureAlpha()
    .png()
    .toFile(pngPath);
  console.log('icon.png generated (256x256)');

  const pngPaths = await Promise.all(
    sizes.map(async (size) => {
      const tmpPngPath = path.join(tmpDir, `icon-${size}.png`);
      await sharp(svgPath)
        .resize(size, size)
        .ensureAlpha()
        .png()
        .toFile(tmpPngPath);
      return tmpPngPath;
    })
  );

  const icoBuffer = await pngToIco.default(pngPaths);
  fs.writeFileSync(icoPath, icoBuffer);

  pngPaths.forEach(p => fs.unlinkSync(p));
  console.log(`icon.ico generated with sizes: ${sizes.join(', ')}px`);
}

generateIcon().catch(console.error);
