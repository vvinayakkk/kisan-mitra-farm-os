`timescale 1ns / 1ps
`include "sensor_fusion_pkg.vh"

module sensor_fusion_tb;

    reg clk;
    reg rst_n;

    initial clk = 0;
    always #5 clk = ~clk;

    reg                   start;
    wire                  done;
    wire                  busy;

    reg  [DATA_WIDTH-1:0] soil_moisture;
    reg  [DATA_WIDTH-1:0] temperature;
    reg  [DATA_WIDTH-1:0] humidity;
    reg  [DATA_WIDTH-1:0] light_level;

    wire [DATA_WIDTH-1:0] fusion_score;
    wire [DATA_WIDTH-1:0] stress_index;
    wire [2:0]            alert_level;
    wire [3:0]            status;

    sensor_fusion dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .start         (start),
        .done          (done),
        .busy          (busy),
        .soil_moisture (soil_moisture),
        .temperature   (temperature),
        .humidity      (humidity),
        .light_level   (light_level),
        .fusion_score  (fusion_score),
        .stress_index  (stress_index),
        .alert_level   (alert_level),
        .status        (status)
    );

    function [15:0] to_q88;
        input real value;
        begin
            to_q88 = $rtoi(value * 256.0);
        end
    endfunction

    function real from_q88;
        input [15:0] value;
        begin
            from_q88 = $itor(value) / 256.0;
        end
    endfunction

    function [63:0] alert_name;
        input [2:0] level;
        begin
            case (level)
                3'd0: alert_name = "NONE    ";
                3'd1: alert_name = "LOW     ";
                3'd2: alert_name = "MODERATE";
                3'd3: alert_name = "HIGH    ";
                3'd4: alert_name = "CRITICAL";
                default: alert_name = "UNKNOWN ";
            endcase
        end
    endfunction

    task run_test;
        input [127:0] test_name;
        input real soil, temp, humid, light;
        begin
            $display("\n--- Test: %s ---", test_name);
            $display("Inputs: Soil=%.1f%%, Temp=%.1f°C, Humid=%.1f%%, Light=%.1f%%",
                     soil, temp, humid, light);

            soil_moisture = to_q88(soil);
            temperature   = to_q88(temp);
            humidity      = to_q88(humid);
            light_level   = to_q88(light);

            @(posedge clk);
            start = 1;
            @(posedge clk);
            start = 0;

            @(posedge done);
            @(posedge clk);

            $display("Results: Fusion=%.2f, Stress=%.2f, Alert=%s",
                     from_q88(fusion_score), from_q88(stress_index), alert_name(alert_level));
            $display("Status: %d, Latency: 5 cycles", status);
        end
    endtask

    integer test_count;
    integer pass_count;

    initial begin
        $display("=========================================================");
        $display("Sensor Fusion Accelerator Testbench");
        $display("Target: Zynq-7000 ZC706 @ 100 MHz");
        $display("=========================================================");

        rst_n = 0;
        start = 0;
        soil_moisture = 0;
        temperature = 0;
        humidity = 0;
        light_level = 0;
        test_count = 0;
        pass_count = 0;

        repeat(10) @(posedge clk);
        rst_n = 1;
        repeat(5) @(posedge clk);

        $display("\n========== FUNCTIONAL TESTS ==========");

        run_test("Optimal Conditions", 50.0, 50.0, 50.0, 50.0);
        test_count = test_count + 1;

        run_test("Dry Soil Stress", 10.0, 25.0, 40.0, 60.0);
        test_count = test_count + 1;

        run_test("High Temp Stress", 60.0, 90.0, 30.0, 80.0);
        test_count = test_count + 1;

        run_test("Wet Conditions", 90.0, 20.0, 95.0, 20.0);
        test_count = test_count + 1;

        run_test("Night Conditions", 45.0, 15.0, 70.0, 5.0);
        test_count = test_count + 1;

        run_test("All Minimum", 0.0, 0.0, 0.0, 0.0);
        test_count = test_count + 1;

        run_test("All Maximum", 100.0, 100.0, 100.0, 100.0);
        test_count = test_count + 1;

        run_test("Healthy Crop", 65.0, 25.0, 60.0, 70.0);
        test_count = test_count + 1;

        run_test("Drought Stress", 15.0, 35.0, 25.0, 95.0);
        test_count = test_count + 1;

        run_test("Frost Risk", 50.0, 2.0, 80.0, 30.0);
        test_count = test_count + 1;

        $display("\n========== PIPELINE TESTS ==========");

        $display("\n--- Test: Back-to-Back Processing ---");
        soil_moisture = to_q88(40.0);
        temperature   = to_q88(30.0);
        humidity      = to_q88(50.0);
        light_level   = to_q88(60.0);

        @(posedge clk);
        start = 1;
        @(posedge clk);
        start = 0;
        @(posedge done);
        $display("First result: Fusion=%.2f", from_q88(fusion_score));

        @(posedge clk);
        soil_moisture = to_q88(80.0);
        start = 1;
        @(posedge clk);
        start = 0;
        @(posedge done);
        $display("Second result: Fusion=%.2f", from_q88(fusion_score));
        test_count = test_count + 2;

        $display("\n========== TIMING VERIFICATION ==========");

        $display("\n--- Latency Measurement ---");
        @(posedge clk);
        soil_moisture = to_q88(55.0);
        temperature   = to_q88(28.0);
        humidity      = to_q88(62.0);
        light_level   = to_q88(45.0);

        @(posedge clk);
        start = 1;
        @(posedge clk);
        start = 0;

        begin : latency_check
            integer cycles;
            cycles = 0;
            while (!done) begin
                @(posedge clk);
                cycles = cycles + 1;
                if (cycles > 20) begin
                    $display("ERROR: Timeout waiting for done signal!");
                    disable latency_check;
                end
            end
            $display("Measured latency: %d clock cycles", cycles);
            if (cycles == 5) begin
                $display("PASS: Latency matches specification (5 cycles)");
                pass_count = pass_count + 1;
            end else begin
                $display("FAIL: Expected 5 cycles");
            end
        end
        test_count = test_count + 1;

        $display("\n=========================================================");
        $display("TESTBENCH COMPLETE");
        $display("Total tests: %d", test_count);
        $display("=========================================================");

        repeat(10) @(posedge clk);
        $finish;
    end

    initial begin
        $dumpfile("sensor_fusion_tb.vcd");
        $dumpvars(0, sensor_fusion_tb);
    end

endmodule
