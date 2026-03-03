/**
 * Input sanitization utilities for preventing XSS and injection attacks
 */

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} text - The text to escape
 * @returns {string} - The escaped text
 */
export function escapeHtml(text) {
  if (typeof text !== "string") {
    return "";
  }
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Sanitize user input by removing potentially dangerous characters
 * @param {string} input - The input to sanitize
 * @param {Object} options - Sanitization options
 * @returns {string} - The sanitized input
 */
export function sanitizeInput(input, options = {}) {
  if (typeof input !== "string") {
    return "";
  }

  let sanitized = input;

  // Remove null bytes
  sanitized = sanitized.replace(/\0/g, "");

  // Trim whitespace unless explicitly disabled
  if (options.trim !== false) {
    sanitized = sanitized.trim();
  }

  // Limit length if specified
  if (options.maxLength && sanitized.length > options.maxLength) {
    sanitized = sanitized.substring(0, options.maxLength);
  }

  return sanitized;
}

/**
 * Validate and sanitize JSON input
 * @param {string} jsonString - The JSON string to validate
 * @returns {Object|null} - Parsed JSON or null if invalid
 */
export function sanitizeJson(jsonString) {
  if (typeof jsonString !== "string") {
    return null;
  }

  const sanitized = sanitizeInput(jsonString, { trim: true });

  try {
    return JSON.parse(sanitized);
  } catch (error) {
    console.warn("Invalid JSON input:", error.message);
    return null;
  }
}

/**
 * Validate email format
 * @param {string} email - The email to validate
 * @returns {boolean} - Whether the email is valid
 */
export function isValidEmail(email) {
  if (typeof email !== "string") {
    return false;
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Sanitize URL to prevent javascript: and data: URIs
 * @param {string} url - The URL to sanitize
 * @returns {string|null} - The sanitized URL or null if invalid
 */
export function sanitizeUrl(url) {
  if (typeof url !== "string") {
    return null;
  }

  const sanitized = sanitizeInput(url, { trim: true });

  // Block dangerous protocols
  const dangerousProtocols = ["javascript:", "data:", "vbscript:"];
  const lowerUrl = sanitized.toLowerCase();

  for (const protocol of dangerousProtocols) {
    if (lowerUrl.startsWith(protocol)) {
      console.warn("Blocked dangerous URL protocol:", protocol);
      return null;
    }
  }

  return sanitized;
}

/**
 * Create a safe text node for displaying user content
 * @param {string} text - The text to display
 * @returns {Text} - A safe text node
 */
export function createSafeTextNode(text) {
  return document.createTextNode(sanitizeInput(text));
}

/**
 * Safely set text content of an element
 * @param {HTMLElement} element - The element to update
 * @param {string} text - The text to set
 */
export function setSafeTextContent(element, text) {
  if (!element) {
    return;
  }
  element.textContent = sanitizeInput(text);
}

/**
 * Validate Firebase configuration object
 * @param {Object} config - The Firebase config to validate
 * @returns {Object} - Validation result with isValid flag and errors
 */
export function validateFirebaseConfig(config) {
  const result = {
    isValid: true,
    errors: [],
  };

  if (!config || typeof config !== "object") {
    result.isValid = false;
    result.errors.push("Configuration must be a valid JSON object");
    return result;
  }

  const requiredFields = ["apiKey", "authDomain", "projectId", "appId"];
  const missingFields = requiredFields.filter((field) => !config[field]);

  if (missingFields.length > 0) {
    result.isValid = false;
    result.errors.push(`Missing required fields: ${missingFields.join(", ")}`);
  }

  // Validate field formats
  if (config.apiKey && config.apiKey.length < 10) {
    result.isValid = false;
    result.errors.push("API key appears to be invalid");
  }

  if (config.authDomain && !config.authDomain.includes(".")) {
    result.isValid = false;
    result.errors.push("Auth domain must be a valid domain");
  }

  return result;
}
