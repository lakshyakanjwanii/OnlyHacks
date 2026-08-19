// One-off script to generate synthetic GS1 DataMatrix demo images.
// Run with: node scripts/generateBarcodes.js
// Not imported by the React app — this is a build-time/demo-prep tool only.

import bwipjs from 'bwip-js';
import { writeFile } from 'fs/promises';
import path from 'path';

const OUTPUT_DIR = path.resolve('public/test-barcodes');

const BARCODES = [
  {
    filename: 'clean-batch.png',
    label: 'CLEAN — LOT001 / Mfg 2025-01-01 / Expiry 2028-01-31 / SER001',
    text: '(01)08912345678900(11)250101(17)280131(10)LOT001(21)SER001',
  },
  {
    filename: 'conflict-batch.png',
    label: 'CONFLICT — LOT001 / Mfg 2025-01-01 / Expiry 2029-01-31 / SER002',
    text: '(01)08912345678900(11)250101(17)290131(10)LOT001(21)SER002',
  },
];

async function generate(barcode) {
  const png = await bwipjs.toBuffer({
    bcid: 'gs1datamatrix',
    text: barcode.text,
    scale: 12,
    includetext: false,
    backgroundcolor: 'FFFFFF',
    padding: 24,
  });

  const outPath = path.join(OUTPUT_DIR, barcode.filename);

  await writeFile(outPath, png);

  console.log(`✅ Generated ${barcode.filename}`);
  console.log(`   ${barcode.label}`);
  console.log(`   Encoded: ${barcode.text}`);
}

async function main() {
  console.log('Generating synthetic GS1 DataMatrix barcodes...\n');

  for (const barcode of BARCODES) {
    await generate(barcode);
  }

  console.log('\nDone. Files are in public/test-barcodes/');
}

main().catch((err) => {
  console.error('❌ Failed to generate barcodes:', err);
  process.exit(1);
});