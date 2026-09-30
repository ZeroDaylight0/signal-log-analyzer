const STORAGE_KEY = "signal-log-provider-settings-v1";
const ITERATIONS = 310_000;

function bytesToBase64(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function base64ToBytes(value) {
  return Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
}

async function encryptionKey(password, salt) {
  const material = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveKey"],
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: ITERATIONS, hash: "SHA-256" },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

export function hasSavedSettings() {
  return localStorage.getItem(STORAGE_KEY) !== null;
}

export async function saveSettings(settings, password) {
  if (password.length < 12) throw new Error("Пароль шифрования должен содержать не менее 12 символов.");
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await encryptionKey(password, salt);
  const encrypted = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    new TextEncoder().encode(JSON.stringify(settings)),
  );
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    version: 1,
    iterations: ITERATIONS,
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    ciphertext: bytesToBase64(new Uint8Array(encrypted)),
  }));
}

export async function unlockSettings(password) {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) throw new Error("Сохранённые настройки не найдены.");
  const envelope = JSON.parse(stored);
  if (envelope.version !== 1 || envelope.iterations !== ITERATIONS) {
    throw new Error("Формат сохранённых настроек не поддерживается.");
  }
  const salt = base64ToBytes(envelope.salt);
  const iv = base64ToBytes(envelope.iv);
  const key = await encryptionKey(password, salt);
  try {
    const decrypted = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv },
      key,
      base64ToBytes(envelope.ciphertext),
    );
    return JSON.parse(new TextDecoder().decode(decrypted));
  } catch (error) {
    if (error instanceof DOMException && error.name === "OperationError") {
      throw new Error("Пароль не подошёл или настройки повреждены.");
    }
    throw error;
  }
}

export function forgetSettings() {
  localStorage.removeItem(STORAGE_KEY);
}
