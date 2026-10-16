#include "sensor_fusion.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#define TOLERANCE 0.01f
#define NUM_RANDOM_TESTS 100

static int tests_passed = 0;
static int tests_failed = 0;

void print_header(const char* test_name) {
    printf("\n");
    printf("═══════════════════════════════════════════════════════════════\n");
    printf("  TEST: %s\n", test_name);
    printf("═══════════════════════════════════════════════════════════════\n");
}

void print_test_case(int test_num, float soil, float temp, float humid, float wind) {
    printf("\n  Test %d:\n", test_num);
    printf("    Inputs:  soil=%.2f%%, temp=%.2f°C, humid=%.2f%%, wind=%.2f m/s\n",
           soil, temp, humid, wind);
}

void print_result(float risk_score, int risk_level, float expected_min, float expected_max, bool pass) {
    const char* level_names[] = {"MINIMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"};
    const char* status = pass ? "✓ PASS" : "✗ FAIL";

    printf("    Output:  risk_score=%.4f, risk_level=%s (%d)\n",
           risk_score, level_names[risk_level], risk_level);
    printf("    Expected: %.2f - %.2f\n", expected_min, expected_max);
    printf("    Status:  %s\n", status);

    if (pass) tests_passed++;
    else tests_failed++;
}

bool run_test(float soil, float temp, float humid, float wind,
              float expected_min, float expected_max, int expected_level_min, int expected_level_max) {

    float risk_score;
    int risk_level;

    fusion_accelerator(soil, temp, humid, wind, &risk_score, &risk_level);

    bool score_pass = (risk_score >= expected_min - TOLERANCE) &&
                      (risk_score <= expected_max + TOLERANCE);
    bool level_pass = (risk_level >= expected_level_min) &&
                      (risk_level <= expected_level_max);
    bool pass = score_pass && level_pass;

    print_result(risk_score, risk_level, expected_min, expected_max, pass);

    return pass;
}

void test_boundary_conditions() {
    print_header("BOUNDARY CONDITIONS");

    print_test_case(1, 0, -10, 0, 0);

    run_test(0, -10, 0, 0, 0.60, 0.90, LEVEL_HIGH, LEVEL_CRITICAL);

    print_test_case(2, 100, 50, 100, 30);

    run_test(100, 50, 100, 30, 0.40, 0.70, LEVEL_MEDIUM, LEVEL_HIGH);

    print_test_case(3, 50, 20, 60, 10);

    run_test(50, 20, 60, 10, 0.20, 0.45, LEVEL_LOW, LEVEL_MEDIUM);
}

void test_agricultural_scenarios() {
    print_header("AGRICULTURAL SCENARIOS");

    print_test_case(1, 15, 38, 25, 8);

    run_test(15, 38, 25, 8, 0.55, 0.80, LEVEL_HIGH, LEVEL_CRITICAL);

    print_test_case(2, 70, 24, 65, 2);

    run_test(70, 24, 65, 2, 0.10, 0.30, LEVEL_MINIMAL, LEVEL_LOW);

    print_test_case(3, 60, 5, 70, 5);

    run_test(60, 5, 70, 5, 0.25, 0.45, LEVEL_LOW, LEVEL_MEDIUM);

    print_test_case(4, 35, 42, 30, 15);

    run_test(35, 42, 30, 15, 0.55, 0.85, LEVEL_HIGH, LEVEL_CRITICAL);

    print_test_case(5, 95, 28, 95, 25);

    run_test(95, 28, 95, 25, 0.30, 0.55, LEVEL_LOW, LEVEL_HIGH);

    print_test_case(6, 65, 22, 55, 3);

    run_test(65, 22, 55, 3, 0.10, 0.25, LEVEL_MINIMAL, LEVEL_LOW);
}

void test_edge_cases() {
    print_header("EDGE CASES & SATURATION");

    print_test_case(1, -50, -50, -50, -50);

    run_test(-50, -50, -50, -50, 0.50, 0.90, LEVEL_MEDIUM, LEVEL_CRITICAL);

    print_test_case(2, 200, 100, 200, 100);

    run_test(200, 100, 200, 100, 0.35, 0.70, LEVEL_MEDIUM, LEVEL_HIGH);

    print_test_case(3, -10, 60, 150, -5);
    run_test(-10, 60, 150, -5, 0.45, 0.75, LEVEL_MEDIUM, LEVEL_HIGH);

    print_test_case(4, 0, -10, 0, 0);
    run_test(0, -10, 0, 0, 0.60, 0.95, LEVEL_HIGH, LEVEL_CRITICAL);

    print_test_case(5, 100, 50, 100, 30);
    run_test(100, 50, 100, 30, 0.40, 0.70, LEVEL_MEDIUM, LEVEL_HIGH);
}

void test_sensor_isolation() {
    print_header("SENSOR ISOLATION TESTS");

    float base_soil = 70;
    float base_temp = 22;
    float base_humid = 60;
    float base_wind = 3;

    print_test_case(1, 10, base_temp, base_humid, base_wind);
    printf("    Testing: SOIL STRESS isolated\n");
    run_test(10, base_temp, base_humid, base_wind, 0.25, 0.45, LEVEL_LOW, LEVEL_MEDIUM);

    print_test_case(2, base_soil, 45, base_humid, base_wind);
    printf("    Testing: TEMPERATURE STRESS isolated\n");
    run_test(base_soil, 45, base_humid, base_wind, 0.20, 0.40, LEVEL_LOW, LEVEL_MEDIUM);

    print_test_case(3, base_soil, base_temp, 10, base_wind);
    printf("    Testing: HUMIDITY STRESS isolated\n");
    run_test(base_soil, base_temp, 10, base_wind, 0.20, 0.40, LEVEL_LOW, LEVEL_MEDIUM);

    print_test_case(4, base_soil, base_temp, base_humid, 28);
    printf("    Testing: WIND STRESS isolated\n");
    run_test(base_soil, base_temp, base_humid, 28, 0.20, 0.40, LEVEL_LOW, LEVEL_MEDIUM);
}

void test_risk_levels() {
    print_header("RISK LEVEL CLASSIFICATION");

    print_test_case(1, 80, 22, 60, 1);
    printf("    Target: MINIMAL (< 0.20)\n");
    run_test(80, 22, 60, 1, 0.05, 0.20, LEVEL_MINIMAL, LEVEL_LOW);

    print_test_case(2, 60, 22, 55, 5);
    printf("    Target: LOW (0.20-0.40)\n");
    run_test(60, 22, 55, 5, 0.15, 0.35, LEVEL_MINIMAL, LEVEL_MEDIUM);

    print_test_case(3, 40, 32, 45, 12);
    printf("    Target: MEDIUM (0.40-0.60)\n");
    run_test(40, 32, 45, 12, 0.35, 0.55, LEVEL_LOW, LEVEL_HIGH);

    print_test_case(4, 20, 40, 30, 18);
    printf("    Target: HIGH (0.60-0.80)\n");
    run_test(20, 40, 30, 18, 0.55, 0.75, LEVEL_HIGH, LEVEL_CRITICAL);

    print_test_case(5, 5, 48, 15, 25);
    printf("    Target: CRITICAL (> 0.80)\n");
    run_test(5, 48, 15, 25, 0.70, 1.00, LEVEL_HIGH, LEVEL_CRITICAL);
}

void test_random_fuzzing() {
    print_header("RANDOM INPUT FUZZING");

    printf("  Running %d random test cases...\n", NUM_RANDOM_TESTS);

    srand(42);

    int fuzz_passed = 0;

    for (int i = 0; i < NUM_RANDOM_TESTS; i++) {

        float soil = ((float)rand() / RAND_MAX) * 150 - 25;
        float temp = ((float)rand() / RAND_MAX) * 100 - 30;
        float humid = ((float)rand() / RAND_MAX) * 150 - 25;
        float wind = ((float)rand() / RAND_MAX) * 50 - 10;

        float risk_score;
        int risk_level;

        fusion_accelerator(soil, temp, humid, wind, &risk_score, &risk_level);

        bool valid = (risk_score >= 0.0f) && (risk_score <= 1.0f) &&
                     (risk_level >= 0) && (risk_level <= 4);

        if (valid) {
            fuzz_passed++;
        } else {
            printf("  ✗ FUZZ FAIL at test %d: soil=%.2f, temp=%.2f, humid=%.2f, wind=%.2f\n",
                   i+1, soil, temp, humid, wind);
            printf("    Output: risk_score=%.4f, risk_level=%d\n", risk_score, risk_level);
            tests_failed++;
        }
    }

    printf("\n  Fuzz testing: %d/%d passed\n", fuzz_passed, NUM_RANDOM_TESTS);
    tests_passed += fuzz_passed;
}

void test_batch_processing() {
    print_header("BATCH PROCESSING");

    float soil[4] = {20, 50, 70, 90};
    float temp[4] = {35, 25, 22, 15};
    float humid[4] = {30, 60, 65, 80};
    float wind[4] = {15, 8, 3, 1};
    float risk_score[4];
    int risk_level[4];

    printf("  Testing batch of 4 samples...\n\n");

    fusion_accelerator_batch(soil, temp, humid, wind, risk_score, risk_level);

    const char* level_names[] = {"MINIMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"};

    for (int i = 0; i < 4; i++) {
        printf("  Sample %d: soil=%.0f, temp=%.0f, humid=%.0f, wind=%.0f\n",
               i+1, soil[i], temp[i], humid[i], wind[i]);
        printf("    → risk=%.4f, level=%s\n", risk_score[i], level_names[risk_level[i]]);

        bool valid = (risk_score[i] >= 0.0f) && (risk_score[i] <= 1.0f);
        if (valid) {
            printf("    ✓ PASS\n\n");
            tests_passed++;
        } else {
            printf("    ✗ FAIL\n\n");
            tests_failed++;
        }
    }
}

int main() {
    printf("\n");
    printf("╔═══════════════════════════════════════════════════════════════╗\n");
    printf("║     SENSOR FUSION ACCELERATOR - COMPREHENSIVE TESTBENCH       ║\n");
    printf("║                AMD Slingshot Hackathon 2026                   ║\n");
    printf("╚═══════════════════════════════════════════════════════════════╝\n");

    test_boundary_conditions();
    test_agricultural_scenarios();
    test_edge_cases();
    test_sensor_isolation();
    test_risk_levels();
    test_random_fuzzing();
    test_batch_processing();

    printf("\n");
    printf("═══════════════════════════════════════════════════════════════\n");
    printf("                      TEST SUMMARY\n");
    printf("═══════════════════════════════════════════════════════════════\n");
    printf("\n");
    printf("  Tests Passed: %d\n", tests_passed);
    printf("  Tests Failed: %d\n", tests_failed);
    printf("  Total Tests:  %d\n", tests_passed + tests_failed);
    printf("\n");

    if (tests_failed == 0) {
        printf("  ╔═══════════════════════════════════════╗\n");
        printf("  ║     ✓ ALL TESTS PASSED               ║\n");
        printf("  ║     Ready for HLS Synthesis!          ║\n");
        printf("  ╚═══════════════════════════════════════╝\n");
        return 0;
    } else {
        printf("  ╔═══════════════════════════════════════╗\n");
        printf("  ║     ✗ SOME TESTS FAILED              ║\n");
        printf("  ║     Review failures before synthesis  ║\n");
        printf("  ╚═══════════════════════════════════════╝\n");
        return 1;
    }
}
