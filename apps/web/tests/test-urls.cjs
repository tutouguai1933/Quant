const WEB_BASE_URL = process.env.QUANT_WEB_BASE_URL || "http://127.0.0.1:9012";
const API_BASE_URL = process.env.QUANT_API_BASE_URL || "http://127.0.0.1:9011/api/v1";

module.exports = {
  WEB_BASE_URL,
  API_BASE_URL,
};
