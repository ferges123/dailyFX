/* eslint-disable no-console */
const isProd = import.meta.env.PROD;

export const logger = {
  log: (...args: unknown[]) => {
    if (!isProd) {
      console.log(...args);
    }
  },
  info: (...args: unknown[]) => {
    if (!isProd) {
      console.info(...args);
    }
  },
  warn: (...args: unknown[]) => {
    if (!isProd) {
      console.warn(...args);
    }
  },
  error: (...args: unknown[]) => {
    if (!isProd) {
      console.error(...args);
    }
  },
};
