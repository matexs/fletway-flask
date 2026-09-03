import assert from 'node:assert/strict';
import test from 'node:test';
import { isTimeout } from '../k6/lib/timeout.js';

test('detects k6 timeout by error text and error code', () => {
  assert.equal(isTimeout({ error: 'request timeout', error_code: 0, timings: {} }), true);
  assert.equal(isTimeout({ error: '', error_code: 1050, timings: {} }), true);
});

test('detects timing timeout and rejects ordinary slow responses', () => {
  assert.equal(isTimeout({ error: '', error_code: 0, timings: { duration: 10001 } }, '10s'), true);
  assert.equal(isTimeout({ error: '', error_code: 0, timings: { duration: 10001 } }, '20s'), false);
});
