module axi_slave #(
    parameter DATA_W = 16,
    parameter ADDR_W = 32
) (
    input                       clk,
    input                       rst_n,
    input   [ADDR_W-1:0]        awaddr,
    input                       awvalid,
    output                      awready,
    input   [DATA_W-1:0]        wdata,
    input   [DATA_W/8-1:0]      wstrb,
    input                       wvalid,
    output                      wready,
    output  [1:0]               bresp,
    output                      bvalid,
    input                       bready
);
    assign awready = awvalid;
    assign wready  = wvalid;
    assign bresp   = 2'b00;
    assign bvalid  = bready;
endmodule
