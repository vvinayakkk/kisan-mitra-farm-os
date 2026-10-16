#include <cstdint>
#include <cmath>

typedef int16_t q88_t;

inline q88_t float_to_q88(float f) {
    return (q88_t)(f * 256.0f);
}

inline float q88_to_float(q88_t v) {
    return (float)v / 256.0f;
}

float min_f(float a, float b) { return (a < b) ? a : b; }
float max_f(float a, float b) { return (a > b) ? a : b; }

void rain_predictor_core(
    q88_t temp,
    q88_t humid,
    q88_t press,
    q88_t wind,
    q88_t *rain_prob,
    q88_t *stress_level,
    uint32_t *alert_flag
) {
    #pragma HLS INTERFACE s_axilite port=temp
    #pragma HLS INTERFACE s_axilite port=humid
    #pragma HLS INTERFACE s_axilite port=press
    #pragma HLS INTERFACE s_axilite port=wind
    #pragma HLS INTERFACE s_axilite port=rain_prob
    #pragma HLS INTERFACE s_axilite port=stress_level
    #pragma HLS INTERFACE s_axilite port=alert_flag
    #pragma HLS INTERFACE s_axilite port=return

    float t = q88_to_float(temp);
    float h = q88_to_float(humid);
    float p = q88_to_float(press);
    float w = q88_to_float(wind);

    float alpha = 17.27f;
    float beta = 237.7f;

    float ln_h = (h > 0.001f) ? logf(h / 100.0f) : logf(0.001f);
    float dew_point = (beta * (alpha * t / (beta + t) + ln_h)) / (alpha - (alpha * t / (beta + t) + ln_h));

    float dew_deficit = t - dew_point;
    float dew_score = 0.0f;

    if (dew_deficit < -2.0f) {
        dew_score = 40.0f;
    } else if (dew_deficit < 0.0f) {
        dew_score = 20.0f + 10.0f * (-dew_deficit / 2.0f);
    } else if (dew_deficit < 3.0f) {
        dew_score = 20.0f - 6.67f * dew_deficit;
    }
    dew_score = max_f(0.0f, min_f(100.0f, dew_score));

    float parcel_temp = t * 0.985f - (p - 50.0f) * 0.01f;
    float lifted_index = t - parcel_temp;

    float li_score = 0.0f;
    if (lifted_index < -4.0f) {
        li_score = 50.0f;
    } else if (lifted_index < -2.0f) {
        li_score = 30.0f;
    } else if (lifted_index < 0.0f) {
        li_score = 15.0f;
    }
    li_score = max_f(0.0f, min_f(50.0f, li_score));

    float pressure_gradient = 100.0f - p;

    float pressure_score = 0.0f;
    if (pressure_gradient > 30.0f) {
        pressure_score = 50.0f;
    } else if (pressure_gradient > 15.0f) {
        pressure_score = 40.0f + min_f(10.0f, (pressure_gradient - 15.0f) * 2.0f);
    } else if (pressure_gradient > 5.0f) {
        pressure_score = 20.0f + (pressure_gradient - 5.0f) * 2.0f;
    } else {
        pressure_score = max_f(0.0f, pressure_gradient * 2.0f);
    }
    pressure_score = max_f(0.0f, min_f(50.0f, pressure_score));

    float wind_score = 0.0f;
    if (w >= 5.0f && w < 12.0f) {
        wind_score = 20.0f;
    } else if (w >= 12.0f && w < 20.0f) {
        wind_score = 15.0f;
    } else if (w >= 20.0f) {
        wind_score = 5.0f;
    } else if (w > 0.0f && w < 5.0f) {
        wind_score = 10.0f;
    }
    wind_score = max_f(0.0f, min_f(20.0f, wind_score));

    float rain_score = 0.0f;

    rain_score += dew_score * 0.35f;
    rain_score += pressure_score * 0.35f;
    rain_score += li_score * 0.20f;
    rain_score += wind_score * 0.10f;

    if (h > 70.0f && p < 50.0f) {
        float interaction = ((h - 70.0f) * 0.3f) * ((50.0f - p) * 0.3f);
        rain_score += min_f(20.0f, interaction);
    }

    rain_score = max_f(0.0f, min_f(100.0f, rain_score));

    *rain_prob = float_to_q88(rain_score);

    float stress = 0.0f;

    if (h > 95.0f) stress += 30.0f;
    else if (h > 85.0f) stress += 20.0f;
    else if (h > 75.0f) stress += 10.0f;

    if (p < 15.0f) stress += 35.0f;
    else if (p < 25.0f) stress += 25.0f;
    else if (p < 35.0f) stress += 15.0f;

    if (t > 38.0f) stress += 20.0f;
    else if (t > 32.0f) stress += 10.0f;

    if (t < 2.0f) stress += 20.0f;
    else if (t < 8.0f) stress += 10.0f;

    if (w > 20.0f) stress += 25.0f;
    else if (w > 15.0f) stress += 15.0f;

    if (lifted_index < -4.0f) stress += 30.0f;
    else if (lifted_index < -2.0f) stress += 20.0f;

    stress = max_f(0.0f, min_f(100.0f, stress));

    *stress_level = float_to_q88(stress);

    *alert_flag = 0;

    if (lifted_index < -2.0f && dew_deficit < 1.0f && w > 5.0f) {
        if (rain_score > 50.0f) *alert_flag = 1;
    }

    if (h > 80.0f && p < 35.0f && dew_deficit < 2.0f) {
        if (rain_score > 60.0f) *alert_flag = 1;
    }

    if (dew_deficit < -1.0f && p < 45.0f) {
        if (rain_score > 55.0f) *alert_flag = 1;
    }

    if (stress > 75.0f && rain_score > 50.0f) {
        *alert_flag = 1;
    }
}

    }
}

void rain_predictor_cpu(
    q88_t temp,
    q88_t humid,
    q88_t press,
    q88_t wind,
    q88_t *rain_prob,
    q88_t *stress_level,
    uint32_t *alert_flag
) {
    rain_predictor_core(temp, humid, press, wind, rain_prob, stress_level, alert_flag);
}
