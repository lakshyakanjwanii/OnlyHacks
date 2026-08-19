// scanner/src/data/drugDatabase.js
//
// ONE dataset per drug: barcode (what the camera scans), product info,
// and known batch records (batch, MFD, EXP). Crocin's batches are REAL
// (physically scanned from two boxes). Every other drug's batches are
// SYNTHETIC (real drug name, made-up batch/expiry) so you can test
// detectConflict() firing on them too.

function computeEAN13CheckDigit(base12) {
  const digits = base12.split('').map(Number);
  const sum = digits.reduce((acc, d, i) => acc + d * (i % 2 === 0 ? 1 : 3), 0);
  const mod = sum % 10;
  return mod === 0 ? 0 : 10 - mod;
}
function makeEAN13(base12) {
  return base12 + computeEAN13CheckDigit(base12);
}

export const DRUGS = [
  {
    barcode: '8901571010554', // REAL — scanned from physical package
    name: 'Crocin Advance',
    manufacturer: 'GlaxoSmithKline Pharma Ltd (Marketed by GSK Asia Pvt Ltd)',
    composition: 'Paracetamol 500mg',
    form: 'Tablet',
    batches: [
      { batch: 'EA26025', mfd: '2026-02', expiry: '2028-01', real: true },
      { batch: 'EA26003', mfd: '2026-01', expiry: '2027-12', real: true },
    ],
  },
  {
    barcode: makeEAN13('890200000001'), // SYNTHETIC barcode, real drug name
    name: 'Dolo 650',
    manufacturer: 'Micro Labs Ltd',
    composition: 'Paracetamol 650mg',
    form: 'Tablet',
    batches: [
      { batch: 'LOT2401', mfd: '2025-06', expiry: '2027-06', real: false },
      { batch: 'LOT2401', mfd: '2025-06', expiry: '2028-06', real: false }, // same batch, altered expiry -> conflict
    ],
  },
  {
    barcode: makeEAN13('890200000002'),
    name: 'Pantocid 40',
    manufacturer: 'Sun Pharmaceutical Industries Ltd',
    composition: 'Pantoprazole 40mg',
    form: 'Tablet',
    batches: [
      { batch: 'LOT2402', mfd: '2025-09', expiry: '2026-09', real: false },
      { batch: 'LOT2402', mfd: '2025-09', expiry: '2027-09', real: false },
    ],
  },
  {
    barcode: makeEAN13('890200000003'),
    name: 'Augmentin 625 Duo Tablet',
    manufacturer: 'Glaxo SmithKline Pharmaceuticals Ltd',
    composition: 'Amoxycillin 500mg + Clavulanic Acid 125mg',
    form: 'Tablet',
    batches: [
      { batch: 'LOT2403', mfd: '2025-12', expiry: '2027-12', real: false },
      { batch: 'LOT2403', mfd: '2025-12', expiry: '2028-12', real: false },
    ],
  },
  {
    barcode: makeEAN13('890200000004'),
    name: 'Combiflam',
    manufacturer: 'Sanofi India Ltd',
    composition: 'Ibuprofen 400mg + Paracetamol 325mg',
    form: 'Tablet',
    batches: [
      { batch: 'LOT2404', mfd: '2025-02', expiry: '2026-02', real: false },
      { batch: 'LOT2404', mfd: '2025-02', expiry: '2027-02', real: false },
    ],
  },
  {
    barcode: makeEAN13('890200000005'),
    name: 'Azithral 500 Tablet',
    manufacturer: 'Alembic Pharmaceuticals Ltd',
    composition: 'Azithromycin 500mg',
    form: 'Tablet',
    batches: [
      { batch: 'LOT2405', mfd: '2025-08', expiry: '2027-08', real: false },
      { batch: 'LOT2405', mfd: '2025-08', expiry: '2028-08', real: false },
    ],
  },
];

export function findDrugByBarcode(barcode) {
  return DRUGS.find((d) => d.barcode === barcode) || null;
}