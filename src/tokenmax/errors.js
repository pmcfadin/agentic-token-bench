class TokenmaxError extends Error {
  constructor({ message, code, agent = null, file = null, recoveryHint = null } = {}) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.agent = agent;
    this.file = file;
    this.recoveryHint = recoveryHint;
  }
}

class PreflightError extends TokenmaxError {
  constructor(opts) { super({ ...opts, code: "preflight_failed" }); }
}

class BackupError extends TokenmaxError {
  constructor(opts) { super({ ...opts, code: "backup_failed" }); }
}

class WriteError extends TokenmaxError {
  constructor(opts) { super({ ...opts, code: "write_failed" }); }
}

class ValidationError extends TokenmaxError {
  constructor(opts) { super({ ...opts, code: "validation_failed" }); }
}

class RollbackError extends TokenmaxError {
  constructor(opts) { super({ ...opts, code: "rollback_failed" }); }
}

module.exports = { TokenmaxError, PreflightError, BackupError, WriteError, ValidationError, RollbackError };
