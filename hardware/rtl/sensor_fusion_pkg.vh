`ifndef SENSOR_FUSION_PKG_VH
`define SENSOR_FUSION_PKG_VH

localparam DATA_WIDTH = 16;
localparam FRAC_BITS  = 8;
localparam INT_BITS   = 8;

localparam [DATA_WIDTH-1:0] WEIGHT_SOIL  = 16'h0059;
localparam [DATA_WIDTH-1:0] WEIGHT_TEMP  = 16'h0040;
localparam [DATA_WIDTH-1:0] WEIGHT_HUMID = 16'h0033;
localparam [DATA_WIDTH-1:0] WEIGHT_LIGHT = 16'h0033;

localparam [DATA_WIDTH-1:0] THRESH_CRITICAL = 16'h5000;
localparam [DATA_WIDTH-1:0] THRESH_HIGH     = 16'h3C00;
localparam [DATA_WIDTH-1:0] THRESH_MODERATE = 16'h2800;
localparam [DATA_WIDTH-1:0] THRESH_LOW      = 16'h1400;

localparam [3:0] STATUS_IDLE       = 4'b0000;
localparam [3:0] STATUS_PROCESSING = 4'b0001;
localparam [3:0] STATUS_DONE       = 4'b0010;
localparam [3:0] STATUS_ERROR      = 4'b1111;

localparam [2:0] ALERT_NONE     = 3'b000;
localparam [2:0] ALERT_LOW      = 3'b001;
localparam [2:0] ALERT_MODERATE = 3'b010;
localparam [2:0] ALERT_HIGH     = 3'b011;
localparam [2:0] ALERT_CRITICAL = 3'b100;

localparam ADDR_CONTROL      = 8'h00;
localparam ADDR_STATUS       = 8'h04;
localparam ADDR_SOIL_IN      = 8'h08;
localparam ADDR_TEMP_IN      = 8'h0C;
localparam ADDR_HUMID_IN     = 8'h10;
localparam ADDR_LIGHT_IN     = 8'h14;
localparam ADDR_FUSION_OUT   = 8'h18;
localparam ADDR_STRESS_OUT   = 8'h1C;
localparam ADDR_TIMESTAMP    = 8'h20;
localparam ADDR_VERSION      = 8'h24;

localparam [31:0] IP_VERSION = 32'h0001_0000;

`endif
