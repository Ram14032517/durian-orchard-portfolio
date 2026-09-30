#pragma once

#include <Arduino.h>
#include <WiFiClient.h>

class TuyaLocal34 {
 public:
  TuyaLocal34(const char* deviceIp, const char* localKey);
  bool getStatus(String& json);
  const String& lastError() const;

 private:
  static const size_t MAX_PACKET = 2048;

  IPAddress ip_;
  uint8_t realKey_[16];
  uint8_t sessionKey_[16];
  uint32_t sequence_ = 1;
  String error_;
  WiFiClient client_;
  uint8_t packetBuffer_[MAX_PACKET];
  uint8_t cryptoBuffer_[MAX_PACKET];

  bool connectAndNegotiate();
  bool sendEncrypted(uint32_t command, const uint8_t* payload, size_t payloadLength,
                     const uint8_t key[16]);
  bool receiveEncrypted(uint32_t& command, uint8_t* plaintext, size_t& plaintextLength,
                        const uint8_t key[16], uint32_t timeoutMs = 5000);
  bool readExact(uint8_t* output, size_t length, uint32_t timeoutMs);
  bool aesEncrypt(const uint8_t key[16], const uint8_t* input, size_t inputLength,
                  uint8_t* output, size_t& outputLength, bool addPadding);
  bool aesDecrypt(const uint8_t key[16], const uint8_t* input, size_t inputLength,
                  uint8_t* output, size_t& outputLength);
  void hmacSha256(const uint8_t key[16], const uint8_t* data, size_t length,
                  uint8_t output[32]);
};
