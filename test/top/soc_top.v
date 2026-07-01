// soc_top — test file for rtl-auto
// DO NOT EDIT: use `make restore` to reset from this original

module soc_top (
    input        clk,
    input        rst_n,
    input  [7:0] data_in,
    input        valid_in,
    output [7:0] data_out,
    output       valid_out
);
  // Beginning of automatic wires (for undeclared instantiated-module outputs)
  wire awready;  // From u01_axi_slave_0 of axi_slave.v, ...
  wire [1:0] bresp;  // From u01_axi_slave_0 of axi_slave.v, ...
  wire bvalid;  // From u01_axi_slave_0 of axi_slave.v, ...
  wire error;  // From u00_sub_module_0 of sub_module.v
  wire wready;  // From u01_axi_slave_0 of axi_slave.v, ...
  // End of automatics

  // Instance: u00_sub_module_0 (sub_module)
  sub_module u00_sub_module_0 (
      // Outputs
      .data_out(data_out[7:0]),
      .valid_out(valid_out),
      .error(error),
      // Inputs
      .clk(clk),
      .rst_n(rst_n),
      .data_in(data_in[7:0]),
      .valid_in(valid_in)
  );

  // Instance: u01_axi_slave_0 (axi_slave)
  axi_slave #(
      .DATA_W(32),
      .ADDR_W(64)
  ) u01_axi_slave_0 (
      // Outputs
      .awready  (awready),
      .wready  (wready),
      .bresp  (bresp[1:0]),
      .bvalid  (bvalid),
      // Inputs
      .clk   (clk),
      .rst_n  (rst_n),
      .awaddr  (awaddr[ADDR_W-1:0]),
      .awvalid  (awvalid),
      .wdata  (wdata[DATA_W-1:0]),
      .wstrb  (wstrb[DATA_W/8-1:0]),
      .wvalid  (wvalid),
      .bready  (bready)
  );

  // Instance: u01_axi_slave_1 (axi_slave)
  axi_slave #(
      .DATA_W(64),
      .ADDR_W(128)
  ) u01_axi_slave_1 (
      // Outputs
      .awready  (awready),
      .wready  (wready),
      .bresp  (bresp[1:0]),
      .bvalid  (bvalid),
      // Inputs
      .clk   (clk),
      .rst_n  (rst_n),
      .awaddr  (awaddr[ADDR_W-1:0]),
      .awvalid  (awvalid),
      .wdata  (wdata[DATA_W-1:0]),
      .wstrb  (wstrb[DATA_W/8-1:0]),
      .wvalid  (wvalid),
      .bready  (bready)
  );

endmodule
