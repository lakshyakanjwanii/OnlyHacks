import { describe, it, expect } from 'vitest';
import { parseGS1 } from '../src/gs1Parser';

const GS = '\u001D';

describe('parseGS1 — clean demo barcode', () => {
  const raw = '01' + '08912345678900' + '17' + '280131' + '10' + 'LOT001' + GS + '21' + 'SER001';

  it('extracts GTIN correctly', () => {
    const result = parseGS1(raw);
    expect(result.gtin).toBe('08912345678900');
  });

  it('extracts and converts expiry date correctly', () => {
    const result = parseGS1(raw);
    expect(result.expiryDate).toBe('2028-01-31');
  });

  it('extracts batch number correctly (variable-length, followed by GS)', () => {
    const result = parseGS1(raw);
    expect(result.batchNumber).toBe('LOT001');
  });

  it('extracts serial number correctly (variable-length, last field, no GS)', () => {
    const result = parseGS1(raw);
    expect(result.serial).toBe('SER001');
  });

  it('has no errors', () => {
    const result = parseGS1(raw);
    expect(result.errors).toHaveLength(0);
  });
});

describe('parseGS1 — conflict demo barcode', () => {
  const raw = '01' + '08912345678900' + '17' + '290131' + '10' + 'LOT001' + GS + '21' + 'SER002';

  it('has the SAME gtin and batch as the clean barcode', () => {
    const result = parseGS1(raw);
    expect(result.gtin).toBe('08912345678900');
    expect(result.batchNumber).toBe('LOT001');
  });

  it('has a DIFFERENT expiry date than the clean barcode', () => {
    const result = parseGS1(raw);
    expect(result.expiryDate).toBe('2029-01-31');
  });

  it('has a different serial number', () => {
    const result = parseGS1(raw);
    expect(result.serial).toBe('SER002');
  });
});

describe('parseGS1 — manufacture date (AI 11, optional)', () => {
  const raw =
    '01' + '08912345678900' + '11' + '250601' + '17' + '280131' + '10' + 'LOT001' + GS + '21' + 'SER001';

  it('extracts manufacture date when present', () => {
    const result = parseGS1(raw);
    expect(result.manufactureDate).toBe('2025-06-01');
  });
});

describe('parseGS1 — batch as the LAST field (no serial, no trailing GS needed)', () => {
  const raw = '01' + '08912345678900' + '17' + '280131' + '10' + 'LOT001';

  it('still extracts batch number correctly when it runs to end of string', () => {
    const result = parseGS1(raw);
    expect(result.batchNumber).toBe('LOT001');
    expect(result.serial).toBeNull();
  });
});

describe('parseGS1 — invalid / malformed input', () => {
  it('returns errors for an empty string', () => {
    const result = parseGS1('');
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('flags an invalid expiry date (month 13)', () => {
    const raw = '01' + '08912345678900' + '17' + '281301' + '10' + 'LOT001';
    const result = parseGS1(raw);
    expect(result.expiryDate).toBeNull();
    expect(result.errors.some((e) => e.includes('AI 17'))).toBe(true);
  });

  it('flags a truncated GTIN (fixed-length field cut short)', () => {
    const raw = '01' + '0891234'; // way less than 14 digits
    const result = parseGS1(raw);
    expect(result.errors.some((e) => e.includes('expected 14 chars'))).toBe(true);
  });

  it('flags an unknown AI and stops parsing safely (no crash)', () => {
    const raw = '99' + '12345' + '01' + '08912345678900';
    const result = parseGS1(raw);
    expect(result.errors.some((e) => e.includes('Unknown AI'))).toBe(true);
  });

  it('flags missing required fields (no GTIN, no batch)', () => {
    const raw = '21' + 'SER001';
    const result = parseGS1(raw);
    expect(result.errors).toContain('Missing required field: GTIN (AI 01)');
    expect(result.errors).toContain('Missing required field: batch number (AI 10)');
  });
});