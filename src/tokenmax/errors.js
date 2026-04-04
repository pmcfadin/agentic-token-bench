class PreflightError extends Error {
  constructor({ message, agent = null, file = null, recoveryHint = null } = {}) {
    super(message);
    this.name = "PreflightError";
    this.code = "preflight_failed";
    this.agent = agent;
    this.file = file;
    this.recoveryHint = recoveryHint;
  }
}

class BackupError extends Error {
  constructor({ message, agent = null, file = null, recoveryHint = null } = {}) {
    super(message);
    this.name = "BackupError";
    this.code = "backup_failed";
    this.agent = agent;
    this.file = file;
    this.recoveryHint = recoveryHint;
  }
}

class WriteError extends Error {
  constructor({ message, agent = null, file = null, recoveryHint = null } = {}) {
    super(message);
    this.name = "WriteError";
    this.code = "write_failed";
    this.agent = agent;
    this.file = file;
    this.recoveryHint = recoveryHint;
  }
}

class ValidationError extends Error {
  constructor({ message, agent = null, file = null, recoveryHint = null } = {}) {
    super(message);
    this.name = "ValidationError";
    this.code = "validation_failed";
    this.agent = agent;
    this.file = file;
    this.recoveryHint = recoveryHint;
  }
}

class RollbackError extends Error {
  constructor({ message, agent = null, file = null, recoveryHint = null } = {}) {
    super(message);
    this.name = "RollbackError";
    this.code = "rollback_failed";
    this.agent = agent;
    this.file = file;
    this.recoveryHint = recoveryHint;
  }
}

module.exports = { PreflightError, BackupError, WriteError, ValidationError, RollbackError };
