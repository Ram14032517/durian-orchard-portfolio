#include "TuyaLocal34.h"

#include <esp_system.h>
#include <mbedtls/aes.h>
#include <mbedtls/md.h>

namespace {
constexpr uint32_t TUYA_PREFIX = 0x000055AA;
constexpr uint32_t TUYA_SUFFIX = 0x0000AA55;
constexpr uint16_t TUYA_PORT = 6668;
constexpr uint32_t CMD_SESSION_START = 3;
constexpr uint32_t CMD_SESSION_RESPONSE = 4;
constexpr uint32_t CMD_SESSION_FINISH = 5;
constexpr uint32_t CMD_DP_QUERY_NEW = 0x10;

void writeBe32(uint8_t* output, uint32_t value) {
  output[0] = (uint8_t)(value >> 24);
  output[1] = (uint8_t)(value >> 16);
  output[2] = (uint8_t)(value >> 8);
  output[3] = (uint8_t)value;
}

uint32_t readBe32(const uint8_t* input) {
  return ((uint32_t)input[0] << 24) | ((uint32_t)input[1] << 16) |
         ((uint32_t)input[2] << 8) | input[3];
}

bool sameBytes(const uint8_t* a, const uint8_t* b, size_t length) {
  uint8_t different = 0;
  for (size_t i = 0; i < length; ++i) different |= a[i] ^ b[i];
  return different == 0;
}
}  // namespace

TuyaLocal34::TuyaLocal34(const char* deviceIp, const char* localKey) {
  ip_.fromString(deviceIp);
  memset(realKey_, 0, sizeof(realKey_));
  if (localKey) memcpy(realKey_, localKey, min((size_t)16, strlen(localKey)));
}

const String& TuyaLocal34::lastError() const { return error_; }

void TuyaLocal34::hmacSha256(const uint8_t key[16], const uint8_t* data,
                             size_t length, uint8_t output[32]) {
  mbedtls_md_context_t context;
  const mbedtls_md_info_t* info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_init(&context);
  mbedtls_md_setup(&context, info, 1);
  mbedtls_md_hmac_starts(&context, key, 16);
  mbedtls_md_hmac_update(&context, data, length);
  mbedtls_md_hmac_finish(&context, output);
  mbedtls_md_free(&context);
}

bool TuyaLocal34::aesEncrypt(const uint8_t key[16], const uint8_t* input,
                             size_t inputLength, uint8_t* output,
                             size_t& outputLength, bool addPadding) {
  size_t paddedLength = inputLength;
  uint8_t padding = 0;
  if (addPadding) {
    padding = 16 - (inputLength % 16);
    paddedLength += padding;
  } else if (inputLength % 16 != 0) {
    error_ = "AES input is not a whole block";
    return false;
  }
  if (paddedLength > MAX_PACKET) {
    error_ = "AES payload too large";
    return false;
  }

  uint8_t block[16];
  mbedtls_aes_context aes;
  mbedtls_aes_init(&aes);
  if (mbedtls_aes_setkey_enc(&aes, key, 128) != 0) {
    mbedtls_aes_free(&aes);
    error_ = "AES key setup failed";
    return false;
  }

  for (size_t offset = 0; offset < paddedLength; offset += 16) {
    for (size_t i = 0; i < 16; ++i) {
      size_t sourceIndex = offset + i;
      block[i] = sourceIndex < inputLength ? input[sourceIndex] : padding;
    }
    if (mbedtls_aes_crypt_ecb(&aes, MBEDTLS_AES_ENCRYPT, block, output + offset) != 0) {
      mbedtls_aes_free(&aes);
      error_ = "AES encryption failed";
      return false;
    }
  }
  mbedtls_aes_free(&aes);
  outputLength = paddedLength;
  return true;
}

bool TuyaLocal34::aesDecrypt(const uint8_t key[16], const uint8_t* input,
                             size_t inputLength, uint8_t* output,
                             size_t& outputLength) {
  if (inputLength == 0 || inputLength % 16 != 0 || inputLength > MAX_PACKET) {
    error_ = "Invalid encrypted payload length";
    return false;
  }

  mbedtls_aes_context aes;
  mbedtls_aes_init(&aes);
  if (mbedtls_aes_setkey_dec(&aes, key, 128) != 0) {
    mbedtls_aes_free(&aes);
    error_ = "AES key setup failed";
    return false;
  }
  for (size_t offset = 0; offset < inputLength; offset += 16) {
    if (mbedtls_aes_crypt_ecb(&aes, MBEDTLS_AES_DECRYPT, input + offset,
                              output + offset) != 0) {
      mbedtls_aes_free(&aes);
      error_ = "AES decryption failed";
      return false;
    }
  }
  mbedtls_aes_free(&aes);

  uint8_t padding = output[inputLength - 1];
  if (padding < 1 || padding > 16 || padding > inputLength) {
    error_ = "Invalid AES padding";
    return false;
  }
  for (size_t i = inputLength - padding; i < inputLength; ++i) {
    if (output[i] != padding) {
      error_ = "Invalid AES padding bytes";
      return false;
    }
  }
  outputLength = inputLength - padding;
  return true;
}

bool TuyaLocal34::sendEncrypted(uint32_t command, const uint8_t* payload,
                                size_t payloadLength, const uint8_t key[16]) {
  size_t encryptedLength = 0;
  if (!aesEncrypt(key, payload, payloadLength, cryptoBuffer_, encryptedLength, true)) {
    return false;
  }

  const size_t packetLength = 16 + encryptedLength + 32 + 4;
  if (packetLength > MAX_PACKET) {
    error_ = "Tuya packet too large";
    return false;
  }

  writeBe32(packetBuffer_, TUYA_PREFIX);
  writeBe32(packetBuffer_ + 4, sequence_++);
  writeBe32(packetBuffer_ + 8, command);
  writeBe32(packetBuffer_ + 12, encryptedLength + 36);
  memcpy(packetBuffer_ + 16, cryptoBuffer_, encryptedLength);
  hmacSha256(key, packetBuffer_, 16 + encryptedLength,
             packetBuffer_ + 16 + encryptedLength);
  writeBe32(packetBuffer_ + packetLength - 4, TUYA_SUFFIX);

  if (client_.write(packetBuffer_, packetLength) != packetLength) {
    error_ = "Tuya socket write failed";
    return false;
  }
  return true;
}

bool TuyaLocal34::readExact(uint8_t* output, size_t length, uint32_t timeoutMs) {
  size_t received = 0;
  unsigned long started = millis();
  while (received < length && millis() - started < timeoutMs) {
    int available = client_.available();
    if (available > 0) {
      int count = client_.read(output + received, min((size_t)available, length - received));
      if (count > 0) received += count;
    } else if (!client_.connected()) {
      break;
    } else {
      delay(2);
    }
  }
  return received == length;
}

bool TuyaLocal34::receiveEncrypted(uint32_t& command, uint8_t* plaintext,
                                   size_t& plaintextLength, const uint8_t key[16],
                                   uint32_t timeoutMs) {
  if (!readExact(packetBuffer_, 16, timeoutMs)) {
    error_ = "Tuya response header timeout";
    return false;
  }
  if (readBe32(packetBuffer_) != TUYA_PREFIX) {
    error_ = "Tuya response prefix invalid";
    return false;
  }

  command = readBe32(packetBuffer_ + 8);
  uint32_t bodyLength = readBe32(packetBuffer_ + 12);
  if (bodyLength < 40 || 16 + bodyLength > MAX_PACKET) {
    error_ = "Tuya response length invalid";
    return false;
  }
  if (!readExact(packetBuffer_ + 16, bodyLength, timeoutMs)) {
    error_ = "Tuya response body timeout";
    return false;
  }

  const size_t packetLength = 16 + bodyLength;
  if (readBe32(packetBuffer_ + packetLength - 4) != TUYA_SUFFIX) {
    error_ = "Tuya response suffix invalid";
    return false;
  }

  uint8_t expectedHmac[32];
  hmacSha256(key, packetBuffer_, packetLength - 36, expectedHmac);
  if (!sameBytes(expectedHmac, packetBuffer_ + packetLength - 36, 32)) {
    error_ = "Tuya response HMAC invalid";
    return false;
  }

  const size_t encryptedLength = bodyLength - 40;  // retcode + HMAC + suffix
  if (encryptedLength == 0) {
    plaintextLength = 0;
    return true;
  }
  return aesDecrypt(key, packetBuffer_ + 20, encryptedLength, plaintext,
                    plaintextLength);
}

bool TuyaLocal34::connectAndNegotiate() {
  client_.stop();
  sequence_ = 1;
  if (!client_.connect(ip_, TUYA_PORT, 3000)) {
    error_ = "Cannot connect to weather station";
    return false;
  }
  client_.setNoDelay(true);
  client_.setTimeout(5000);

  uint8_t localNonce[16];
  esp_fill_random(localNonce, sizeof(localNonce));
  if (!sendEncrypted(CMD_SESSION_START, localNonce, sizeof(localNonce), realKey_)) {
    client_.stop();
    return false;
  }

  size_t responseLength = 0;
  uint32_t responseCommand = 0;
  if (!receiveEncrypted(responseCommand, cryptoBuffer_, responseLength, realKey_)) {
    error_ = "session handshake: " + error_;
    client_.stop();
    return false;
  }
  if (responseCommand != CMD_SESSION_RESPONSE || responseLength < 48) {
    error_ = "Tuya session response invalid";
    client_.stop();
    return false;
  }

  uint8_t nonceHmac[32];
  hmacSha256(realKey_, localNonce, sizeof(localNonce), nonceHmac);
  if (!sameBytes(nonceHmac, cryptoBuffer_ + 16, 32)) {
    error_ = "Tuya session nonce check failed";
    client_.stop();
    return false;
  }

  uint8_t finishHmac[32];
  hmacSha256(realKey_, cryptoBuffer_, 16, finishHmac);
  if (!sendEncrypted(CMD_SESSION_FINISH, finishHmac, sizeof(finishHmac), realKey_)) {
    client_.stop();
    return false;
  }

  uint8_t nonceXor[16];
  for (size_t i = 0; i < 16; ++i) nonceXor[i] = localNonce[i] ^ cryptoBuffer_[i];
  size_t sessionLength = 0;
  if (!aesEncrypt(realKey_, nonceXor, sizeof(nonceXor), sessionKey_, sessionLength,
                  false) || sessionLength != 16) {
    error_ = "Tuya session key generation failed";
    client_.stop();
    return false;
  }
  return true;
}

bool TuyaLocal34::getStatus(String& json) {
  json = "";
  error_ = "";
  if (!connectAndNegotiate()) return false;

  const uint8_t query[] = {'{', '}'};
  if (!sendEncrypted(CMD_DP_QUERY_NEW, query, sizeof(query), sessionKey_)) {
    client_.stop();
    return false;
  }

  for (int attempt = 0; attempt < 5; ++attempt) {
    size_t responseLength = 0;
    uint32_t responseCommand = 0;
    if (!receiveEncrypted(responseCommand, cryptoBuffer_, responseLength,
                          sessionKey_)) {
      error_ = "status query: " + error_;
      client_.stop();
      return false;
    }
    if (responseLength == 0) continue;

    size_t jsonStart = 0;
    while (jsonStart < responseLength && cryptoBuffer_[jsonStart] != '{') ++jsonStart;
    if (jsonStart == responseLength) continue;

    json.reserve(responseLength - jsonStart + 1);
    for (size_t i = jsonStart; i < responseLength; ++i) json += (char)cryptoBuffer_[i];
    client_.stop();
    return true;
  }

  client_.stop();
  error_ = "Tuya status JSON not received";
  return false;
}
