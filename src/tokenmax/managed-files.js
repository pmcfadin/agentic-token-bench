const {
  MANAGED_BLOCK_END,
  MANAGED_BLOCK_START,
} = require("./constants");

function buildManagedBlock(content) {
  return `${MANAGED_BLOCK_START}\n${content.trim()}\n${MANAGED_BLOCK_END}`;
}

function upsertManagedBlock(existingContent, newBlockContent) {
  const block = buildManagedBlock(newBlockContent);
  const trimmed = existingContent == null ? "" : existingContent.trimEnd();

  if (!trimmed) {
    return `${block}\n`;
  }

  const startIndex = trimmed.indexOf(MANAGED_BLOCK_START);
  const endIndex = trimmed.indexOf(MANAGED_BLOCK_END);

  if (startIndex >= 0 && endIndex > startIndex) {
    const prefix = trimmed.slice(0, startIndex).trimEnd();
    const suffix = trimmed.slice(endIndex + MANAGED_BLOCK_END.length).trimStart();
    return joinSegments([prefix, block, suffix]);
  }

  return joinSegments([trimmed, block]);
}

function removeManagedBlock(existingContent) {
  if (!existingContent) {
    return "";
  }

  const startIndex = existingContent.indexOf(MANAGED_BLOCK_START);
  const endIndex = existingContent.indexOf(MANAGED_BLOCK_END);

  if (startIndex < 0 || endIndex < startIndex) {
    return existingContent;
  }

  const prefix = existingContent.slice(0, startIndex).trimEnd();
  const suffix = existingContent.slice(endIndex + MANAGED_BLOCK_END.length).trimStart();
  return joinSegments([prefix, suffix]);
}

function extractManagedBlock(existingContent) {
  if (!existingContent) {
    return null;
  }
  const startIndex = existingContent.indexOf(MANAGED_BLOCK_START);
  const endIndex = existingContent.indexOf(MANAGED_BLOCK_END);
  if (startIndex < 0 || endIndex < startIndex) {
    return null;
  }
  return existingContent
    .slice(startIndex + MANAGED_BLOCK_START.length, endIndex)
    .trim();
}

function joinSegments(segments) {
  const filtered = segments.filter(Boolean);
  if (filtered.length === 0) {
    return "";
  }
  return `${filtered.join("\n\n")}\n`;
}

module.exports = {
  buildManagedBlock,
  extractManagedBlock,
  removeManagedBlock,
  upsertManagedBlock,
};
