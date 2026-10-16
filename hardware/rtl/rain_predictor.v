module rain_predictor (
    input clk,
    input rst_n,

    input [15:0] temp_in,
    input [15:0] humid_in,
    input [15:0] press_in,
    input [15:0] wind_in,

    output reg [15:0] rain_prob_out,
    output reg [15:0] stress_level_out,
    output reg alert_flag_out,

    input start,
    output reg done
);

    localparam Q88_70  = 16'h4600;
    localparam Q88_100 = 16'h6400;
    localparam Q88_50  = 16'h3200;
    localparam Q88_90  = 16'h5A00;
    localparam Q88_30  = 16'h1E00;
    localparam Q88_60  = 16'h3C00;
    localparam Q88_25  = 16'h1900;
    localparam Q88_15  = 16'h0F00;
    localparam Q88_85  = 16'h5500;
    localparam Q88_40  = 16'h2800;
    localparam Q88_80  = 16'h5000;
    localparam Q88_95  = 16'h5F00;
    localparam Q88_20  = 16'h1400;
    localparam Q88_45  = 16'h2D00;
    localparam Q88_5   = 16'h0500;
    localparam Q88_35  = 16'h2300;

    reg [2:0] state;
    localparam IDLE = 0, COMPUTE = 1, DONE_STATE = 2;

    reg [23:0] rain_score;
    reg [23:0] stress_score;
    reg alert;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            done <= 0;
            rain_prob_out <= 0;
            stress_level_out <= 0;
            alert_flag_out <= 0;
        end else begin
            case (state)
                IDLE: begin
                    done <= 0;
                    if (start) begin
                        state <= COMPUTE;
                    end
                end

                COMPUTE: begin

                    rain_score = 0;

                    if (humid_in > Q88_70) begin

                        rain_score = rain_score + 32'h0023 + (humid_in - Q88_70);
                    end else if (humid_in > Q88_50) begin

                        rain_score = rain_score + ((humid_in - Q88_50) * 28) >> 4;
                    end

                    if (press_in < Q88_30) begin

                        rain_score = rain_score + ((Q88_30 - press_in) * 21) >> 4;
                    end else if (press_in < Q88_50) begin

                        rain_score = rain_score + ((Q88_50 - press_in) * 6) >> 4;
                    end

                    if ((temp_in >= Q88_15) && (temp_in <= Q88_25)) begin
                        rain_score = rain_score + 16'h000F;
                    end else if ((temp_in > Q88_25) && (temp_in < Q88_35)) begin
                        rain_score = rain_score + 16'h000A;
                    end else if ((temp_in >= Q88_5) && (temp_in < Q88_15)) begin
                        rain_score = rain_score + 16'h000C;
                    end

                    if ((wind_in > Q88_5) && (wind_in < Q88_15)) begin
                        rain_score = rain_score + 16'h000A;
                    end else if (wind_in >= Q88_15) begin
                        rain_score = rain_score + 16'h0008;
                    end

                    if (rain_score > Q88_100) rain_score = Q88_100;
                    rain_prob_out <= rain_score[15:0];

                    stress_score = 0;

                    if ((humid_in > Q88_90) || (humid_in < Q88_20)) begin
                        stress_score = stress_score + 16'h0019;
                    end else if ((humid_in > Q88_80) || (humid_in < Q88_30)) begin
                        stress_score = stress_score + 16'h000F;
                    end

                    if (press_in < Q88_20) begin
                        stress_score = stress_score + 16'h001E;
                    end else if (press_in < Q88_30) begin
                        stress_score = stress_score + 16'h0014;
                    end

                    if ((temp_in > 16'h2800) || (temp_in < Q88_5)) begin
                        stress_score = stress_score + 16'h0014;
                    end else if ((temp_in > Q88_35) || (temp_in < 16'h0500)) begin
                        stress_score = stress_score + 16'h000A;
                    end

                    if (wind_in > 16'h1400) begin
                        stress_score = stress_score + 16'h0019;
                    end else if (wind_in > Q88_15) begin
                        stress_score = stress_score + 16'h000F;
                    end

                    if (stress_score > Q88_100) stress_score = Q88_100;
                    stress_level_out <= stress_score[15:0];

                    alert = 0;

                    if ((rain_score > 16'h003C) && (press_in < Q88_40)) begin
                        alert = 1;
                    end

                    if ((humid_in > Q88_85) && (press_in < Q88_45)) begin
                        alert = 1;
                    end

                    if ((stress_score > 16'h0046) && (rain_score > 16'h0032)) begin
                        alert = 1;
                    end

                    alert_flag_out <= alert;

                    state <= DONE_STATE;
                end

                DONE_STATE: begin
                    done <= 1;
                    if (!start) state <= IDLE;
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule
