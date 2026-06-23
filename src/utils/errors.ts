// src/utils/errors.ts

/** Base for all app errors — carries a code, structured context, and a recoverable flag. */
export class AppError extends Error {
  readonly code: string;
  readonly context: Record<string, unknown>;
  readonly recoverable: boolean;

  constructor(message: string, code: string, context: Record<string, unknown> = {}, recoverable = true) {
    super(message);
    this.name = 'AppError';
    this.code = code;
    this.context = context;
    this.recoverable = recoverable;
  }
}

export class GeometryError extends AppError {
  constructor(message: string, context: Record<string, unknown> = {}) {
    super(message, 'GEOMETRY_ERROR', context, true);
    this.name = 'GeometryError';
  }
}

export class AssetLoadError extends AppError {
  constructor(assetPath: string, cause?: Error) {
    super(`Failed to load asset: ${assetPath}`, 'ASSET_LOAD_ERROR', { assetPath, originalError: cause?.message }, true);
    this.name = 'AssetLoadError';
  }
}

export class StoreCorruptionError extends AppError {
  constructor(sliceName: string, details: string) {
    super(`Store corruption in ${sliceName}: ${details}`, 'STORE_CORRUPTION', { sliceName, details }, false);
    this.name = 'StoreCorruptionError';
  }
}

export class VastuCalculationError extends AppError {
  constructor(message: string, context: Record<string, unknown> = {}) {
    super(message, 'VASTU_CALC_ERROR', context, true);
    this.name = 'VastuCalculationError';
  }
}
