/*
 * For a detailed explanation regarding each configuration property, visit:
 * https://jestjs.io/docs/configuration
 */

module.exports = {
  testEnvironment: 'jsdom',
  testMatch: [
    '**/test/js/**/*.test.js',
    '**/test/js/**/*.test.ts',
  ],
  collectCoverageFrom: [
    'kalanjiyam/static/js/*.{js,ts}',
    '!kalanjiyam/static/js/*.d.ts',
  ],
  moduleNameMapping: {
    '^@/(.*)': '<rootDir>/kalanjiyam/static/js/$1',
  },
  setupFilesAfterEnv: ['<rootDir>/test/js/setup.js'],
  transform: {
    '^.+\\.ts$': 'ts-jest',
  },
  globals: {
    'ts-jest': {
      tsconfig: 'tsconfig.json',
    },
  },
};
