#ifndef SENSOR_FUSION_H
#define SENSOR_FUSION_H

#include <ap_fixed.h>
#include <hls_stream.h>

#define WEIGHT_SOIL      0.35f
#define WEIGHT_TEMP      0.25f
#define WEIGHT_HUMIDITY  0.20f
#define WEIGHT_WIND      0.20f

#define SOIL_MIN         0.0f
#define SOIL_MAX         100.0f
#define TEMP_MIN         -10.0f
#define TEMP_MAX         50.0f
#define HUMIDITY_MIN     0.0f
#define HUMIDITY_MAX     100.0f
#define WIND_MIN         0.0f
#define WIND_MAX         30.0f

#define RISK_CRITICAL    0.80f
#define RISK_HIGH        0.60f
#define RISK_MEDIUM      0.40f
#define RISK_LOW         0.20f

#define REG_SOIL_MOISTURE   0x00
#define REG_TEMPERATURE     0x04
#define REG_HUMIDITY        0x08
#define REG_WIND_SPEED      0x0C
#define REG_RISK_SCORE      0x10
#define REG_RISK_LEVEL      0x14
#define REG_STATUS          0x18
#define REG_CONTROL         0x1C

#define STATUS_DONE         0x01
#define STATUS_IDLE         0x02
#define STATUS_READY        0x04

#define CTRL_START          0x01
#define CTRL_RESET          0x02

typedef ap_fixed<32, 16> fixed32_t;
typedef ap_fixed<16, 8>  fixed16_t;

typedef enum {
    LEVEL_MINIMAL  = 0,
    LEVEL_LOW      = 1,
    LEVEL_MEDIUM   = 2,
    LEVEL_HIGH     = 3,
    LEVEL_CRITICAL = 4
} risk_level_t;

typedef struct {
    bool done;
    bool idle;
    bool ready;
    unsigned int compute_count;
} accel_status_t;

void fusion_accelerator(
    float soil_moisture,
    float temperature,
    float humidity,
    float wind_speed,
    float *risk_score,
    int *risk_level
);

void fusion_accelerator_fixed(
    fixed32_t soil_moisture,
    fixed32_t temperature,
    fixed32_t humidity,
    fixed32_t wind_speed,
    fixed32_t *risk_score,
    int *risk_level
);

void fusion_accelerator_stream(
    hls::stream<float> &sensor_stream,
    hls::stream<float> &result_stream
);

inline float normalize(float value, float min_val, float max_val) {
    float normalized = (value - min_val) / (max_val - min_val);

    if (normalized < 0.0f) normalized = 0.0f;
    if (normalized > 1.0f) normalized = 1.0f;
    return normalized;
}

inline float compute_soil_stress(float soil_moisture) {
    float normalized = normalize(soil_moisture, SOIL_MIN, SOIL_MAX);

    return 1.0f - normalized;
}

inline float compute_temp_stress(float temperature) {
    float normalized = normalize(temperature, TEMP_MIN, TEMP_MAX);

    float deviation = (normalized - 0.5f);
    if (deviation < 0.0f) deviation = -deviation;
    return deviation * 2.0f;
}

inline float compute_humidity_stress(float humidity) {
    float normalized = normalize(humidity, HUMIDITY_MIN, HUMIDITY_MAX);

    float optimal = 0.6f;
    float deviation = (normalized - optimal);
    if (deviation < 0.0f) deviation = -deviation;

    return deviation / 0.6f;
}

inline float compute_wind_stress(float wind_speed) {
    return normalize(wind_speed, WIND_MIN, WIND_MAX);
}

inline risk_level_t classify_risk(float risk_score) {
    if (risk_score >= RISK_CRITICAL) return LEVEL_CRITICAL;
    if (risk_score >= RISK_HIGH)     return LEVEL_HIGH;
    if (risk_score >= RISK_MEDIUM)   return LEVEL_MEDIUM;
    if (risk_score >= RISK_LOW)      return LEVEL_LOW;
    return LEVEL_MINIMAL;
}

inline float saturate(float value, float min_val, float max_val) {
    if (value < min_val) return min_val;
    if (value > max_val) return max_val;
    return value;
}

#endif
