// scanner/src/gs1Parser.js

// The invisible separator character used between variable-length GS1 fields.
// Real scanners (ZXing etc.) decode this as U+001D from the barcode's FNC1 encoding.
const GS = '\u001D';

// Definitions for the Application Identifiers we care about.
// fixedLength: number of chars if fixed, or null if variable-length.
const AI_DEFINITIONS = {
  '01': { field: 'gtin', fixedLength: 14 },
  '10': { field: 'batchNumber', fixedLength: null, maxLength: 20 },
  '11': { field: 'manufactureDate', fixedLength: 6 },
  '17': { field: 'expiryDate', fixedLength: 6 },
  '21': { field: 'serial', fixedLength: null, maxLength: 20 },
};

/**
 * Validates a GTIN-14's check digit using the GS1 Mod-10 algorithm.
 */
function isValidGTIN14(gtin) {
  if (!gtin || gtin.length !== 14 || !/^\d{14}$/.test(gtin)) {
    return false;
  }

  const digits = gtin.split('').map(Number);
  const checkDigit = digits[13];
  const base = digits.slice(0, 13);

  let sum = 0;

  for (let i = 0; i < base.length; i++) {
    // Rightmost of the 13 base digits gets weight 3,
    // alternating from there.
    const weight = (base.length - 1 - i) % 2 === 0 ? 3 : 1;
    sum += base[i] * weight;
  }

  const calculatedCheckDigit = (10 - (sum % 10)) % 10;

  return calculatedCheckDigit === checkDigit;
}

/**
 * Converts a GS1 date string "YYMMDD" into "YYYY-MM-DD".
 *
 * GS1 rule:
 * YY 00-49 => 2000-2049
 * YY 50-99 => 1950-1999
 *
 * Returns null if the date is malformed or invalid.
 */
function parseGS1Date(yymmdd) {
  if (!yymmdd || yymmdd.length !== 6 || !/^\d{6}$/.test(yymmdd)) {
    return null;
  }

  const yy = parseInt(yymmdd.slice(0, 2), 10);
  const mm = parseInt(yymmdd.slice(2, 4), 10);
  const dd = parseInt(yymmdd.slice(4, 6), 10);

  const year = yy <= 49 ? 2000 + yy : 1900 + yy;

  if (mm < 1 || mm > 12) {
    return null;
  }

  if (dd < 1 || dd > 31) {
    return null;
  }

  const date = new Date(Date.UTC(year, mm - 1, dd));

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== mm - 1 ||
    date.getUTCDate() !== dd
  ) {
    return null;
  }

  const pad = (n) => String(n).padStart(2, '0');

  return `${year}-${pad(mm)}-${pad(dd)}`;
}

/**
 * Parses a raw GS1 element string into structured drug data.
 *
 * Some GS1 DataMatrix decoders return a leading Group Separator
 * (U+001D). We remove ONLY leading separators.
 *
 * Internal Group Separators are preserved because they are required
 * to separate variable-length fields such as AI 10 (batch number)
 * from the next AI.
 *
 * @param {string} rawPayload
 * @returns {{
 *   gtin: string|null,
 *   batchNumber: string|null,
 *   expiryDate: string|null,
 *   manufactureDate: string|null,
 *   serial: string|null,
 *   rawPayload: string,
 *   errors: string[]
 * }}
 */
export function parseGS1(rawPayload) {
  const result = {
    gtin: null,
    batchNumber: null,
    expiryDate: null,
    manufactureDate: null,
    serial: null,
    rawPayload: rawPayload,
    errors: [],
  };

  if (typeof rawPayload !== 'string' || rawPayload.length === 0) {
    result.errors.push('Empty or invalid payload');
    return result;
  }

  // Some scanners prepend a Group Separator before the first AI.
  // Remove only leading GS characters.
  //
  // IMPORTANT:
  // Do NOT remove internal GS characters. They are needed to parse
  // variable-length fields such as AI 10 and AI 21.
  const payload = rawPayload.replace(/^\u001D+/, '');

  let pos = 0;

  while (pos < payload.length) {
    const ai = payload.slice(pos, pos + 2);

    if (!/^\d{2}$/.test(ai)) {
      result.errors.push(
        `Malformed AI at position ${pos}: "${ai}"`
      );
      break;
    }

    const def = AI_DEFINITIONS[ai];

    pos += 2;

    if (!def) {
      result.errors.push(
        `Unknown AI "${ai}" — stopping parse (cannot determine its length)`
      );
      break;
    }

    let value;

    // Fixed-length Application Identifier
    if (def.fixedLength !== null) {
      value = payload.slice(pos, pos + def.fixedLength);

      if (value.length < def.fixedLength) {
        result.errors.push(
          `AI ${ai} expected ${def.fixedLength} chars but payload ended early`
        );
        break;
      }

      pos += def.fixedLength;
    }

    // Variable-length Application Identifier
    else {
      const gsIndex = payload.indexOf(GS, pos);

      if (gsIndex === -1) {
        // No separator means this is the final field.
        value = payload.slice(pos);
        pos = payload.length;
      } else {
        // Read until the Group Separator.
        value = payload.slice(pos, gsIndex);

        // Skip the separator and continue with the next AI.
        pos = gsIndex + 1;
      }

      if (def.maxLength && value.length > def.maxLength) {
        result.errors.push(
          `AI ${ai} value exceeds max length ${def.maxLength}`
        );
      }
    }

    // AI 17 = Expiry date
    if (ai === '17') {
      const parsed = parseGS1Date(value);

      if (parsed === null) {
        result.errors.push(
          `AI 17 (expiry) has invalid date value: "${value}"`
        );
      }

      result.expiryDate = parsed;
    }

    // AI 11 = Manufacture date
    else if (ai === '11') {
      const parsed = parseGS1Date(value);

      if (parsed === null) {
        result.errors.push(
          `AI 11 (manufacture date) has invalid date value: "${value}"`
        );
      }

      result.manufactureDate = parsed;
    }

    // AI 01 = GTIN
    else if (ai === '01') {
      if (!isValidGTIN14(value)) {
        result.errors.push(
          `AI 01 (GTIN) has invalid check digit: "${value}"`
        );
      }

      result.gtin = value;
    }

    // AI 10 / AI 21
    else {
      result[def.field] = value;
    }
  }

  // Required fields
  if (!result.gtin) {
    result.errors.push(
      'Missing required field: GTIN (AI 01)'
    );
  }

  if (!result.batchNumber) {
    result.errors.push(
      'Missing required field: batch number (AI 10)'
    );
  }

  return result;
}