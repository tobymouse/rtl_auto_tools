// soc_top — test file for rtl-auto
// DO NOT EDIT: use `make restore` to reset from this original

module soc_top (
    input           clk,
    input           rst_n,
    input   [7:0]   data_in,
    input           valid_in,
    output  [7:0]   data_out,
    output          valid_out
);

// Instance: u00_sub_module_0 (sub_module)
sub_module u00_sub_module_0 (
    .clk        (clk),
    .rst_n      (rst_n),
    .data_in    (data_in),
    .valid_in   (valid_in),
    .data_out   (data_out),
    .valid_out  (valid_out),
    .error      (error)
);

// Instance: u01_axi_slave_0 (axi_slave)
axi_slave #(
    .DATA_W(32),
    .ADDR_W(64)
) u01_axi_slave_0 (
    .clk        (clk),
    .rst_n      (rst_n),
    .awaddr     (awaddr),
    .awvalid    (awvalid),
    .awready    (awready),
    .wdata      (wdata),
    .wstrb      (wstrb),
    .wvalid     (wvalid),
    .wready     (wready),
    .bresp      (bresp),
    .bvalid     (bvalid),
    .bready     (bready)
);

// Instance: u01_axi_slave_1 (axi_slave)
axi_slave #(
    .DATA_W(64),
    .ADDR_W(128)
) u01_axi_slave_1 (
    .clk        (clk),
    .rst_n      (rst_n),
    .awaddr     (awaddr),
    .awvalid    (awvalid),
    .awready    (awready),
    .wdata      (wdata),
    .wstrb      (wstrb),
    .wvalid     (wvalid),
    .wready     (wready),
    .bresp      (bresp),
    .bvalid     (bvalid),
    .bready     (bready)
);

endmodule
// Local Variables:
// verilog-library-directories:("../rtl")
// verilog-library-extensions:(".v")
// End:
