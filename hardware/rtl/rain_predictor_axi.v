module rain_predictor_axi (

    input clk,
    input rst_n,

    input [11:0] awaddr,
    input awvalid,
    output awready,

    input [31:0] wdata,
    input [3:0] wstrb,
    input wvalid,
    output wready,

    output [1:0] bresp,
    output bvalid,
    input bready,

    input [11:0] araddr,
    input arvalid,
    output arready,

    output [31:0] rdata,
    output [1:0] rresp,
    output rvalid,
    input rready
);

    reg [31:0] control_reg;
    reg [15:0] temp_in_reg;
    reg [15:0] humid_in_reg;
    reg [15:0] press_in_reg;
    reg [15:0] wind_in_reg;
    reg [31:0] timestamp_counter;

    wire [15:0] rain_out_wire;
    wire [15:0] stress_out_wire;
    wire alert_out_wire;
    wire start_pulse;
    wire done_flag;

    reg [15:0] rain_out_reg;
    reg [15:0] stress_out_reg;
    reg alert_out_reg;

    rain_predictor rain_pred_inst (
        .clk(clk),
        .rst_n(rst_n),
        .temp_in(temp_in_reg),
        .humid_in(humid_in_reg),
        .press_in(press_in_reg),
        .wind_in(wind_in_reg),
        .rain_prob_out(rain_out_wire),
        .stress_level_out(stress_out_wire),
        .alert_flag_out(alert_out_wire),
        .start(start_pulse),
        .done(done_flag)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rain_out_reg <= 0;
            stress_out_reg <= 0;
            alert_out_reg <= 0;
        end else begin
            rain_out_reg <= rain_out_wire;
            stress_out_reg <= stress_out_wire;
            alert_out_reg <= alert_out_wire;
        end
    end

    reg start_r;
    assign start_pulse = control_reg[0] & ~start_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            timestamp_counter <= 0;
        else
            timestamp_counter <= timestamp_counter + 1;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            start_r <= 0;
        else
            start_r <= control_reg[0];
    end

    reg aw_active, w_active;
    reg [11:0] write_addr;

    assign awready = !aw_active;
    assign wready = !w_active;
    assign bvalid = aw_active & w_active;
    assign bresp = 2'b00;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            aw_active <= 0;
            w_active <= 0;
            write_addr <= 0;
        end else begin

            if (awvalid & awready) begin
                aw_active <= 1;
                write_addr <= awaddr;
            end

            if (wvalid & wready) begin
                w_active <= 1;
            end

            if (bvalid & bready) begin
                aw_active <= 0;
                w_active <= 0;
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            control_reg <= 0;
            temp_in_reg <= 0;
            humid_in_reg <= 0;
            press_in_reg <= 0;
            wind_in_reg <= 0;
        end else if (wvalid & wready) begin
            case (write_addr)
                12'h000: control_reg <= wdata;
                12'h008: temp_in_reg <= wdata[15:0];
                12'h00C: humid_in_reg <= wdata[15:0];
                12'h010: press_in_reg <= wdata[15:0];
                12'h014: wind_in_reg <= wdata[15:0];
                default: ;
            endcase
        end
    end

    reg ar_active;
    reg [11:0] read_addr;
    reg [31:0] read_data;

    assign arready = !ar_active;
    assign rvalid = ar_active;
    assign rresp = 2'b00;
    assign rdata = read_data;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ar_active <= 0;
            read_addr <= 0;
        end else begin
            if (arvalid & arready) begin
                ar_active <= 1;
                read_addr <= araddr;
            end else if (rvalid & rready) begin
                ar_active <= 0;
            end
        end
    end

    always @(*) begin
        case (read_addr)
            12'h000: read_data = {done_flag, 30'b0, control_reg[0]};
            12'h004: read_data = {31'b0, alert_out_reg};
            12'h018: read_data = {16'b0, rain_out_reg};
            12'h01C: read_data = {16'b0, stress_out_reg};
            12'h020: read_data = {31'b0, alert_out_reg};
            12'h024: read_data = timestamp_counter;
            12'h028: read_data = 32'h00010000;
            default: read_data = 32'h00000000;
        endcase
    end

endmodule
