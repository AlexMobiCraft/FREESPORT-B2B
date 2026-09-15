/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const toIco = require('to-ico');

const svgPath = path.join(__dirname, '..', 'public', 'Icons', 'Souvenirs.svg');
const outputPath = path.join(__dirname, '..', 'src', 'app', 'favicon.ico');

const svgContent = fs.readFileSync(svgPath, 'utf8');

// Извлекаем viewBox для определения размеров
const viewBoxMatch = svgContent.match(/viewBox="([^"]+)"/);
if (!viewBoxMatch) {
  console.error('ViewBox not found in SVG');
  process.exit(1);
}

const [, viewBox] = viewBoxMatch;
const [x, y, width, height] = viewBox.split(/\s+/).map(Number);
const maxDim = Math.max(width, height);
const paddingX = (maxDim - width) / 2;
const paddingY = (maxDim - height) / 2;

// Модифицируем SVG: квадратный viewBox + translate для центрирования
const newViewBox = `${x - paddingX} ${y - paddingY} ${maxDim} ${maxDim}`;

// Заменяем viewBox и добавляем transform к первому <g> или создаем wrapper
let modifiedSvg = svgContent
  .replace(/viewBox="[^"]+"/, `viewBox="${newViewBox}"`)
  .replace(/enable-background:new\s+[^;]+;/, ''); // убираем старый enable-background

// Если нет wrapper <g>, добавляем transform к существующему <g>
if (!modifiedSvg.includes('transform=')) {
  modifiedSvg = modifiedSvg.replace(/<g>/, `<g transform="translate(${paddingX}, ${paddingY})">`);
}

// Добавляем xmlns если отсутствует
if (!modifiedSvg.includes('xmlns="http://www.w3.org/2000/svg"')) {
  modifiedSvg = modifiedSvg.replace(/<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
}

async function main() {
  try {
    // Рендерим SVG в PNG 256x256 для качества
    const pngBuffer = await sharp(Buffer.from(modifiedSvg))
      .resize(256, 256, { fit: 'contain', background: { r: 255, g: 255, b: 255, alpha: 0 } })
      .png()
      .toBuffer();

    // Конвертируем PNG в ICO с размерами 16, 32, 48
    const icoBuffer = await toIco(pngBuffer, {
      resize: true,
      sizes: [16, 32, 48],
    });

    fs.writeFileSync(outputPath, icoBuffer);
    console.log(`Favicon created: ${outputPath}`);
    console.log(`Sizes included: 16x16, 32x32, 48x48`);
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  }
}

main();
