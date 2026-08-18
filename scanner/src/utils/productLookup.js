// scanner/src/utils/productLookup.js
import { findDrugByBarcode } from '../data/drugDatabase';

export async function lookupProduct(barcode) {
  const drug = findDrugByBarcode(barcode);

  if (drug) {
    return {
      found: true,
      name: drug.name,
      manufacturer: drug.manufacturer,
      composition: drug.composition,
      form: drug.form,
      batches: drug.batches, // full batch/MFD/EXP list
    };
  }

  return { found: false };
}